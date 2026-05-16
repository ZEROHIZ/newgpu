import asyncio
import time
import os
import json
import sys
import httpx  # 需要安装: pip install httpx

# 增加路径，确保能导入 core 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.redis_client import redis_manager
from core.gpu_monitor import gpu_monitor
from core.config_loader import get_gpu_config

class GPUAgent:
    def __init__(self, gpu_index: int = 0, gpu_id: str = None):
        self.gpu_index = gpu_index
        # 逻辑 ID (如 ae52f72d)，用于匹配渠道；物理索引用于监控显卡
        self.gpu_id = gpu_id if gpu_id else str(gpu_index)
        self.agent_id = f"agent_{os.getpid()}_{self.gpu_id}"
        self.config = get_gpu_config()
        self.active_workers = {} # channel_id -> task

    async def report_status(self):
        """定时上报本地 GPU 状态到 Redis"""
        print(f"[{self.agent_id}] Status reporting started...")
        while True:
            try:
                stats = gpu_monitor.get_gpu_info()
                if stats and len(stats) > self.gpu_index:
                    gpu_info = stats[self.gpu_index].dict()
                    gpu_info["last_update"] = time.time()
                    gpu_info["agent_id"] = self.agent_id
                    await redis_manager.set_json(f"gpu_realtime:{self.gpu_id}", gpu_info, ex=30)
            except Exception as e:
                print(f"[{self.agent_id}] Report error: {e}")
            await asyncio.sleep(self.config["check_interval"])

    async def process_task(self, channel, task_data):
        """处理并转发任务到上游服务"""
        task_id = task_data.get("id")
        service_url = channel.get("service_url")
        print(f"[{self.agent_id}] 🚀 正在处理任务: {task_id} (渠道: {channel['name']})")

        # 1. 更新任务状态为 running
        task_data["status"] = "running"
        task_data["start_time"] = time.time()
        task_data["gpu_id"] = self.gpu_id
        await redis_manager.set_json(f"task:{task_id}", task_data, ex=3600)

        try:
            # 2. 转发请求到上游服务 (支持 JSON 或文件上传)
            async with httpx.AsyncClient(timeout=600.0) as client:
                payload = task_data.get("payload", {})
                file_path = payload.get("file_path")
                
                print(f"[{self.agent_id}] 调试: 收到文件路径='{file_path}', 是否存在={os.path.exists(file_path) if file_path else 'N/A'}")
                
                # 特殊处理：如果是文件任务且本地存在该文件
                if file_path and os.path.exists(file_path):
                    print(f"[{self.agent_id}] 📎 发现本地文件，正在准备上传流: {file_path}")
                    with open(file_path, "rb") as f:
                        # 构造 Multipart 上传
                        files = {"file": (os.path.basename(file_path), f)}
                        # 其他参数作为表单数据
                        data = {k: v for k, v in payload.items() if k != "file_path"}
                        response = await client.post(service_url, files=files, data=data)
                else:
                    # 普通 JSON 转发
                    response = await client.post(service_url, json=payload)
                
                if response.status_code == 200:
                    task_data["status"] = "completed"
                    task_data["result"] = response.json()
                else:
                    task_data["status"] = "failed"
                    error_msg = f"上游错误({response.status_code}): {response.text}"
                    task_data["error"] = error_msg
                    print(f"[{self.agent_id}] ❌ 任务 {task_id} 失败: {error_msg}")
        except Exception as e:
            task_data["status"] = "failed"
            error_msg = f"请求转发异常: {str(e)}"
            task_data["error"] = error_msg
            print(f"[{self.agent_id}] ❌ 任务 {task_id} 转发异常: {error_msg}")

        # 3. 回写最终结果
        task_data["end_time"] = time.time()
        await redis_manager.set_json(f"task:{task_id}", task_data, ex=604800) # 延长到 7 天
        print(f"[{self.agent_id}] ✅ 任务 {task_id} 处理完毕，结果: {task_data['status']}")

    async def channel_worker(self, channel_id):
        """针对特定渠道的监听协程"""
        print(f"[{self.agent_id}] 🟢 已启动渠道监听协程: {channel_id}")
        while True:
            try:
                # 检查渠道是否依然有效
                ch = await redis_manager.get_json(f"channel:{channel_id}")
                if not ch or not ch.get("active"):
                    print(f"[{self.agent_id}] 🔴 渠道 {channel_id} 已失效，停止监听")
                    break

                # 从 Redis 队列中获取任务 (阻塞式)
                queue_key = f"channel:{channel_id}"
                # print(f"[{self.agent_id}] 正在从队列 queue:{queue_key} 尝试获取任务...")
                task = await redis_manager.pop_task(queue_key, timeout=10)
                
                if task:
                    print(f"[{self.agent_id}] 📥 成功从队列 {queue_key} 获取任务: {task.get('id')}")
                    await self.process_task(ch, task)
            except Exception as e:
                print(f"[{self.agent_id}] Worker 异常: {e}")
                await asyncio.sleep(5)

    async def task_loop(self):
        """管理并启动多个渠道的监听任务"""
        print(f"[{self.agent_id}] Task manager started, searching for channels...")
        while True:
            try:
                # --- 动态绑定与手动同步逻辑 ---
                # 检查是否有手动同步信号
                sync_signal = await redis_manager.client.get("signal:sync_agent")
                
                # 如果当前是默认 ID "0" 或者收到了手动同步信号
                if self.gpu_id == "0" or sync_signal:
                    gpu_keys = await redis_manager.keys("gpu_device:*")
                    if gpu_keys:
                        gpu_data = await redis_manager.get_json(gpu_keys[0])
                        if gpu_data:
                            new_id = gpu_data["id"]
                            if self.gpu_id != new_id:
                                self.gpu_id = new_id
                                print(f"[{self.agent_id}] 🎯 显卡绑定已更新: {self.gpu_id}")
                    # 处理完信号后删除
                    if sync_signal:
                        await redis_manager.client.delete("signal:sync_agent")

                # 1. 发现属于我这张显卡的活跃渠道
                keys = await redis_manager.keys("channel:*")
                # ... 剩余逻辑不变 ...
                found_channels = 0
                for k in keys:
                    ch = await redis_manager.get_json(k)
                    if ch and str(ch.get("gpu_id")) == self.gpu_id and ch.get("active"):
                        cid = ch["id"]
                        found_channels += 1
                        if cid not in self.active_workers or self.active_workers[cid].done():
                            print(f"[{self.agent_id}] 🆕 启动渠道监听: {cid} ({ch.get('name')})")
                            self.active_workers[cid] = asyncio.create_task(self.channel_worker(cid))
                
                # if found_channels == 0:
                #     print(f"[{self.agent_id}] 💤 等待渠道绑定到 GPU:{self.gpu_id}...")
            except Exception as e:
                print(f"[{self.agent_id}] Manager loop error: {e}")
            
            await asyncio.sleep(5) 

    async def start(self):
        print(f"=== GPUREDIS Agent Started (GPU ID: {self.gpu_id}) ===")
        await asyncio.gather(
            self.report_status(),
            self.task_loop()
        )

if __name__ == "__main__":
    # 使用方式: python agent.py 0  (这里的 0 是显卡索引)
    gpu_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    agent = GPUAgent(gpu_idx)
    try:
        asyncio.run(agent.start())
    except KeyboardInterrupt:
        print("Agent stopped.")

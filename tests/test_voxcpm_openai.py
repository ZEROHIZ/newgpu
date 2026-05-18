import requests
import json
import time
import os
import sys

# 确保控制台输出编码为 utf-8，避免 Windows 下控制台中文乱码
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# GPUREDIS 调度网关地址与端口（使用 6621）
BASE_URL = "http://127.0.0.1:6621"
TASKS_URL = f"{BASE_URL}/api/tasks"
CHANNELS_URL = f"{BASE_URL}/api/channels"
GPUS_URL = f"{BASE_URL}/api/gpus"
SYNC_URL = f"{BASE_URL}/api/agent/sync"

def ensure_voxcpm_channel():
    """检查并自动配置 VoxCPM 调度渠道，以实现开箱即用"""
    print("🔍 正在检查调度系统中已有的服务渠道...")
    try:
        resp = requests.get(CHANNELS_URL)
        if resp.status_code == 200:
            channels = resp.json().get("channels", [])
            for ch in channels:
                if ch.get("service_type") == "voxcpm" and ch.get("active"):
                    print(f"✅ 找到可用的 VoxCPM 渠道: {ch.get('name')} (绑定 GPU: {ch.get('gpu_id')})")
                    return True
            print("⚠️ 未找到活跃的 'voxcpm' 渠道。尝试自动注册一个默认渠道...")
        else:
            print(f"❌ 获取渠道列表失败: {resp.text}")
            return False
    except Exception as e:
        print(f"❌ 连接网关失败，请确保 GPUREDIS 服务在 {BASE_URL} 正常运行！错误: {e}")
        return False

    # 自动获取可用的 GPU 列表
    try:
        gpu_resp = requests.get(GPUS_URL)
        if gpu_resp.status_code == 200:
            gpus = gpu_resp.json().get("gpus", [])
            if not gpus:
                print("❌ 调度系统中暂未绑定任何 GPU 设备，请先添加显卡！")
                return False
            selected_gpu = gpus[0]
            gpu_id = selected_gpu.get("id")
            gpu_name = selected_gpu.get("name")
            print(f"🎯 选择首张可用 GPU 设备: {gpu_name} (ID: {gpu_id})")
        else:
            print(f"❌ 获取 GPU 设备失败: {gpu_resp.text}")
            return False
    except Exception as e:
        print(f"❌ 获取 GPU 设备异常: {e}")
        return False

    # 注册 VoxCPM 服务渠道
    channel_payload = {
        "name": "本地 VoxCPM2 智能音色渠道",
        "gpu_id": gpu_id,
        "service_type": "voxcpm",
        "service_url": "http://127.0.0.1:8089/v1/audio/speech", # 指向本地 VoxCPM2 接口
        "execution_mode": "sync",
        "base_vram": 2.0,  # 预估占用显存
        "base_ram": 1.0,
        "weight": 10,
        "active": True
    }

    try:
        reg_resp = requests.post(CHANNELS_URL, json=channel_payload)
        if reg_resp.status_code == 200:
            print("🎉 自动注册 VoxCPM 调度渠道成功！")
            # 触发 Agent 同步信号，使本地 Agent 立即加载新绑定的渠道监听
            requests.post(SYNC_URL)
            print("🔄 已向本地 Agent 发送热重载绑定信号。等待 3 秒使绑定生效...")
            time.sleep(3)
            return True
        else:
            print(f"❌ 注册渠道失败: {reg_resp.text}")
            return False
    except Exception as e:
        print(f"❌ 注册渠道异常: {e}")
        return False

def run_voice_design_test():
    print("=" * 60)
    print("🚀 开始进行 VoxCPM2 音色设计功能自动化测试 (GPUREDIS 调度模式)")
    print("=" * 60)

    # 1. 确保渠道已就绪
    if not ensure_voxcpm_channel():
        print("❌ 准备工作失败，测试终止。")
        return

    # 2. 准备音色设计合成载荷 (根据新 API 文档规范)
    task_payload = {
        "service_type": "voxcpm",
        "priority": 0,
        "payload": {
            "model": "openbmb/VoxCPM2",
            "input": "您好主人！我已经通过分布式 GPU 调度网关和音色设计功能成功完成了语音合成！这是一只傲娇女孩的甜美声音喔！",
            "voice": "default",
            "response_format": "wav",
            # 控制音色和情感风格的高阶控制指令
            "instructions": "年轻女孩，声音软萌甜美，带着一丝傲娇、嗔怪的语气，语速偏慢。"
        }
    }

    print("\n📝 提交的任务载荷:")
    print(json.dumps(task_payload, indent=4, ensure_ascii=False))

    # 3. 提交任务到调度网关
    try:
        print("\n📤 正在提交任务到 GPUREDIS 调度网关...")
        resp = requests.post(TASKS_URL, json=task_payload)
        if resp.status_code == 200:
            data = resp.json()
            task_id = data["task_id"]
            assigned_gpu = data.get("assigned_to", {}).get("gpu_id", "未知")
            print(f"✅ 任务提交成功！")
            print(f"🆔 任务 ID: {task_id}")
            print(f"🖥️ 调度分发显卡 ID: {assigned_gpu}")
            if data.get("is_queued"):
                print("🕒 当前任务处于排队队列中，正在等待显存就绪...")
        else:
            print(f"❌ 提交任务失败: {resp.text}")
            return
    except Exception as e:
        print(f"❌ 提交任务请求异常: {e}")
        return

    # 4. 循环轮询任务执行状态
    print("\n🕒 开始轮询任务状态...")
    start_time = time.time()
    while True:
        try:
            status_resp = requests.get(f"{TASKS_URL}/{task_id}")
            if status_resp.status_code == 200:
                task_data = status_resp.json()
                status = task_data.get("status")
                
                if status == "completed":
                    elapsed = time.time() - start_time
                    print(f"\n🎉 任务执行成功！总耗时: {elapsed:.2f} 秒")
                    result = task_data.get("result", {})
                    
                    # 5. 下载并保存合成出的音频文件
                    if isinstance(result, dict) and "url" in result:
                        audio_url = f"{BASE_URL}{result['url']}"
                        print(f"🌐 自动获取音频静态地址: {audio_url}")
                        
                        # 确保 tests 目录存在
                        os.makedirs("tests", exist_ok=True)
                        output_file = "tests/test_voxcpm_output.wav"
                        
                        print(f"💾 正在下载并落地保存文件到本地: {output_file} ...")
                        audio_resp = requests.get(audio_url)
                        if audio_resp.status_code == 200:
                            with open(output_file, "wb") as f:
                                f.write(audio_resp.content)
                            print(f"🥇 【测试彻底成功】音频已完美落地保存！文件大小: {len(audio_resp.content)} 字节")
                            print(f"📂 存储绝对路径: {os.path.abspath(output_file)}")
                        else:
                            print(f"❌ 下载音频流失败: 状态码 {audio_resp.status_code}")
                    else:
                        print(f"⚠️ 调度系统已判定成功，但未返回可用的音频 URL。Result: {result}")
                    break
                    
                elif status == "failed":
                    print(f"\n❌ 任务执行失败！")
                    print(f"⚠️ 错误原因: {task_data.get('error')}")
                    break
                    
                else:
                    print(f"🕒 当前状态: [{status}] ... 已等待 {time.time() - start_time:.1f}s")
            else:
                print(f"❌ 查询任务状态失败: {status_resp.text}")
                
        except Exception as e:
            print(f"⚠️ 轮询状态时发生异常: {e}")
            
        time.sleep(2)

if __name__ == "__main__":
    run_voice_design_test()

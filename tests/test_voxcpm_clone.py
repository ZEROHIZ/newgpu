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
BASE_URL = "http://192.168.110.30:6621"
TASKS_URL = f"{BASE_URL}/api/tasks"
UPLOAD_URL = f"{BASE_URL}/api/upload"

# 用于克隆的本地参考音频路径
LOCAL_AUDIO = "C:\\Users\\Administrator\\Downloads\\cs.mp3"

def upload_file(local_path):
    """上传文件到网关并返回远程 URL"""
    if not os.path.exists(local_path):
        print(f"❌ 本地参考音频不存在: {local_path}")
        return None
    
    print(f"📤 正在上传参考音频: {os.path.basename(local_path)} ...")
    try:
        with open(local_path, "rb") as f:
            files = {"file": (os.path.basename(local_path), f)}
            resp = requests.post(UPLOAD_URL, files=files)
            if resp.status_code == 200:
                data = resp.json()
                remote_url = f"{BASE_URL}{data['url']}"
                print(f"✅ 上传成功: {remote_url}")
                return remote_url
            else:
                print(f"❌ 上传失败: {resp.text}")
                return None
    except Exception as e:
        print(f"❌ 上传网络异常: {e}")
        return None

def run_voxcpm_clone_test():
    print("=" * 60)
    print("🚀 开始进行 VoxCPM2 声音克隆与穿透自动化测试")
    print("=" * 60)

    # 1. 上传参考音频文件
    remote_url = upload_file(LOCAL_AUDIO)
    if not remote_url:
        print("❌ 文件上传失败，测试终止。")
        return

    # 2. 构造干净的网关请求体（一比一对应，没有多余套娃！）
    task_payload = {
        "service_type": "voxcpm",
        "_file_path_key": "audio",  # 💡 声明 "audio" 字段需要作为中转文件处理
        "payload": {
            "audio": remote_url,    # 💡 对应的键位直接传入远程 URL
            "model": "openbmb/VoxCPM2"
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
                    print(f"🥇 【测试成功】Result: {result}")
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
    run_voxcpm_clone_test()

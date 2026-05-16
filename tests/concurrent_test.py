import requests
import threading
import time
import json
import os

# GPUREDIS 调度网关地址
BASE_URL = "http://192.168.110.30:6621"
TASKS_URL = f"{BASE_URL}/api/tasks"
UPLOAD_URL = f"{BASE_URL}/api/upload"

# 配置测试文件（本地存在的路径）
# 如果是远程测试，脚本会自动先上传文件到网关
LOCAL_FILES = [
    "C:\\Users\\Administrator\\Downloads\\cs.mp3",
    "C:\\Users\\Administrator\\Downloads\\下载 (1).mp4"
]

def upload_file(local_path):
    """上传文件到网关并返回远程 URL"""
    if not os.path.exists(local_path):
        print(f"⚠️ 文件不存在: {local_path}")
        return local_path
    
    print(f"📤 正在上传文件: {os.path.basename(local_path)} ...")
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
            return local_path

def run_task(task_config):
    name = task_config["name"]
    print(f"🚀 开始准备: {name}...")
    
    # --- 核心改进：先上传 ---
    file_path = task_config["file_path"]
    if os.path.exists(file_path):
        remote_url = upload_file(file_path)
        task_config["file_path"] = remote_url
    
    # 提交任务
    payload = {
        "service_type": task_config["service_type"],
        "payload": {
            "file_path": task_config["file_path"],
            "model": task_config.get("model", "default")
        }
    }
    
    try:
        resp = requests.post(TASKS_URL, json=payload)
        if resp.status_code == 200:
            task_id = resp.json()["task_id"]
            print(f"✅ {name} 提交成功, 任务ID: {task_id}")
            
            # 轮询结果
            while True:
                status_resp = requests.get(f"{TASKS_URL}/{task_id}")
                status_data = status_resp.json()
                status = status_data["status"]
                
                if status in ["completed", "failed"]:
                    print(f"🎉 {name} 执行结束！状态: {status}")
                    if status == "failed":
                        print(f"❌ 错误详情: {status_data.get('error')}")
                    break
                
                print(f"🕒 {name} 当前状态: {status}")
                time.sleep(3)
        else:
            print(f"❌ {name} 提交失败: {resp.text}")
    except Exception as e:
        print(f"❌ {name} 请求异常: {e}")

if __name__ == "__main__":
    print("=== GPUREDIS 分布式并发测试工具 (带自动上传) ===")
    
    # 定义任务
    tasks = [
        {
            "name": "任务 1 (音频上传转写)",
            "service_type": "whisper",
            "file_path": LOCAL_FILES[0],
            "model": "deepdml/faster-whisper-large-v3-turbo-ct2"
        },
        {
            "name": "任务 2 (视频上传转写)",
            "service_type": "whisper",
            "file_path": LOCAL_FILES[1],
            "model": "deepdml/faster-whisper-large-v3-turbo-ct2"
        }
    ]
    
    threads = []
    for t_cfg in tasks:
        th = threading.Thread(target=run_task, args=(t_cfg,))
        th.start()
        threads.append(th)
        time.sleep(1) # 稍微错开提交时间
        
    for th in threads:
        th.join()
        
    print("=== 所有任务测试完成 ===")

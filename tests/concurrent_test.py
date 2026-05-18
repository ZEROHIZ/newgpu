import requests
import threading
import time
import json
import os
import sys

# 确保控制台输出编码为 utf-8，避免 Windows 下控制台中文及 Emoji 乱码和崩溃
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

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
        print(f"⚠️ 测量提示 - 文件暂不存在，请确保路径正确: {local_path}")
        return local_path
    
    print(f"📤 正在上传文件: {os.path.basename(local_path)} ...")
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
                return local_path
    except Exception as e:
        print(f"❌ 上传网络异常: {e}")
        return local_path

def run_task(task_config):
    name = task_config["name"]
    print(f"🚀 开始准备: {name}...")
    
    # --- 核心改进：先上传 ---
    file_path = task_config["file_path"]
    if os.path.exists(file_path):
        remote_url = upload_file(file_path)
        task_config["file_path"] = remote_url
    
    # 动态把文件路径写进指定的键名中，测试单键穿透功能
    path_key = task_config.get("path_key", "file_path")
    payload_data = {
        "model": task_config.get("model", "default")
    }
    payload_data[path_key] = task_config["file_path"]
    
    # 提交任务，按照用户的提议，_file_path_key 与 payload 处于同级 (即最外层)
    payload = {
        "service_type": task_config["service_type"],
        "payload": payload_data
    }
    
    # 如果定义了 path_key，则放在 TaskRequest 的最外层作为系统控制字
    if path_key:
        payload["_file_path_key"] = path_key
    
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
                    else:
                        print(f"🥇 {name} 运行成功！Result: {status_data.get('result')}")
                    break
                
                print(f"🕒 {name} 当前状态: {status}")
                time.sleep(3)
        else:
            print(f"❌ {name} 提交失败: {resp.text}")
    except Exception as e:
        print(f"❌ {name} 请求异常: {e}")
 
if __name__ == "__main__":
    print("=== GPUREDIS 分布式并发与文件上传穿透测试工具 ===")
    
    # 定义任务：同时测试传统格式与最新外层单键穿透上传格式
    tasks = [
        {
            "name": "任务 1 (默认没有 _file_path_key，回退模式测试)",
            "service_type": "whisper",
            "file_path": LOCAL_FILES[0],
            "path_key": "file_path",  # 默认键名测试
            "model": "deepdml/faster-whisper-large-v3-turbo-ct2"
        },
        {
            "name": "任务 2 (最外层 _file_path_key='file' 完美穿透测试)",
            "service_type": "whisper",
            "file_path": LOCAL_FILES[1],
            "path_key": "file",  # 💡 动态定义上传给上游的 Key 为 "file" 以完美契合 Whisper 上游！
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

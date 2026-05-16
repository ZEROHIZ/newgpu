import requests
import threading
import time
import json

# GPUREDIS 调度网关地址
GATEWAY_URL = "http://localhost:8000/api/tasks"

# 配置三个不同的测试任务
# 请在此处修改你的文件路径和参数
TASKS_TO_RUN = [
    {
        "name": "任务 1 (视频转写)",
        "service_type": "whisper",
        "file_path": "C:\\Users\\Administrator\\Downloads\\cs.mp3", # <-- 修改这里
        "model": "deepdml/faster-whisper-large-v3-turbo-ct2"
    },
    {
        "name": "任务 2 (音频转写)",
        "service_type": "whisper",
        "file_path": "C:\\Users\\Administrator\\Downloads\\下载 (1).mp4", # <-- 修改这里
        "model": "deepdml/faster-whisper-large-v3-turbo-ct2"
    },
    {
        "name": "任务 3 (长视频转写)",
        "service_type": "whisper",
        "file_path": "C:\\Users\\Administrator\\Downloads\\cs.mp3", # <-- 修改这里
        "model": "deepdml/faster-whisper-large-v3-turbo-ct2"
    }
]

def submit_and_watch(task_info):
    print(f"🚀 开始提交: {task_info['name']}...")
    
    # 构造 payload，这部分会透传给底层的执行器
    # 注意：在真实分布式环境下，Worker 需要能访问到这个 file_path
    payload = {
        "service_type": task_info["service_type"],
        "payload": {
            "file_path": task_info["file_path"],
            "model": task_info["model"],
        }
    }
    
    try:
        # 发送给调度器
        resp = requests.post(GATEWAY_URL, json=payload)
        if resp.status_code != 200:
            print(f"❌ {task_info['name']} 提交失败: {resp.text}")
            return

        result = resp.json()
        task_id = result["task_id"]
        channel = result["assigned_to"]["channel"]
        print(f"✅ {task_info['name']} 已分配到渠道: [{channel}], 任务ID: {task_id}")

        # 开始轮询状态
        while True:
            status_resp = requests.get(f"http://localhost:8000/api/tasks/{task_id}")
            task_status = status_resp.json().get("status", "unknown")
            print(f"🕒 {task_info['name']} 当前状态: {task_status}")
            
            if task_status in ["completed", "failed"]:
                print(f"🎉 {task_info['name']} 执行结束！状态: {task_status}")
                break
            
            time.sleep(2)
            
    except Exception as e:
        print(f"⚠️ {task_info['name']} 运行异常: {e}")

if __name__ == "__main__":
    print("=== GPUREDIS 并发压力测试工具 ===")
    threads = []
    for task in TASKS_TO_RUN:
        t = threading.Thread(target=submit_and_watch, args=(task,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
    print("=== 所有任务测试完成 ===")

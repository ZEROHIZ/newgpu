import json
import os
from typing import List, Dict, Any

DATA_DIR = "data"

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def save_data(filename: str, data: Any):
    """保存数据到 data/ 文件夹下的 JSON 文件"""
    ensure_data_dir()
    path = os.path.join(DATA_DIR, f"{filename}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_data(filename: str) -> Any:
    """从 data/ 文件夹下的 JSON 文件加载数据"""
    path = os.path.join(DATA_DIR, f"{filename}.json")
    if not os.path.exists(path):
        return [] if filename != "config" else {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return [] if filename != "config" else {}

def get_all_gpus() -> List[Dict]:
    return load_data("gpus")

def save_gpus(gpus: List[Dict]):
    save_data("gpus", gpus)

def get_all_channels() -> List[Dict]:
    return load_data("channels")

def save_channels(channels: List[Dict]):
    save_data("channels", channels)

def get_all_tasks() -> List[Dict]:
    return load_data("tasks")

def save_tasks(tasks: List[Dict]):
    save_data("tasks", tasks)

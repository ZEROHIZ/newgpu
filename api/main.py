from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from core.redis_client import redis_manager
import uuid
import os
import asyncio
import sys
import shutil

# 确保可以从父目录导入 worker
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from worker.agent import GPUAgent
from core.persistence import get_all_gpus, save_gpus, get_all_channels, save_channels, get_all_tasks, save_tasks

app = FastAPI(title="GPUREDIS API Gateway")
templates = Jinja2Templates(directory="web/templates")

# 确保静态文件目录存在
os.makedirs("web/static", exist_ok=True)
os.makedirs("data/uploads", exist_ok=True)

app.mount("/static", StaticFiles(directory="web/static"), name="static")
app.mount("/uploads", StaticFiles(directory="data/uploads"), name="uploads")

# ========== 系统工具 ==========

async def cleanup_old_files(force_all=False):
    """清理 data/temp 和 data/uploads 中的文件"""
    import time
    now = time.time()
    retention = 0 if force_all else 24 * 3600 # 24 小时
    
    dirs = ["data/temp", "data/uploads"]
    count = 0
    for d in dirs:
        if not os.path.exists(d): continue
        for f in os.listdir(d):
            fpath = os.path.join(d, f)
            if os.path.isfile(fpath):
                if force_all or (now - os.path.getmtime(fpath) > retention):
                    try:
                        os.remove(fpath)
                        count += 1
                    except: pass
    return count

# ========== 数据模型 ==========

class GPUDevice(BaseModel):
    id: str = ""
    name: str            # 显卡名称
    total_vram: float    # 总显存 (GB)
    total_ram: float     # 总内存 (GB)
    host: str = "localhost"

class Channel(BaseModel):
    id: str = ""
    name: str
    gpu_id: str
    service_type: str
    service_url: str = ""
    query_url: str = ""
    execution_mode: str = "sync"
    base_vram: float = 0.0
    base_ram: float = 0.0
    weight: int = 10
    active: bool = True

# ========== 页面路由 ==========

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})

# ========== 启动事件 ==========

@app.on_event("startup")
async def startup_event():
    try:
        client = await redis_manager.connect()
        await client.ping()
        print("✅ Redis 连接成功")
        
        # --- 从本地 JSON 同步到 Redis ---
        local_gpus = get_all_gpus()
        for gpu in local_gpus:
            await redis_manager.set_json(f"gpu_device:{gpu['id']}", gpu)
        
        local_channels = get_all_channels()
        for ch in local_channels:
            await redis_manager.set_json(f"channel:{ch['id']}", ch)
        print(f"✅ 数据同步完成: {len(local_gpus)} 显卡, {len(local_channels)} 渠道")

        # --- 清理 24 小时前的临时文件 ---
        asyncio.create_task(cleanup_old_files())

        # 自动启动本地 Agent
        gpu_id = os.getenv("DEFAULT_GPU_ID", "0")
        if gpu_id == "0" and local_gpus:
            gpu_id = local_gpus[0].get("id", "0")
        
        agent = GPUAgent(gpu_index=0, gpu_id=gpu_id)
        asyncio.create_task(agent.start())
        print(f"🚀 本地 GPU Agent 已启动: {gpu_id}")
    except Exception as e:
        print(f"❌ 启动异常: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    await redis_manager.close()

# ========== GPU 设备管理 API ==========

@app.get("/api/gpus")
async def list_gpus():
    try:
        keys = await redis_manager.keys("gpu_device:*")
        gpus = []
        for key in keys:
            data = await redis_manager.get_json(key)
            if data: gpus.append(data)
        return {"gpus": gpus, "redis_connected": True}
    except Exception as e:
        return {"gpus": [], "redis_connected": False, "error": str(e)}

@app.post("/api/gpus")
async def add_gpu(gpu: GPUDevice):
    gpu.id = str(uuid.uuid4())[:8]
    await redis_manager.set_json(f"gpu_device:{gpu.id}", gpu.dict())
    # 本地同步
    all_gpus = get_all_gpus()
    all_gpus.append(gpu.dict())
    save_gpus(all_gpus)
    return gpu

@app.delete("/api/gpus/{gpu_id}")
async def delete_gpu(gpu_id: str):
    await redis_manager.delete(f"gpu_device:{gpu_id}")
    # 本地同步
    all_gpus = [g for g in get_all_gpus() if g['id'] != gpu_id]
    save_gpus(all_gpus)
    # 同时删除绑定在该显卡上的所有渠道
    keys = await redis_manager.keys("channel:*")
    for key in keys:
        data = await redis_manager.get_json(key)
        if data and data.get("gpu_id") == gpu_id:
            await redis_manager.delete(key)
    # 渠道本地同步
    all_chs = [ch for ch in get_all_channels() if ch['gpu_id'] != gpu_id]
    save_channels(all_chs)
    return {"ok": True}

# ========== 渠道管理 API ==========

@app.get("/api/channels")
async def list_channels():
    try:
        keys = await redis_manager.keys("channel:*")
        channels = []
        for key in keys:
            data = await redis_manager.get_json(key)
            if data: channels.append(data)
        return {"channels": channels}
    except Exception as e:
        return {"channels": [], "error": str(e)}

@app.post("/api/channels")
async def add_channel(channel: Channel):
    channel.id = str(uuid.uuid4())[:8]
    await redis_manager.set_json(f"channel:{channel.id}", channel.dict())
    # 本地同步
    all_chs = get_all_channels()
    all_chs.append(channel.dict())
    save_channels(all_chs)
    return channel

@app.put("/api/channels/{channel_id}")
async def update_channel(channel_id: str, channel: Channel):
    channel.id = channel_id
    await redis_manager.set_json(f"channel:{channel_id}", channel.dict())
    # 本地同步
    all_chs = [ch if ch['id'] != channel_id else channel.dict() for ch in get_all_channels()]
    save_channels(all_chs)
    return channel

@app.delete("/api/channels/{channel_id}")
async def delete_channel(channel_id: str):
    await redis_manager.delete(f"channel:{channel_id}")
    # 本地同步
    all_chs = [ch for ch in get_all_channels() if ch['id'] != channel_id]
    save_channels(all_chs)
    return {"ok": True}

@app.post("/api/agent/sync")
async def sync_agent():
    # 设置一个同步信号，有效期 10 秒
    await redis_manager.client.set("signal:sync_agent", "1", ex=10)
    return {"ok": True}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    # 生成唯一文件名
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{ext}"
    save_path = os.path.join("data", "uploads", filename)
    
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 返回文件的相对访问路径
    return {
        "filename": file.filename,
        "url": f"/uploads/{filename}",
        "full_path": os.path.abspath(save_path)
    }

@app.get("/api/system/storage")
async def get_storage_stats():
    stats = {}
    for d in ["data/temp", "data/uploads"]:
        os.makedirs(d, exist_ok=True)
        files = os.listdir(d)
        size = sum(os.path.getsize(os.path.join(d, f)) for f in files if os.path.isfile(os.path.join(d, f)))
        stats[d.split("/")[-1]] = {
            "count": len(files),
            "size": round(size / (1024 * 1024), 2) # MB
        }
    return stats

@app.post("/api/system/storage/clear")
async def manual_clear_storage():
    deleted_count = await cleanup_old_files(force_all=True)
    return {"ok": True, "deleted_count": deleted_count}

# ========== 系统状态 ==========

@app.get("/api/status")
async def get_system_status():
    try:
        client = await redis_manager.connect()
        await client.ping()
        gpu_keys = await redis_manager.keys("gpu_device:*")
        channel_keys = await redis_manager.keys("channel:*")
        return {
            "redis_connected": True,
            "gpu_count": len(gpu_keys),
            "channel_count": len(channel_keys),
        }
    except Exception as e:
        return {"redis_connected": False, "error": str(e)}

# ========== 任务调度与负载均衡 API ==========

class TaskRequest(BaseModel):
    service_type: str
    priority: int = 0
    payload: dict

@app.post("/api/tasks")
async def create_task(req: TaskRequest):
    import random
    import time

    keys = await redis_manager.keys("channel:*")
    matching_channels = []
    for key in keys:
        ch = await redis_manager.get_json(key)
        if ch and ch.get("service_type") == req.service_type and ch.get("active"):
            matching_channels.append(ch)
            
    if not matching_channels:
        raise HTTPException(status_code=404, detail=f"未找到可用的服务渠道: {req.service_type}")

    # 资源校验
    valid_channels = []
    for ch in matching_channels:
        vram_needed = ch.get("base_vram", 0.0)
        gpu_id = ch.get("gpu_id")
        realtime = await redis_manager.get_json(f"gpu_realtime:{gpu_id}")
        if not realtime: continue
            
        current_free_vram = realtime.get("free_vram", 0)
        running_tasks_vram = 0
        task_keys = await redis_manager.keys("task:*")
        for t_key in task_keys:
            t_data = await redis_manager.get_json(t_key)
            if t_data and t_data.get("gpu_id") == gpu_id and t_data.get("status") == "running":
                running_tasks_vram += t_data.get("vram_allocated", 0)

        if (current_free_vram - running_tasks_vram) >= vram_needed:
            valid_channels.append(ch)

    if not valid_channels:
        selected_channel = max(matching_channels, key=lambda x: x.get("weight", 10))
        is_pending = True
    else:
        total_weight = sum(ch.get("weight", 10) for ch in valid_channels)
        r = random.uniform(0, total_weight)
        upto = 0
        selected_channel = valid_channels[0]
        for ch in valid_channels:
            weight = ch.get("weight", 10)
            if upto + weight >= r:
                selected_channel = ch
                break
            upto += weight
        is_pending = False

    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "service_type": req.service_type,
        "channel_id": selected_channel["id"],
        "gpu_id": selected_channel["gpu_id"],
        "vram_allocated": selected_channel.get("base_vram", 0),
        "payload": req.payload,
        "status": "pending",
        "created_at": time.time()
    }
    
    await redis_manager.set_json(f"task:{task_id}", task, ex=604800)
    await redis_manager.push_task(f"channel:{selected_channel['id']}", task)

    return {
        "status": "success",
        "task_id": task_id, 
        "is_queued": is_pending,
        "assigned_to": {
            "channel": selected_channel["name"],
            "gpu_id": selected_channel["gpu_id"]
        }
    }

@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    task = await redis_manager.get_json(f"task:{task_id}")
    if not task: raise HTTPException(status_code=404, detail="任务不存在")
    return task

@app.get("/api/queue")
async def get_queue_tasks():
    import json
    task_keys = await redis_manager.keys("task:*")
    all_tasks = []
    for tk in task_keys:
        task = await redis_manager.get_json(tk)
        if task:
            all_tasks.append({
                "id": task.get("id"),
                "service_type": task.get("service_type"),
                "channel_id": task.get("channel_id"),
                "created_at": task.get("created_at"),
                "status": task.get("status"),
                "result": task.get("result"),
                "error": task.get("error")
            })
    all_tasks.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return {"tasks": all_tasks[:50]}

@app.delete("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    task_key = f"task:{task_id}"
    task = await redis_manager.get_json(task_key)
    if not task: raise HTTPException(status_code=404, detail="任务不存在")
    if task.get("status") not in ["pending", "waiting"]:
        raise HTTPException(status_code=400, detail="只能取消排队中的任务")

    queue_keys = await redis_manager.keys("queue:channel:*")
    import json
    for q in queue_keys:
        items = await redis_manager.get_list(q)
        for item in items:
            try:
                t = json.loads(item)
                if t.get("id") == task_id:
                    await redis_manager.remove_from_list(q, item)
                    break
            except: pass

    task["status"] = "cancelled"
    await redis_manager.set_json(task_key, task, ex=604800)
    return {"ok": True}

@app.delete("/api/tasks/{task_id}")
async def delete_task_record(task_id: str):
    await redis_manager.delete(f"task:{task_id}")
    return {"ok": True}

@app.delete("/api/tasks/history/clear")
async def clear_task_history():
    task_keys = await redis_manager.keys("task:*")
    count = 0
    for tk in task_keys:
        task = await redis_manager.get_json(tk)
        if task and task.get("status") in ["completed", "failed", "cancelled"]:
            await redis_manager.delete(tk)
            count += 1
    return {"deleted_count": count}

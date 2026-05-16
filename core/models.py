from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
import time

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

class Task(BaseModel):
    id: str
    service_type: str  # whisper, comfyui, llm
    payload: Dict[str, Any]
    priority: int = 0
    status: TaskStatus = TaskStatus.PENDING
    vram_required: float = 0.0  # 预估显存 (GB)
    ram_required: float = 0.0   # 预估内存 (GB)
    created_at: float = Field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    result: Optional[Any] = None
    gpu_id: Optional[int] = None

class GPUInfo(BaseModel):
    id: int
    name: str
    total_vram: float  # GB
    free_vram: float   # GB
    total_ram: float   # GB
    free_ram: float    # GB
    load: float        # %
    last_update: float = Field(default_factory=time.time)

class Channel(BaseModel):
    id: str
    gpu_id: int
    service_type: str
    weight: int = 10
    active: bool = True
    base_vram: float = 0.0
    base_ram: float = 0.0

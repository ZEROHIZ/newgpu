import pynvml
import psutil
from typing import List
from .models import GPUInfo
import time

class GPUMonitor:
    def __init__(self):
        try:
            pynvml.nvmlInit()
            self.initialized = True
        except Exception:
            self.initialized = False

    def get_gpu_info(self) -> List[GPUInfo]:
        if not self.initialized:
            return []
        
        info_list = []
        device_count = pynvml.nvmlDeviceGetCount()
        
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode('utf-8')
            
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            
            # 获取系统内存信息
            vm = psutil.virtual_memory()
            
            info_list.append(GPUInfo(
                id=i,
                name=name,
                total_vram=mem.total / 1024**3,
                free_vram=mem.free / 1024**3,
                total_ram=vm.total / 1024**3,
                free_ram=vm.available / 1024**3,
                load=util.gpu,
                last_update=time.time()
            ))
        return info_list

    def __del__(self):
        if self.initialized:
            try:
                pynvml.nvmlShutdown()
            except:
                pass

gpu_monitor = GPUMonitor()

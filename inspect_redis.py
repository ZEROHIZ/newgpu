import asyncio
import os
import sys
import json

# 增加路径，确保能导入 core 模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.redis_client import redis_manager

async def list_redis_data():
    try:
        client = await redis_manager.connect()
        print("Connected to Redis.")
        
        def safe_decode(val):
            if isinstance(val, bytes):
                return val.decode()
            return val

        # 获取所有 GPU 设备
        gpu_keys = await client.keys("gpu_device:*")
        print(f"\n--- GPU Devices ({len(gpu_keys)}) ---")
        for key in gpu_keys:
            val = await client.get(key)
            print(f"{safe_decode(key)}: {safe_decode(val)}")
            
        # 获取所有渠道
        channel_keys = await client.keys("channel:*")
        print(f"\n--- Channels ({len(channel_keys)}) ---")
        for key in channel_keys:
            val = await client.get(key)
            print(f"{safe_decode(key)}: {safe_decode(val)}")
            
        # 检查是否有其他配置
        all_keys = await client.keys("*")
        for key in all_keys:
            k = safe_decode(key)
            if not k.startswith("gpu_device") and not k.startswith("channel"):
                try:
                    val = await client.get(key)
                    print(f"Other: {k} -> {safe_decode(val)[:100]}")
                except:
                    pass

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await redis_manager.close()

if __name__ == "__main__":
    asyncio.run(list_redis_data())

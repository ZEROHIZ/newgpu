import redis.asyncio as redis
import json
from typing import Optional, Any
from core.config_loader import get_redis_config

class RedisClient:
    def __init__(self):
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        if not self.client:
            cfg = get_redis_config()
            self.client = redis.Redis(
                host=cfg["host"],
                port=cfg["port"],
                db=cfg["db"],
                password=cfg["password"],
                decode_responses=True
            )
        return self.client

    async def close(self):
        if self.client:
            await self.client.close()
            self.client = None

    async def set_json(self, key: str, value: Any, ex: int = None):
        client = await self.connect()
        await client.set(key, json.dumps(value, ensure_ascii=False), ex=ex)

    async def get_json(self, key: str) -> Optional[Any]:
        client = await self.connect()
        data = await client.get(key)
        if data:
            return json.loads(data)
        return None

    async def delete(self, key: str):
        client = await self.connect()
        await client.delete(key)

    async def keys(self, pattern: str):
        client = await self.connect()
        return await client.keys(pattern)

    async def push_task(self, queue_name: str, task_data: dict):
        client = await self.connect()
        # 统一使用 queue: 作为前缀，不要重复叠加
        await client.lpush(f"queue:{queue_name}", json.dumps(task_data, ensure_ascii=False))

    async def pop_task(self, queue_name: str, timeout: int = 0):
        client = await self.connect()
        result = await client.brpop(f"queue:{queue_name}", timeout=timeout)
        if result:
            return json.loads(result[1])
        return None

    async def get_list(self, list_name: str):
        client = await self.connect()
        return await client.lrange(list_name, 0, -1)

    async def remove_from_list(self, list_name: str, item_json_str: str):
        client = await self.connect()
        # count=0 表示移除所有匹配的元素
        await client.lrem(list_name, 0, item_json_str)

redis_manager = RedisClient()

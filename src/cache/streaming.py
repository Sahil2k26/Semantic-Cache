import time
import json
import asyncio
from typing import AsyncGenerator, List, Dict, Optional
from dataclasses import dataclass

@dataclass
class StreamChunk:
    token: str
    timestamp_ms: int
    is_final: bool = False

class StreamingCache:
    def __init__(self, cache_manager):
        self.cache_manager = cache_manager

    async def stream_and_cache(
        self,
        query_key: str,
        token_generator: AsyncGenerator[str, None],
        metadata: Dict
    ) -> AsyncGenerator[str, None]:
        """Streams tokens to user while simultaneously caching chronologically."""
        chunks: List[StreamChunk] = []
        start_time = time.time() * 1000
        
        async for token in token_generator:
            chunk = StreamChunk(
                token=token,
                timestamp_ms=int(time.time() * 1000 - start_time)
            )
            chunks.append(chunk)
            yield token
            
        if chunks:
            chunks[-1].is_final = True
            
        asyncio.create_task(self._store_stream(query_key, chunks, metadata))

    async def _store_stream(self, key: str, chunks: List[StreamChunk], metadata: Dict):
        stream_data = {
            "chunks": [
                {
                    "token": c.token,
                    "delay_ms": c.timestamp_ms,
                    "is_final": c.is_final
                } for c in chunks
            ],
            "metadata": metadata,
            "total_tokens": len(chunks),
            "stored_at": time.time()
        }
        
        # In a real cluster we could write to L2 explicitly, 
        # but using the cache_manager abstraction:
        from src.cache.base import CacheEntry
        
        emb_dim = getattr(self.cache_manager.config, "embedding_dimension", 384)
        entry = CacheEntry(
            query_id=f"stream:{key}",
            query_text=metadata.get("query", key),
            embedding=[0.0] * emb_dim,
            response=json.dumps(stream_data),
            metadata=metadata
        )
        entry.calculate_memory(emb_dim)
        self.cache_manager.put(entry, tenant_id="default")


    async def get_stream(self, key: str, speed_multiplier: float = 1.0) -> Optional[AsyncGenerator[str, None]]:
        """Retrieves and replays tokens adhering to temporal offsets for realistic feeling."""
        # Note: We rely on standard memory cache here. In true semantic mode, we'd hit semantic index.
        # But stream fetching is usually exact-match via query_id
        entry = self.cache_manager.l1_cache.get(f"stream:{key}")
        
        if not entry and self.cache_manager.l2_cache:
            entry = await self.cache_manager.l2_cache.get(f"stream:{key}")
            
        if not entry:
            return None
            
        stream_data = json.loads(entry.response)
        
        async def fast_replay():
            chunks = stream_data["chunks"]
            if speed_multiplier == 0:
                for chunk in chunks:
                    yield chunk["token"]
                    await asyncio.sleep(0) 
            else:
                last_delay = 0
                for chunk in chunks:
                    adjusted_wait = (chunk["delay_ms"] - last_delay) / speed_multiplier
                    if adjusted_wait > 5:
                        await asyncio.sleep(adjusted_wait / 1000)
                    yield chunk["token"]
                    last_delay = chunk["delay_ms"]
                    
        return fast_replay()

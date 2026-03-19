"""
Cache Manager - Two-Tier Cache Orchestration

Orchestrates L1 (in-memory) and L2 (Redis) caches for optimal performance.
Implements tiered lookup, write-through, and write-back strategies.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.cache.base import CacheEntry, CacheHitReason, CacheConfig
from src.cache.l1_cache import L1Cache
from src.cache.l2_cache import L2Cache, L2CacheMetrics
from src.cache.redis_config import RedisConfig


logger = logging.getLogger(__name__)


class CacheStrategy(Enum):
    """Cache operation strategies."""
    WRITE_THROUGH = "write_through"  # Write to L1 and L2 simultaneously
    WRITE_BACK = "write_back"        # Write to L1, sync L2 asynchronously
    L1_ONLY = "l1_only"              # Only use L1 cache
    L2_ONLY = "l2_only"              # Only use L2 cache


class TieredCacheMetrics:
    """Combined metrics for both L1 and L2 caches."""
    
    def __init__(self):
        """Initialize metrics."""
        self.created_at = time.time()
        self.total_requests = 0
        self.l1_hits = 0
        self.l2_hits = 0
        self.misses = 0
        self.l1_to_l2_promotions = 0  # L2 hits copied to L1
        self.tiered_hit_rate = 0.0
    
    def get_combined_hit_rate(self) -> float:
        """Get overall hit rate."""
        if self.total_requests == 0:
            return 0.0
        return (self.l1_hits + self.l2_hits) / self.total_requests
    
    def record_hit(self, source: str) -> None:
        """Record cache hit.
        
        Args:
            source: Hit source ("L1" or "L2")
        """
        self.total_requests += 1
        if source == "L1":
            self.l1_hits += 1
        elif source == "L2":
            self.l2_hits += 1
    
    def record_miss(self) -> None:
        """Record cache miss."""
        self.total_requests += 1
        self.misses += 1


@dataclass
class CacheManagerConfig:
    """Configuration for cache manager."""
    
    l1_config: CacheConfig = None
    l2_config: Optional[RedisConfig] = None
    
    strategy: CacheStrategy = CacheStrategy.WRITE_THROUGH
    enable_l1_to_l2_promotion: bool = True  # Promote L2 hits to L1
    enable_l2_compression: bool = False
    
    def __post_init__(self):
        """Initialize defaults."""
        if self.l1_config is None:
            self.l1_config = CacheConfig()
        
        if self.l2_config is None:
            self.l2_config = RedisConfig()


class CacheManager:
    """Two-tier cache orchestrator combining L1 and L2 caches.
    
    L1: In-memory HNSW cache for speed
    L2: Redis cache for persistence and distribution
    
    Implements intelligent tiered lookup and promotion strategies.
    """
    
    def __init__(self, config: Optional[CacheManagerConfig] = None):
        """Initialize cache manager.
        
        Args:
            config: Manager configuration
        """
        if config is None:
            config = CacheManagerConfig()
        
        self.config = config
        self.l1_cache = L1Cache(config.l1_config)
        self.l2_cache = L2Cache(config.l2_config) if config.l2_config else None
        self.metrics = TieredCacheMetrics()
        
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize both cache tiers.
        
        Returns:
            True if initialization successful
        """
        try:
            # L1 is always initialized (in-memory)
            logger.info("L1 cache initialized")
            
            # L2 optional, connect if available
            if self.l2_cache is not None:
                if self.l2_cache.connect():
                    logger.info("L2 cache initialized")
                else:
                    logger.warning("L2 cache connection failed, continuing with L1 only")
                    self.l2_cache = None
            
            self._initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Cache manager initialization failed: {e}")
            return False
    
    def put(self, entry: CacheEntry) -> bool:
        """Store entry in cache.
        
        Implements configured strategy (write-through/write-back/L1-only).
        
        Args:
            entry: Cache entry
            
        Returns:
            True if successful
        """
        if not self._initialized:
            return False
        
        try:
            if self.config.strategy == CacheStrategy.WRITE_THROUGH:
                # Write to both L1 and L2
                l1_ok = self.l1_cache.put(entry)
                l2_ok = True
                
                if self.l2_cache is not None:
                    l2_ok = self.l2_cache.put(entry)
                
                return l1_ok and l2_ok
                
            elif self.config.strategy == CacheStrategy.WRITE_BACK:
                # Write to L1, sync L2 asynchronously
                l1_ok = self.l1_cache.put(entry)
                
                # Non-blocking L2 write (could be async in production)
                if self.l2_cache is not None:
                    try:
                        self.l2_cache.put(entry)
                    except Exception as e:
                        logger.warning(f"Async L2 write failed: {e}")
                
                return l1_ok
                
            elif self.config.strategy == CacheStrategy.L1_ONLY:
                return self.l1_cache.put(entry)
                
            elif self.config.strategy == CacheStrategy.L2_ONLY:
                if self.l2_cache is not None:
                    return self.l2_cache.put(entry)
                return False
                
        except Exception as e:
            logger.error(f"Put operation failed: {e}")
            return False
    
    def get(self, query_id: str) -> Optional[Tuple[CacheEntry, str]]:
        """Retrieve entry from cache.
        
        Implements tiered lookup:
        1. Check L1 (in-memory)
        2. If miss, check L2 (Redis)
        3. If L2 hit, promote to L1
        
        Args:
            query_id: Query ID
            
        Returns:
            (CacheEntry, hit_source) or None if not found
        """
        if not self._initialized:
            return None
        
        try:
            # Check L1
            entry = self.l1_cache.get(query_id)
            if entry is not None:
                self.metrics.record_hit("L1")
                logger.debug(f"L1 hit for {query_id}")
                return (entry, "L1")
            
            # Check L2 if available
            if self.l2_cache is not None:
                entry = self.l2_cache.get(query_id)
                if entry is not None:
                    self.metrics.record_hit("L2")
                    logger.debug(f"L2 hit for {query_id}")
                    
                    # Promote to L1
                    if self.config.enable_l1_to_l2_promotion:
                        self.l1_cache.put(entry)
                        self.metrics.l1_to_l2_promotions += 1
                        logger.debug(f"Promoted {query_id} from L2 to L1")
                    
                    return (entry, "L2")
            
            # Miss
            self.metrics.record_miss()
            logger.debug(f"Cache miss for {query_id}")
            return None
            
        except Exception as e:
            logger.error(f"Get operation failed: {e}")
            self.metrics.record_miss()
            return None
    
    def delete(self, query_id: str) -> bool:
        """Delete entry from both tiers.
        
        Args:
            query_id: Query ID
            
        Returns:
            True if successful
        """
        try:
            l1_ok = self.l1_cache.delete(query_id)
            l2_ok = True
            
            if self.l2_cache is not None:
                l2_ok = self.l2_cache.delete(query_id)
                self.publish_invalidation(query_id)
            
            return l1_ok and l2_ok
            
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False
    
    def clear(self) -> bool:
        """Clear both cache tiers.
        
        Returns:
            True if successful
        """
        try:
            l1_ok = self.l1_cache.clear()
            l2_ok = True
            
            if self.l2_cache is not None:
                l2_ok = self.l2_cache.clear()
                self.publish_invalidation("__FLUSHALL__")
            
            return l1_ok and l2_ok
            
        except Exception as e:
            logger.error(f"Clear failed: {e}")
            return False
    
    def sync_l1_to_l2(self) -> Tuple[int, int]:
        """Sync all L1 entries to L2.
        
        Returns:
            (successful, failed) count
        """
        if self.l2_cache is None:
            logger.warning("L2 cache not available, cannot sync")
            return 0, 0
        
        try:
            all_entries = []
            
            # Get all entries from L1
            for query_id in list(self.l1_cache.entries.keys()):
                entry = self.l1_cache.entries[query_id]
                if entry and not entry.is_expired(self.config.l1_config.ttl_seconds):
                    all_entries.append(entry)
            
            # Batch write to L2
            return self.l2_cache.batch_put(all_entries)
            
        except Exception as e:
            logger.error(f"L1->L2 sync failed: {e}")
            return 0, len(self.l1_cache.entries)
    
    def sync_l2_to_l1(self) -> Tuple[int, int]:
        """Sync all L2 entries to L1.
        
        Returns:
            (successful, failed) count
        """
        if self.l2_cache is None:
            logger.warning("L2 cache not available, cannot sync")
            return 0, 0
        
        try:
            all_keys = self.l2_cache.get_all_keys()
            entries = self.l2_cache.batch_get(all_keys)
            
            successful = 0
            failed = 0
            
            for entry in entries:
                if entry is not None:
                    if self.l1_cache.put(entry):
                        successful += 1
                    else:
                        failed += 1
            
            return successful, failed
            
        except Exception as e:
            logger.error(f"L2->L1 sync failed: {e}")
            return 0, len(all_keys) if self.l2_cache else 0
    
    def get_l1_stats(self) -> Dict[str, Any]:
        """Get L1 cache stats.
        
        Returns:
            L1 statistics
        """
        metrics = self.l1_cache.get_metrics()
        total_evictions = (
            metrics.evictions_lru + 
            metrics.evictions_lfu + 
            metrics.evictions_ttl + 
            metrics.evictions_memory
        )
        return {
            "size": self.l1_cache.size(),
            "memory_mb": self.l1_cache.memory_usage_mb(),
            "hit_rate": metrics.hit_rate if metrics.total_requests > 0 else 0.0,
            "total_requests": metrics.total_requests,
            "cache_hits": metrics.cache_hits,
            "cache_misses": metrics.cache_misses,
            "evictions": total_evictions,
        }
    
    def get_l2_stats(self) -> Dict[str, Any]:
        """Get L2 cache stats.
        
        Returns:
            L2 statistics
        """
        if self.l2_cache is None:
            return {}
        
        return self.l2_cache.get_stats()
    
    def get_combined_stats(self) -> Dict[str, Any]:
        """Get combined stats from both tiers.
        
        Returns:
            Combined statistics
        """
        return {
            "l1": self.get_l1_stats(),
            "l2": self.get_l2_stats(),
            "tiered": {
                "total_requests": self.metrics.total_requests,
                "l1_hits": self.metrics.l1_hits,
                "l2_hits": self.metrics.l2_hits,
                "misses": self.metrics.misses,
                "combined_hit_rate": self.metrics.get_combined_hit_rate(),
                "l1_to_l2_promotions": self.metrics.l1_to_l2_promotions,
            }
        }
    
    def get_metrics(self) -> TieredCacheMetrics:
        """Get manager metrics.
        
        Returns:
            Tiered cache metrics
        """
        return self.metrics
    
    def health_check(self) -> Dict[str, bool]:
        """Check health of both tiers.
        
        Returns:
            Health status dict
        """
        return {
            "l1": True,  # L1 is always in-memory
            "l2": self.l2_cache.health_check() if self.l2_cache else True,
        }
    
    def shutdown(self) -> None:
        """Shutdown cache manager.
        
        Cleans up resources and closes connections.
        """
        try:
            if self.l2_cache is not None:
                self.l2_cache.disconnect()
            
            logger.info("Cache manager shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    def start_invalidation_listener(self) -> None:
        """Start a background thread listening for L1 invalidation events."""
        if self.l2_cache is None or not self.l2_cache.ensure_connected():
            return
            
        import threading
        
        def listener():
            try:
                pubsub = self.l2_cache._client.pubsub()
                pubsub.subscribe("semantic_cache_invalidation")
                logger.info("Started Redis pub/sub listener for cache invalidation")
                for message in pubsub.listen():
                    if message["type"] == "message":
                        key = message["data"].decode("utf-8")
                        if key == "__FLUSHALL__":
                            self.l1_cache.clear()
                        else:
                            self.l1_cache.delete(key)
            except Exception as e:
                logger.error(f"Pub/sub listener failed: {e}")
                
        self._listener_thread = threading.Thread(target=listener, daemon=True)
        self._listener_thread.start()
        
    def publish_invalidation(self, query_id: str) -> None:
        """Publish an invalidation event to other nodes."""
        if self.l2_cache is not None and self.l2_cache.ensure_connected():
            self.l2_cache._client.publish("semantic_cache_invalidation", query_id)


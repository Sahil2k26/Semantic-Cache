"""
Cache Manager - Three-Tier Cache Orchestration with Semantic Search

Orchestrates L1 (in-memory), L2 (Redis), and L3 (PostgreSQL) caches for optimal performance.
Implements tiered lookup, write-through, and write-back strategies.

CACHE HIERARCHY:
- L1: In-memory cache (<1ms latency, ~100K entries)
- L2: Redis cache (5-10ms latency, ~1M entries)  
- L3: PostgreSQL cache (20-50ms latency, ~10M entries, persistent)

SEMANTIC SEARCH INTEGRATION (Phase Fix):
- get_semantic(): Find similar cached entries by embedding similarity
- put_with_embedding(): Store entries with proper embeddings in unified index
- Integrates with UnifiedIndexManager for cross-component search
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Callable, Awaitable, TYPE_CHECKING

from src.cache.base import CacheEntry, CacheHitReason, CacheConfig
from src.cache.l1_cache import L1Cache
from src.cache.l2_cache import L2Cache, L2CacheMetrics
from src.cache.l3_cache import L3Cache, L3CacheMetrics
from src.cache.redis_config import RedisConfig
from src.ml.query_parser import QueryNormalizer, RuleBasedIntentDetector, MultiIntentQuery, SubQuery

if TYPE_CHECKING:
    from src.cache.index_manager import UnifiedIndexManager


logger = logging.getLogger(__name__)


@dataclass
class SemanticSearchResult:
    """Result of a semantic cache search."""
    entry: Optional[CacheEntry]
    similarity: float
    hit_source: str  # "L1", "L2", "index", "none"
    hit_reason: CacheHitReason
    is_exact_match: bool = False
    domain: str = "general"
    threshold_used: float = 0.85


class CacheStrategy(Enum):
    """Cache operation strategies."""
    WRITE_THROUGH = "write_through"  # Write to L1 and L2 simultaneously
    WRITE_BACK = "write_back"        # Write to L1, sync L2 asynchronously
    L1_ONLY = "l1_only"              # Only use L1 cache
    L2_ONLY = "l2_only"              # Only use L2 cache


class TieredCacheMetrics:
    """Combined metrics for L1, L2, and L3 caches."""
    
    def __init__(self):
        """Initialize metrics."""
        self.created_at = time.time()
        self.total_requests = 0
        self.l1_hits = 0
        self.l2_hits = 0
        self.l3_hits = 0
        self.misses = 0
        self.l1_to_l2_promotions = 0  # L2 hits copied to L1
        self.l3_to_l1_promotions = 0  # L3 hits promoted to L1
        self.l3_to_l2_promotions = 0  # L3 hits promoted to L2
        self.tiered_hit_rate = 0.0
    
    def get_combined_hit_rate(self) -> float:
        """Get overall hit rate."""
        if self.total_requests == 0:
            return 0.0
        return (self.l1_hits + self.l2_hits + self.l3_hits) / self.total_requests
    
    def record_hit(self, source: str) -> None:
        """Record cache hit.
        
        Args:
            source: Hit source ("L1", "L2", or "L3")
        """
        self.total_requests += 1
        if source == "L1":
            self.l1_hits += 1
        elif source == "L2":
            self.l2_hits += 1
        elif source == "L3":
            self.l3_hits += 1
    
    def record_miss(self) -> None:
        """Record cache miss."""
        self.total_requests += 1
        self.misses += 1


@dataclass
class CacheManagerConfig:
    """Configuration for cache manager."""
    
    l1_config: CacheConfig = None
    l2_config: Optional[RedisConfig] = None
    enable_l3: bool = True  # Enable L3 PostgreSQL cache
    l3_ttl_days: int = 30   # Default TTL for L3 entries
    
    strategy: CacheStrategy = CacheStrategy.WRITE_THROUGH
    enable_l1_to_l2_promotion: bool = True  # Promote L2 hits to L1
    enable_l3_promotion: bool = True  # Promote L3 hits to L1/L2
    enable_l2_compression: bool = False
    
    # Semantic search configuration
    embedding_dimension: int = 384  # Default for all-MiniLM-L6-v2
    default_similarity_threshold: float = 0.85
    enable_semantic_search: bool = True
    
    def __post_init__(self):
        """Initialize defaults."""
        if self.l1_config is None:
            self.l1_config = CacheConfig()
        
        if self.l2_config is None:
            self.l2_config = RedisConfig()


class CacheManager:
    """Three-tier cache orchestrator combining L1, L2, and L3 caches.
    
    L1: In-memory HNSW cache for speed (<1ms)
    L2: Redis cache for warm data (5-10ms)
    L3: PostgreSQL cache for cold, persistent storage (20-50ms)
    
    Implements intelligent tiered lookup and promotion strategies.
    
    SEMANTIC SEARCH:
    This class now integrates with UnifiedIndexManager to provide
    semantic similarity search across cached items. Use get_semantic()
    for similarity-based lookups and put_with_embedding() for properly
    indexed storage.
    """
    
    def __init__(
        self,
        config: Optional[CacheManagerConfig] = None,
        index_manager: Optional['UnifiedIndexManager'] = None,
        embedding_service: Optional[Any] = None,
        domain_classifier: Optional[Any] = None,
        threshold_manager: Optional[Any] = None,
        db_manager: Optional[Any] = None,
    ):
        """Initialize cache manager.
        
        Args:
            config: Manager configuration
            index_manager: Shared UnifiedIndexManager instance
            embedding_service: EmbeddingService for generating embeddings
            domain_classifier: DomainClassifier for query classification
            threshold_manager: AdaptiveThresholdManager for domain thresholds
            db_manager: DatabaseManager for L3 cache (optional)
        """
        if config is None:
            config = CacheManagerConfig()
        
        self.config = config
        self.l1_cache = L1Cache(config.l1_config)
        self.l2_cache = L2Cache(config.l2_config) if config.l2_config else None
        self.l3_cache: Optional[L3Cache] = None
        self._db_manager = db_manager
        self.metrics = TieredCacheMetrics()
        
        # Semantic search components
        self._index_manager = index_manager
        self._embedding_service = embedding_service
        self._domain_classifier = domain_classifier
        self._threshold_manager = threshold_manager
        self._query_normalizer = QueryNormalizer()
        self._intent_detector = RuleBasedIntentDetector()
        
        from src.core.circuit_breaker import CircuitBreaker
        self.embedding_breaker = CircuitBreaker(name="embedding_service", failure_threshold=5, recovery_timeout=30)
        self.compute_breaker = CircuitBreaker(name="compute_service", failure_threshold=5, recovery_timeout=60)
        
        # Semantic metrics
        self._semantic_metrics = {
            "semantic_hits": 0,
            "semantic_misses": 0,
            "exact_matches": 0,
            "embeddings_generated": 0,
        }
        
        self._initialized = False
    
    def set_index_manager(self, index_manager: 'UnifiedIndexManager') -> None:
        """Set the unified index manager (for late initialization)."""
        self._index_manager = index_manager
        # Also wire to L1Cache for similarity search delegation
        if self.l1_cache:
            self.l1_cache.set_index_manager(index_manager)
        logger.info("Index manager attached to CacheManager and L1Cache")
    
    def set_embedding_service(self, embedding_service: Any) -> None:
        """Set the embedding service (for late initialization)."""
        self._embedding_service = embedding_service
        logger.info("Embedding service attached to CacheManager")
    
    def set_domain_classifier(self, classifier: Any) -> None:
        """Set the domain classifier."""
        self._domain_classifier = classifier
    
    def set_threshold_manager(self, manager: Any) -> None:
        """Set the adaptive threshold manager."""
        self._threshold_manager = manager
    
    def initialize(self) -> bool:
        """Initialize all cache tiers.
        
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
            
            # L3 optional, initialize if enabled
            if self.config.enable_l3:
                try:
                    self.l3_cache = L3Cache(
                        db_manager=self._db_manager,
                        default_ttl_days=self.config.l3_ttl_days,
                        embedding_dimension=self.config.embedding_dimension,
                    )
                    if self.l3_cache.connect():
                        logger.info("L3 cache initialized (PostgreSQL)")
                    else:
                        logger.warning("L3 cache connection failed, continuing without L3")
                        self.l3_cache = None
                except Exception as e:
                    logger.warning(f"L3 cache initialization failed: {e}, continuing without L3")
                    self.l3_cache = None
            
            self._initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Cache manager initialization failed: {e}")
            return False
    
    def put(self, entry: CacheEntry, tenant_id: str = "default") -> bool:
        """Store entry in cache.
        
        Implements configured strategy (write-through/write-back/L1-only).
        For write-through, data is written to all available tiers.
        
        Args:
            entry: Cache entry
            tenant_id: Tenant ID for L3 cache
            
        Returns:
            True if successful
        """
        if not self._initialized:
            return False
        
        try:
            if self.config.strategy == CacheStrategy.WRITE_THROUGH:
                # Write to L1, L2, and L3
                l1_ok = self.l1_cache.put(entry)
                l2_ok = True
                l3_ok = True
                
                if self.l2_cache is not None:
                    l2_ok = self.l2_cache.put(entry)
                
                # Also write to L3 for persistence
                if self.l3_cache is not None:
                    try:
                        l3_ok = self.l3_cache.put(entry, tenant_id=tenant_id)
                    except Exception as e:
                        logger.warning(f"L3 write failed: {e}")
                        l3_ok = False
                
                return l1_ok and l2_ok
                
            elif self.config.strategy == CacheStrategy.WRITE_BACK:
                # Write to L1, sync L2/L3 asynchronously
                l1_ok = self.l1_cache.put(entry)
                
                # Non-blocking L2 write
                if self.l2_cache is not None:
                    try:
                        self.l2_cache.put(entry)
                    except Exception as e:
                        logger.warning(f"Async L2 write failed: {e}")
                
                # Non-blocking L3 write
                if self.l3_cache is not None:
                    try:
                        self.l3_cache.put(entry, tenant_id=tenant_id)
                    except Exception as e:
                        logger.warning(f"Async L3 write failed: {e}")
                
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
    
    def get(self, query_id: str, tenant_id: Optional[str] = None) -> Optional[Tuple[CacheEntry, str]]:
        """Retrieve entry from cache.
        
        Implements tiered lookup:
        1. Check L1 (in-memory) - <1ms
        2. If miss, check L2 (Redis) - 5-10ms
        3. If miss, check L3 (PostgreSQL) - 20-50ms
        4. Promote hits from lower tiers to higher tiers
        
        Args:
            query_id: Query ID
            tenant_id: Optional tenant ID for L3 queries
            
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
            
            # Check L3 if available (cold storage)
            if self.l3_cache is not None:
                entry = self.l3_cache.get(query_id, tenant_id=tenant_id)
                if entry is not None:
                    self.metrics.record_hit("L3")
                    logger.debug(f"L3 hit for {query_id}")
                    
                    # Promote to L1 and L2
                    if self.config.enable_l3_promotion:
                        self.l1_cache.put(entry)
                        self.metrics.l3_to_l1_promotions += 1
                        logger.debug(f"Promoted {query_id} from L3 to L1")
                        
                        if self.l2_cache is not None:
                            self.l2_cache.put(entry)
                            self.metrics.l3_to_l2_promotions += 1
                            logger.debug(f"Promoted {query_id} from L3 to L2")
                    
                    return (entry, "L3")
            
            # Miss
            self.metrics.record_miss()
            logger.debug(f"Cache miss for {query_id}")
            return None
            
        except Exception as e:
            logger.error(f"Get operation failed: {e}")
            self.metrics.record_miss()
            return None
    
    def delete(self, query_id: str, tenant_id: Optional[str] = None) -> bool:
        """Delete entry from all cache tiers.
        
        Args:
            query_id: Query ID
            tenant_id: Optional tenant ID for L3 deletion
            
        Returns:
            True if successful
        """
        try:
            l1_ok = self.l1_cache.delete(query_id)
            l2_ok = True
            l3_ok = True
            
            if self.l2_cache is not None:
                l2_ok = self.l2_cache.delete(query_id)
                self.publish_invalidation(query_id)
            
            if self.l3_cache is not None:
                l3_ok = self.l3_cache.delete(query_id, tenant_id=tenant_id)
            
            return l1_ok and l2_ok and l3_ok
            
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False
    
    def clear(self, tenant_id: Optional[str] = None) -> bool:
        """Clear all cache tiers.
        
        Args:
            tenant_id: If provided, only clear entries for this tenant
            
        Returns:
            True if successful
        """
        try:
            l1_ok = self.l1_cache.clear()
            l2_ok = True
            l3_ok = True
            
            if self.l2_cache is not None:
                l2_ok = self.l2_cache.clear()
                self.publish_invalidation("__FLUSHALL__")
            
            if self.l3_cache is not None:
                self.l3_cache.clear(tenant_id=tenant_id)
            
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
    
    def get_l3_stats(self) -> Dict[str, Any]:
        """Get L3 cache stats.
        
        Returns:
            L3 statistics
        """
        if self.l3_cache is None:
            return {}
        
        return self.l3_cache.get_stats()
    
    def get_combined_stats(self) -> Dict[str, Any]:
        """Get combined stats from all tiers.
        
        Returns:
            Combined statistics
        """
        return {
            "l1": self.get_l1_stats(),
            "l2": self.get_l2_stats(),
            "l3": self.get_l3_stats(),
            "tiered": {
                "total_requests": self.metrics.total_requests,
                "l1_hits": self.metrics.l1_hits,
                "l2_hits": self.metrics.l2_hits,
                "l3_hits": self.metrics.l3_hits,
                "misses": self.metrics.misses,
                "combined_hit_rate": self.metrics.get_combined_hit_rate(),
                "l1_to_l2_promotions": self.metrics.l1_to_l2_promotions,
                "l3_to_l1_promotions": self.metrics.l3_to_l1_promotions,
                "l3_to_l2_promotions": self.metrics.l3_to_l2_promotions,
            }
        }
    
    def get_metrics(self) -> TieredCacheMetrics:
        """Get manager metrics.
        
        Returns:
            Tiered cache metrics
        """
        return self.metrics
    
    def health_check(self) -> Dict[str, bool]:
        """Check health of all tiers.
        
        Returns:
            Health status dict
        """
        return {
            "l1": True,  # L1 is always in-memory
            "l2": self.l2_cache.health_check() if self.l2_cache else True,
            "l3": self.l3_cache.is_connected() if self.l3_cache else True,
        }
    
    def shutdown(self) -> None:
        """Shutdown cache manager.
        
        Cleans up resources and closes connections.
        """
        try:
            if self.l2_cache is not None:
                self.l2_cache.disconnect()
            
            if self.l3_cache is not None:
                self.l3_cache.disconnect()
            
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

    # =========================================================================
    # SEMANTIC SEARCH METHODS (Integration Fix)
    # =========================================================================
    
    def get_semantic(
        self,
        query_text: str,
        embedding: List[float],
        tenant_id: Optional[str] = None,
        domain: Optional[str] = None,
        threshold: Optional[float] = None,
    ) -> Optional[SemanticSearchResult]:
        """
        Search cache by semantic similarity.
        
        This is the primary method for semantic cache lookups. It searches
        the unified index for similar cached entries and returns the best match.
        
        Args:
            query_text: Original query text
            embedding: Query embedding vector (must match configured dimension)
            tenant_id: Tenant ID for isolation
            domain: Domain for threshold selection (auto-detected if None)
            threshold: Similarity threshold (uses domain default if None)
            
        Returns:
            SemanticSearchResult with matched entry and metadata, or None if no match
        """
        if not self._initialized:
            logger.warning("Cache manager not initialized")
            return None
        
        if self._index_manager is None:
            logger.warning("Index manager not available, falling back to exact match")
            # Fall back to exact key lookup
            result = self.get(f"{tenant_id}:{query_text}" if tenant_id else query_text)
            if result:
                return SemanticSearchResult(
                    entry=result[0],
                    similarity=1.0,
                    hit_source=result[1],
                    hit_reason=CacheHitReason.EXACT_MATCH,
                    is_exact_match=True,
                )
            return None
        
        start_time = time.time()
        
        # Auto-detect domain if not provided
        if domain is None and self._domain_classifier:
            try:
                domain = self._domain_classifier.classify(query_text)
            except Exception as e:
                logger.warning(f"Domain classification failed: {e}")
                domain = "general"
        domain = domain or "general"
        
        # Get adaptive threshold if not provided
        if threshold is None:
            if self._threshold_manager:
                try:
                    threshold = self._threshold_manager.get_threshold(domain)
                except Exception:
                    threshold = self._index_manager.get_threshold(domain)
            else:
                threshold = self._index_manager.get_threshold(domain)
        
        # Search unified index
        try:
            results = self._index_manager.search_by_text(
                query_text=query_text,
                embedding=embedding,
                k=1,
                threshold=threshold,
                domain=domain,
                tenant_id=tenant_id,
            )
            
            search_time = (time.time() - start_time) * 1000
            
            if results:
                item_id, similarity, index_entry, is_exact = results[0]
                
                # Get full cache entry
                cache_key = f"{tenant_id}:{item_id}" if tenant_id else item_id
                cache_result = self.get(cache_key)
                
                if cache_result:
                    entry, source = cache_result
                    self._semantic_metrics["semantic_hits"] += 1
                    if is_exact:
                        self._semantic_metrics["exact_matches"] += 1
                    
                    logger.debug(
                        f"Semantic hit: similarity={similarity:.3f}, "
                        f"threshold={threshold:.3f}, domain={domain}, "
                        f"time={search_time:.2f}ms"
                    )
                    
                    return SemanticSearchResult(
                        entry=entry,
                        similarity=similarity,
                        hit_source=source,
                        hit_reason=CacheHitReason.EXACT_MATCH if is_exact else CacheHitReason.SEMANTIC_MATCH,
                        is_exact_match=is_exact,
                        domain=domain,
                        threshold_used=threshold,
                    )
            
            # No match found
            self._semantic_metrics["semantic_misses"] += 1
            logger.debug(f"Semantic miss: threshold={threshold:.3f}, domain={domain}")
            return None
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            self._semantic_metrics["semantic_misses"] += 1
            return None
    
    async def get_semantic_async(
        self,
        query_text: str,
        tenant_id: Optional[str] = None,
        domain: Optional[str] = None,
        threshold: Optional[float] = None,
    ) -> Optional[SemanticSearchResult]:
        """
        Async version of get_semantic that generates embedding automatically.
        
        Args:
            query_text: Query text to search for
            tenant_id: Tenant ID for isolation
            domain: Domain for threshold selection
            threshold: Similarity threshold
            
        Returns:
            SemanticSearchResult or None
        """
        if self._embedding_service is None:
            logger.error("Embedding service not available for async semantic search")
            return None
        
        try:
            # Query normalization
            normalized_query = self._query_normalizer.normalize(query_text)
            
            # Generate embedding
            async def get_emb():
                return await self._embedding_service.embed_text(normalized_query)
            embedding_record = await self.embedding_breaker.call(get_emb)
            self._semantic_metrics["embeddings_generated"] += 1
            
            # Search with embedding
            return self.get_semantic(
                query_text=normalized_query,
                embedding=embedding_record.embedding,
                tenant_id=tenant_id,
                domain=domain,
                threshold=threshold,
            )
        except Exception as e:
            logger.error(f"Async semantic search failed: {e}")
            return None

    async def get_semantic_multi_async(
        self,
        query_text: str,
        tenant_id: Optional[str] = None,
        domain: Optional[str] = None,
        threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Decomposes query into multiple intents and searches for each.
        Returns a dict of sub_queries matched, syntesised response (if all hit), etc.
        """
        # Normalize
        normalized_query = self._query_normalizer.normalize(query_text)
        
        # Decompose
        multi_intent = self._intent_detector.decompose(normalized_query)
        
        results = {
            "original_query": query_text,
            "normalized_query": normalized_query,
            "sub_queries": [],
            "all_hit": True,
            "synthesized_response": None,
            "hit_ratio": 0.0
        }
        
        if len(multi_intent.sub_queries) <= 1:
            # Fall back to normal search
            res = await self.get_semantic_async(query_text, tenant_id, domain, threshold)
            if res and res.entry:
                results["sub_queries"].append({
                    "id": multi_intent.sub_queries[0].id if multi_intent.sub_queries else "sq_1",
                    "text": normalized_query,
                    "hit": True,
                    "response": res.entry.response
                })
                results["synthesized_response"] = res.entry.response
                results["hit_ratio"] = 1.0
            else:
                results["all_hit"] = False
            return results
            
        hits = 0
        responses = []
        for sq in multi_intent.sub_queries:
            sq_res = await self.get_semantic_async(sq.text, tenant_id, domain, threshold)
            hit = sq_res is not None and sq_res.entry is not None
            if hit:
                hits += 1
                responses.append(sq_res.entry.response)
                results["sub_queries"].append({
                    "id": sq.id,
                    "text": sq.text,
                    "hit": True,
                    "response": sq_res.entry.response
                })
            else:
                results["all_hit"] = False
                results["sub_queries"].append({
                    "id": sq.id,
                    "text": sq.text,
                    "hit": False,
                    "response": None
                })
                
        results["hit_ratio"] = hits / len(multi_intent.sub_queries)
        if results["all_hit"]:
            results["synthesized_response"] = self._intent_detector.synthesize(normalized_query, [str(r) for r in responses])
            
        return results
    
    def put_semantic(
        self,
        query_text: str,
        embedding: List[float],
        response: Any,
        tenant_id: Optional[str] = None,
        domain: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Store an entry with proper indexing for semantic search.
        
        This method stores the entry in both the cache tiers AND the
        unified similarity index, ensuring it can be found via semantic search.
        
        Args:
            query_text: Original query text
            embedding: Embedding vector for the query
            response: Response data to cache
            tenant_id: Tenant ID for isolation
            domain: Domain classification
            metadata: Additional metadata
            ttl_seconds: TTL override
            
        Returns:
            True if successfully stored
        """
        if not self._initialized:
            return False
        
        # Generate cache key
        import hashlib
        query_hash = hashlib.sha256(query_text.encode()).hexdigest()[:16]
        cache_key = f"{tenant_id}:{query_hash}" if tenant_id else query_hash
        
        # Create cache entry
        entry = CacheEntry(
            query_id=cache_key,
            query_text=query_text,
            embedding=embedding,
            response=response,
            metadata=metadata or {},
            domain=domain,
        )
        
        # Calculate memory estimate
        entry.calculate_memory(len(embedding))
        
        # Store in cache tiers
        success = self.put(entry)
        
        if success and self._index_manager:
            # Also index in unified index manager
            # Use query_hash as item_id since index_manager adds tenant prefix
            try:
                self._index_manager.add(
                    item_id=query_hash,
                    embedding=embedding,
                    query_text=query_text,
                    tenant_id=tenant_id,
                    domain=domain,
                    metadata=metadata,
                )
                logger.debug(f"Indexed {query_hash} in unified index")
            except Exception as e:
                logger.error(f"Failed to index {query_hash}: {e}")
                # Cache storage succeeded, index failed - still return True
        
        return success
    
    async def put_semantic_async(
        self,
        query_text: str,
        response: Any,
        tenant_id: Optional[str] = None,
        domain: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Async version that generates embedding automatically before storing.
        
        Args:
            query_text: Query text
            response: Response to cache
            tenant_id: Tenant ID
            domain: Domain (auto-detected if None)
            metadata: Additional metadata
            
        Returns:
            True if successful
        """
        if self._embedding_service is None:
            logger.error("Embedding service not available")
            return False
        
        try:
            # Query normalization
            normalized_query = self._query_normalizer.normalize(query_text)

            # Auto-detect domain
            if domain is None and self._domain_classifier:
                domain = self._domain_classifier.classify(normalized_query)
            domain = domain or "general"
            
            # Generate embedding
            async def get_emb():
                return await self._embedding_service.embed_text(normalized_query)
            embedding_record = await self.embedding_breaker.call(get_emb)
            self._semantic_metrics["embeddings_generated"] += 1
            
            # Store with embedding
            return self.put_semantic(
                query_text=normalized_query,
                embedding=embedding_record.embedding,
                response=response,
                tenant_id=tenant_id,
                domain=domain,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Async put failed: {e}")
            return False
    
    async def get_or_compute(
        self,
        query_text: str,
        compute_fn: Callable[[str], Awaitable[Any]],
        tenant_id: Optional[str] = None,
        domain: Optional[str] = None,
        threshold: Optional[float] = None,
        cache_result: bool = True,
        ttl_seconds: Optional[int] = None,
        stale_multiplier: float = 2.0,
    ) -> Tuple[Any, bool, float]:
        """
        Get cached response or compute and cache if not found.
        
        This implements the canonical semantic cache pattern:
        1. Generate embedding for query
        2. Search for similar cached responses
        3. If found, return cached response
        4. If not found, call compute_fn and cache the result
        
        Args:
            query_text: Query text
            compute_fn: Async function to compute response on cache miss
            tenant_id: Tenant ID for isolation
            domain: Domain for threshold selection
            threshold: Similarity threshold
            cache_result: Whether to cache computed results
            
        Returns:
            Tuple of (response, was_cache_hit, similarity_score)
        """
        start_time = time.time()
        
        # Try semantic search first
        result = await self.get_semantic_async(
            query_text=query_text,
            tenant_id=tenant_id,
            domain=domain,
            threshold=threshold,
        )
        
        import asyncio
        
        if result and result.entry:
            entry = result.entry
            
            # Check SWR thresholds
            if not entry.is_expired(ttl_seconds):
                # Fresh Cache hit
                logger.info(
                    f"Cache hit: similarity={result.similarity:.3f}, "
                    f"source={result.hit_source}"
                )
                return (entry.response, True, result.similarity)
            else:
                if entry.is_stale(ttl_seconds, stale_multiplier):
                    logger.info("Stale Cache Hit - triggering background refresh")
                    if not entry.is_refreshing:
                        entry.is_refreshing = True
                        
                        async def background_refresh():
                            try:
                                new_response = await compute_fn(query_text)
                                if cache_result:
                                    await self.put_semantic_async(
                                        query_text=query_text,
                                        response=new_response,
                                        tenant_id=tenant_id,
                                        domain=domain,
                                        metadata={"compute_time_ms": (time.time() - start_time) * 1000},
                                    )
                            except Exception as e:
                                logger.error(f"Background refresh failed: {e}")
                            finally:
                                entry.is_refreshing = False
                                
                        asyncio.create_task(background_refresh())
                    
                    return (entry.response, True, result.similarity)
                else:
                    # Too old! Falls through to compute
                    pass
        
        # Cache miss - compute response
        logger.info("Cache miss, computing response...")
        
        try:
            async def run_compute():
                return await compute_fn(query_text)
            response = await self.compute_breaker.call(run_compute)
            
            # Cache the result
            if cache_result:
                await self.put_semantic_async(
                    query_text=query_text,
                    response=response,
                    tenant_id=tenant_id,
                    domain=domain,
                    metadata={"compute_time_ms": (time.time() - start_time) * 1000},
                )
            
            return (response, False, 0.0)
            
        except Exception as e:
            logger.error(f"Compute function failed: {e}")
            raise
    
    def delete_semantic(self, query_text: str, tenant_id: Optional[str] = None) -> bool:
        """
        Delete an entry from both cache and index.
        
        Args:
            query_text: Query text to delete
            tenant_id: Tenant ID
            
        Returns:
            True if deleted
        """
        import hashlib
        query_hash = hashlib.sha256(query_text.encode()).hexdigest()[:16]
        cache_key = f"{tenant_id}:{query_hash}" if tenant_id else query_hash
        
        # Delete from cache
        cache_deleted = self.delete(cache_key)
        
        # Delete from index
        index_deleted = False
        if self._index_manager:
            index_deleted = self._index_manager.delete(cache_key, tenant_id)
        
        return cache_deleted or index_deleted
    
    def get_semantic_stats(self) -> Dict[str, Any]:
        """Get semantic search statistics."""
        total = self._semantic_metrics["semantic_hits"] + self._semantic_metrics["semantic_misses"]
        hit_rate = self._semantic_metrics["semantic_hits"] / total if total > 0 else 0.0
        
        stats = {
            **self._semantic_metrics,
            "semantic_hit_rate": hit_rate,
            "total_semantic_requests": total,
        }
        
        if self._index_manager:
            stats["index_stats"] = self._index_manager.get_stats()
        
        return stats



"""
Cache Layer Base Abstractions

Defines interfaces and data structures for semantic caching with pluggable
eviction policies and comprehensive metrics tracking.

Features:
- Abstract CacheEntry and CachePolicy interfaces
- Domain-aware cache configuration
- Comprehensive cache metrics and statistics
- Support for inline and asynchronous operations
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import time
from datetime import datetime, timedelta


class EvictionPolicy(str, Enum):
    """Available eviction policies for cache overflow."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    TTL = "ttl"  # Time To Live
    ADAPTIVE = "adaptive"  # Adaptive (combines LRU + LFU)
    COST_AWARE = "cost_aware"  # Cost-aware eviction based on compute/latency


class CacheHitReason(str, Enum):
    """Reasons for cache hit detection."""
    EXACT_MATCH = "exact_match"  # Exact text match with deduplication
    SEMANTIC_MATCH = "semantic_match"  # Semantic similarity above threshold
    CACHED_EMBEDDING = "cached_embedding"  # Embedding cached, similarity cached
    HYBRID_MATCH = "hybrid_match"  # Combined exact + semantic match


@dataclass
class CacheConfig:
    """Configuration for L1 cache layer."""
    
    max_size: int = 1000  # Maximum number of entries
    embedding_dimension: int = 384  # Dimension of embeddings
    eviction_policy: EvictionPolicy = EvictionPolicy.ADAPTIVE
    ttl_seconds: Optional[int] = None  # Time-to-live in seconds (None = unlimited)
    
    # Memory limits
    max_memory_mb: float = 512.0  # Maximum memory footprint
    
    # Hit rate optimization
    enable_deduplication: bool = True  # Enable query text deduplication
    enable_exact_match: bool = True  # Enable fast exact text matching
    
    # Metrics
    track_detailed_metrics: bool = True
    
    def __post_init__(self):
        """Validate configuration."""
        if self.max_size <= 0:
            raise ValueError("max_size must be positive")
        if self.embedding_dimension <= 0:
            raise ValueError("embedding_dimension must be positive")
        if self.max_memory_mb <= 0:
            raise ValueError("max_memory_mb must be positive")


@dataclass
class CacheEntry:
    """Single entry in the cache."""
    
    query_id: str  # Unique query identifier
    query_text: str  # Original query text
    embedding: List[float]  # Query embedding (384-dim typical)
    response: Any  # Cached response (generic object)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    domain: str = "general"  # Domain classification
    
    # Timing
    created_at: float = field(default_factory=time.time)  # Unix timestamp
    last_accessed_at: float = field(default_factory=time.time)  # Unix timestamp
    
    # Access tracking
    access_count: int = 0  # Number of times accessed (for LFU)
    
    # Memory estimate (in bytes)
    memory_estimate: float = 0.0
    
    def is_expired(self, ttl_seconds: Optional[int]) -> bool:
        """Check if entry has expired based on TTL."""
        if ttl_seconds is None:
            return False
        age = time.time() - self.created_at
        return age > ttl_seconds
    
    def record_access(self) -> None:
        """Record that entry was accessed."""
        self.last_accessed_at = time.time()
        self.access_count += 1
    
    def calculate_memory(self, embedding_dimension: int) -> float:
        """
        Estimate memory footprint in bytes.
        
        Includes:
        - Embedding vector (float32 = 4 bytes per dimension)
        - Query text (1 byte per character)
        - Response (estimate based on pickle size)
        - Metadata overhead
        """
        # Embedding: 4 bytes * dimension
        embedding_size = embedding_dimension * 4
        
        # Query text
        text_size = len(self.query_text.encode('utf-8'))
        
        # Response (rough estimate - assume JSON serializable)
        response_size = 100  # Minimum overhead
        if self.response:
            try:
                import json
                response_size = len(json.dumps(self.response).encode('utf-8'))
            except (TypeError, ValueError):
                response_size = 200  # Fallback
        
        # Metadata
        metadata_size = 50 + len(self.metadata) * 30
        
        # Object overhead
        overhead = 100
        
        total = embedding_size + text_size + response_size + metadata_size + overhead
        self.memory_estimate = float(total)
        return total


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    
    total_requests: int = 0  # Total cache lookups
    cache_hits: int = 0  # Number of hits
    cache_misses: int = 0  # Number of misses
    
    # Hit breakdown
    exact_match_hits: int = 0  # Hits from exact text matching
    semantic_match_hits: int = 0  # Hits from semantic similarity
    hybrid_match_hits: int = 0  # Hits from combined matching
    
    # Eviction tracking
    evictions_lru: int = 0  # LRU evictions
    evictions_lfu: int = 0  # LFU evictions
    evictions_ttl: int = 0  # TTL evictions
    evictions_memory: int = 0  # Memory overflow evictions
    
    # Performance
    total_latency_ms: float = 0.0  # Cumulative lookup time
    total_response_time_ms: float = 0.0  # Cumulative response time
    
    # Deduplication
    duplicate_queries: int = 0  # Queries detected as duplicates
    
    # Memory
    current_memory_mb: float = 0.0
    peak_memory_mb: float = 0.0
    current_entries: int = 0
    
    # Timestamps
    created_at: float = field(default_factory=time.time)
    last_reset: float = field(default_factory=time.time)
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests
    
    @property
    def avg_lookup_time_ms(self) -> float:
        """Calculate average lookup time."""
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests
    
    @property
    def avg_response_time_ms(self) -> float:
        """Calculate average response time."""
        if self.cache_hits == 0:
            return 0.0
        return self.total_response_time_ms / self.cache_hits
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        uptime_seconds = time.time() - self.created_at
        return {
            "hit_rate": f"{self.hit_rate:.1%}",
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_breakdown": {
                "exact_match": self.exact_match_hits,
                "semantic_match": self.semantic_match_hits,
                "hybrid_match": self.hybrid_match_hits,
            },
            "evictions": {
                "lru": self.evictions_lru,
                "lfu": self.evictions_lfu,
                "ttl": self.evictions_ttl,
                "memory": self.evictions_memory,
            },
            "performance": {
                "avg_lookup_ms": f"{self.avg_lookup_time_ms:.2f}",
                "avg_response_ms": f"{self.avg_response_time_ms:.2f}",
            },
            "memory": {
                "current_mb": f"{self.current_memory_mb:.2f}",
                "peak_mb": f"{self.peak_memory_mb:.2f}",
                "current_entries": self.current_entries,
            },
            "deduplication": {
                "duplicate_queries": self.duplicate_queries,
            },
            "uptime_seconds": f"{uptime_seconds:.1f}",
        }


class EvictionPolicyInterface(ABC):
    """Abstract base class for eviction policies."""
    
    @abstractmethod
    def select_victim(self, entries: Dict[str, CacheEntry], timestamp: float) -> Optional[str]:
        """
        Select an entry to evict.
        
        Args:
            entries: Dictionary of cache entries (id -> entry)
            timestamp: Current timestamp
            
        Returns:
            Query ID of entry to evict, or None if none should be evicted
        """
        pass
    
    @abstractmethod
    def update_on_access(self, entry: CacheEntry, timestamp: float) -> None:
        """
        Update policy state when entry is accessed.
        
        Args:
            entry: Accessed cache entry
            timestamp: Access timestamp
        """
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """Reset policy state."""
        pass


class CacheBackendInterface(ABC):
    """Abstract interface for cache implementations."""
    
    @abstractmethod
    def put(self, entry: CacheEntry) -> bool:
        """
        Store entry in cache.
        
        Returns:
            True if stored successfully, False if rejected
        """
        pass
    
    @abstractmethod
    def get(self, query_id: str) -> Optional[CacheEntry]:
        """
        Retrieve entry from cache by ID.
        
        Returns:
            CacheEntry if found, None otherwise
        """
        pass
    
    @abstractmethod
    def search_similar(
        self,
        embedding: List[float],
        k: int = 5,
        threshold: float = 0.85,
    ) -> List[Tuple[str, float]]:
        """
        Search for semantically similar entries.
        
        Args:
            embedding: Query embedding
            k: Number of results
            threshold: Minimum similarity
            
        Returns:
            List of (query_id, similarity) tuples
        """
        pass
    
    @abstractmethod
    def delete(self, query_id: str) -> bool:
        """
        Remove entry from cache.
        
        Returns:
            True if removed, False if not found
        """
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all entries from cache."""
        pass
    
    @abstractmethod
    def size(self) -> int:
        """Get number of entries in cache."""
        pass
    
    @abstractmethod
    def memory_usage_mb(self) -> float:
        """Get estimated memory usage in MB."""
        pass
    
    @abstractmethod
    def get_metrics(self) -> CacheMetrics:
        """Get cache performance metrics."""
        pass
    
    @abstractmethod
    def reset_metrics(self) -> None:
        """Reset metrics counters."""
        pass

"""
Cache Eviction Policies

Implements various memory eviction strategies for cache overflow management:
- LRU (Least Recently Used): Evict least recently accessed entries
- LFU (Least Frequently Used): Evict least frequently accessed entries
- TTL (Time To Live): Evict expired entries based on age
- FIFO (First In First Out): Evict oldest entries
- Adaptive: Combines LRU and LFU for balanced behavior
"""

import heapq
from typing import Dict, Optional
from collections import defaultdict

from src.cache.base import EvictionPolicyInterface, CacheEntry


class LRUEvictionPolicy(EvictionPolicyInterface):
    """
    Least Recently Used (LRU) eviction policy.
    
    Evicts the entry that was accessed longest time ago.
    Good for temporal locality in queries.
    """
    
    def __init__(self):
        """Initialize LRU policy."""
        self.access_times: Dict[str, float] = {}
    
    def select_victim(self, entries: Dict[str, CacheEntry], timestamp: float) -> Optional[str]:
        """
        Select entry with earliest last_accessed_at.
        
        Args:
            entries: Dictionary of cache entries
            timestamp: Current timestamp
            
        Returns:
            Query ID of least recently used entry
        """
        if not entries:
            return None
        
        # Find entry with minimum last_accessed_at
        lru_id = min(entries.keys(), key=lambda id: entries[id].last_accessed_at)
        return lru_id
    
    def update_on_access(self, entry: CacheEntry, timestamp: float) -> None:
        """Record access time for LRU tracking."""
        self.access_times[entry.query_id] = timestamp
    
    def reset(self) -> None:
        """Clear access time tracking."""
        self.access_times.clear()


class LFUEvictionPolicy(EvictionPolicyInterface):
    """
    Least Frequently Used (LFU) eviction policy.
    
    Evicts the entry with the fewest accesses.
    Good for distinguishing frequently-used queries.
    """
    
    def __init__(self):
        """Initialize LFU policy."""
        self.frequency_map: Dict[str, int] = defaultdict(int)
    
    def select_victim(self, entries: Dict[str, CacheEntry], timestamp: float) -> Optional[str]:
        """
        Select entry with lowest access_count and earliest timestamp to break ties.
        
        Args:
            entries: Dictionary of cache entries
            timestamp: Current timestamp
            
        Returns:
            Query ID of least frequently used entry
        """
        if not entries:
            return None
        
        # Sort by access count, then by creation time for ties
        lfu_id = min(
            entries.keys(),
            key=lambda id: (entries[id].access_count, entries[id].created_at)
        )
        return lfu_id
    
    def update_on_access(self, entry: CacheEntry, timestamp: float) -> None:
        """Increment frequency counter for entry."""
        self.frequency_map[entry.query_id] += 1
    
    def reset(self) -> None:
        """Clear frequency tracking."""
        self.frequency_map.clear()


class FIFOEvictionPolicy(EvictionPolicyInterface):
    """
    First In First Out (FIFO) eviction policy.
    
    Evicts the oldest entry by creation time.
    Simple, cache-aware policy with predictable behavior.
    """
    
    def select_victim(self, entries: Dict[str, CacheEntry], timestamp: float) -> Optional[str]:
        """
        Select entry with earliest creation time.
        
        Args:
            entries: Dictionary of cache entries
            timestamp: Current timestamp
            
        Returns:
            Query ID of oldest entry
        """
        if not entries:
            return None
        
        # Find entry with minimum created_at
        oldest_id = min(entries.keys(), key=lambda id: entries[id].created_at)
        return oldest_id
    
    def update_on_access(self, entry: CacheEntry, timestamp: float) -> None:
        """FIFO doesn't track access patterns."""
        pass
    
    def reset(self) -> None:
        """No state to reset for FIFO."""
        pass


class TTLEvictionPolicy(EvictionPolicyInterface):
    """
    Time To Live (TTL) eviction policy.
    
    Evicts entries that exceed maximum age, or least recently used if no TTL entries exist.
    Useful for time-sensitive data with bounded freshness requirements.
    """
    
    def __init__(self, ttl_seconds: Optional[int] = None):
        """
        Initialize TTL policy.
        
        Args:
            ttl_seconds: Maximum age for entries in seconds
        """
        self.ttl_seconds = ttl_seconds
    
    def select_victim(self, entries: Dict[str, CacheEntry], timestamp: float) -> Optional[str]:
        """
        Select oldest expired entry, or least recently used if none expired.
        
        Args:
            entries: Dictionary of cache entries
            timestamp: Current timestamp
            
        Returns:
            Query ID to evict
        """
        if not entries:
            return None
        
        # First, look for expired entries
        for query_id, entry in entries.items():
            if self.ttl_seconds and entry.is_expired(self.ttl_seconds):
                return query_id
        
        # If no expired entries, fall back to LRU
        lru_id = min(entries.keys(), key=lambda id: entries[id].last_accessed_at)
        return lru_id
    
    def update_on_access(self, entry: CacheEntry, timestamp: float) -> None:
        """TTL doesn't need to track access patterns separately."""
        pass
    
    def reset(self) -> None:
        """No state to reset for TTL."""
        pass


class AdaptiveEvictionPolicy(EvictionPolicyInterface):
    """
    Adaptive eviction policy combining LRU and LFU.
    
    Uses a weighted score: w * LRU_rank + (1-w) * LFU_rank
    Provides balanced behavior considering both temporal locality and frequency.
    """
    
    def __init__(self, lru_weight: float = 0.6, lfu_weight: float = 0.4):
        """
        Initialize adaptive policy.
        
        Args:
            lru_weight: Weight for LRU component (0-1)
            lfu_weight: Weight for LFU component (0-1)
        """
        if not (0 <= lru_weight <= 1):
            raise ValueError("lru_weight must be between 0 and 1")
        
        self.lru_weight = lru_weight
        self.lfu_weight = lfu_weight
        
        self.lru_policy = LRUEvictionPolicy()
        self.lfu_policy = LFUEvictionPolicy()
    
    def select_victim(self, entries: Dict[str, CacheEntry], timestamp: float) -> Optional[str]:
        """
        Compute adaptive score for each entry and evict lowest scorer.
        
        Score = w_lru * (1 - last_accessed_rank) + w_lfu * (1 - frequency_rank)
        """
        if not entries:
            return None
        
        entry_ids = list(entries.keys())
        
        # Compute LRU ranks (0 = most recent)
        sorted_by_accessed = sorted(
            entry_ids,
            key=lambda id: entries[id].last_accessed_at
        )
        lru_ranks = {id: i / len(entry_ids) for i, id in enumerate(sorted_by_accessed)}
        
        # Compute LFU ranks (0 = most frequent)
        sorted_by_freq = sorted(
            entry_ids,
            key=lambda id: entries[id].access_count
        )
        lfu_ranks = {id: i / len(entry_ids) for i, id in enumerate(sorted_by_freq)}
        
        # Compute adaptive scores (lower is worse, should be evicted first)
        min_score = float('inf')
        victim_id = None
        
        for query_id in entry_ids:
            # Invert ranks so higher recency/frequency = higher score
            lru_score = 1 - lru_ranks[query_id]
            lfu_score = 1 - lfu_ranks[query_id]
            
            combined_score = (self.lru_weight * lru_score + self.lfu_weight * lfu_score)
            
            if combined_score < min_score:
                min_score = combined_score
                victim_id = query_id
        
        return victim_id
    
    def update_on_access(self, entry: CacheEntry, timestamp: float) -> None:
        """Update both LRU and LFU policies."""
        self.lru_policy.update_on_access(entry, timestamp)
        self.lfu_policy.update_on_access(entry, timestamp)
    
    def reset(self) -> None:
        """Reset both policies."""
        self.lru_policy.reset()
        self.lfu_policy.reset()


def create_eviction_policy(policy_name: str, **kwargs) -> EvictionPolicyInterface:
    """
    Factory function to create eviction policy by name.
    
    Args:
        policy_name: Name of policy ("lru", "lfu", "fifo", "ttl", "adaptive")
        **kwargs: Policy-specific arguments
        
    Returns:
        EvictionPolicyInterface instance
        
    Raises:
        ValueError: If policy_name is unknown
    """
    policy_name = policy_name.lower()
    
    if policy_name == "lru":
        return LRUEvictionPolicy()
    elif policy_name == "lfu":
        return LFUEvictionPolicy()
    elif policy_name == "fifo":
        return FIFOEvictionPolicy()
    elif policy_name == "ttl":
        ttl_seconds = kwargs.get("ttl_seconds")
        return TTLEvictionPolicy(ttl_seconds=ttl_seconds)
    elif policy_name == "adaptive":
        lru_weight = kwargs.get("lru_weight", 0.6)
        lfu_weight = kwargs.get("lfu_weight", 0.4)
        return AdaptiveEvictionPolicy(lru_weight=lru_weight, lfu_weight=lfu_weight)
    elif policy_name == "cost_aware":
        from src.ml.cost_aware_eviction import CostAwareEvictionPolicy
        # Mapping the ML class to the interface expected by L1Cache
        class AdaptedCostPolicy(EvictionPolicyInterface):
            def __init__(self):
                self.policy = CostAwareEvictionPolicy()
            def select_victim(self, entries, timestamp):
                victims = self.policy.evict(entries, 1)
                return victims[0] if victims else None
            def update_on_access(self, entry, timestamp): pass
            def reset(self): pass
        return AdaptedCostPolicy()
    else:
        raise ValueError(f"Unknown eviction policy: {policy_name}")

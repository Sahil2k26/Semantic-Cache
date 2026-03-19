"""
Cost-Aware Eviction Policy (Phase 4.4)
"""
import time
from typing import Dict, List
from src.cache.base import CacheEntry

class CostAwareEvictionPolicy:
    """
    Evicts items based on a heuristic combining cost to compute and recency.
    Highly expensive queries to generate (e.g. LLM API calls) stay longer.
    """
    def calculate_score(self, entry: CacheEntry) -> float:
        """
        Calculate retention score. Lower score = more likely to be evicted.
        """
        compute_cost = entry.metadata.get("compute_cost_ms", 100) if entry.metadata else 100
        time_since_access = max(1.0, time.time() - entry.last_accessed_at)
        
        w_cost = 0.5
        w_freq = 0.3
        w_age = 0.2
        
        score = (w_cost * compute_cost) + (w_freq * entry.access_count * 100) - (w_age * time_since_access)
        return score

    def evict(self, current_entries: Dict[str, CacheEntry], num_to_evict: int = 1) -> List[str]:
        """
        Returns keys to evict based on lowest scores.
        """
        if not current_entries:
            return []
            
        scored_items = [
            (key, self.calculate_score(entry))
            for key, entry in current_entries.items()
        ]
        
        # Sort by score ascending (lowest score gets evicted first)
        scored_items.sort(key=lambda x: x[1])
        
        return [key for key, _ in scored_items[:num_to_evict]]

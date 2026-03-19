"""
Adaptive Thresholds module (Phase 4.2)

Adjusts semantic search thresholds dynamically based on query domain.
"""

class AdaptiveThresholdManager:
    def __init__(self):
        self.domain_thresholds = {
            "coding": 0.85,    # High precision required for code
            "finance": 0.85,   # High precision required
            "healthcare": 0.80, # Moderate precision
            "legal": 0.90,     # Very high precision
            "general": 0.70    # Default threshold
        }
        
    def get_threshold(self, domain: str) -> float:
        """Returns the optimal semantic similarity threshold for a domain."""
        return self.domain_thresholds.get(domain, 0.70)

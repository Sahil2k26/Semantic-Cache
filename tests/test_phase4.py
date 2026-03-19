import unittest
import time
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ml.domain_classifier import KeyWordDomainClassifier
from src.ml.adaptive_thresholds import AdaptiveThresholdManager
from src.ml.cost_aware_eviction import CostAwareEvictionPolicy
from src.cache.base import CacheEntry

class TestPhase4Intelligence(unittest.TestCase):
    def setUp(self):
        self.classifier = KeyWordDomainClassifier()
        self.threshold_manager = AdaptiveThresholdManager()
        self.eviction_policy = CostAwareEvictionPolicy()

    def test_domain_classification(self):
        self.assertEqual(self.classifier.classify("How to fix a python bug?"), "coding")
        self.assertEqual(self.classifier.classify("What is the stock price of Apple?"), "finance")
        self.assertEqual(self.classifier.classify("Symptoms of flu"), "healthcare")
        self.assertEqual(self.classifier.classify("Weather in London"), "general")

    def test_adaptive_thresholds(self):
        self.assertEqual(self.threshold_manager.get_threshold("coding"), 0.85)
        self.assertEqual(self.threshold_manager.get_threshold("legal"), 0.90)
        self.assertEqual(self.threshold_manager.get_threshold("unknown"), 0.70)

    def test_cost_aware_eviction(self):
        # Create some dummy entries with different costs
        entry_low_cost = CacheEntry(
            query_id="low", query_text="low", embedding=[0.1]*384, response="low",
            metadata={"compute_cost_ms": 10}
        )
        entry_high_cost = CacheEntry(
            query_id="high", query_text="high", embedding=[0.1]*384, response="high",
            metadata={"compute_cost_ms": 5000}
        )
        
        # Set same access count and recency
        now = time.time()
        entry_low_cost.last_accessed_at = now
        entry_high_cost.last_accessed_at = now
        
        score_low = self.eviction_policy.calculate_score(entry_low_cost)
        score_high = self.eviction_policy.calculate_score(entry_high_cost)
        
        # Higher cost should result in higher score (retained longer)
        self.assertGreater(score_high, score_low)
        
        # Test eviction selection
        entries = {"low": entry_low_cost, "high": entry_high_cost}
        victims = self.eviction_policy.evict(entries, 1)
        self.assertEqual(victims[0], "low")

if __name__ == "__main__":
    unittest.main()

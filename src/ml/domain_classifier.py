"""
Domain Classifier module (Phase 4.1)

Predicts the domain of an incoming query to route it to domain-specific
cache thresholds and policies.
"""

from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class KeyWordDomainClassifier:
    """
    A lightweight, regex/keyword-based domain classifier.
    Can be swapped seamlessly with an ML-based zero-shot classifier 
    when compute resources allow.
    """
    def __init__(self):
        self.domain_keywords = {
            "coding": ["python", "javascript", "code", "function", "error", "bug", "git", "api", "database"],
            "finance": ["stock", "market", "price", "investment", "bond", "crypto", "dividend", "tax"],
            "healthcare": ["symptom", "disease", "doctor", "hospital", "medication", "pain", "virus"],
            "legal": ["law", "lawyer", "sue", "court", "justice", "contract", "agreement", "rights"],
        }
        
    def classify(self, query: str) -> str:
        """
        Classify the query into a domain based on term frequency.
        
        Args:
            query: The incoming query text
            
        Returns:
            A domain string (e.g., 'coding') or 'general'
        """
        query_lower = query.lower()
        best_domain = "general"
        max_matches = 0
        
        for domain, keywords in self.domain_keywords.items():
            matches = sum(1 for kw in keywords if kw in query_lower)
            if matches > max_matches:
                max_matches = matches
                best_domain = domain
                
        return best_domain

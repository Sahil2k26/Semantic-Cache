import pytest
from src.ml.query_parser import QueryNormalizer, RuleBasedIntentDetector

def test_query_normalizer():
    qn = QueryNormalizer()
    
    # Normal definitions
    assert qn.normalize("what is python") == "Explain python"
    assert qn.normalize("what is an apple") == "Explain apple"
    assert qn.normalize("how to bake a cake?") == "How to bake a cake"
    assert qn.normalize("python vs java") == "Compare python and java"
    assert qn.normalize("who is Albert Einstein") == "Fact lookup albert einstein"

def test_rule_based_intent_detector():
    detector = RuleBasedIntentDetector()
    
    # Simple decompose
    res = detector.decompose("What is Python, and how to use it")
    assert len(res.sub_queries) == 2
    assert res.sub_queries[0].text == "What is Python"
    assert res.sub_queries[1].text == "how to use it"
    
    # Complex decompose
    res2 = detector.decompose("Compare Python and Java, and explain which is better for web development")
    assert len(res2.sub_queries) == 2
    assert "Compare Python and Java" in res2.sub_queries[0].text

    # Synthesize
    syn = detector.synthesize("test", ["Answer 1", "Answer 2"])
    assert "1. Answer 1" in syn
    assert "2. Answer 2" in syn

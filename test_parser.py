import sys
import os

# Add project root to python path to avoid ModuleNotFoundError
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.ml.query_parser import QueryNormalizer, RuleBasedIntentDetector, IntentType

print("Testing QueryNormalizer...")
qn = QueryNormalizer()
n1 = qn.normalize("what is python")
assert n1 == "Explain python", f"Got: {n1}"
n2 = qn.normalize("what is a python")
assert n2 == "Explain python", f"Got: {n2}"
n3 = qn.normalize("how to bake a cake?")
assert n3 == "How to bake a cake", f"Got: {n3}"
n4 = qn.normalize("python vs java")
assert n4 == "Compare python and java", f"Got: {n4}"
n5 = qn.normalize("who is Albert Einstein")
assert n5 == "Fact lookup albert einstein", f"Got: {n5}"

print("QueryNormalizer OK!")

print("Testing RuleBasedIntentDetector...")
id = RuleBasedIntentDetector()
res = id.decompose("What is Python, and how to use it")
print("Decomposed to:", len(res.sub_queries), "subqueries")
assert len(res.sub_queries) == 2, f"Got {len(res.sub_queries)}"
assert res.sub_queries[0].text == "What is Python"
assert res.sub_queries[1].text == "how to use it"

res2 = id.decompose("Compare Python and Java, and explain which is better for web development")
assert len(res2.sub_queries) == 2, f"Got {len(res2.sub_queries)}"
assert "Compare Python and Java" in res2.sub_queries[0].text

print("RuleBasedIntentDetector OK!")

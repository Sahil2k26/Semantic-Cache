#!/usr/bin/env python
"""Test Phase 2.2 Search API endpoints."""

import requests
import json
import time

BASE_URL = "http://localhost:8001"
TEST_USER_ID = "test_user_123"
TEST_TENANT_ID = "tenant_001"

def get_auth_token(user_id: str = TEST_USER_ID, tenant_id: str = TEST_TENANT_ID, role: str = "user") -> str:
    """Generate auth token for testing."""
    response = requests.get(
        f"{BASE_URL}/token",
        params={
            "user_id": user_id,
            "tenant_id": tenant_id,
            "role": role
        }
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to get token: {response.text}")
        return None
    
    data = response.json()
    return data.get("access_token")

def test_similarity_embedding(token: str) -> bool:
    print("\n🧪 Testing Similarity Embedding Endpoint")
    print("=" * 50)
    
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "query": "What is machine learning?",
        "top_k": 5,
        "threshold": 0.5
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/similarity/embedding",
        params=params,
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Similarity Embedding Successful")
        print(f"   Query: {data.get('text')}")
        print(f"   Dim: {data.get('embedding_dimension')}")
        return True
    else:
        print(f"❌ Similarity Embedding Failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

def test_search(token: str) -> bool:
    print("\n🧪 Testing Semantic Search Endpoint")
    print("=" * 50)
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "query": "What is artificial intelligence?",
        "top_k": 5,
        "threshold": 0.5,
        "metric": "cosine"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/search",
        json=payload,
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Semantic Search Successful")
        print(f"   Query: {data.get('query')}")
        print(f"   Results Count: {data.get('count')}")
        return True
    else:
        print(f"❌ Semantic Search Failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

def main():
    print("\n" + "="*60)
    print("Phase 2 Search API Integration Tests")
    print("="*60)
    
    token = get_auth_token()
    if not token:
        print("❌ Failed to get token, cannot proceed")
        return
        
    results = []
    results.append(("Similarity Embedding", test_similarity_embedding(token)))
    results.append(("Semantic Search", test_search(token)))
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print("\n" + "="*60)
    print(f"Total: {passed}/{total} tests passed")

if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Test Phase 2 Cache API endpoints with Phase 1 cache manager integration."""

import requests
import json
import time
from typing import Dict, Any

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


def test_health():
    """Test health endpoint."""
    print("\n🧪 Testing Health Endpoint")
    print("=" * 50)
    
    response = requests.get(f"{BASE_URL}/health")
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Health Check Passed")
        print(f"   Status: {data.get('status')}")
        print(f"   Cache Level: {data.get('cache_level')}")
        print(f"   Redis: {data.get('redis')}")
        print(f"   Postgres: {data.get('postgres')}")
        return True
    else:
        print(f"❌ Health Check Failed: {response.status_code}")
        return False


def test_cache_put(token: str) -> bool:
    """Test cache PUT operation."""
    print("\n🧪 Testing Cache PUT Operation")
    print("=" * 50)
    
    test_key = "test_query_1"
    test_value = {"result": "sample cached response", "timestamp": int(time.time())}
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.put(
        f"{BASE_URL}/api/v1/cache/{test_key}",
        json={"value": test_value},
        headers=headers
    )
    
    if response.status_code == 201:
        data = response.json()
        print("✅ Cache PUT Successful")
        print(f"   Key: {data.get('key')}")
        print(f"   Cached: {data.get('cached')}")
        print(f"   Cache Level: {data.get('cache_level')}")
        print(f"   Size: {data.get('size_bytes')} bytes")
        return True
    else:
        print(f"❌ Cache PUT Failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False


def test_cache_get(token: str) -> bool:
    """Test cache GET operation."""
    print("\n🧪 Testing Cache GET Operation")
    print("=" * 50)
    
    test_key = "test_query_1"
    
    headers = {
        "Authorization": f"Bearer {token}",
    }
    
    response = requests.get(
        f"{BASE_URL}/api/v1/cache/{test_key}",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Cache GET Successful")
        print(f"   Key: {data.get('key')}")
        print(f"   Hit: {data.get('hit')}")
        print(f"   Cache Level: {data.get('cache_level')}")
        print(f"   Latency: {data.get('latency_ms')} ms")
        print(f"   Value: {data.get('value')}")
        return True
    else:
        print(f"❌ Cache GET Failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False


def test_cache_batch(token: str) -> bool:
    """Test cache batch GET operation."""
    print("\n🧪 Testing Cache BATCH GET Operation")
    print("=" * 50)
    
    # First, cache multiple values
    for i in range(3):
        test_key = f"batch_test_{i}"
        test_value = {"index": i, "data": f"test_data_{i}"}
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        requests.put(
            f"{BASE_URL}/api/v1/cache/{test_key}",
            json={"value": test_value},
            headers=headers
        )
    
    # Now test batch GET
    batch_keys = ["batch_test_0", "batch_test_1", "batch_test_2", "nonexistent_key"]
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/cache/batch",
        json={"keys": batch_keys},
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Cache BATCH GET Successful")
        print(f"   Total Keys: {len(data.get('results', []))}")
        print(f"   Hits: {data.get('hit_count')}")
        print(f"   Misses: {data.get('miss_count')}")
        print(f"   Hit Rate: {data.get('hit_rate'):.2%}")
        
        for result in data.get('results', []):
            status = "✓" if result['hit'] else "✗"
            print(f"   {status} {result['key']}: {result['value'] is not None}")
        
        return True
    else:
        print(f"❌ Cache BATCH GET Failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False


def test_cache_delete(token: str) -> bool:
    """Test cache DELETE operation."""
    print("\n🧪 Testing Cache DELETE Operation")
    print("=" * 50)
    
    test_key = "test_query_1"
    
    headers = {
        "Authorization": f"Bearer {token}",
    }
    
    response = requests.delete(
        f"{BASE_URL}/api/v1/cache/{test_key}",
        headers=headers
    )
    
    if response.status_code == 204:
        print("✅ Cache DELETE Successful")
        
        # Verify it's deleted
        response = requests.get(
            f"{BASE_URL}/api/v1/cache/{test_key}",
            headers=headers
        )
        
        if response.status_code == 404:
            print("   ✓ Verified: Key no longer exists")
            return True
        else:
            print("   ✗ Verification failed: Key still exists")
            return False
    else:
        print(f"❌ Cache DELETE Failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False


def test_cache_clear(admin_token: str) -> bool:
    """Test cache CLEAR operation (admin only)."""
    print("\n🧪 Testing Cache CLEAR Operation (Admin)")
    print("=" * 50)
    
    headers = {
        "Authorization": f"Bearer {admin_token}",
    }
    
    response = requests.delete(
        f"{BASE_URL}/api/v1/cache",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Cache CLEAR Successful")
        print(f"   Cleared: {data.get('cleared')}")
        print(f"   Message: {data.get('message')}")
        return True
    else:
        print(f"❌ Cache CLEAR Failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Phase 2 Cache API Integration Tests")
    print("="*60)
    
    results = []
    
    # Test health
    results.append(("Health Check", test_health()))
    
    # Get auth token
    print("\n🔐 Generating Auth Token...")
    token = get_auth_token()
    if not token:
        print("❌ Failed to get token, cannot proceed")
        return
    print(f"✅ Token: {token[:50]}...")
    
    # Get admin token
    admin_token = get_auth_token(role="admin")
    if not admin_token:
        print("❌ Failed to get admin token")
    
    # Run tests
    results.append(("Cache PUT", test_cache_put(token)))
    results.append(("Cache GET", test_cache_get(token)))
    results.append(("Cache BATCH", test_cache_batch(token)))
    results.append(("Cache DELETE", test_cache_delete(token)))
    
    if admin_token:
        results.append(("Cache CLEAR", test_cache_clear(admin_token)))
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Phase 2.1 cache integration complete.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review output above.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Test Phase 2.3 Admin API endpoints."""

import requests
import json
import time

BASE_URL = "http://localhost:8002"
TEST_USER_ID = "test_admin_123"
TEST_TENANT_ID = "tenant_001"

def get_auth_token(user_id: str = TEST_USER_ID, tenant_id: str = TEST_TENANT_ID, role: str = "admin") -> str:
    """Generate admin auth token for testing."""
    response = requests.get(
        f"{BASE_URL}/token",
        params={
            "user_id": user_id,
            "tenant_id": tenant_id,
            "role": role
        }
    )
    return response.json().get("access_token")

def test_optimize(token: str) -> bool:
    response = requests.post(
        f"{BASE_URL}/api/v1/admin/cache/optimize",
        json={"strategy": "aggressive"},
        headers={"Authorization": f"Bearer {token}"}
    )
    return response.status_code == 200

def test_compress(token: str) -> bool:
    response = requests.post(
        f"{BASE_URL}/api/v1/admin/cache/compress",
        headers={"Authorization": f"Bearer {token}"}
    )
    return response.status_code == 200

def test_stats(token: str) -> bool:
    response = requests.get(
        f"{BASE_URL}/api/v1/admin/stats",
        headers={"Authorization": f"Bearer {token}"}
    )
    return response.status_code == 200

def test_policies(token: str) -> bool:
    response = requests.put(
        f"{BASE_URL}/api/v1/admin/policies",
        headers={"Authorization": f"Bearer {token}"}
    )
    return response.status_code == 200

def main():
    print("\n" + "="*60)
    print("Phase 2 Admin API Integration Tests")
    print("="*60)
    
    token = get_auth_token()
    if not token:
        print("❌ Failed to get admin token")
        return
        
    results = [
        ("Optimize Cache", test_optimize(token)),
        ("Compress Cache", test_compress(token)),
        ("Get Stats", test_stats(token)),
        ("Update Policies", test_policies(token)),
    ]
    
    for name, res in results:
        print(f"{'✅ PASS' if res else '❌ FAIL'}: {name}")
        
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")

if __name__ == "__main__":
    main()

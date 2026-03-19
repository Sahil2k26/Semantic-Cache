#!/usr/bin/env python
"""Test Phase 2.4 Tenant API endpoints."""

import requests
import json
import time

BASE_URL = "http://localhost:8002"
TEST_ADMIN_ID = "test_admin_123"
TEST_TENANT_ID = "tenant_001"

def get_auth_token(user_id: str = TEST_ADMIN_ID, tenant_id: str = TEST_TENANT_ID, role: str = "superadmin") -> str:
    response = requests.get(
        f"{BASE_URL}/token",
        params={"user_id": user_id, "tenant_id": tenant_id, "role": role}
    )
    return response.json().get("access_token")

def test_create_tenant(token: str) -> bool:
    payload = {
        "tenant_id": "new_tenant_999",
        "quota_memory_mb": 500,
        "quota_queries_daily": 10000,
        "quota_request_size_kb": 250
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/tenant/create",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code != 200:
        print(response.text)
    return response.status_code == 200

def test_tenant_metrics(token: str) -> bool:
    response = requests.get(
        f"{BASE_URL}/api/v1/tenant/{TEST_TENANT_ID}/metrics",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code != 200:
        print(response.text)
    return response.status_code == 200

def test_update_quota(token: str) -> bool:
    response = requests.put(
        f"{BASE_URL}/api/v1/tenant/{TEST_TENANT_ID}/quota",
        params={"memory_mb": 2000},
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code != 200:
        print(response.text)
    return response.status_code == 200

def test_delete_tenant(token: str) -> bool:
    response = requests.delete(
        f"{BASE_URL}/api/v1/tenant/{TEST_TENANT_ID}",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code != 200:
        print(response.text)
    return response.status_code == 200

def test_verify_isolation(token: str) -> bool:
    response = requests.get(
        f"{BASE_URL}/api/v1/tenant/verify-isolation",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code != 200:
        print(response.text)
    return response.status_code == 200

def main():
    print("\n" + "="*60)
    print("Phase 2 Tenant API Integration Tests")
    print("="*60)
    
    token = get_auth_token()
    if not token:
        print("❌ Failed to get admin token")
        return
        
    results = [
        ("Create Tenant", test_create_tenant(token)),
        ("Get Tenant Metrics", test_tenant_metrics(token)),
        ("Update Tenant Quota", test_update_quota(token)),
        ("Delete Tenant", test_delete_tenant(token)),
        ("Verify Isolation", test_verify_isolation(token)),
    ]
    
    for name, res in results:
        print(f"{'✅ PASS' if res else '❌ FAIL'}: {name}")
        
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")

if __name__ == "__main__":
    main()

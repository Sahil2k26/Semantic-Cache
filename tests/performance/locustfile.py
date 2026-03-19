from locust import HttpUser, task, between
import json
import random

class SemanticCacheUser(HttpUser):
    wait_time = between(0.1, 1.0)
    
    def on_start(self):
        """Get an auth token before testing."""
        response = self.client.get("/token?user_id=load_tester&tenant_id=tenant_001&role=user")
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        else:
            self.token = None
            self.headers = {}
            
    @task(3)
    def test_cache_put(self):
        if not self.headers:
            return
        key = f"load_key_{random.randint(1, 1000)}"
        self.client.put(
            f"/api/v1/cache/{key}",
            headers=self.headers,
            json={"result": f"Data for {key}", "computation_cost": random.randint(10, 100)},
            name="/api/v1/cache/[key]"
        )

    @task(5)
    def test_cache_get(self):
        if not self.headers:
            return
        key = f"load_key_{random.randint(1, 1000)}"
        with self.client.get(
            f"/api/v1/cache/{key}",
            headers=self.headers,
            name="/api/v1/cache/[key]",
            catch_response=True
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")
        
    @task(1)
    def test_semantic_search(self):
        if not self.headers:
            return
        query = random.choice([
            "What is Python?",
            "How does machine learning work?",
            "Explain vector databases",
            "What is semantic search?",
            "FastAPI deployment guide"
        ])
        self.client.post(
            "/api/v1/search",
            headers=self.headers,
            json={"query": query, "top_k": 3, "threshold": 0.7, "metric": "cosine"},
            name="/api/v1/search"
        )

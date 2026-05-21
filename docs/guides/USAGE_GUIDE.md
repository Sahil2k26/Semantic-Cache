# Semantic Cache - Complete Usage Guide

A comprehensive guide to using the Semantic Cache system in development and production environments, including integration with RAG (Retrieval-Augmented Generation) applications.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture Overview](#architecture-overview)
3. [Installation & Setup](#installation--setup)
4. [API Reference](#api-reference)
5. [Python SDK Usage](#python-sdk-usage)
6. [RAG Integration](#rag-integration)
7. [Production Deployment](#production-deployment)
8. [Testing in Production](#testing-in-production)
9. [Monitoring & Observability](#monitoring--observability)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1. Start Infrastructure

```bash
cd semantic-cache
docker-compose up -d
```

This starts:
- **Redis** (port 6379) - L2 cache
- **PostgreSQL** (port 5432) - L3 persistent cache
- **Prometheus** (port 9090) - Metrics
- **Grafana** (port 3000) - Dashboards

### 2. Start the API Server

```bash
# Install dependencies
pip install -r requirements.txt

# Start server
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Test Health Endpoint

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "cache_level": "l3",
  "redis": "connected",
  "postgres": "connected",
  "uptime_seconds": 42
}
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Your RAG Application                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Semantic Cache API                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Embedding  │  │   Domain    │  │   Adaptive Thresholds   │  │
│  │   Service   │  │  Classifier │  │      & Cost Policy      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
    ┌──────────┐         ┌──────────┐         ┌──────────┐
    │ L1 Cache │         │ L2 Cache │         │ L3 Cache │
    │ (Memory) │         │ (Redis)  │         │(Postgres)│
    │   <1ms   │         │  5-10ms  │         │ 10-50ms  │
    │  ~10K    │         │  ~100K   │         │ Millions │
    └──────────┘         └──────────┘         └──────────┘
```

### Cache Tiers

| Tier | Backend | Latency | Capacity | Use Case |
|------|---------|---------|----------|----------|
| **L1** | In-Memory | <1ms | ~10K entries | Hot data, frequent queries |
| **L2** | Redis | 5-10ms | ~100K entries | Warm data, shared across instances |
| **L3** | PostgreSQL | 10-50ms | Millions | Cold data, persistent storage |

---

## Installation & Setup

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- 4GB+ RAM recommended

### Environment Variables

Create a `.env` file:

```bash
# Database
DATABASE_URL=postgresql://semantic_cache:semantic_cache_dev@localhost:5432/semantic_cache

# Redis
REDIS_URL=redis://localhost:6379/0

# Embedding Model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# Cache Settings
L1_MAX_SIZE=10000
L2_TTL_HOURS=24
L3_TTL_DAYS=30

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY=your-secret-key-here

# Multi-tenancy
DEFAULT_TENANT_ID=default
ENABLE_TENANT_ISOLATION=true
```

### Docker Compose Production Setup

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  semantic-cache:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/cache
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - postgres
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 2G

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 1gb --maxmemory-policy allkeys-lru

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

---

## API Reference

### Authentication

All API requests require a Bearer token:

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/cache/semantic
```

For development, use the default token or disable auth in config.

### Core Endpoints

#### 1. Semantic Cache Store (PUT)

Store a query-response pair with semantic indexing:

```bash
curl -X POST http://localhost:8000/api/v1/cache/semantic \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "query": "What is machine learning?",
    "response": "Machine learning is a subset of AI that enables systems to learn from data...",
    "domain": "technology",
    "metadata": {
      "source": "openai",
      "model": "gpt-4",
      "cost": 0.003,
      "tokens": 150
    }
  }'
```

#### 2. Semantic Cache Search (GET)

Search for semantically similar cached responses:

```bash
curl -X POST http://localhost:8000/api/v1/cache/semantic/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "query": "Explain ML to me",
    "threshold": 0.85,
    "domain": "technology"
  }'
```

Response:
```json
{
  "query": "Explain ML to me",
  "response": "Machine learning is a subset of AI...",
  "hit": true,
  "similarity": 0.92,
  "cache_level": "l1",
  "hit_reason": "semantic_match",
  "domain": "technology",
  "threshold_used": 0.85,
  "latency_ms": 2.34,
  "embedding_generated": true
}
```

#### 3. Health Check

```bash
curl http://localhost:8000/health
```

#### 4. Detailed Metrics

```bash
curl http://localhost:8000/health/detailed
```

#### 5. Admin Stats

```bash
curl http://localhost:8000/api/v1/admin/stats \
  -H "Authorization: Bearer <admin-token>"
```

### All API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Basic health check |
| `/health/detailed` | GET | Detailed system health |
| `/api/v1/cache/{key}` | GET | Get by exact key |
| `/api/v1/cache/{key}` | PUT | Store by exact key |
| `/api/v1/cache/{key}` | DELETE | Delete by key |
| `/api/v1/cache/semantic` | POST | Store with semantic indexing |
| `/api/v1/cache/semantic/search` | POST | Semantic similarity search |
| `/api/v1/cache/semantic/stats` | GET | Cache statistics |
| `/api/v1/cache/batch` | POST | Batch operations |
| `/api/v1/search/search` | POST | Direct similarity search |
| `/api/v1/admin/stats` | GET | Admin statistics |
| `/api/v1/admin/cache/optimize` | POST | Trigger optimization |
| `/api/v1/tenant/create` | POST | Create tenant |
| `/api/v1/tenant/{id}/metrics` | GET | Tenant metrics |

---

## Python SDK Usage

### Basic Usage

```python
from src.cache.cache_manager import CacheManager, CacheManagerConfig
from src.embedding.embedding_service import EmbeddingService
from src.cache.base import CacheEntry

# Initialize
config = CacheManagerConfig(
    l1_max_size=10000,
    l2_ttl_hours=24,
    enable_l3=True,
    l3_ttl_days=30
)

embedding_service = EmbeddingService()
cache_manager = CacheManager(config, embedding_service)
await cache_manager.initialize()

# Store a response
entry = CacheEntry(
    query_id="q-001",
    query_text="What is Python?",
    embedding=embedding_service.generate("What is Python?"),
    response="Python is a high-level programming language...",
    metadata={"source": "gpt-4", "cost": 0.002},
    domain="programming"
)

await cache_manager.put(entry, tenant_id="my-tenant")

# Search semantically
result = await cache_manager.get_semantic(
    query_text="Tell me about Python programming",
    tenant_id="my-tenant",
    threshold=0.85
)

if result:
    print(f"Cache hit! Similarity: {result.similarity}")
    print(f"Response: {result.response}")
```

### With Domain Classification

```python
from src.ml.domain_classifier import KeywordDomainClassifier

classifier = KeywordDomainClassifier()

# Classify query domain
domain = classifier.classify("How do I fix a memory leak in Java?")
# Returns: "programming"

# Get domain-specific threshold
from src.ml.adaptive_thresholds import AdaptiveThresholdManager

threshold_manager = AdaptiveThresholdManager()
threshold = threshold_manager.get_threshold(domain)
# Returns: 0.82 for programming (higher precision needed)
```

### Async Context Manager

```python
async with CacheManager(config, embedding_service) as cache:
    await cache.initialize()
    
    # Use cache
    result = await cache.get_semantic("my query", "tenant-1")
    
# Automatically cleaned up
```

---

## RAG Integration

### Integration Pattern

```
┌──────────────────────────────────────────────────────────────────┐
│                         RAG Pipeline                              │
│                                                                   │
│  User Query ──► Semantic Cache ──► Cache Hit? ──► Return Cached  │
│                      │                   │                        │
│                      │                   ▼ No                     │
│                      │            Vector Store Search             │
│                      │                   │                        │
│                      │                   ▼                        │
│                      │              LLM Generation                │
│                      │                   │                        │
│                      │                   ▼                        │
│                      └────────── Cache Response ◄─────────────────│
│                                         │                        │
│                                         ▼                        │
│                                  Return to User                   │
└──────────────────────────────────────────────────────────────────┘
```

### LangChain Integration

```python
from langchain.llms import OpenAI
from langchain.chains import RetrievalQA
from langchain.vectorstores import FAISS
import httpx

class SemanticCacheWrapper:
    """Wrapper to integrate semantic cache with LangChain."""
    
    def __init__(self, cache_url: str, api_key: str):
        self.cache_url = cache_url
        self.headers = {"Authorization": f"Bearer {api_key}"}
    
    async def get_cached(self, query: str, threshold: float = 0.85) -> dict | None:
        """Check cache for similar query."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.cache_url}/api/v1/cache/semantic/search",
                json={"query": query, "threshold": threshold},
                headers=self.headers
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("hit"):
                    return data
        return None
    
    async def cache_response(self, query: str, response: str, metadata: dict = None):
        """Store response in cache."""
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.cache_url}/api/v1/cache/semantic",
                json={
                    "query": query,
                    "response": response,
                    "metadata": metadata or {}
                },
                headers=self.headers
            )

# Usage in RAG pipeline
async def rag_with_cache(query: str, retriever, llm):
    cache = SemanticCacheWrapper("http://localhost:8000", "your-api-key")
    
    # Check cache first
    cached = await cache.get_cached(query)
    if cached:
        print(f"Cache hit! Similarity: {cached['similarity']}")
        return cached["response"]
    
    # Cache miss - run full RAG pipeline
    docs = retriever.get_relevant_documents(query)
    context = "\n".join([doc.page_content for doc in docs])
    
    response = llm.predict(f"Context: {context}\n\nQuestion: {query}")
    
    # Cache the response
    await cache.cache_response(query, response, {
        "source": "rag",
        "docs_used": len(docs)
    })
    
    return response
```

### LlamaIndex Integration

```python
from llama_index import VectorStoreIndex, ServiceContext
from llama_index.callbacks import CallbackManager
import httpx

class SemanticCacheCallback:
    """LlamaIndex callback for semantic caching."""
    
    def __init__(self, cache_url: str):
        self.cache_url = cache_url
        self.client = httpx.Client()
    
    def on_query_start(self, query: str) -> str | None:
        """Check cache before query execution."""
        response = self.client.post(
            f"{self.cache_url}/api/v1/cache/semantic/search",
            json={"query": query, "threshold": 0.85}
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("hit"):
                return data["response"]
        return None
    
    def on_query_end(self, query: str, response: str):
        """Cache response after query execution."""
        self.client.post(
            f"{self.cache_url}/api/v1/cache/semantic",
            json={"query": query, "response": response}
        )

# Usage
cache_callback = SemanticCacheCallback("http://localhost:8000")

def query_with_cache(index, query: str):
    # Check cache
    cached = cache_callback.on_query_start(query)
    if cached:
        return cached
    
    # Query index
    response = index.query(query)
    
    # Cache result
    cache_callback.on_query_end(query, str(response))
    
    return response
```

### Phase 6-9 Advanced Caching Capabilities

The semantic cache supports the following production-grade capabilities:

#### 1. Context-Aware Smart Conversational Routing (`/api/v1/cache/chat`)
State-free semantic caches fail on pronoun-rich queries (e.g., *"What did he direct?"*). Our smart router:
- Analyzes incoming queries via `ContextAnalyzer`.
- Classifies queries into `STATELESS`, `CONTEXTUAL`, or `AMBIGUOUS`.
- Blends query vectors with conversation history headers (`X-Conversation-History`) for `CONTEXTUAL` queries, creating isolated, pronoun-resolved similarity cache index keys per session.

**Code Example:**
```python
import httpx

# Query with historical turns
response = httpx.post(
    "http://localhost:8000/api/v1/cache/chat",
    headers={
        "X-Conversation-Id": "conversation-uuid-505",
        "X-Conversation-History": '[{"role":"user","content":"Tell me about Christopher Nolan"},{"role":"assistant","content":"He is a famous director..."}]'
    },
    json={"query": "What was his first movie?"}
)
print(response.json())
```

#### 2. SSE timing-Authentic Streaming Cache (`/api/v1/cache/semantic/stream`)
Standard caches wait for streams to complete, returning flat text. Our streaming cache:
- Captures first-time chunk timings dynamically when streaming from backing LLMs.
- Saves the timing signature alongside the content chunks in PostgreSQL and Redis.
- Simulates exact, timing-authentic chunk streaming replay on hits, preserving LLM user experiences.

**Code Example:**
```python
import httpx

# Query timing-authentic SSE streaming
with httpx.stream(
    "POST",
    "http://localhost:8000/api/v1/cache/semantic/stream",
    json={"query": "Explain quantum entanglement in 3 sentences."}
) as r:
    for chunk in r.iter_raw():
        print(chunk.decode("utf-8"), end="", flush=True)
```

#### 3. Stale-While-Revalidate (SWR) Engine
Keeps data ultra-fast while ensuring freshness in background:
- If a cache entry is hit but its age exceeds the configured `swr_fresh_ttl`, the cached value is returned to the user immediately (`<2ms`).
- An asynchronous background validation task is spawned to query the backing LLM, update the L1/L2/L3 tiers, and rebuild the similarity index with the freshest response.

#### 4. Automatic LLM Fallback on Cache Miss
Removes the need for client-side fallback orchestration:
- On a cache lookup miss, the API automatically triggers a call to `LLMService` (which abstracts Gemini-pro REST integrations).
- Returns the generated response immediately to the client with `{"hit": false, "hit_reason": "miss_llm_generated"}`.
- Triggers a write-through promotion task (`put_semantic_async`) in the background, writing to L1 Memory, L2 Redis, L3 Postgres, and HNSW indexes concurrently.

---

## Production Deployment

### Kubernetes Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: semantic-cache
spec:
  replicas: 3
  selector:
    matchLabels:
      app: semantic-cache
  template:
    metadata:
      labels:
        app: semantic-cache
    spec:
      containers:
      - name: semantic-cache
        image: semantic-cache:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: cache-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: cache-secrets
              key: redis-url
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: semantic-cache
spec:
  selector:
    app: semantic-cache
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

### Performance Tuning

```python
# config/production.py
from src.cache.cache_manager import CacheManagerConfig

PRODUCTION_CONFIG = CacheManagerConfig(
    # L1 - Memory cache
    l1_max_size=50000,  # 50K hot entries
    
    # L2 - Redis
    l2_ttl_hours=48,    # 2 days TTL
    
    # L3 - PostgreSQL
    enable_l3=True,
    l3_ttl_days=90,     # 3 months persistence
    enable_l3_promotion=True,
    
    # Similarity settings
    default_threshold=0.85,
    
    # Domain-specific thresholds
    domain_thresholds={
        "medical": 0.95,      # High precision
        "legal": 0.93,
        "technical": 0.88,
        "general": 0.82,
        "creative": 0.75      # More lenient
    }
)
```

---

## Testing in Production

### 1. Smoke Tests

```bash
#!/bin/bash
# smoke_test.sh

BASE_URL="https://your-cache.example.com"
TOKEN="your-api-token"

echo "=== Smoke Test Suite ==="

# Health check
echo -n "Health check: "
HEALTH=$(curl -s "$BASE_URL/health")
if echo "$HEALTH" | grep -q "healthy"; then
    echo "✅ PASS"
else
    echo "❌ FAIL"
    exit 1
fi

# Store test entry
echo -n "Store entry: "
STORE=$(curl -s -X POST "$BASE_URL/api/v1/cache/semantic" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"query": "smoke test query", "response": "smoke test response"}')
if echo "$STORE" | grep -q "stored"; then
    echo "✅ PASS"
else
    echo "❌ FAIL"
fi

# Search entry
echo -n "Search entry: "
SEARCH=$(curl -s -X POST "$BASE_URL/api/v1/cache/semantic/search" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"query": "smoke test query"}')
if echo "$SEARCH" | grep -q '"hit":true'; then
    echo "✅ PASS"
else
    echo "❌ FAIL"
fi

echo "=== Smoke Tests Complete ==="
```

### 2. Load Testing with Locust

```python
# locustfile.py
from locust import HttpUser, task, between
import random

SAMPLE_QUERIES = [
    "What is machine learning?",
    "How does Python work?",
    "Explain neural networks",
    "What is cloud computing?",
    "How to optimize databases?",
]

class CacheUser(HttpUser):
    wait_time = between(0.5, 2)
    
    def on_start(self):
        self.headers = {"Authorization": "Bearer test-token"}
    
    @task(3)
    def search_cache(self):
        """High frequency: search queries."""
        query = random.choice(SAMPLE_QUERIES)
        self.client.post(
            "/api/v1/cache/semantic/search",
            json={"query": query, "threshold": 0.85},
            headers=self.headers
        )
    
    @task(1)
    def store_entry(self):
        """Low frequency: store new entries."""
        query = f"Test query {random.randint(1, 10000)}"
        self.client.post(
            "/api/v1/cache/semantic",
            json={
                "query": query,
                "response": f"Response for {query}",
                "domain": "test"
            },
            headers=self.headers
        )
    
    @task(1)
    def health_check(self):
        """Periodic health checks."""
        self.client.get("/health")

# Run: locust -f locustfile.py --host=http://localhost:8000
```

### 3. RAG Integration Test

```python
# test_rag_integration.py
"""
Production RAG integration test.
Tests the full flow: cache miss → RAG → cache store → cache hit
"""
import asyncio
import httpx
import time

CACHE_URL = "http://localhost:8000"
API_KEY = "your-api-key"

async def test_rag_flow():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    async with httpx.AsyncClient(timeout=30) as client:
        # Test queries that simulate real RAG usage
        test_cases = [
            {
                "query": "What are the benefits of microservices architecture?",
                "domain": "technology",
                "expected_similarity": 0.85
            },
            {
                "query": "How do I implement authentication in FastAPI?",
                "domain": "programming",
                "expected_similarity": 0.82
            },
            {
                "query": "Explain the CAP theorem in distributed systems",
                "domain": "technology",
                "expected_similarity": 0.85
            }
        ]
        
        results = []
        
        for tc in test_cases:
            print(f"\n{'='*60}")
            print(f"Testing: {tc['query'][:50]}...")
            
            # Step 1: First search (expect miss)
            start = time.time()
            response = await client.post(
                f"{CACHE_URL}/api/v1/cache/semantic/search",
                json={"query": tc["query"], "threshold": tc["expected_similarity"]},
                headers=headers
            )
            search_time = (time.time() - start) * 1000
            
            data = response.json()
            first_hit = data.get("hit", False)
            print(f"  First search: {'HIT' if first_hit else 'MISS'} ({search_time:.1f}ms)")
            
            # Step 2: Simulate RAG response and cache it
            if not first_hit:
                rag_response = f"Simulated RAG response for: {tc['query']}"
                
                start = time.time()
                await client.post(
                    f"{CACHE_URL}/api/v1/cache/semantic",
                    json={
                        "query": tc["query"],
                        "response": rag_response,
                        "domain": tc["domain"],
                        "metadata": {"source": "test_rag", "cost": 0.003}
                    },
                    headers=headers
                )
                store_time = (time.time() - start) * 1000
                print(f"  Stored response ({store_time:.1f}ms)")
            
            # Step 3: Search again (expect hit)
            start = time.time()
            response = await client.post(
                f"{CACHE_URL}/api/v1/cache/semantic/search",
                json={"query": tc["query"], "threshold": tc["expected_similarity"]},
                headers=headers
            )
            search_time = (time.time() - start) * 1000
            
            data = response.json()
            second_hit = data.get("hit", False)
            similarity = data.get("similarity", 0)
            cache_level = data.get("cache_level", "unknown")
            
            print(f"  Second search: {'HIT' if second_hit else 'MISS'}")
            print(f"    Similarity: {similarity:.3f}")
            print(f"    Cache level: {cache_level}")
            print(f"    Latency: {search_time:.1f}ms")
            
            # Step 4: Test semantic similarity with variation
            variation = tc["query"].replace("What", "Explain").replace("How", "What is")
            start = time.time()
            response = await client.post(
                f"{CACHE_URL}/api/v1/cache/semantic/search",
                json={"query": variation, "threshold": 0.80},
                headers=headers
            )
            var_time = (time.time() - start) * 1000
            
            var_data = response.json()
            var_hit = var_data.get("hit", False)
            var_sim = var_data.get("similarity", 0)
            
            print(f"  Variation test: {'HIT' if var_hit else 'MISS'}")
            print(f"    Query: {variation[:40]}...")
            print(f"    Similarity: {var_sim:.3f}")
            
            results.append({
                "query": tc["query"],
                "first_miss": not first_hit,
                "second_hit": second_hit,
                "similarity": similarity,
                "variation_hit": var_hit,
                "variation_similarity": var_sim
            })
        
        # Summary
        print(f"\n{'='*60}")
        print("TEST SUMMARY")
        print(f"{'='*60}")
        
        passed = sum(1 for r in results if r["first_miss"] and r["second_hit"])
        print(f"Basic flow (miss→store→hit): {passed}/{len(results)} passed")
        
        semantic_hits = sum(1 for r in results if r["variation_hit"])
        print(f"Semantic matching: {semantic_hits}/{len(results)} variations hit")
        
        avg_sim = sum(r["similarity"] for r in results) / len(results)
        print(f"Average similarity: {avg_sim:.3f}")

if __name__ == "__main__":
    asyncio.run(test_rag_flow())
```

### 4. Cost Savings Calculator

```python
# cost_analysis.py
"""
Calculate cost savings from semantic cache in production.
"""
import httpx

async def calculate_savings(cache_url: str, api_key: str):
    headers = {"Authorization": f"Bearer {api_key}"}
    
    async with httpx.AsyncClient() as client:
        # Get cache stats
        response = await client.get(
            f"{cache_url}/api/v1/cache/semantic/stats",
            headers=headers
        )
        stats = response.json()
        
        # Calculate savings
        total_queries = stats.get("total_queries", 0)
        cache_hits = stats.get("cache_hits", 0)
        hit_rate = cache_hits / total_queries if total_queries > 0 else 0
        
        # Assume average LLM cost per query
        avg_llm_cost = 0.003  # $0.003 per query (GPT-4 average)
        
        queries_saved = cache_hits
        cost_saved = queries_saved * avg_llm_cost
        
        # Latency savings
        avg_llm_latency = 2000  # 2 seconds
        avg_cache_latency = stats.get("avg_latency_ms", 10)
        latency_saved_per_hit = avg_llm_latency - avg_cache_latency
        total_latency_saved_seconds = (latency_saved_per_hit * cache_hits) / 1000
        
        print(f"""
╔══════════════════════════════════════════════════════════╗
║              SEMANTIC CACHE COST ANALYSIS                ║
╠══════════════════════════════════════════════════════════╣
║  Total Queries:        {total_queries:>10,}                      ║
║  Cache Hits:           {cache_hits:>10,}                      ║
║  Hit Rate:             {hit_rate:>10.1%}                      ║
╠══════════════════════════════════════════════════════════╣
║  SAVINGS                                                 ║
║  ───────                                                 ║
║  LLM Calls Avoided:    {queries_saved:>10,}                      ║
║  Cost Saved:           ${cost_saved:>9,.2f}                      ║
║  Time Saved:           {total_latency_saved_seconds:>10,.0f}s                     ║
╚══════════════════════════════════════════════════════════╝
        """)

# Run
import asyncio
asyncio.run(calculate_savings("http://localhost:8000", "your-key"))
```

---

## Monitoring & Observability

### Prometheus Metrics

The cache exposes metrics at `/metrics`:

```
# Cache hit rates
semantic_cache_hits_total{level="l1"} 15234
semantic_cache_hits_total{level="l2"} 8921
semantic_cache_hits_total{level="l3"} 2341
semantic_cache_misses_total 4521

# Latency histograms
semantic_cache_latency_seconds_bucket{le="0.001"} 12000
semantic_cache_latency_seconds_bucket{le="0.01"} 20000
semantic_cache_latency_seconds_bucket{le="0.1"} 25000

# Cache size
semantic_cache_entries{level="l1"} 9823
semantic_cache_entries{level="l2"} 45231
semantic_cache_entries{level="l3"} 234521
```

### Grafana Dashboard

Import the dashboard from `monitoring/grafana/dashboards/semantic-cache.json`.

Key panels:
- **Hit Rate**: Real-time cache hit rate by tier
- **Latency Percentiles**: p50, p95, p99 latencies
- **Cost Savings**: Estimated LLM cost savings
- **Cache Size**: Entries per tier over time
- **Top Domains**: Most cached domains

### Alerting Rules

```yaml
# prometheus/alerts.yml
groups:
  - name: semantic-cache
    rules:
      - alert: CacheHitRateLow
        expr: semantic_cache_hit_rate < 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Cache hit rate below 50%"
          
      - alert: CacheLatencyHigh
        expr: histogram_quantile(0.95, semantic_cache_latency_seconds_bucket) > 0.1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "p95 latency exceeds 100ms"
          
      - alert: RedisConnectionFailed
        expr: semantic_cache_redis_connected == 0
        for: 1m
        labels:
          severity: critical
```

---

## Troubleshooting

### Common Issues

#### 1. Low Hit Rate

**Symptoms**: Hit rate below 30%

**Causes & Solutions**:
- **Threshold too high**: Lower from 0.85 to 0.80
- **Domain mismatch**: Enable domain classification
- **Cold cache**: Run predictive warming

```python
# Lower threshold for better hit rate
result = await cache.get_semantic(query, threshold=0.80)

# Enable domain-specific thresholds
config.domain_thresholds = {
    "general": 0.78,
    "technical": 0.85
}
```

#### 2. High Latency

**Symptoms**: Latency >100ms

**Causes & Solutions**:
- **L3 heavy**: Increase L1/L2 sizes
- **Redis slow**: Check Redis memory, enable cluster
- **Index large**: Enable HNSW pruning

```bash
# Check Redis memory
redis-cli INFO memory

# Monitor cache tier distribution
curl localhost:8000/api/v1/admin/stats
```

#### 3. Memory Issues

**Symptoms**: OOM errors, slow GC

**Solutions**:
```python
# Reduce L1 size
config.l1_max_size = 5000

# Enable aggressive eviction
config.eviction_policy = "lru"
config.eviction_threshold = 0.8
```

#### 4. PostgreSQL Connection Errors

**Symptoms**: L3 failures, connection pool exhausted

**Solutions**:
```python
# Increase pool size
db_config = DatabaseConfig(
    url="postgresql://...",
    pool_size=20,
    max_overflow=10
)
```

### Debug Mode

Enable verbose logging:

```bash
export LOG_LEVEL=DEBUG
python -m uvicorn src.api.main:app --log-level debug
```

### Health Check Script

```bash
#!/bin/bash
# health_check.sh

echo "Checking Semantic Cache Health..."

# API Health
API_HEALTH=$(curl -s localhost:8000/health | jq -r '.status')
echo "API: $API_HEALTH"

# Redis
REDIS_PING=$(redis-cli ping)
echo "Redis: $REDIS_PING"

# PostgreSQL
PG_STATUS=$(pg_isready -h localhost -p 5432 && echo "ready" || echo "not ready")
echo "PostgreSQL: $PG_STATUS"

# Cache Stats
STATS=$(curl -s localhost:8000/api/v1/cache/semantic/stats)
echo "L1 entries: $(echo $STATS | jq -r '.l1_entries')"
echo "L2 entries: $(echo $STATS | jq -r '.l2_entries')"
echo "L3 entries: $(echo $STATS | jq -r '.l3_entries')"
echo "Hit rate: $(echo $STATS | jq -r '.hit_rate')"
```

---

## Next Steps

1. **Set up monitoring**: Import Grafana dashboards
2. **Configure alerts**: Set up PagerDuty/Slack alerts
3. **Tune thresholds**: Analyze hit rates by domain
4. **Enable warming**: Configure predictive cache warming
5. **Scale horizontally**: Add more cache instances

For more information, see:
- [Architecture Documentation](../architecture/)
- [API Reference](../api/)
- [Deployment Guide](./DEPLOYMENT.md)

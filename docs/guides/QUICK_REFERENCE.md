# Production Cache - Quick Reference Guide

This document acts as an immediate cheat sheet for common operations, API endpoints, environment variables, and diagnostic checks.

---

## 🚀 Common Code Snippets

### 1. Conversational Chat Routing (`/chat`)
To interact with the smart context-aware conversational routing endpoint:
```python
import httpx

response = httpx.post("http://localhost:8000/api/v1/cache/chat", 
    headers={
        "X-Conversation-Id": "conversation-uuid-101",
        "X-Conversation-History": '[{"role":"user","content":"Who directed Inception?"},{"role":"assistant","content":"Christopher Nolan."}]'
    },
    json={
        "query": "What other movies did he direct?",
        "domain": "general"
    }
)
print(response.json())
```

### 2. Semantic Search with Auto-LLM Caching (`/search`)
Querying the similarity search engine with automatic Gemini-fallback recovery:
```python
import httpx

response = httpx.post("http://localhost:8000/api/v1/cache/semantic/search", json={
    "query": "How do you declare a list in Python?",
    "threshold": 0.85
})
print(response.json())
# Returns: {"hit": true/false, "hit_reason": "exact_match"/"semantic_match"/"miss_llm_generated", "response": "..."}
```

### 3. SSE Streaming Cache Replay (`/stream`)
Initiate token stream caching or timing-authentic playback:
```python
import httpx

with httpx.stream("POST", "http://localhost:8000/api/v1/cache/semantic/stream", 
    json={"query": "Write a python fibonacci function"}
) as r:
    for chunk in r.iter_raw():
        print(chunk.decode("utf-8"), end="")
```

---

## 🗺️ Key API Routes

### Core Cache Tiers
- `POST /api/v1/cache/semantic` — Index a query-response pair explicitly.
- `POST /api/v1/cache/semantic/search` — Search similarity cache (fallback generates via LLM and writes).
- `POST /api/v1/cache/semantic/stream` — Timing-replayed SSE token streaming cache.
- `POST /api/v1/cache/chat` — Conversational cache routing using history state headers.

### Live Metrics & WebSockets
- `GET /api/v1/metrics/realtime` — L1/L2/L3 split rates and active latency metrics.
- `GET /api/v1/metrics/historical` — postgres-aggregated time-series graph.
- `GET /api/v1/insights/top-queries` — Lists most active queries and hit count.
- `WS /ws/realtime` — Persistent WebSocket pushing metrics every 5 seconds.

---

## ⚙️ Environment Variables Cheat Sheet

| Variable | Default | Purpose |
|----------|---------|---------|
| `REDIS_HOST` | `localhost` | Redis Warm cache host |
| `DATABASE_URL` | `postgresql://...` | Postgres DB for persistent cache & analytics |
| `EMBEDDING_MODEL` | `sentence-transformers/...` | Model used to vectorize queries |
| `LLM_PROVIDER` | `gemini` | Fallback LLM client ("gemini" or "openai") |
| `LLM_API_KEY` | None | API token for Google Generative AI / OpenAI |
| `LOG_LEVEL` | `INFO` | Output logging granularity |

---

## 🩺 Diagnostic Commands

### 1. Backend Service Status
```bash
# Check docker containers
docker-compose ps

# Health status JSON endpoint
curl http://localhost:8000/health
```

### 2. Verify Cache Hits/Latency in CLI
```bash
# Test stateless exact match
curl -X POST http://localhost:8000/api/v1/cache/semantic/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Explain gravity","threshold":0.99}'
```

### 3. Clear Cache Data (Dangerous)
To wipe Redis and PostgreSQL databases locally:
```bash
# Reset database volumes
docker-compose down -v
docker-compose up -d
```

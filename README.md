# Semantic Caching Layer for Vector Databases

A production-grade semantic cache that sits between LLM-powered applications and backend AI services, reducing latency and cost through intelligent similarity-aware caching and automatic LLM-powered cache-miss recovery.

## 🚀 Quick Start

```bash
# 1. Start infrastructure (Redis, Postgres, Prometheus, Grafana)
docker-compose up -d

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
# Edit .env to set your LLM_API_KEY (Gemini is the default provider)

# 4. Start the API server
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# 5. Test it works
curl http://localhost:8000/health
```

## Overview

This project implements a smart caching layer that goes beyond exact-match caching, using semantic similarity to reuse responses for similar queries.

### Key Features

| Feature | Description |
|---------|-------------|
| **3-Tier Caching** | L1 (Memory <1ms) → L2 (Redis 5-10ms) → L3 (PostgreSQL 10-50ms) |
| **Semantic Matching** | Find similar queries using embeddings & HNSW index |
| **Domain-Adaptive Thresholds** | Auto-adjusts similarity thresholds per domain |
| **Cost-Aware Eviction** | Keeps expensive LLM responses longer |
| **Multi-Tenant Isolation** | Secure tenant separation with quotas |
| **Predictive Warming** | Pre-caches likely queries |
| **Query Normalization** | Canonicalize queries before embedding for higher hit rates |
| **Multi-Intent Detection** | Decompose complex queries into atomic sub-queries |
| **Stale-While-Revalidate** | Serve stale entries instantly while refreshing in the background |
| **Streaming Response Cache** | Cache and replay LLM token streams with accurate timing |
| **Analytics API** | Real-time and historical performance metrics via REST & WebSocket |
| **Circuit Breaker** | Protect embedding/LLM services with CLOSED → OPEN → HALF-OPEN states |
| **Context-Aware Caching** | Route conversational queries through a smart context-hash cache |
| **LLM Miss Fallback** | Call Gemini/OpenAI on cache miss and automatically index the response |

### Architecture

```
┌───────────────────────────────────────────────────────────────┐
┌───────────────────────────────────────────────────────────────┐
│                     Your Application / Chatbot                │
└───────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                      SmartCacheRouter                         │
│   ┌──────────────────┐      ┌─────────────────────────────┐   │
│   │  ContextAnalyzer │      │      QueryNormalizer         │   │
│   │  (stateless vs   │      │  + Multi-Intent Detector    │   │
│   │   contextual)    │      │  + Circuit Breaker          │   │
│   └──────────────────┘      └─────────────────────────────┘   │
└───────────────────────────────────────────────────────────────┘
          │                                │
          ▼                                ▼
┌──────────────────┐            ┌──────────────────────┐
│  Semantic Cache  │            │  Context-Aware Cache │
│  (stateless q.)  │            │  (conversational q.) │
└──────────────────┘            └──────────────────────┘
          \                                /
           ▼                              ▼
      ┌──────────┐  ┌──────────┐  ┌──────────┐
      │ L1 Cache │  │ L2 Cache │  │ L3 Cache │      Cache Miss
      │ (Memory) │  │ (Redis)  │  │(Postgres)│  ──────────────────►  ┌──────────────┐
      │   <1ms   │  │  5-10ms  │  │ 10-50ms  │                       │ LLM Service  │
      └──────────┘  └──────────┘  └──────────┘                       │ (Gemini/OAI) │
                                                                     └──────────────┘
```

## 📖 Documentation

| Document | Description |
|----------|-----------|
| **[Feature Reference](./docs/FEATURES.md)** | All features: SWR, Streaming, Analytics, Circuit Breaker, Context-Aware Routing |
| **[Setup Guide](./docs/guides/SETUP.md)** | Detailed installation and environment configuration instructions |
| **[Usage Guide](./docs/guides/USAGE_GUIDE.md)** | Complete usage guide with RAG integration and LLM fallback examples |
| **[Architecture](./docs/architecture/ARCHITECTURE.md)** | System architecture, component breakdowns, and design decisions |
| **[LLM Integration](./docs/guides/LLM_INTEGRATION.md)** | Documentation for the LLM Service (Gemini/OpenAI) and automatic caching |
| **[Frontend Apps](./docs/guides/FRONTEND.md)** | Running and integrating the Analytics Dashboard and Chat Application |

## Usage Examples

### Conversational Caching (/chat)

```python
import httpx

# Chat with conversational context routing and auto-LLM fallback on miss
response = httpx.post("http://localhost:8000/api/v1/cache/chat", 
    headers={
        "X-Conversation-Id": "session-123",
        "X-Conversation-History": '[{"role":"user","content":"What is python?"},{"role":"assistant","content":"Python is a programming language."}]'
    },
    json={
        "query": "Is it dynamically typed?",
        "domain": "technology"
    }
)

print(response.json())
# {"response": "Yes, Python is dynamically typed...", "cached": true, "cache_type": "contextual"}
```

### RAG Integration

```python
async def rag_with_cache(query: str, retriever, llm):
    # 1. Check cache first
    cache_result = await cache.search(query, threshold=0.85)
    if cache_result.hit:
        return cache_result.response  # Fast path: ~5ms
    
    # 2. Cache miss - run full RAG pipeline
    docs = retriever.get_relevant_documents(query)
    response = llm.generate(query, context=docs)  # Slow path: ~2000ms
    
    # 3. Cache for future queries
    await cache.store(query, response, metadata={"cost": 0.003})
    
    return response
```

See the [Usage Guide](./docs/guides/USAGE_GUIDE.md) for complete examples with LangChain, LlamaIndex, and OpenAI.

## API Endpoints

### Core Cache
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with cache status |
| `/api/v1/cache/semantic` | POST | Store with semantic indexing |
| `/api/v1/cache/semantic/search` | POST | Semantic similarity search (auto-generates LLM response on miss) |
| `/api/v1/cache/semantic/multi/search` | POST | Multi-intent query decomposition |
| `/api/v1/cache/{key}` | GET/PUT/DEL | Exact key operations |

### Conversational & Streaming
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/cache/chat` | POST | Smart context-aware routing (sets `X-Conversation-Id` / `X-Conversation-History` headers) |
| `/api/v1/cache/semantic/stream` | POST | SSE token streaming with cache replay (auto-streams from LLM on miss) |

### Analytics
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/metrics/realtime` | GET | Current in-memory cache hit rates |
| `/api/v1/metrics/historical` | GET | Aggregated time-series stats (Postgres `DATE_TRUNC`) |
| `/api/v1/insights/top-queries` | GET | Top cache-hit queries by frequency |
| `/ws/realtime` | WebSocket | Push live metrics every 5 seconds |

### Admin & Tenant
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/admin/stats` | GET | Full cache statistics |
| `/api/v1/tenant/create` | POST | Create tenant |

## Project Structure

```
semantic-cache/
├── src/
│   ├── api/
│   │   └── routes/
│   │       ├── cache.py          # Cache + chat + stream endpoints
│   │       └── analytics.py      # Metrics & WebSocket analytics
│   ├── cache/
│   │   ├── cache_manager.py      # Tiered cache orchestrator (L1→L2→L3) + SWR + Circuit Breaker
│   │   ├── base.py               # CacheEntry, CacheMetrics, is_stale()
│   │   ├── context.py            # ContextAnalyzer, ContextAwareCache, SmartCacheRouter
│   │   ├── streaming.py          # StreamingCache: stream_and_cache() + get_stream()
│   │   ├── l1_cache.py           # In-memory LRU/LFU
│   │   ├── l2_cache.py           # Redis cache tier
│   │   └── l3_cache.py           # PostgreSQL + pgvector
│   ├── core/
│   │   ├── config.py             # Server & LLM configuration
│   │   └── circuit_breaker.py    # CircuitBreaker (CLOSED/OPEN/HALF_OPEN)
│   ├── llm/
│   │   └── service.py            # Modular LLM service integration (Gemini & OpenAI)
│   ├── ml/
│   │   └── query_parser.py       # QueryNormalizer + RuleBasedIntentDetector
│   ├── monitoring/
│   │   └── analytics.py          # AnalyticsCollector (Redis Streams → Postgres)
│   ├── embedding/                # Embedding service (sentence-transformers)
│   ├── similarity/               # HNSW index & similarity search
│   └── multi_tenancy/            # Tenant isolation & quotas
├── frontend-services/
│   ├── dashboard/                # Next.js Analytics Dashboard (WebSocket & Recharts)
│   └── chat-app/                 # Consumer Chat client app
├── tests/
│   ├── unit/                     # Comprehensive test suites
│   └── ...
├── docs/
│   └── FEATURES.md               # Detailed feature documentation
├── monitoring/                   # Grafana dashboards, Prometheus config
└── docker-compose.yml
```

## Development Status

| Phase | Status | Features |
|-------|--------|---------|
| **Phase 1**: Core Cache | ✅ Complete | Redis + HNSW, embeddings, monitoring |
| **Phase 2**: Multi-Level | ✅ Complete | L1/L2/L3 tiers, eviction policies |
| **Phase 3**: Intelligence | ✅ Complete | Domain classifier, adaptive thresholds, predictive warming |
| **Phase 4**: Production | ✅ Complete | Multi-tenancy, security, load testing |
| **Phase 5**: Semantic Enhancement | ✅ Complete | Query normalization, multi-intent detection |
| **Phase 6**: Production Resilience | ✅ Complete | SWR, Streaming, Analytics API, Circuit Breaker |
| **Phase 7**: Context-Aware Routing | ✅ Complete | Smart router, conversational caching, `/chat` endpoint |
| **Phase 8**: Frontend Dashboard | ✅ Complete | Next.js Analytics dashboard, real-time WebSocket insights |
| **Phase 9**: LLM Integration | ✅ Complete | Modular LLM service (Gemini/OpenAI), auto-cache-on-miss fallback |

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## Monitoring

Access monitoring dashboards:
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090

Key metrics:
- Cache hit rate by tier (L1, L2, L3)
- Latency percentiles (p50, p95, p99)
- Cost savings estimation
- Query throughput

## License

MIT License - See LICENSE file for details

---

📚 **[Full Setup Guide →](./docs/guides/SETUP.md)** | **[Full Usage Guide →](./docs/guides/USAGE_GUIDE.md)**


# Semantic Caching Layer for Vector Databases

A production-grade semantic cache that sits between LLM-powered applications and backend AI services, reducing latency and cost through intelligent similarity-aware caching.

## Overview

This project implements a smart caching layer that goes beyond exact-match caching, using semantic similarity to reuse responses for similar queries. It features:

- **Multi-level caching** (in-memory, SSD, disk)
- **Domain-adaptive similarity thresholds**
- **Predictive cache warming**
- **Cost-aware eviction policies**
- **Multi-tenant isolation**
- **Real-time monitoring and explainability**

## Project Structure

```
semantic-cache/
├── src/                          # Main source code
│   ├── core/                     # Core cache engine
│   ├── cache/                    # Cache implementations (L1, L2, L3)
│   ├── embedding/                # Embedding service integrations
│   ├── similarity/               # Similarity matching algorithms
│   ├── api/                      # FastAPI endpoints
│   ├── ml/                       # ML models and inference
│   ├── multi_tenancy/            # Multi-tenant functionality
│   ├── monitoring/               # Monitoring and metrics
│   └── utils/                    # Utilities and helpers
├── tests/                        # Test suites
│   ├── unit/                     # Unit tests
│   ├── integration/              # Integration tests
│   └── performance/              # Performance benchmarks
├── config/                       # Configuration files
├── deployment/                   # Deployment artifacts
│   ├── docker/                   # Docker configurations
│   ├── kubernetes/               # Kubernetes manifests
│   └── terraform/                # IaC scripts
├── docs/                         # Documentation
│   ├── architecture/             # Architecture docs
│   ├── api/                      # API documentation
│   └── guides/                   # Integration guides
├── monitoring/                   # Monitoring stack configs
│   ├── prometheus/               # Prometheus configs
│   └── grafana/                  # Grafana dashboards
└── scripts/                      # Utility scripts
```

## Development Roadmap

### Phase 1: Core Cache (Months 1-4) ✅ COMPLETE
- Basic semantic cache with Redis + HNSW
- Embedding service integration
- Monitoring dashboards

### Phase 2: Multi-Level & Hybrid Search (Months 5-7) ✅ COMPLETE
- L2 (SSD) and L3 (disk) cache layers
- Metadata filtering with RedisSearch
- Eviction policies (LRU, LFU)

### Phase 3: Intelligence Layer ✅ COMPLETE
- Domain classifier and adaptive thresholds
- Predictive warming
- Cost-aware eviction

### Phase 4: Production Hardening ✅ COMPLETE
- Multi-tenancy with quotas
- Security headers & rate limiting
- Load testing (Locust)
- Fine-tuning pipeline

## Getting Started

### Prerequisites
- Python 3.10+
- Docker & Docker Compose
- Redis (local or containerized)
- FAISS or HNSWlib

### Installation

```bash
# Clone and setup
cd semantic-cache
pip install -r requirements.txt

# Run tests
pytest tests/

# Start services
docker-compose up -d
```

See [SETUP.md](./docs/guides/SETUP.md) for detailed setup instructions.

## Usage

### Basic Example

```python
from src.core.semantic_cache import SemanticCache

# Initialize cache
cache = SemanticCache(
    embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    similarity_threshold=0.85
)

# Query the cache
response = cache.query(
    query_text="What is machine learning?",
    tenant_id="tenant_123"
)
```

See [docs/guides](./docs/guides/) for more examples.

## API Endpoints

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/v1/cache` | GET/PUT/DEL/POST | Cache operations (get, put, batch, delete) |
| `/api/v1/search` | POST | Semantic similarity search and embedding |
| `/api/v1/admin` | GET/POST/PUT | Admin cache optimization, compression, policies |
| `/api/v1/tenant`| GET/POST/PUT/DEL | Resource isolation, quotas, and tenant management |

## Architecture

See [docs/architecture](./docs/architecture/) for:
- High-level system design
- Component interactions
- Data flow diagrams
- Performance characteristics

## Contributing

1. Create a feature branch
2. Make changes with tests
3. Run `pytest` and `black`
4. Submit a pull request

## Team

See [PROJECT_CONTEXT.md](./PROJECT_CONTEXT.md) for team roles and responsibilities.

## License

MIT License - See LICENSE file for details

## Contact

For questions or contributions, contact the project team.

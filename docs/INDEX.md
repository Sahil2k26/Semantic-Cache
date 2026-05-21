# Documentation Index & Navigation Guide

**Project**: Production-Grade Semantic Caching Layer  
**Last Updated**: May 18, 2026  
**Status**: All Phases Complete (Phase 1–9)  

---

## 🚀 Welcome to the Project

This index acts as a central map for all project documentation. The files listed here will guide you from initial local environment setup to production-grade implementation and analytics visualization.

### Documentation Map

```
docs/
├── FEATURES.md                 # Detailed breakdown of advanced features (SWR, Streaming, CB, etc.)
│
├── guides/
│   ├── SETUP.md                # Quickstart, Docker setup, and environment configurations
│   ├── USAGE_GUIDE.md          # Multi-provider usage (Langchain, LlamaIndex) & RAG examples
│   ├── LLM_INTEGRATION.md      # Auto-miss recovery and timing-accurate stream caching guides
│   └── FRONTEND.md             # Running the Analytics Dashboard and Consumer Chat applications
│
└── architecture/
    └── ARCHITECTURE.md         # High-level architecture, multi-tier data flows, and schemas
```

---

## 📖 Directory & Document Reference

### 1. **[Feature Reference](./FEATURES.md)**
- **Scope:** Detailed breakdowns of all advanced caching features.
- **Includes:** 
  - Stale-While-Revalidate (SWR) background tasks
  - Timing-authentic Streaming Caches (SSE)
  - Circuit Breaker CLOSED/OPEN/HALF_OPEN state engine
  - Context-Aware composite conversational keys
  - Multi-intent query normalizers and rule detectors

### 2. **[Setup Guide](./guides/SETUP.md)**
- **Scope:** Complete guide to installing, configuring, and running the cache locally or via Docker.
- **Includes:**
  - Python and venv installation commands
  - Redis, PostgreSQL, Prometheus, and Grafana docker configurations
  - Environment variables template (`LLM_PROVIDER`, `LLM_API_KEY`, etc.)
  - Testing suite executions (`pytest`)

### 3. **[Usage Guide](./guides/USAGE_GUIDE.md)**
- **Scope:** Implementation examples demonstrating client-side caching.
- **Includes:**
  - Standard REST calls for exact or semantic matches
  - Context-aware RAG pipeline integrations
  - Connecting LangChain and LlamaIndex agents to the API
  - Auto-fallback LLM query examples

### 4. **[System Architecture](./architecture/ARCHITECTURE.md)**
- **Scope:** Under-the-hood design decisions and layout maps.
- **Includes:**
  - High-level ASCII architecture diagram
  - Data flows for cache hits and cache misses
  - HNSW in-memory (L1), Redis warm (L2), and PostgreSQL cold (L3) storage configurations
  - Database schema diagrams for queries, metrics, and tenants

### 5. **[LLM Integration](./guides/LLM_INTEGRATION.md)**
- **Scope:** How the backend coordinates semantic queries with LLMs.
- **Includes:**
  - Configuring Gemini or OpenAI API keys
  - The automatic cache-miss fallback mechanism
  - Token-replay timing offsets for streaming channels

### 6. **[Frontend Applications](./guides/FRONTEND.md)**
- **Scope:** Guides for the Web Visual Suite.
- **Includes:**
  - Running the Next.js Analytics Dashboard (WebSocket metrics, Recharts tables)
  - Interfacing with the Consumer Chat Client to test smart routing badging

---

## 🎓 Learning Paths by Role

### 🛠️ Backend Developers
1. Set up your environment using **[Setup Guide](./guides/SETUP.md)**.
2. Review data schemas in **[System Architecture](./architecture/ARCHITECTURE.md)**.
3. Call standard cache endpoints following **[Usage Guide](./guides/USAGE_GUIDE.md)**.

### 🧠 ML/AI Engineers
1. Understand normalizers and detectors in **[Feature Reference](./FEATURES.md)**.
2. Read how fallback caching is orchestrated in **[LLM Integration](./guides/LLM_INTEGRATION.md)**.
3. Customize similarity thresholds per-domain using configurations in **[Setup Guide](./guides/SETUP.md)**.

### 🖥️ Full-Stack & DevOps Engineers
1. Configure tiered backing services in **[Setup Guide](./guides/SETUP.md)**.
2. Deploy the visual suite following **[Frontend Applications](./guides/FRONTEND.md)**.
3. Access Prometheus metrics and Grafana alerts detailed in **[System Architecture](./architecture/ARCHITECTURE.md)**.

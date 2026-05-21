# Future Improvements & Roadmap

This document outlines the planned roadmap and potential enhancements for the Semantic Caching Layer.

---

## 🔒 Security & Authentication

### 1. Analytics Routes Hardening
Currently, the `/api/v1/metrics/*` REST endpoints and `/ws/realtime` WebSocket endpoint fetch metrics and stream cache data without strict Token verification. 
- **Plan:** Apply the standard FastAPI `get_current_user` dependency to all analytics routes. Ensure WebSocket connection handshakes pass the JWT token in query parameters or auth subprotocols.
- **Scope:** Medium

### 2. Multi-Tenant Encryption at Rest
While tenants are logically separated via namespace prefixes in L1, L2, and L3, sensitive cache payloads should be encrypted individually.
- **Plan:** Implement AES-256 GCM encryption on cached payload fields utilizing tenant-specific keys managed through a secure KMS (Key Management Service).
- **Scope:** High

---

## 💾 Storage & Scalability

### 1. TimescaleDB for Analytics
Currently, historical metrics are aggregated using standard PostgreSQL tables with `DATE_TRUNC`. Under millions of queries, this can lead to performance degradation.
- **Plan:** Migrate the metrics backend to TimescaleDB or utilize partitions on the `cache_events` table by timestamp.
- **Scope:** Medium

### 2. HNSW Index Serialization & Scaling
The in-memory HNSW index for L1 operates efficiently but requires complete rebuilds on startup or after large eviction cycles.
- **Plan:** Standardize disk backups of the HNSW indices per tenant and stream index modifications to persistent block storage dynamically.
- **Scope:** High

---

## 🧠 ML & NLP Enhancements

### 1. Production-Grade Named Entity Recognition (NER)
Currently, `ContextAnalyzer._extract_entities()` in `src/cache/context.py` uses a simple rule/regex matcher to identify referring pronouns and context shifts.
- **Plan:** Integrate spaCy (`en_core_web_sm` or `en_core_web_trf`) to accurately tag pronouns, entities, and subjects, ensuring contextual hashes only update when subjects actually shift.
- **Scope:** Medium

### 2. Conversation History Summarization
When conversation histories get long, composite semantic search keys become bloated, leading to degraded similarity matching.
- **Plan:** Implement the `ContextAwareCache._generate_summary()` stub to dynamically summarize chat sessions using Gemini or a fast local T5 model before creating semantic search embeddings.
- **Scope:** Medium

### 3. Modular LLM Provider Extensions
The `LLMService` currently implements Gemini REST and contains an OpenAI modular driver placeholder.
- **Plan:** Complete the OpenAI implementation and add Anthropic (Claude) and Cohere integrations, allowing run-time failover between LLM providers on cache misses.
- **Scope:** Low

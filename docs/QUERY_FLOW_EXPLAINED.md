# Query Flow: From User Request to Cached Response

**Date:** March 21, 2026  
**Purpose:** Deep-dive into how a query flows through the semantic cache system

---

## Table of Contents

1. [High-Level Overview](#1-high-level-overview)
2. [Detailed Query Flow](#2-detailed-query-flow)
3. [Semantic vs Exact Matching](#3-semantic-vs-exact-matching)
4. [Intelligence Layer Optimizations](#4-intelligence-layer-optimizations)
5. [Cache Miss Flow (Write Path)](#5-cache-miss-flow-write-path)
6. [Code Walkthrough](#6-code-walkthrough)

---

## 1. High-Level Overview

### The Big Picture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           USER QUERY                                      │
│                    "How do I fix a Python bug?"                          │
└─────────────────────────────┬────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  STEP 1: EMBEDDING GENERATION                                            │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  Query Text → Sentence Transformer → 384-dim Vector                │  │
│  │  "How do I fix a Python bug?" → [0.23, -0.45, 0.12, ..., 0.87]    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────┬────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  STEP 2: DOMAIN CLASSIFICATION (Intelligence Layer)                      │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  "python", "bug" detected → Domain: "coding"                       │  │
│  │  Threshold adjusted: 0.85 (high precision for code)                │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────┬────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  STEP 3: UNIFIED INDEX SEARCH                                            │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  HNSW Index Search:                                                │  │
│  │    1. Check exact text match first                                 │  │
│  │    2. Cosine similarity search on embedding                        │  │
│  │    3. Filter by tenant_id                                          │  │
│  │    4. Filter by threshold (0.85)                                   │  │
│  │                                                                    │  │
│  │  Result: item_id="abc123", similarity=0.92, entry_metadata         │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────┬────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  STEP 4: CACHE DATA RETRIEVAL                                            │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  Tiered lookup (fastest first):                                    │  │
│  │    L1 (Memory) → Found? Return immediately (<1ms)                  │  │
│  │    L2 (Redis)  → Found? Promote to L1, return (5-10ms)            │  │
│  │    L3 (Postgres) → Found? Promote to L1+L2, return (20-50ms)      │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────┬────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        CACHE HIT RESPONSE                                 │
│  {                                                                        │
│    "response": "To fix a Python bug, use debugging tools like pdb...",   │
│    "similarity": 0.92,                                                   │
│    "hit_source": "L1",                                                   │
│    "domain": "coding",                                                   │
│    "is_exact_match": false                                               │
│  }                                                                        │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Detailed Query Flow

### Step-by-Step Breakdown

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              COMPLETE QUERY FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌────────────────┐                                                             │
│  │  HTTP Request  │  POST /api/v1/cache/semantic                                │
│  │  {query: "..."}│                                                             │
│  └───────┬────────┘                                                             │
│          │                                                                       │
│          ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                        FastAPI Route Handler                            │     │
│  │  src/api/routes/cache.py                                               │     │
│  │                                                                         │     │
│  │  @router.post("/semantic")                                             │     │
│  │  async def semantic_cache(request: SemanticCacheRequest):              │     │
│  │      # Extract tenant_id from JWT token                                │     │
│  │      tenant_id = get_tenant_id(token)                                  │     │
│  │      # Call cache manager                                              │     │
│  │      result = await cache_manager.get_semantic_async(...)              │     │
│  └───────┬────────────────────────────────────────────────────────────────┘     │
│          │                                                                       │
│          ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                     CacheManager.get_semantic_async()                   │     │
│  │  src/cache/cache_manager.py:646                                        │     │
│  │                                                                         │     │
│  │  1. Generate Embedding:                                                │     │
│  │     embedding = await embedding_service.embed_text(query_text)         │     │
│  │     # Returns 384-dimension vector                                     │     │
│  │                                                                         │     │
│  │  2. Call sync search:                                                  │     │
│  │     return self.get_semantic(query_text, embedding, tenant_id, ...)    │     │
│  └───────┬────────────────────────────────────────────────────────────────┘     │
│          │                                                                       │
│          ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                      CacheManager.get_semantic()                        │     │
│  │  src/cache/cache_manager.py:525                                        │     │
│  │                                                                         │     │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │     │
│  │  │ INTELLIGENCE LAYER ACTIVATION                                     │  │     │
│  │  │                                                                   │  │     │
│  │  │ A) Domain Classification (if domain not provided):               │  │     │
│  │  │    domain = self._domain_classifier.classify(query_text)         │  │     │
│  │  │    # Analyzes keywords: "python", "bug" → "coding"               │  │     │
│  │  │                                                                   │  │     │
│  │  │ B) Adaptive Threshold Selection:                                 │  │     │
│  │  │    threshold = self._threshold_manager.get_threshold(domain)     │  │     │
│  │  │    # "coding" domain → 0.85 threshold                            │  │     │
│  │  └──────────────────────────────────────────────────────────────────┘  │     │
│  │                                                                         │     │
│  │  3. Search Unified Index:                                              │     │
│  │     results = self._index_manager.search_by_text(                      │     │
│  │         query_text=query_text,                                         │     │
│  │         embedding=embedding,                                           │     │
│  │         k=1,                                                           │     │
│  │         threshold=threshold,  # 0.85                                   │     │
│  │         domain=domain,        # "coding"                               │     │
│  │         tenant_id=tenant_id,                                           │     │
│  │     )                                                                  │     │
│  └───────┬────────────────────────────────────────────────────────────────┘     │
│          │                                                                       │
│          ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                  UnifiedIndexManager.search_by_text()                   │     │
│  │  src/cache/index_manager.py:259                                        │     │
│  │                                                                         │     │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │     │
│  │  │ TWO-PHASE SEARCH:                                                 │  │     │
│  │  │                                                                   │  │     │
│  │  │ PHASE 1: EXACT TEXT MATCH (O(n) scan)                            │  │     │
│  │  │   for entry in self._entries.values():                           │  │     │
│  │  │       if entry.query_text.lower() == query_text.lower():         │  │     │
│  │  │           return entry with similarity=1.0, is_exact=True        │  │     │
│  │  │                                                                   │  │     │
│  │  │ PHASE 2: SEMANTIC SIMILARITY (HNSW search)                       │  │     │
│  │  │   raw_results = self._index.search(embedding, k=k*2)             │  │     │
│  │  │   # HNSW navigates hierarchical graph layers                     │  │     │
│  │  │   # Returns: [(item_id, cosine_similarity), ...]                 │  │     │
│  │  │                                                                   │  │     │
│  │  │ PHASE 3: FILTER & RANK                                           │  │     │
│  │  │   - Filter by threshold (similarity >= 0.85)                     │  │     │
│  │  │   - Filter by tenant_id                                          │  │     │
│  │  │   - Boost near-exact matches (+0.05)                             │  │     │
│  │  │   - Sort by final similarity                                     │  │     │
│  │  └──────────────────────────────────────────────────────────────────┘  │     │
│  │                                                                         │     │
│  │  Returns: [(item_id, 0.92, entry_metadata, is_exact=False)]            │     │
│  └───────┬────────────────────────────────────────────────────────────────┘     │
│          │                                                                       │
│          ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │               CACHE DATA RETRIEVAL (Back in CacheManager)               │     │
│  │                                                                         │     │
│  │  cache_key = f"{tenant_id}:{item_id}"  # "tenant123:abc123"            │     │
│  │  cache_result = self.get(cache_key)                                    │     │
│  │                                                                         │     │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │     │
│  │  │ TIERED LOOKUP:                                                    │  │     │
│  │  │                                                                   │  │     │
│  │  │ ① L1 Cache (In-Memory Dict)                                      │  │     │
│  │  │    entry = self.l1_cache.get(cache_key)                          │  │     │
│  │  │    if entry: return (entry, "L1")  # <1ms                        │  │     │
│  │  │                                                                   │  │     │
│  │  │ ② L2 Cache (Redis)                                               │  │     │
│  │  │    entry = self.l2_cache.get(cache_key)                          │  │     │
│  │  │    if entry:                                                      │  │     │
│  │  │        self.l1_cache.put(entry)  # Promote to L1                 │  │     │
│  │  │        return (entry, "L2")  # 5-10ms                            │  │     │
│  │  │                                                                   │  │     │
│  │  │ ③ L3 Cache (PostgreSQL) - if configured                          │  │     │
│  │  │    entry = self._database_lookup(cache_key)                      │  │     │
│  │  │    if entry:                                                      │  │     │
│  │  │        self.l1_cache.put(entry)  # Promote                       │  │     │
│  │  │        self.l2_cache.put(entry)  # Promote                       │  │     │
│  │  │        return (entry, "L3")  # 20-50ms                           │  │     │
│  │  └──────────────────────────────────────────────────────────────────┘  │     │
│  └───────┬────────────────────────────────────────────────────────────────┘     │
│          │                                                                       │
│          ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │                         RESPONSE CONSTRUCTION                           │     │
│  │                                                                         │     │
│  │  return SemanticSearchResult(                                          │     │
│  │      entry=entry,              # Full cached response                  │     │
│  │      similarity=0.92,          # How close the match was               │     │
│  │      hit_source="L1",          # Which cache tier                      │     │
│  │      hit_reason=SEMANTIC_MATCH,# Not exact, but similar                │     │
│  │      is_exact_match=False,                                             │     │
│  │      domain="coding",          # Classified domain                     │     │
│  │      threshold_used=0.85,      # Threshold that was applied            │     │
│  │  )                                                                     │     │
│  └───────────────────────────────────────────────────────────────────────┘     │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Semantic vs Exact Matching

### How Both Work Together

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    MATCHING STRATEGY IN UnifiedIndexManager                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Query: "How do I fix a Python bug?"                                            │
│                                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ STEP 1: EXACT MATCH CHECK (First Priority)                                │  │
│  │                                                                            │  │
│  │ def _find_exact_match(self, query_text, tenant_id):                       │  │
│  │     normalized = query_text.lower().strip()                               │  │
│  │     for full_id, entry in self._entries.items():                          │  │
│  │         if entry.query_text.lower().strip() == normalized:                │  │
│  │             if tenant_id is None or entry.tenant_id == tenant_id:         │  │
│  │                 return entry.item_id  # EXACT MATCH FOUND                 │  │
│  │     return None                                                            │  │
│  │                                                                            │  │
│  │ ✓ If exact match found: Return with similarity=1.0, is_exact=True         │  │
│  │ ✗ If no exact match: Proceed to semantic search                           │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                     │                                            │
│                                     ▼                                            │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ STEP 2: SEMANTIC SIMILARITY SEARCH (HNSW Algorithm)                       │  │
│  │                                                                            │  │
│  │ Query Embedding: [0.23, -0.45, 0.12, ..., 0.87]  (384 dimensions)         │  │
│  │                                                                            │  │
│  │ ┌─────────────────────────────────────────────────────────────────────┐   │  │
│  │ │                    HNSW INDEX STRUCTURE                              │   │  │
│  │ │                                                                      │   │  │
│  │ │  Layer 2 (sparse):     ●─────────●─────────●                        │   │  │
│  │ │                        │         │         │                        │   │  │
│  │ │  Layer 1 (medium):  ●──●──●──●──●──●──●──●──●                       │   │  │
│  │ │                     │  │  │  │  │  │  │  │  │                       │   │  │
│  │ │  Layer 0 (dense):   ●●●●●●●●●●●●●●●●●●●●●●●●●●●●                    │   │  │
│  │ │                          ▲                                          │   │  │
│  │ │                    Query enters here                                │   │  │
│  │ │                                                                      │   │  │
│  │ │  Search Process:                                                    │   │  │
│  │ │  1. Start at top layer with random entry point                      │   │  │
│  │ │  2. Greedily move to nearest neighbor (cosine similarity)           │   │  │
│  │ │  3. Drop to lower layer, repeat                                     │   │  │
│  │ │  4. At layer 0, explore ef neighbors for best matches               │   │  │
│  │ └─────────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                            │  │
│  │ Raw Results from HNSW:                                                    │  │
│  │   [("tenant123:abc123", 0.92),                                            │  │
│  │    ("tenant123:def456", 0.88),                                            │  │
│  │    ("tenant123:ghi789", 0.72)]   ← Below threshold, filtered out          │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                     │                                            │
│                                     ▼                                            │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ STEP 3: FILTERING & RANKING                                               │  │
│  │                                                                            │  │
│  │ for full_id, similarity in raw_results:                                   │  │
│  │     # Filter 1: Threshold check                                           │  │
│  │     if similarity < 0.85:  # Domain threshold                             │  │
│  │         continue  ← Skip low similarity                                   │  │
│  │                                                                            │  │
│  │     # Filter 2: Tenant isolation                                          │  │
│  │     entry = self._entries.get(full_id)                                    │  │
│  │     if tenant_id and entry.tenant_id != tenant_id:                        │  │
│  │         continue  ← Skip other tenants' data                              │  │
│  │                                                                            │  │
│  │     # Filter 3: Check for near-exact text match                           │  │
│  │     is_near_exact = entry.query_text.lower() == query_text.lower()        │  │
│  │     if is_near_exact:                                                     │  │
│  │         similarity += 0.05  # Boost score                                 │  │
│  │                                                                            │  │
│  │     results.append((item_id, similarity, entry, is_near_exact))           │  │
│  │                                                                            │  │
│  │ Final Results (sorted by similarity):                                     │  │
│  │   [("abc123", 0.92, entry_data, False)]                                   │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Comparison: Exact vs Semantic

| Aspect | Exact Match | Semantic Match |
|--------|-------------|----------------|
| **Method** | String comparison | Embedding cosine similarity |
| **Speed** | O(n) scan | O(log n) HNSW |
| **When Used** | Always checked first | If no exact match |
| **Similarity** | Always 1.0 | 0.0 to 1.0 |
| **Example** | "Python bug fix" = "python bug fix" | "Python bug fix" ≈ "How to debug Python" |

---

## 4. Intelligence Layer Optimizations

### How Each Component Optimizes the Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         INTELLIGENCE LAYER COMPONENTS                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ 1. DOMAIN CLASSIFIER (src/ml/domain_classifier.py)                        │  │
│  │                                                                            │  │
│  │ PURPOSE: Route queries to domain-specific thresholds                      │  │
│  │                                                                            │  │
│  │ ┌────────────────────────────────────────────────────────────────────┐    │  │
│  │ │  class KeyWordDomainClassifier:                                    │    │  │
│  │ │      domain_keywords = {                                           │    │  │
│  │ │          "coding": ["python", "javascript", "code", "function",    │    │  │
│  │ │                     "error", "bug", "git", "api", "database"],     │    │  │
│  │ │          "finance": ["stock", "market", "price", "investment"],    │    │  │
│  │ │          "healthcare": ["symptom", "disease", "doctor", "pain"],   │    │  │
│  │ │          "legal": ["law", "lawyer", "court", "contract"],          │    │  │
│  │ │      }                                                             │    │  │
│  │ │                                                                    │    │  │
│  │ │      def classify(self, query: str) -> str:                        │    │  │
│  │ │          # Count keyword matches per domain                        │    │  │
│  │ │          # Return domain with most matches, or "general"           │    │  │
│  │ └────────────────────────────────────────────────────────────────────┘    │  │
│  │                                                                            │  │
│  │ EXAMPLE:                                                                   │  │
│  │   Query: "How do I fix a Python bug in my code?"                          │  │
│  │   Matches: "python" ✓, "bug" ✓, "code" ✓ → 3 matches for "coding"         │  │
│  │   Result: domain = "coding"                                               │  │
│  │                                                                            │  │
│  │ OPTIMIZATION: Different domains need different precision levels           │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                     │                                            │
│              ## 5. Cache Miss Flow (Write Path)

### When Query Has No Match (Integrated LLM Fallback)

In Phase 9, the semantic cache integrates an automated LLM fallback. When a request misses the cache, the API router automatically queries the modular LLM service, stores the newly generated response asynchronously in the tiered cache, and returns it to the client.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     INTEGRATED LLM FALLBACK CACHE MISS FLOW                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Query: "Explain quantum entanglement simply"                                   │
│  Search Result: No match above threshold in L1/L2/L3                            │
│                                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ STEP 1: CACHE MISS DETECTED BY ROUTER                                     │  │
│  │                                                                            │  │
│  │ Router (src/api/routes/cache.py) intercepts the None cache result.         │  │
│  │ Instead of raising a 404, it invokes the built-in LLMService.              │  │
│  └───────┬───────────────────────────────────────────────────────────────────┘  │
│          │                                                                       │
│          ▼                                                                       │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ STEP 2: AUTOMATIC SERVICE LLM CALL (Gemini / OpenAI)                      │  │
│  │                                                                            │  │
│  │ response = await llm_service.generate_async(                              │  │
│  │     prompt=query_text,                                                    │  │
│  │     provider=config.LLM_PROVIDER  # "gemini"                              │  │
│  │ )                                                                         │  │
│  │                                                                            │  │
│  │ response_text = "Quantum entanglement is when two particles..."          │  │
│  └───────┬───────────────────────────────────────────────────────────────────┘  │
│          │                                                                       │
│          ▼                                                                       │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ STEP 3: ASYNCHRONOUS BACKEND STORAGE (put_semantic_async)                 │  │
│  │                                                                            │  │
│  │ Router triggers an asyncio.create_task() for cache storage:               │  │
│  │ cache_manager.put_semantic_async(                                         │  │
│  │     query_text="Explain quantum entanglement simply",                     │  │
│  │     response=response_text,                                               │  │
│  │     domain="general",                                                     │  │
│  │     metadata={"model": "gemini-pro", "generation_latency_ms": 780}        │  │
│  │ )                                                                         │  │
│  └───────┬───────────────────────────────────────────────────────────────────┘  │
│          │                                                                       │
│          ▼                                                                       │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ STEP 4: WRITE-THROUGH & GRAPH INDEXING                                    │  │
│  │                                                                            │  │
│  │ 1. Creates unique f"{tenant_id}:{query_hash}" cache key                   │  │
│  │ 2. Writes CacheEntry to L1 (Memory)                                       │  │
│  │ 3. Writes CacheEntry to L2 (Redis)                                        │  │
│  │ 4. Writes CacheEntry to L3 (PostgreSQL)                                   │  │
│  │ 5. Indexes the query_text & embedding into HNSW Index                     │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  RESULT: Response returned to client immediately with hit=False &                │
│          hit_reason="miss_llm_generated". Entry is now cached for future queries.│
│                                                                                  │
│  Next query: "Can you explain quantum entanglement in simple terms?"            │
│  → Embedding similarity: 0.94 with cached entry                                 │
│  → CACHE HIT! Returns in <1ms instead of 780ms                                  │
│  → Cost savings: ~100% saved                                                    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ 4. PREDICTIVE CACHE WARMER (src/ml/predictive_warmer.py)                  │  │
│  │                                                                            │  │
│  │ PURPOSE: Pre-load likely-to-be-needed items into L1 cache                 │  │
│  │                                                                            │  │
│  │ ┌────────────────────────────────────────────────────────────────────┐    │  │
│  │ │  class PredictiveCacheWarmer:                                      │    │  │
│  │ │      # Runs every 5 minutes (configurable)                         │    │  │
│  │ │      run_interval_seconds = 300                                    │    │  │
│  │ │                                                                    │    │  │
│  │ │      def warm_l1_cache(self, top_k=50):                           │    │  │
│  │ │          # 1. Scan L2 cache for hot items                         │    │  │
│  │ │          # 2. Sort by access_count                                │    │  │
│  │ │          # 3. Promote top-k to L1 (if not already there)          │    │  │
│  │ │                                                                    │    │  │
│  │ │  WARMING LOOP:                                                    │    │  │
│  │ │    L2 Keys → Filter (not in L1) → Sort by popularity → Promote   │    │  │
│  │ └────────────────────────────────────────────────────────────────────┘    │  │
│  │                                                                            │  │
│  │ OPTIMIZATION: Reduces L2 lookups by anticipating frequently accessed      │  │
│  │               items and loading them into faster L1 cache proactively     │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Intelligence Layer Impact on Query Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      HOW INTELLIGENCE OPTIMIZES EACH STEP                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  QUERY: "How do I handle Python exceptions properly?"                           │
│                                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ WITHOUT INTELLIGENCE LAYER                                                │  │
│  │                                                                            │  │
│  │ 1. Generate embedding ✓                                                   │  │
│  │ 2. Search with default threshold (0.85)                                   │  │
│  │ 3. Find match: "Python try-catch best practices" (similarity: 0.82)      │  │
│  │ 4. RESULT: MISS (0.82 < 0.85)                                            │  │
│  │ 5. Call LLM API → $0.002 cost, 800ms latency                             │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ WITH INTELLIGENCE LAYER                                                   │  │
│  │                                                                            │  │
│  │ 1. Generate embedding ✓                                                   │  │
│  │ 2. Domain Classifier: "python", "exceptions" → domain="coding"            │  │
│  │ 3. Adaptive Threshold: coding domain → threshold=0.85                     │  │
│  │    (same in this case, but healthcare would be 0.80)                      │  │
│  │ 4. Search: "Python try-catch best practices" (similarity: 0.82)          │  │
│  │ 5. RESULT: MISS (still below threshold for high-precision code domain)   │  │
│  │                                                                            │  │
│  │ BUT LATER...                                                              │  │
│  │ 6. Cost-Aware Policy stores the new response with high value score       │  │
│  │    (coding responses are expensive to generate correctly)                 │  │
│  │ 7. Predictive Warmer promotes it to L1 after 3 accesses                  │  │
│  │ 8. Next similar query → L1 HIT in <1ms instead of L2 (5-10ms)            │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Cache Miss Flow (Write Path)

### When Query Has No Match

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CACHE MISS FLOW                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Query: "Explain quantum entanglement simply"                                   │
│  Search Result: No match above threshold                                        │
│                                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ STEP 1: CACHE MISS DETECTED                                               │  │
│  │                                                                            │  │
│  │ CacheManager.get_semantic() returns None                                  │  │
│  │ Application must call external LLM API                                    │  │
│  └───────┬───────────────────────────────────────────────────────────────────┘  │
│          │                                                                       │
│          ▼                                                                       │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ STEP 2: EXTERNAL LLM CALL (Application Layer)                             │  │
│  │                                                                            │  │
│  │ response = await openai.chat.completions.create(                          │  │
│  │     model="gpt-4",                                                        │  │
│  │     messages=[{"role": "user", "content": query_text}]                    │  │
│  │ )                                                                         │  │
│  │ # Cost: $0.003, Latency: 1200ms                                          │  │
│  │                                                                            │  │
│  │ response_text = "Quantum entanglement is when two particles..."          │  │
│  └───────┬───────────────────────────────────────────────────────────────────┘  │
│          │                                                                       │
│          ▼                                                                       │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ STEP 3: STORE IN CACHE (put_semantic)                                     │  │
│  │                                                                            │  │
│  │ CacheManager.put_semantic(                                                │  │
│  │     query_text="Explain quantum entanglement simply",                     │  │
│  │     embedding=embedding,        # Already generated earlier               │  │
│  │     response=response_text,                                               │  │
│  │     tenant_id="tenant123",                                                │  │
│  │     domain="general",           # Classified as general science           │  │
│  │     metadata={                                                            │  │
│  │         "model": "gpt-4",                                                 │  │
│  │         "cost": 0.003,                                                    │  │
│  │         "latency_ms": 1200                                                │  │
│  │     }                                                                     │  │
│  │ )                                                                         │  │
│  └───────┬───────────────────────────────────────────────────────────────────┘  │
│          │                                                                       │
│          ▼                                                                       │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ STEP 4: WRITE-THROUGH TO CACHE TIERS                                      │  │
│  │                                                                            │  │
│  │ ┌──────────────────────────────────────────────────────────────────────┐  │  │
│  │ │ A) Generate Cache Key                                                │  │  │
│  │ │    query_hash = sha256("Explain quantum entanglement simply")[:16]  │  │  │
│  │ │    cache_key = f"tenant123:{query_hash}"                            │  │  │
│  │ └──────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                            │  │
│  │ ┌──────────────────────────────────────────────────────────────────────┐  │  │
│  │ │ B) Create CacheEntry                                                 │  │  │
│  │ │    entry = CacheEntry(                                              │  │  │
│  │ │        query_id=cache_key,                                          │  │  │
│  │ │        query_text=query_text,                                       │  │  │
│  │ │        embedding=embedding,                                         │  │  │
│  │ │        response=response_text,                                      │  │  │
│  │ │        metadata=metadata,                                           │  │  │
│  │ │        domain="general",                                            │  │  │
│  │ │    )                                                                │  │  │
│  │ └──────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                            │  │
│  │ ┌──────────────────────────────────────────────────────────────────────┐  │  │
│  │ │ C) Store in L1 (Memory)                                             │  │  │
│  │ │    self.l1_cache.put(entry)                                         │  │  │
│  │ │    # Immediate, <1ms                                                │  │  │
│  │ └──────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                            │  │
│  │ ┌──────────────────────────────────────────────────────────────────────┐  │  │
│  │ │ D) Store in L2 (Redis) - Write-Through                              │  │  │
│  │ │    self.l2_cache.put(entry)                                         │  │  │
│  │ │    # Async, 2-5ms                                                   │  │  │
│  │ └──────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                            │  │
│  │ ┌──────────────────────────────────────────────────────────────────────┐  │  │
│  │ │ E) Index in UnifiedIndexManager                                     │  │  │
│  │ │    self._index_manager.add(                                         │  │  │
│  │ │        item_id=query_hash,                                          │  │  │
│  │ │        embedding=embedding,                                         │  │  │
│  │ │        query_text=query_text,                                       │  │  │
│  │ │        tenant_id="tenant123",                                       │  │  │
│  │ │        domain="general",                                            │  │  │
│  │ │    )                                                                │  │  │
│  │ │    # Adds to HNSW graph for future similarity searches             │  │  │
│  │ └──────────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  RESULT: Entry now searchable for future similar queries                        │
│                                                                                  │
│  Next query: "Can you explain quantum entanglement in simple terms?"            │
│  → Embedding similarity: 0.94 with cached entry                                 │
│  → CACHE HIT! Returns in <1ms instead of 1200ms                                 │
│  → Cost savings: $0.003 saved                                                   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Code Walkthrough

### Key Functions Reference

| Function | File | Purpose |
|----------|------|---------|
| `get_semantic_async()` | cache_manager.py:646 | Entry point - generates embedding, calls sync search |
| `get_semantic()` | cache_manager.py:525 | Main search - domain classification, threshold selection, index search |
| `search_by_text()` | index_manager.py:259 | Combined exact + semantic search in HNSW |
| `search()` | index_manager.py:200 | Raw HNSW similarity search |
| `put_semantic()` | cache_manager.py:686 | Store entry in all tiers + index |
| `classify()` | domain_classifier.py:27 | Keyword-based domain detection |
| `get_threshold()` | adaptive_thresholds.py:17 | Domain-specific threshold lookup |
| `warm_l1_cache()` | predictive_warmer.py:53 | Background L2→L1 promotion |

### Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           COMPLETE SYSTEM FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│                            ┌─────────────────┐                                  │
│                            │   User Query    │                                  │
│                            │  "Fix Python    │                                  │
│                            │      bug"       │                                  │
│                            └────────┬────────┘                                  │
│                                     │                                            │
│                                     ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         EMBEDDING SERVICE                                 │   │
│  │                    sentence-transformers                                  │   │
│  │              "Fix Python bug" → [0.23, -0.45, ...]                       │   │
│  └──────────────────────────────────┬───────────────────────────────────────┘   │
│                                     │                                            │
│               ┌─────────────────────┼─────────────────────┐                     │
│               ▼                     ▼                     ▼                     │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐        │
│  │ DOMAIN CLASSIFIER  │  │ THRESHOLD MANAGER  │  │  UNIFIED INDEX     │        │
│  │                    │  │                    │  │                    │        │
│  │ Keywords detected: │  │ Domain: "coding"   │  │ HNSW Search:       │        │
│  │ "python", "bug"    │  │ Threshold: 0.85    │  │ 1. Exact match?    │        │
│  │ → domain="coding"  │  │                    │  │ 2. Cosine search   │        │
│  └────────────────────┘  └────────────────────┘  │ 3. Filter results  │        │
│                                                   └──────────┬─────────┘        │
│                                                              │                   │
│                              ┌────────────────────────────────┘                  │
│                              ▼                                                   │
│                    ┌───────────────────┐                                        │
│                    │  Match Found?     │                                        │
│                    │  sim >= 0.85      │                                        │
│                    └─────────┬─────────┘                                        │
│                              │                                                   │
│               ┌──────────────┴──────────────┐                                   │
│               │ YES                         │ NO                                │
│               ▼                             ▼                                   │
│  ┌─────────────────────────┐   ┌─────────────────────────┐                     │
│  │    CACHE DATA LOOKUP    │   │     CACHE MISS          │                     │
│  │                         │   │                         │                     │
│  │  ① L1 (Memory) <1ms    │   │  → Call LLM API         │                     │
│  │  ② L2 (Redis) 5-10ms   │   │  → Store response       │                     │
│  │  ③ L3 (Postgres) 20ms  │   │  → Index for future     │                     │
│  └───────────┬─────────────┘   └───────────┬─────────────┘                     │
│              │                              │                                   │
│              ▼                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                           RESPONSE TO USER                               │   │
│  │                                                                          │   │
│  │  Cache Hit: <5ms, $0 cost                                               │   │
│  │  Cache Miss: ~1000ms, ~$0.002 cost                                      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    BACKGROUND OPTIMIZATION (Async)                       │   │
│  │                                                                          │   │
│  │  • Cost-Aware Policy: Tracks value of cached items                      │   │
│  │  • Predictive Warmer: Promotes hot L2 items to L1 every 5 min           │   │
│  │  • Eviction: Removes low-value items when memory is full                │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Summary

### Key Takeaways

1. **Embedding First**: Every query is converted to a 384-dimensional vector using sentence-transformers

2. **Two-Phase Search**: 
   - Phase 1: Exact text match (fast, O(n))
   - Phase 2: HNSW semantic similarity (O(log n))

3. **Tiered Storage**: Index finds WHAT to return, cache tiers store WHERE to get the data
   - L1 (Memory): <1ms
   - L2 (Redis): 5-10ms  
   - L3 (Postgres): 20-50ms

4. **Intelligence Layer Optimizations**:
   - **Domain Classifier**: Routes queries to appropriate precision levels
   - **Adaptive Thresholds**: Legal=0.90, Coding=0.85, General=0.70
   - **Cost-Aware Eviction**: Keeps expensive-to-generate, frequently-accessed items
   - **Predictive Warming**: Promotes hot items to L1 proactively

5. **Tenant Isolation**: All searches filtered by tenant_id prefix

---

**Document Created:** March 21, 2026  
**Version:** 1.0

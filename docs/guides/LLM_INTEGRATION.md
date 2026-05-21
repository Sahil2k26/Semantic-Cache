# Modular LLM Integration Guide

This guide describes how the Semantic Cache integrates downstream Large Language Models (LLMs) to automatically handle cache misses, support streaming responses, and capture token generation timings.

---

## 🗺️ Architectural Context

When a client queries the semantic cache, the request follows a similarity search path. If a cache miss occurs (no entry satisfies the similarity threshold), the system automatically intercepts the miss, generates the response via a modular LLM adapter, writes it asynchronously to L1/L2/L3 cache tiers, and returns the result.

```
                  ┌───────────────────────────────┐
                  │ Client: GET /semantic/search  │
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                     [ 🔎 Similarity Search ]
                                  │
                     ┌────────────┴────────────┐
                     │                         │
            (Cache Hit > Threshold)   (Cache Miss)
                     │                         │
                     ▼                         ▼
             [ Return Cache ]        [ 🤖 LLMService ]
                                               │
                                               ▼
                                      [ Generate Response ]
                                               │
                                     ┌─────────┴─────────┐
                                     │                   │
                                (Flat Text)         (SSE Stream)
                                     │                   │
                                     ▼                   ▼
                               [ put_semantic ]   [ Timing Recorded ]
                                     │                   │
                                     ▼                   ▼
                              [ Async Write ]    [ Timing Playback ]
```

---

## 🧩 LLMService Component

- **File Path:** [service.py](file:///c:/Coding/Project%20Btech/Semantic-Cache/src/llm/service.py)
- **Class:** `LLMService`

The `LLMService` implements a unified, thread-safe asynchronous manager supporting pluggable adapters.

### Supported Providers
1. **Google Gemini (Default):** Calls the standard Google Generative Language REST API (`/v1beta/models/gemini-pro:generateContent` and `streamGenerateContent`).
2. **OpenAI (Stub):** Pluggable placeholder driver supporting seamless integration with standard OpenAI clients.

### Interface Details
```python
class LLMService:
    async def generate_response(
        self, 
        prompt: str, 
        provider: Optional[str] = None
    ) -> str:
        """
        Generates a flat, non-streaming text response from the LLM.
        """
        ...

    async def generate_stream(
        self, 
        prompt: str, 
        provider: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Yields tokens/chunks from the LLM via SSE.
        """
        ...
```

---

## 🔄 Automatic Fallback Loop

When executing a semantic search request, client applications do not need to construct backend fallback blocks:

```python
# From src/api/routes/cache.py
@router.post("/semantic/search")
async def search_semantic_cache(body: SemanticSearchRequest):
    # 1. Search the tiered cache
    result = await cache_manager.get_semantic(body.query, threshold=body.threshold)
    
    if result:
        return SemanticSearchResponse(
            hit=True,
            hit_reason="semantic_match",
            response=result.response,
            similarity=result.similarity,
            latency_ms=timer.elapsed()
        )
        
    # 2. Fallback on Cache Miss
    llm_response = await llm_service.generate_response(body.query)
    
    # 3. Asynchronously store the generated response in the background
    asyncio.create_task(
        cache_manager.put_semantic_async(
            query_text=body.query,
            response=llm_response,
            domain="general",
            metadata={"model": "gemini-pro"}
        )
    )
    
    return SemanticSearchResponse(
        hit=False,
        hit_reason="miss_llm_generated",
        response=llm_response,
        similarity=0.0
    )
```

---

## ⚡ SSE Token Stream Recording & Playback

Streaming caches traditionally face a dilemma: *either return flat text immediately (ruining the streaming UX) or re-stream with generic intervals (ruining authentic speeds).*

We solve this through a **Timing-Authentic Streaming Cache**:

### 1. Timing-Authentic Recording (First-time Stream)
When an LLM stream is fetched for the first time, a special recorder captures both the token text and the exact interval delay since the previous token:

```json
[
  {"text": "Quantum ", "delay_ms": 12},
  {"text": "physics ", "delay_ms": 18},
  {"text": "is ", "delay_ms": 15}
]
```
These arrays are saved in PostgreSQL as JSON alongside the completed text.

### 2. Authentic Playback (Replay on Hit)
On subsequent cached stream hits, the SSE router reads the stored timing array and streams tokens back to the client, replicating the original generation latency and behavior.

"""Cache operations endpoints with semantic search integration."""

import time
import json
from fastapi import APIRouter, Depends, Path, Query, Request, HTTPException, status, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Any, List
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from ..schemas import (
    CachePutRequest, CachePutResponse, CacheGetResponse,
    CacheBatchRequest, CacheBatchResponse, CacheBatchResult
)
from ..auth.jwt import get_current_user, get_tenant_id, TokenPayload
from ..middleware.error import CacheNotFoundException
from src.cache.base import CacheEntry
from src.cache.streaming import StreamingCache

router = APIRouter()


# ============================================================================
# Semantic Cache Request/Response Models
# ============================================================================

class CachePutBody(BaseModel):
    """Request body for PUT /cache/{key}."""
    value: Any = Field(..., description="Value to store in the cache (any JSON-serialisable data)")
    domain: Optional[str] = Field(None, description="Domain hint for threshold selection")
    metadata: Optional[dict] = Field(None, description="Additional metadata to attach to the entry")


class SemanticCacheRequest(BaseModel):
    """Request for semantic cache operations."""
    query: str = Field(..., description="Query text to cache or search")
    response: Optional[Any] = Field(None, description="Response to cache (for PUT)")
    domain: Optional[str] = Field(None, description="Domain for threshold selection")
    threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Similarity threshold")
    metadata: Optional[dict] = Field(None, description="Additional metadata")


class SemanticCacheResponse(BaseModel):
    """Response from semantic cache operations."""
    query: str
    response: Optional[Any]
    hit: bool
    similarity: float = 0.0
    cache_level: str = "none"
    hit_reason: str = "none"  # "exact_match", "semantic_match", "miss"
    domain: str = "general"
    threshold_used: float = 0.85
    latency_ms: float = 0.0
    embedding_generated: bool = False


class SubQueryResponse(BaseModel):
    id: str
    text: str
    hit: bool
    response: Optional[Any]

class SemanticCacheMultiResponse(BaseModel):
    """Response from multi-intent semantic cache operations."""
    query: str
    normalized_query: str
    sub_queries: List[SubQueryResponse]
    all_hit: bool
    synthesized_response: Optional[Any]
    hit_ratio: float
    latency_ms: float = 0.0


class SemanticGetOrComputeRequest(BaseModel):
    """Request for get-or-compute pattern."""
    query: str = Field(..., description="Query text")
    domain: Optional[str] = Field(None, description="Domain classification")
    threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    # Note: compute_fn is provided server-side, not in request


# ============================================================================
# Standard Cache Endpoints (Backward Compatible)
# ============================================================================

@router.get("/{key}", response_model=CacheGetResponse)
async def get_cache(
    request: Request,
    key: str = Path(..., description="Cache key"),
    current_user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Retrieve value from cache by exact key."""
    cache_manager = request.app.state.cache_manager if request and hasattr(request.app.state, 'cache_manager') else None
    
    if cache_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache manager not available"
        )
    
    cache_key = f"{tenant_id}:{key}"
    start_time = time.time()
    
    result = cache_manager.get(cache_key)
    latency_ms = (time.time() - start_time) * 1000
    
    if result is None:
        raise CacheNotFoundException(f"Key '{key}' not found in cache")
    
    entry, source = result
    
    ttl_remaining = None
    if cache_manager.config.l1_config.ttl_seconds:
        age = time.time() - entry.created_at
        remaining = cache_manager.config.l1_config.ttl_seconds - age
        ttl_remaining = max(0, int(remaining))
    
    return CacheGetResponse(
        key=key,
        value=entry.response,
        hit=True,
        cache_level=("l1" if source == "L1" else "l2"),
        latency_ms=round(latency_ms, 2),
        ttl_remaining_seconds=ttl_remaining
    )


@router.put("/{key}", response_model=CachePutResponse, status_code=201)
async def put_cache(
    request: Request,
    key: str = Path(..., description="Cache key"),
    body: CachePutBody = ...,
    current_user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Cache a value with automatic embedding generation.

    Stores `body.value` under `key` with real sentence-transformer embeddings,
    enabling semantic similarity search for future lookups.
    """
    cache_manager = request.app.state.cache_manager if hasattr(request.app.state, 'cache_manager') else None
    embedding_service = getattr(request.app.state, 'embedding_service', None)
    index_manager = getattr(request.app.state, 'index_manager', None)
    domain_classifier = getattr(request.app.state, 'domain_classifier', None)

    if cache_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache manager not available"
        )

    value = body.value
    cache_key = f"{tenant_id}:{key}"

    # Detect domain (body override wins, then classifier, then default)
    domain = body.domain or "general"
    if not body.domain and domain_classifier:
        try:
            domain = domain_classifier.classify(key)
        except Exception:
            pass

    # Generate real embedding if service available
    embedding = None
    embedding_dim = 384  # Default dimension

    if embedding_service:
        try:
            embedding_record = await embedding_service.embed_text(key)
            embedding = embedding_record.embedding
            embedding_dim = len(embedding)
        except Exception as e:
            import logging
            logging.warning(f"Embedding generation failed, using placeholder: {e}")

    # Fall back to placeholder if no embedding generated
    if embedding is None:
        embedding = [0.0] * embedding_dim

    # Build entry metadata
    entry_metadata = {"source": "api", "object": "cache_put", "has_real_embedding": embedding_service is not None}
    if body.metadata:
        entry_metadata.update(body.metadata)

    # Create cache entry with real embedding
    entry = CacheEntry(
        query_id=cache_key,
        query_text=key,
        embedding=embedding,
        response=value,
        metadata=entry_metadata,
        domain=domain
    )
    entry.calculate_memory(embedding_dim)

    # Store in cache
    success = cache_manager.put(entry)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cache value"
        )

    # Also add to unified index for semantic search
    if index_manager and embedding_service:
        try:
            index_manager.add(
                item_id=cache_key,
                embedding=embedding,
                query_text=key,
                tenant_id=tenant_id,
                domain=domain,
                metadata={"source": "api"}
            )
        except Exception as e:
            import logging
            logging.warning(f"Failed to add to index: {e}")

    return CachePutResponse(
        key=key,
        cached=True,
        cache_level="l2" if cache_manager.config.strategy.name == "WRITE_THROUGH" else "l1",
        size_bytes=int(entry.memory_estimate)
    )


@router.delete("/{key}", status_code=204)
async def delete_cache(
    request: Request,
    key: str = Path(..., description="Cache key"),
    current_user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Delete cached value."""
    if request is None:
        raise HTTPException(status_code=400, detail="Request required")
        
    cache_manager = request.app.state.cache_manager if hasattr(request.app.state, 'cache_manager') else None
    index_manager = getattr(request.app.state, 'index_manager', None)
    
    if cache_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache manager not available"
        )
    
    cache_key = f"{tenant_id}:{key}"
    
    # Delete from cache
    success = cache_manager.delete(cache_key)
    
    # Also delete from index
    if index_manager:
        try:
            index_manager.delete(cache_key, tenant_id)
        except Exception:
            pass
    
    if not success:
        raise CacheNotFoundException(f"Key '{key}' not found or deletion failed")


@router.post("/batch", response_model=CacheBatchResponse)
async def batch_get_cache(
    request: Request,
    body: Optional[CacheBatchRequest] = None,
    current_user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Get multiple cache values in one request."""
    if request is None:
        raise HTTPException(status_code=400, detail="Request required")
        
    cache_manager = request.app.state.cache_manager if hasattr(request.app.state, 'cache_manager') else None
    
    if cache_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache manager not available"
        )
    
    if body is None or not body.keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No keys provided"
        )
    
    results = []
    hit_count = 0
    miss_count = 0
    
    for key in body.keys:
        cache_key = f"{tenant_id}:{key}"
        result = cache_manager.get(cache_key)
        
        if result is not None:
            entry, _source = result
            results.append(CacheBatchResult(key=key, value=entry.response, hit=True))
            hit_count += 1
        else:
            results.append(CacheBatchResult(key=key, value=None, hit=False))
            miss_count += 1
    
    hit_rate = hit_count / len(body.keys) if body.keys else 0.0
    
    return CacheBatchResponse(
        results=results,
        hit_count=hit_count,
        miss_count=miss_count,
        hit_rate=round(hit_rate, 3)
    )


@router.delete("", status_code=200)
async def clear_cache(
    request: Request,
    current_user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Clear all cache (admin only)."""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    if request is None:
        raise HTTPException(status_code=400, detail="Request required")
        
    cache_manager = request.app.state.cache_manager if hasattr(request.app.state, 'cache_manager') else None
    index_manager = getattr(request.app.state, 'index_manager', None)
    
    if cache_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache manager not available"
        )
    
    success = cache_manager.clear()
    
    # Also clear index
    if index_manager:
        try:
            index_manager.clear(tenant_id)
        except Exception:
            pass
    
    if success is False:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )
    
    return {
        "cleared": True,
        "message": "All cache entries cleared"
    }


# ============================================================================
# Semantic Cache Endpoints (New)
# ============================================================================

@router.post("/semantic", response_model=SemanticCacheResponse)
async def semantic_cache_put(
    request: Request,
    body: SemanticCacheRequest,
    current_user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Store an item with full semantic indexing.
    
    This endpoint generates embeddings and indexes the item for
    semantic similarity search. Use this when you want items to be
    findable via similar queries, not just exact key matches.
    """
    if request is None:
        raise HTTPException(status_code=400, detail="Request required")
        
    cache_manager = request.app.state.cache_manager if hasattr(request.app.state, 'cache_manager') else None
    embedding_service = getattr(request.app.state, 'embedding_service', None)
    
    if cache_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache manager not available"
        )
    
    if embedding_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding service not available"
        )
    
    if body.response is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Response field is required for PUT operation"
        )
    
    start_time = time.time()
    
    # Use async put_semantic method
    success = await cache_manager.put_semantic_async(
        query_text=body.query,
        response=body.response,
        tenant_id=tenant_id,
        domain=body.domain,
        metadata=body.metadata,
    )
    
    latency_ms = (time.time() - start_time) * 1000
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cache value"
        )
    
    return SemanticCacheResponse(
        query=body.query,
        response=body.response,
        hit=False,  # This is a PUT, not a GET
        similarity=1.0,
        cache_level="l1",
        hit_reason="stored",
        domain=body.domain or "general",
        threshold_used=body.threshold or 0.85,
        latency_ms=round(latency_ms, 2),
        embedding_generated=True
    )


@router.post("/semantic/search", response_model=SemanticCacheResponse)
async def semantic_cache_search(
    request: Request,
    body: SemanticCacheRequest,
    current_user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Search cache by semantic similarity.
    
    This is the primary endpoint for semantic cache lookups. It:
    1. Generates an embedding for your query
    2. Searches for cached items with similar embeddings
    3. Returns the best match if similarity exceeds threshold
    
    Use domain-specific thresholds for better precision:
    - medical/legal: 0.90-0.95 (high precision)
    - general: 0.85 (balanced)
    - ecommerce: 0.75-0.80 (broad matching)
    """
    if request is None:
        raise HTTPException(status_code=400, detail="Request required")
        
    cache_manager = request.app.state.cache_manager if hasattr(request.app.state, 'cache_manager') else None
    
    if cache_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache manager not available"
        )
    
    start_time = time.time()
    
    # Use semantic search
    result = await cache_manager.get_semantic_async(
        query_text=body.query,
        tenant_id=tenant_id,
        domain=body.domain,
        threshold=body.threshold,
    )
    
    latency_ms = (time.time() - start_time) * 1000
    
    if result and result.entry:
        return SemanticCacheResponse(
            query=body.query,
            response=result.entry.response,
            hit=True,
            similarity=round(result.similarity, 4),
            cache_level=result.hit_source.lower(),
            hit_reason="exact_match" if result.is_exact_match else "semantic_match",
            domain=result.domain,
            threshold_used=result.threshold_used,
            latency_ms=round(latency_ms, 2),
            embedding_generated=True
        )
    
    llm_service = getattr(request.app.state, 'llm_service', None)
    
    if llm_service and llm_service.api_key:
        generated_response = await llm_service.generate_response(body.query)
        
        if generated_response and not generated_response.startswith("Error:"):
            # Cache the generated response
            await cache_manager.put_semantic_async(
                query_text=body.query,
                response=generated_response,
                tenant_id=tenant_id,
                domain=body.domain,
                metadata={"source": "llm_generated"}
            )
            
            return SemanticCacheResponse(
                query=body.query,
                response=generated_response,
                hit=False,
                similarity=0.0,
                cache_level="l1",
                hit_reason="miss_llm_generated",
                domain=body.domain or "general",
                threshold_used=body.threshold or 0.85,
                latency_ms=round((time.time() - start_time) * 1000, 2),
                embedding_generated=True
            )
    
    return SemanticCacheResponse(
        query=body.query,
        response=None,
        hit=False,
        similarity=0.0,
        cache_level="none",
        hit_reason="miss",
        domain=body.domain or "general",
        threshold_used=body.threshold or 0.85,
        latency_ms=round(latency_ms, 2),
        embedding_generated=True
    )


@router.post("/semantic/multi/search", response_model=SemanticCacheMultiResponse)
async def semantic_cache_multi_search(
    request: Request,
    body: SemanticCacheRequest,
    current_user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Search cache utilizing automatic query decomposition for multi-intent queries.
    """
    if request is None:
        raise HTTPException(status_code=400, detail="Request required")
        
    cache_manager = request.app.state.cache_manager if hasattr(request.app.state, 'cache_manager') else None
    
    if cache_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache manager not available"
        )
    
    start_time = time.time()
    
    result = await cache_manager.get_semantic_multi_async(
        query_text=body.query,
        tenant_id=tenant_id,
        domain=body.domain,
        threshold=body.threshold,
    )
    
    latency_ms = (time.time() - start_time) * 1000
    
    sub_queries = [
        SubQueryResponse(
            id=sq["id"],
            text=sq["text"],
            hit=sq["hit"],
            response=sq["response"]
        ) for sq in result["sub_queries"]
    ]
    
    return SemanticCacheMultiResponse(
        query=result["original_query"],
        normalized_query=result["normalized_query"],
        sub_queries=sub_queries,
        all_hit=result["all_hit"],
        synthesized_response=result["synthesized_response"],
        hit_ratio=result["hit_ratio"],
        latency_ms=round(latency_ms, 2)
    )

@router.get("/semantic/stats")
async def get_semantic_stats(
    request: Request,
    current_user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Get semantic cache statistics."""
    if request is None:
        raise HTTPException(status_code=400, detail="Request required")
        
    cache_manager = request.app.state.cache_manager if hasattr(request.app.state, 'cache_manager') else None
    
    if cache_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache manager not available"
        )
    
    semantic_stats = cache_manager.get_semantic_stats()
    combined_stats = cache_manager.get_combined_stats()
    
    return {
        "semantic": semantic_stats,
        "cache": combined_stats,
        "tenant_id": tenant_id
    }

@router.post("/semantic/stream")
async def semantic_cache_stream(
    request: Request,
    body: SemanticCacheRequest,
    current_user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Look up stream cache; if missed, pretend to generate and cache stream tokens.
    """
    if request is None:
        raise HTTPException(status_code=400, detail="Request required")
        
    cache_manager = getattr(request.app.state, 'cache_manager', None)
    if not cache_manager:
        raise HTTPException(status_code=503, detail="Cache disabled")
        
    stream_cache = StreamingCache(cache_manager)
    query_key = body.query
    
    # Try hit
    cached_stream = await stream_cache.get_stream(query_key)
    if cached_stream:
        return StreamingResponse(
            cached_stream, 
            media_type="text/event-stream",
            headers={"X-Cache-Status": "HIT"}
        )
        
    # Miss -> generate
    llm_service = getattr(request.app.state, 'llm_service', None)
    
    if llm_service and llm_service.api_key:
        generator = stream_cache.stream_and_cache(
            query_key, 
            llm_service.generate_stream(query_key), 
            body.metadata or {"source": "llm_generated"}
        )
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={"X-Cache-Status": "MISS"}
        )
    else:
        async def generate_mock_stream():
            yield "LLM service not configured. Could not generate response."
            
        generator = stream_cache.stream_and_cache(query_key, generate_mock_stream(), body.metadata or {})
        return StreamingResponse(
            generator, 
            media_type="text/event-stream",
            headers={"X-Cache-Status": "MISS"}
        )

from src.api.models import ChatRequest, Message

@router.post("/chat")
async def chat(
    req: Request,
    body: ChatRequest,
    x_conversation_id: Optional[str] = Header(None),
    x_conversation_history: Optional[str] = Header(None),
    current_user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Stateless, context-aware smart chat routing endpoint.
    Uses local LLM for context query rewriting and intent decomposition.
    """
    if req is None:
        raise HTTPException(status_code=400, detail="Request required")
        
    cache_manager = getattr(req.app.state, 'cache_manager', None)
    if not cache_manager:
        raise HTTPException(status_code=503, detail="Cache disabled")
        
    if not hasattr(req.app.state, 'smart_router'):
        from src.cache.context import SmartCacheRouter
        embedder = getattr(cache_manager, '_embedding_service', None)
        req.app.state.smart_router = SmartCacheRouter(cache_manager, embedder)
        
    router_instance = req.app.state.smart_router
    
    # 1. Resolve conversation history: prioritize body.history, fallback to header
    history = body.history
    if not history and x_conversation_history:
        try:
            raw_history = json.loads(x_conversation_history)
            if isinstance(raw_history, list):
                history = [Message(role=item.get("role", "user"), content=item.get("content", "")) for item in raw_history]
        except Exception:
            pass
            
    # Resolve conversation_id (context_id)
    conversation_id = body.context_id or x_conversation_id

    # Resolve tenant_id
    resolved_tenant_id = body.tenant_id if body.tenant_id and body.tenant_id != "default" else tenant_id
    
    llm_service = getattr(req.app.state, 'llm_service', None)
    
    # 2. Invoke SmartCacheRouter.handle_chat statelessly
    cache_result = await router_instance.handle_chat(
        query=body.query,
        history=history,
        context_id=conversation_id,  # Ignored for lookup inside router
        tenant_id=resolved_tenant_id,
        domain=body.domain or "general",
        metadata=body.metadata,
        llm_service=llm_service
    )
    
    return {
        "response": cache_result.get("response"),
        "cached": cache_result.get("hit", False),
        "source": cache_result.get("source", "llm_generated"),
        "rewritten_query": cache_result.get("rewritten_query"),
        "sub_queries": cache_result.get("sub_queries")
    }


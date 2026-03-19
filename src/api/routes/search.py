"""Search and similarity endpoints."""

import sys
import os
import time
from fastapi import APIRouter, Depends, Request, HTTPException, status
from typing import Optional, List

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from ..schemas import SearchRequest, SearchResponse, SearchResult
from ..auth.jwt import get_current_user, get_tenant_id, TokenPayload
from src.embedding.service import EmbeddingService
from src.embedding.base import EmbeddingProviderType
from src.similarity.service import SimilaritySearchService
from src.similarity.base import SimilarityMetric, SimilaritySearchRequest as SimilarityReq, DomainType

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search_cache(
    request: SearchRequest,
    http_request: Request = None,
    current_user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Find semantically similar cached queries."""
    # Get services from app state
    embedding_service = http_request.app.state.embedding_service if hasattr(http_request.app.state, 'embedding_service') else None
    similarity_service = http_request.app.state.similarity_service if hasattr(http_request.app.state, 'similarity_service') else None
    cache_manager = http_request.app.state.cache_manager if hasattr(http_request.app.state, 'cache_manager') else None
    
    if embedding_service is None or similarity_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding or similarity service not available"
        )
    
    try:
        # Generate embedding for query
        start_time = time.time()
        
        embedding_record = await embedding_service.embed_text(request.query)
        embedding = embedding_record.embedding
        
        # Search for similar items in similarity service
        metric = SimilarityMetric(request.metric) if request.metric in [m.value for m in SimilarityMetric] else SimilarityMetric.COSINE
        
        # Phase 4 Intelligence: Adaptive Threshold & Domain Classification
        domain_classifier = getattr(http_request.app.state, 'domain_classifier', None)
        threshold_manager = getattr(http_request.app.state, 'adaptive_thresholds', None)
        
        domain_str = "general"
        if domain_classifier:
            domain_str = domain_classifier.classify(request.query)
            
        # Use adaptive threshold unless user explicitly provided one that differs from default (assuming 0.75 default)
        # For simplicity, if threshold manager exists, we override the default fallback
        final_threshold = request.threshold
        if threshold_manager and (request.threshold == 0.75 or request.threshold is None):
            final_threshold = threshold_manager.get_threshold(domain_str)

        search_req = SimilarityReq(
            query_embedding=embedding,
            query_id=f"search_{int(time.time() * 1000)}",
            query_text=request.query,
            metric=metric,
            threshold=final_threshold,
            top_k=request.top_k,
            domain=DomainType.GENERAL # Enum is used by base, but we apply threshold immediately
        )
        
        search_result = similarity_service.search(search_req)
        
        # Convert similarity results to SearchResult objects
        results = []
        if search_result and search_result.matches:
            for match in search_result.matches:
                # Try to get cached value from cache manager
                cached_value = None
                cache_level = "none"
                
                if cache_manager is not None:
                    cache_entry = cache_manager.get(f"{tenant_id}:{match.candidate_id}")
                    if cache_entry:
                        cached_value = cache_entry[0].response
                        cache_level = cache_entry[1]
                
                results.append(SearchResult(
                    key=match.candidate_id,
                    similarity=round(match.similarity, 4),
                    value=cached_value,
                    cache_level=cache_level
                ))
        
        search_time = (time.time() - start_time) * 1000
        
        return SearchResponse(
            query=request.query,
            metric=request.metric,
            results=results,
            count=len(results),
            search_time_ms=round(search_time, 2)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.post("/similarity/embedding")
async def embedding_search(
    query: str,
    top_k: int = 10,
    threshold: float = 0.75,
    http_request: Request = None,
    current_user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Generate embedding and find similar cached items."""
    # Get services from app state
    embedding_service = http_request.app.state.embedding_service if hasattr(http_request.app.state, 'embedding_service') else None
    similarity_service = http_request.app.state.similarity_service if hasattr(http_request.app.state, 'similarity_service') else None
    cache_manager = http_request.app.state.cache_manager if hasattr(http_request.app.state, 'cache_manager') else None
    
    if embedding_service is None or similarity_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding or similarity service not available"
        )
    
    try:
        # Generate embedding
        start_time = time.time()
        
        embedding_record = await embedding_service.embed_text(query)
        embedding = embedding_record.embedding
        embedding_time = (time.time() - start_time) * 1000
        
        # Search for similar items
        search_req = SimilarityReq(
            query_embedding=embedding,
            query_id=f"embed_{int(time.time() * 1000)}",
            query_text=query,
            metric=SimilarityMetric.COSINE,
            threshold=threshold,
            top_k=top_k,
            domain=DomainType.GENERAL
        )
        
        search_result = similarity_service.search(search_req)
        
        # Build similar items list
        similar_items = []
        if search_result and search_result.matches:
            for match in search_result.matches:
                cached_value = None
                
                if cache_manager is not None:
                    cache_entry = cache_manager.get(f"{tenant_id}:{match.candidate_id}")
                    if cache_entry:
                        cached_value = cache_entry[0].response
                
                similar_items.append({
                    "key": match.candidate_id,
                    "similarity": round(match.similarity, 4),
                    "value": cached_value,
                    "rank": match.rank
                })
        
        search_time = (time.time() - start_time) * 1000
        
        return {
            "text": query,
            "embedding_dimension": len(embedding),
            "embedding_time_ms": round(embedding_time, 2),
            "similar_items": similar_items,
            "count": len(similar_items),
            "search_time_ms": round(search_time, 2),
            "model": embedding_record.model
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding search failed: {str(e)}"
        )

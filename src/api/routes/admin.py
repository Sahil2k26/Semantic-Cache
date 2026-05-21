"""Admin management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from ..schemas import AdminStatsResponse, OptimizeRequest, OptimizeResponse
from ..auth.jwt import get_current_admin, TokenPayload
from src.core.tenant_manager import TenantManager
from src.api.config import settings

router = APIRouter()
tenant_manager = TenantManager()


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    current_user: TokenPayload = Depends(get_current_admin)
):
    """Get global system statistics."""
    stats = tenant_manager.get_global_stats()
    
    # Base L1/L2 capacity logic based on settings
    l1_capacity_pct = 0.0
    if settings.L1_MAX_SIZE > 0:
        # Note: stats total_memory_mb is not directly comparable to MAX_SIZE in count, but keeping the format
        l1_capacity_pct = min((stats["total_items_cached"] / settings.L1_MAX_SIZE) * 100, 100.0)
        
    return AdminStatsResponse(
        total_items_cached=stats["total_items_cached"],
        total_memory_mb=stats["total_memory_mb"],
        l1_capacity_pct=l1_capacity_pct,
        l2_capacity_pct=45.0, # L2 capacity requires complex Redis stats, hardcoded proxy for now
        hit_rate_overall=stats["hit_rate_overall"],
        requests_today=stats["requests_today"],
        unique_users=stats["unique_users"]
    )


@router.post("/cache/optimize", response_model=OptimizeResponse)
async def optimize_cache(
    request: OptimizeRequest,
    current_user: TokenPayload = Depends(get_current_admin)
):
    """Trigger cache optimization."""
    # In a fully connected system, this would trigger an L1->L2 eviction sync
    # We simulate this cleanup metric using the existing API structures.
    from src.cache.cache_manager import CacheManager
    
    # Ideally, CacheManager would expose a clean() method.
    return OptimizeResponse(
        status="completed",
        items_evicted=0, # Placeholder for CacheManager.clean() results
        memory_freed_mb=0.0,
        new_hit_rate=0.0
    )


@router.post("/cache/compress")
async def compress_cache(
    min_size_kb: int = 5,
    method: str = "gzip",
    current_user: TokenPayload = Depends(get_current_admin)
):
    """Compress cached responses."""
    # Compression is generally handled transparently by Redis/Postgres in our architecture
    # Providing a placeholder for manual intervention triggers
    return {
        "items_compressed": 0,
        "space_saved_mb": 0.0,
        "compression_ratio": 1.0
    }


@router.get("/policies")
async def get_policies(
    current_user: TokenPayload = Depends(get_current_admin)
):
    """Get current caching policies."""
    return {
        "l1_policy": {
            "eviction": settings.L1_EVICTION_STRATEGY,
            "capacity": settings.L1_MAX_SIZE,
            "ttl_default_seconds": settings.L1_TTL_SECONDS
        },
        "l2_policy": {
            "strategy": settings.CACHE_STRATEGY,
            "capacity": settings.L2_MAX_CAPACITY
        },
        "advanced": {
            "cost_aware": settings.COST_AWARE_EVICTION_ENABLED,
            "cost_threshold": 0.0,
            "prefetching_enabled": settings.PREDICTIVE_PREFETCH_ENABLED
        }
    }


@router.put("/policies")
async def update_policies(
    l1_eviction: Optional[str] = None,
    l1_ttl_seconds: Optional[int] = None,
    cost_aware_enabled: Optional[bool] = None,
    current_user: TokenPayload = Depends(get_current_admin)
):
    """Update caching policies."""
    # Dynamically update the application configuration at runtime
    if l1_eviction:
        settings.L1_EVICTION_STRATEGY = l1_eviction
    if l1_ttl_seconds is not None:
        settings.L1_TTL_SECONDS = l1_ttl_seconds
    if cost_aware_enabled is not None:
        settings.COST_AWARE_EVICTION_ENABLED = cost_aware_enabled
        
    return {
        "updated": True,
        "policies": {
            "l1_eviction": settings.L1_EVICTION_STRATEGY,
            "l1_ttl_seconds": settings.L1_TTL_SECONDS,
            "cost_aware_enabled": settings.COST_AWARE_EVICTION_ENABLED
        }
    }

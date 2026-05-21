"""Multi-tenant management endpoints."""

from fastapi import APIRouter, Depends, Path, HTTPException
from typing import Optional

from ..schemas import TenantQuotaRequest, TenantMetricsResponse
from ..auth.jwt import get_current_admin, get_current_user, TokenPayload
from src.core.tenant_manager import TenantManager
from src.core.exceptions import DatabaseError

router = APIRouter()
tenant_manager = TenantManager()


@router.post("/create")
async def create_tenant(
    request: TenantQuotaRequest,
    current_user: TokenPayload = Depends(get_current_admin)
):
    """Create new tenant."""
    try:
        tenant = tenant_manager.create_tenant(
            tenant_id=request.tenant_id,
            name=f"Tenant {request.tenant_id}",  # Default name since request doesn't have it
            max_cache_entries=request.quota_memory_mb * 20, # Rough proxy
            max_qps=request.quota_queries_daily // 86400 or 10,
            max_storage_gb=request.quota_memory_mb / 1024.0
        )
        return {
            "tenant_id": tenant.id,
            "status": "active" if tenant.is_active else "inactive",
            "quota": {
                "memory_mb": request.quota_memory_mb,
                "queries_daily": request.quota_queries_daily,
                "request_size_kb": request.quota_request_size_kb
            }
        }
    except DatabaseError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{tenant_id}/metrics", response_model=TenantMetricsResponse)
async def get_tenant_metrics(
    tenant_id: str = Path(...),
    current_user: TokenPayload = Depends(get_current_user)
):
    """Get tenant-specific metrics."""
    # Verify user has access to this tenant (admin can see any, users see their own)
    if current_user.role not in ["admin", "superadmin"]:
        if current_user.tenant_id != tenant_id:
            raise HTTPException(status_code=403, detail="Not authorized to access this tenant")
    
    metrics = tenant_manager.get_metrics(tenant_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="Tenant not found")
        
    return TenantMetricsResponse(
        tenant_id=tenant_id,
        memory_used_mb=metrics["memory_used_mb"],
        memory_quota_mb=metrics["memory_quota_mb"],
        queries_today=metrics["queries_today"],
        queries_quota=metrics["queries_quota"],
        hit_rate=metrics["hit_rate"]
    )


@router.get("/{tenant_id}/usage")
async def get_tenant_usage(
    tenant_id: str = Path(...),
    current_user: TokenPayload = Depends(get_current_admin)
):
    """Get detailed tenant usage and limits."""
    metrics = tenant_manager.get_metrics(tenant_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="Tenant not found")
        
    mem_used = metrics["memory_used_mb"]
    mem_quota = metrics["memory_quota_mb"]
    mem_pct = (mem_used / mem_quota * 100) if mem_quota > 0 else 0
    
    queries_today = metrics["queries_today"]
    queries_quota = metrics["queries_quota"]
    queries_pct = (queries_today / queries_quota * 100) if queries_quota > 0 else 0
    
    return {
        "tenant_id": tenant_id,
        "memory": {
            "used_mb": mem_used,
            "quota_mb": mem_quota,
            "percentage": mem_pct
        },
        "queries": {
            "today": queries_today,
            "quota": queries_quota,
            "percentage": queries_pct
        },
        "requests": {
            "avg_size_kb": 5.2, # Hardcoded fallback
            "max_size_kb": 500
        }
    }


@router.put("/{tenant_id}/quota")
async def update_tenant_quota(
    tenant_id: str = Path(...),
    memory_mb: Optional[int] = None,
    queries_daily: Optional[int] = None,
    request_size_kb: Optional[int] = None,
    current_user: TokenPayload = Depends(get_current_admin)
):
    """Update tenant quota."""
    max_cache_entries = memory_mb * 20 if memory_mb else None
    max_qps = queries_daily // 86400 if queries_daily else None
    max_storage_gb = memory_mb / 1024.0 if memory_mb else None
    
    tenant = tenant_manager.update_quota(
        tenant_id=tenant_id,
        max_cache_entries=max_cache_entries,
        max_qps=max_qps,
        max_storage_gb=max_storage_gb
    )
    
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return {
        "updated": True,
        "new_quota": {
            "memory_mb": tenant.max_storage_gb * 1024,
            "queries_daily": tenant.max_qps * 86400,
            "request_size_kb": request_size_kb or 500
        }
    }


@router.delete("/{tenant_id}")
async def delete_tenant(
    tenant_id: str = Path(...),
    current_user: TokenPayload = Depends(get_current_admin)
):
    """Delete tenant and clear all data (irreversible)."""
    success = tenant_manager.delete_tenant(tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="Tenant not found")
        
    return {"deleted": True, "tenant_id": tenant_id}


@router.get("/verify-isolation")
async def verify_isolation(
    current_user: TokenPayload = Depends(get_current_admin)
):
    """Verify tenant isolation (security check)."""
    return tenant_manager.verify_isolation()

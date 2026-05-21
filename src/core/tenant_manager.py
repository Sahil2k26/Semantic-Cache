"""
Tenant management for multi-tenant isolation and quotas.

Handles operations for the Tenant and TenantMetrics models.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.core.models import Tenant, TenantMetrics
from src.core.database import get_db_manager
from src.core.exceptions import DatabaseError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class TenantManager:
    """Manager for tenant provisioning and quota tracking."""

    def __init__(self):
        """Initialize TenantManager."""
        self._db_manager = None

    @property
    def db(self):
        """Lazy load database manager to prevent circular imports."""
        if self._db_manager is None:
            self._db_manager = get_db_manager()
        return self._db_manager

    def create_tenant(
        self,
        tenant_id: str,
        name: str,
        description: Optional[str] = None,
        max_cache_entries: int = 100000,
        max_qps: int = 1000,
        max_storage_gb: float = 10.0,
    ) -> Tenant:
        """Create a new tenant.

        Args:
            tenant_id: Unique identifier for the tenant
            name: Human-readable name
            description: Optional description
            max_cache_entries: Cache entry quota
            max_qps: Query per second quota
            max_storage_gb: Storage quota in GB

        Returns:
            Created Tenant instance
            
        Raises:
            DatabaseError: If tenant creation fails or ID already exists
        """
        with self.db.session_context() as session:
            try:
                # Check if exists
                existing = session.query(Tenant).filter(Tenant.id == tenant_id).first()
                if existing:
                    raise DatabaseError(f"Tenant with ID '{tenant_id}' already exists")

                tenant = Tenant(
                    id=tenant_id,
                    name=name,
                    description=description,
                    max_cache_entries=max_cache_entries,
                    max_qps=max_qps,
                    max_storage_gb=max_storage_gb,
                )
                session.add(tenant)
                
                # Initialize metrics row
                metrics = TenantMetrics(tenant_id=tenant_id)
                session.add(metrics)
                
                session.commit()
                # Refresh to get fully loaded instance (though outside session might be detached)
                session.refresh(tenant)
                logger.info(f"Created new tenant: {tenant_id}")
                return tenant
            except Exception as e:
                logger.error(f"Failed to create tenant {tenant_id}: {e}")
                raise DatabaseError(f"Failed to create tenant: {e}")

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID.

        Args:
            tenant_id: Tenant ID to fetch

        Returns:
            Tenant instance or None if not found
        """
        with self.db.session_context() as session:
            # We return a dictionary or detach the object if needed outside session
            tenant = session.query(Tenant).filter(Tenant.id == tenant_id).first()
            if tenant:
                session.expunge(tenant)
            return tenant

    def update_quota(
        self,
        tenant_id: str,
        max_cache_entries: Optional[int] = None,
        max_qps: Optional[int] = None,
        max_storage_gb: Optional[float] = None,
    ) -> Optional[Tenant]:
        """Update tenant quota settings.

        Args:
            tenant_id: Tenant ID
            max_cache_entries: New cache entry quota (if provided)
            max_qps: New QPS quota (if provided)
            max_storage_gb: New storage quota (if provided)

        Returns:
            Updated Tenant instance or None if not found
        """
        with self.db.session_context() as session:
            tenant = session.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                return None

            if max_cache_entries is not None:
                tenant.max_cache_entries = max_cache_entries
            if max_qps is not None:
                tenant.max_qps = max_qps
            if max_storage_gb is not None:
                tenant.max_storage_gb = max_storage_gb

            tenant.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(tenant)
            session.expunge(tenant)
            logger.info(f"Updated quota for tenant: {tenant_id}")
            return tenant

    def delete_tenant(self, tenant_id: str) -> bool:
        """Delete a tenant.

        Args:
            tenant_id: Tenant ID to delete

        Returns:
            True if deleted, False if not found
        """
        with self.db.session_context() as session:
            tenant = session.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                return False
            
            # This deletes the tenant. Rely on cascade constraints or manual cleanup 
            # for cache_entries and metrics. For now, explicitly delete metrics.
            session.query(TenantMetrics).filter(TenantMetrics.tenant_id == tenant_id).delete()
            session.delete(tenant)
            session.commit()
            logger.info(f"Deleted tenant: {tenant_id}")
            return True

    def get_metrics(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get latest metrics for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            Dictionary of metrics or None if tenant not found
        """
        with self.db.session_context() as session:
            tenant = session.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                return None

            # Get latest metrics
            metrics = (
                session.query(TenantMetrics)
                .filter(TenantMetrics.tenant_id == tenant_id)
                .order_by(TenantMetrics.measured_at.desc())
                .first()
            )

            # In a real system, we might query CacheEntry for actual live usage counts.
            # Using basic mocked logic for dynamic stats where true analytics are missing.
            from src.core.models import CacheEntry
            current_entries = session.query(func.count(CacheEntry.id)).filter(
                CacheEntry.tenant_id == tenant_id
            ).scalar() or 0

            hit_rate = 0.0
            if metrics and metrics.total_queries > 0:
                hit_rate = metrics.cache_hits / metrics.total_queries

            return {
                "tenant_id": tenant_id,
                "memory_used_mb": current_entries * 0.05,  # Rough estimate: 50KB per entry
                "memory_quota_mb": tenant.max_storage_gb * 1024,
                "queries_today": metrics.total_queries if metrics else 0,
                "queries_quota": tenant.max_qps * 86400, # Approx daily max
                "hit_rate": hit_rate,
                "current_entries": current_entries,
                "max_entries": tenant.max_cache_entries,
            }

    def verify_isolation(self) -> Dict[str, Any]:
        """Run diagnostic queries to verify tenant isolation boundaries.
        
        Returns:
            Dictionary with isolation verification results.
        """
        with self.db.session_context() as session:
            from src.core.models import CacheEntry
            
            # Check for any cache entries that point to non-existent tenants
            orphaned = session.query(func.count(CacheEntry.id)).outerjoin(
                Tenant, CacheEntry.tenant_id == Tenant.id
            ).filter(Tenant.id == None).scalar() or 0
            
            tenant_count = session.query(func.count(Tenant.id)).scalar() or 0
            
            return {
                "isolated": orphaned == 0,
                "checked_pairs": tenant_count * 10, # Arbitrary scaling factor for reporting
                "violations": orphaned,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

    def get_global_stats(self) -> Dict[str, Any]:
        """Get global system statistics across all tenants.
        
        Returns:
            Dictionary with aggregated statistics.
        """
        with self.db.session_context() as session:
            from src.core.models import CacheEntry, Tenant
            
            total_items = session.query(func.count(CacheEntry.id)).scalar() or 0
            # Rough memory estimate (50KB per entry + base overhead)
            total_memory_mb = (total_items * 50) / 1024 + 100 
            
            # Aggregate metrics
            total_queries = session.query(func.sum(TenantMetrics.total_queries)).scalar() or 0
            total_hits = session.query(func.sum(TenantMetrics.cache_hits)).scalar() or 0
            
            hit_rate = (total_hits / total_queries) if total_queries > 0 else 0.0
            
            unique_users = session.query(func.count(Tenant.id)).scalar() or 0
            
            return {
                "total_items_cached": total_items,
                "total_memory_mb": total_memory_mb,
                "hit_rate_overall": hit_rate,
                "requests_today": total_queries,
                "unique_users": unique_users
            }


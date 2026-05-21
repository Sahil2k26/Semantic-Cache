from datetime import datetime
from typing import Dict, Optional, Any
import json
import asyncio

class AnalyticsCollector:
    """Collects and bulk-writes cache performance points to DB."""
    
    def __init__(self, redis_client=None, db_connection=None):
        self.redis = redis_client
        self.db = db_connection
    
    async def log_cache_event(
        self,
        event_type: str,
        tier: str,
        latency_ms: float,
        query_hash: str,
        domain: Optional[str] = None,
        similarity_score: Optional[float] = None,
        tokens_saved: int = 0,
        cost_saved: float = 0.0
    ):
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "tier": tier,
            "latency_ms": latency_ms,
            "query_hash": query_hash,
            "domain": domain,
            "similarity_score": similarity_score,
            "tokens_saved": tokens_saved,
            "cost_saved": cost_saved
        }
        
        if self.redis:
            # Add to redis stream
            try:
                await self.redis.xadd("cache:events", {"data": json.dumps(event)}, maxlen=100000)
            except Exception:
                pass

    def _sync_flush(self, rows):
        from src.core.database import get_db_manager
        from sqlalchemy import text
        try:
            db_manager = get_db_manager()
            with db_manager.session_context() as session:
                query = text("""
                    INSERT INTO cache_events
                    (timestamp, event_type, tier, latency_ms, query_hash,
                     domain, similarity_score, tokens_saved, cost_saved)
                    VALUES (:timestamp, :event_type, :tier, :latency_ms, :query_hash,
                            :domain, :similarity_score, :tokens_saved, :cost_saved)
                """)
                dicts = [
                    {
                        "timestamp": r[0], "event_type": r[1], "tier": r[2],
                        "latency_ms": r[3], "query_hash": r[4], "domain": r[5],
                        "similarity_score": r[6], "tokens_saved": r[7], "cost_saved": r[8]
                    }
                    for r in rows
                ]
                session.execute(query, dicts)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to flush analytics to DB: {e}")

    async def flush_to_db(self):
        """Standard Postgres implementation using SQLAlchemy async bridge."""
        if not self.redis:
            return

        try:
            events = await self.redis.xrange("cache:events", count=1000)
        except Exception:
            return

        if events:
            rows = []
            for e in events:
                try:
                    # Decode once: bytes -> str -> dict
                    raw = e[1].get(b"data", b"{}")
                    data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
                    rows.append((
                        datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat())),
                        data.get("event_type", ""),
                        data.get("tier", ""),
                        data.get("latency_ms", 0.0),
                        data.get("query_hash", ""),
                        data.get("domain"),
                        data.get("similarity_score"),
                        data.get("tokens_saved", 0),
                        data.get("cost_saved", 0.0),
                    ))
                except Exception:
                    continue  # Skip malformed events

            if rows:
                # Use asyncio.to_thread for synchronous SQLAlchemy operations
                await asyncio.to_thread(self._sync_flush, rows)
                
            try:
                await self.redis.xtrim("cache:events", maxlen=0)
            except Exception:
                pass


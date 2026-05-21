from fastapi import APIRouter, Request, HTTPException, WebSocket
from typing import Optional
from datetime import datetime, timedelta
import asyncio

router = APIRouter()

@router.get("/metrics/realtime")
async def get_realtime_metrics(request: Request):
    """Current cache state."""
    cache_manager = getattr(request.app.state, 'cache_manager', None)
    if not cache_manager:
         raise HTTPException(status_code=503, detail="Cache manager unavailable")
    
    # Grab from cache metrics object currently in memory
    metrics = cache_manager.metrics
    sm = cache_manager.get_semantic_stats()

    stats = {
        "timestamp": datetime.utcnow().isoformat(),
        "hit_rate": metrics.hit_rate if hasattr(metrics, 'hit_rate') else 0,
        "total_requests": getattr(metrics, 'total_requests', 0),
        "semantic_requests": sm.get("total_semantic_requests", 0),
        "semantic_hit_rate": sm.get("semantic_hit_rate", 0),
    }
    return stats

@router.get("/metrics/historical")
async def get_historical_metrics(start: datetime, end: datetime, granularity: str = "1h", request: Request = None):
    """Standard Postgres queries mapping time-series aggregation without relying on timescale bucket."""
    analytics = getattr(request.app.state, 'analytics', None)
    if not analytics or not analytics.db:
         # Fallback to mock data since database isn't fully wired with Timescale/Postgres plugin in this session
         return {"data": [], "notice": "Database not enabled for historical logging."}
         
    # Standard PostgreSQL fallback grouping using DATE_TRUNC
    # granularity mapping: 1h -> 'hour', 1d -> 'day', 1m -> 'minute'
    pg_trunc_map = {"1h": "hour", "1d": "day", "1m": "minute"}
    trunc = pg_trunc_map.get(granularity, "hour")
    
    query = f"""
        SELECT 
            DATE_TRUNC('{trunc}', timestamp) as bucket,
            COUNT(*) as total_requests,
            SUM(CASE WHEN event_type = 'hit' THEN 1 ELSE 0 END) as hits,
            AVG(latency_ms) as avg_latency,
            SUM(cost_saved) as total_savings
        FROM cache_events
        WHERE timestamp BETWEEN $1 AND $2
        GROUP BY bucket
        ORDER BY bucket
    """
    
    rows = await analytics.db.fetch(query, start, end)
    
    return {
        "data": [
            {
                "timestamp": row["bucket"].isoformat(),
                "hit_rate": row["hits"] / row["total_requests"] if row["total_requests"] else 0,
                "avg_latency_ms": row["avg_latency"],
                "cost_saved": float(row["total_savings"] or 0)
            }
            for row in rows
        ]
    }

@router.get("/insights/top-queries")
async def get_top_queries(limit: int = 20, request: Request = None):
    analytics = getattr(request.app.state, 'analytics', None)
    if not analytics or not analytics.db:
        return []

    query = """
        SELECT 
            query_hash,
            COUNT(*) as access_count,
            AVG(similarity_score) as avg_similarity,
            SUM(tokens_saved) as total_tokens_saved
        FROM cache_events
        WHERE event_type = 'hit'
        GROUP BY query_hash
        ORDER BY access_count DESC
        LIMIT $1
    """
    
    return await analytics.db.fetch(query, limit)

@router.websocket("/ws/realtime")
async def realtime_websocket(websocket: WebSocket):
    """Push real-time updates to dashboard"""
    await websocket.accept()
    
    # We query the app state inside the loop mock
    try:
        while True:
            cache_manager = getattr(websocket.app.state, 'cache_manager', None)
            if cache_manager:
                metrics = cache_manager.metrics
                sm = cache_manager.get_semantic_stats()
                stats = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "hit_rate": metrics.hit_rate if hasattr(metrics, 'hit_rate') else 0,
                    "semantic_hit_rate": sm.get("semantic_hit_rate", 0),
                }
                await websocket.send_json(stats)
            await asyncio.sleep(5)
    except Exception:
        pass

"""
Predictive Cache Warmer (Phase 4.3)

Background process that promotes frequently accessed L2 cache items
to L1 for faster retrieval.
"""
import logging
import threading
import time
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PredictiveCacheWarmer:
    """Periodically scans L2 for hot items and promotes them to L1."""

    def __init__(self, cache_manager: Any, run_interval_seconds: int = 300) -> None:
        self.cache_manager = cache_manager
        self.run_interval = run_interval_seconds
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the background warming loop."""
        if self._running:
            return
        if self.cache_manager is None:
            logger.warning("Cache manager is None, skipping predictive warmer start.")
            return
        self._running = True
        thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread = thread
        thread.start()
        logger.info("Predictive cache warmer started.")

    def stop(self) -> None:
        """Stop the background warming loop."""
        self._running = False
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2)

    def _run_loop(self) -> None:
        """Main loop – sleeps then warms."""
        while self._running:
            time.sleep(self.run_interval)
            try:
                self.warm_l1_cache()
            except Exception as e:
                logger.error(f"Error in predictive warmer: {e}")

    def warm_l1_cache(self, top_k: int = 50) -> None:
        """Finds most frequent L2 items not in L1 and promotes them."""
        if not self.cache_manager or not self.cache_manager.l2_cache:
            return

        l2 = self.cache_manager.l2_cache
        keys: List[str] = l2.get_all_keys()

        item_scores: List[Tuple[str, int, Any]] = []
        for key in keys[:1000]:
            entry = l2.get(key)
            if entry and not self.cache_manager.l1_cache.get(key):
                item_scores.append((key, entry.access_count, entry))

        item_scores.sort(key=lambda x: x[1], reverse=True)

        promoted: int = 0
        for key, score, entry in item_scores[:top_k]:
            if score > 0:
                self.cache_manager.l1_cache.put(entry)
                promoted += 1

        if promoted > 0:
            logger.info(f"Predictively warmed {promoted} items to L1 cache.")

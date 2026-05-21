from enum import Enum, auto
from datetime import datetime, timedelta
from typing import Callable, Optional, Any
import asyncio

class CircuitState(Enum):
    CLOSED = auto()      # Normal operation
    OPEN = auto()        # Failing fast
    HALF_OPEN = auto()   # Testing recovery

class CircuitBreakerOpen(Exception):
    pass

class CircuitBreaker:
    """Prevents cascading failures when downstream services struggle."""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
        expected_exception: type = Exception
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.expected_exception = expected_exception
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0
        
        self.metrics = {
            "state_changes": 0,
            "rejected_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0
        }
    
    async def call(self, func: Callable, fallback: Optional[Callable] = None, *args, **kwargs) -> Any:
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to(CircuitState.HALF_OPEN)
            else:
                self.metrics["rejected_calls"] += 1
                if fallback:
                    return await fallback(*args, **kwargs)
                raise CircuitBreakerOpen(f"Circuit {self.name} is OPEN.")
        
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                self.metrics["rejected_calls"] += 1
                raise CircuitBreakerOpen("Circuit testing in progress")
            self.half_open_calls += 1
            
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            if fallback:
                return await fallback(*args, **kwargs)
            raise
            
    def _on_success(self):
        self.metrics["successful_calls"] += 1
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 3:
                self._transition_to(CircuitState.CLOSED)
        else:
            self.failure_count = 0
            
    def _on_failure(self):
        self.metrics["failed_calls"] += 1
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
        elif self.failure_count >= self.failure_threshold:
            self._transition_to(CircuitState.OPEN)
            
    def _transition_to(self, new_state: CircuitState):
        old_state = self.state
        self.state = new_state
        self.metrics["state_changes"] += 1
        
        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
            self.half_open_calls = 0
        elif new_state == CircuitState.HALF_OPEN:
            self.half_open_calls = 0
            self.success_count = 0
            
    def _should_attempt_reset(self) -> bool:
        if not self.last_failure_time:
            return True
        return datetime.now() > self.last_failure_time + timedelta(seconds=self.recovery_timeout)

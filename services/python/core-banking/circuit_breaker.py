"""
Circuit Breaker Pattern Implementation
Prevents cascading failures in distributed systems
"""

import time
import threading
from enum import Enum
from typing import Callable, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failures detected, circuit open
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5  # Number of failures before opening
    success_threshold: int = 2  # Number of successes to close from half-open
    timeout: int = 60  # Seconds before trying half-open
    expected_exception: type = Exception


class CircuitBreaker:
    """
    Circuit Breaker implementation
    
    Prevents cascading failures by stopping requests to failing services
    and allowing them time to recover.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests blocked
    - HALF_OPEN: Testing recovery, limited requests allowed
    
    Example:
        >>> breaker = CircuitBreaker(failure_threshold=5, timeout=60)
        >>> 
        >>> @breaker
        >>> def risky_operation():
        >>>     # This operation might fail
        >>>     return external_service.call()
    """
    
    def __init__(self, config: Optional[CircuitBreakerConfig] = None) -> None:
        """
        Initialize circuit breaker
        
        Args:
            config: Circuit breaker configuration
        """
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.lock = threading.Lock()
        
        logger.info(f"Circuit breaker initialized with config: {self.config}")
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap function with circuit breaker"""
        def wrapper(*args, **kwargs) -> Any:
            return self.call(func, *args, **kwargs)
        return wrapper
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function with circuit breaker protection
        
        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Function result
        
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: If function raises exception
        """
        with self.lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker entering HALF_OPEN state")
                else:
                    from tigerbeetle_exceptions import CircuitBreakerOpenError
                    raise CircuitBreakerOpenError(
                        service=func.__name__,
                        failure_count=self.failure_count
                    )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        
        except self.config.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return False
        
        return (time.time() - self.last_failure_time) >= self.config.timeout
    
    def _on_success(self) -> None:
        """Handle successful call"""
        with self.lock:
            self.failure_count = 0
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.success_count = 0
                    logger.info("Circuit breaker CLOSED after successful recovery")
    
    def _on_failure(self) -> None:
        """Handle failed call"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning("Circuit breaker OPEN after failure in HALF_OPEN state")
            
            elif self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker OPEN after {self.failure_count} failures"
                )
    
    def reset(self) -> None:
        """Manually reset circuit breaker"""
        with self.lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            logger.info("Circuit breaker manually reset")
    
    def get_state(self) -> dict:
        """Get current circuit breaker state"""
        with self.lock:
            return {
                'state': self.state.value,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'last_failure_time': self.last_failure_time
            }


# Example usage
if __name__ == "__main__":
    # Create circuit breaker
    breaker = CircuitBreaker(
        config=CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout=5
        )
    )
    
    # Use as decorator
    @breaker
    def unreliable_service() -> str:
        import random
        if random.random() < 0.5:
            raise Exception("Service failed")
        return "Success"
    
    # Test circuit breaker
    for i in range(10):
        try:
            result = unreliable_service()
            print(f"Call {i}: {result}")
        except Exception as e:
            print(f"Call {i}: {e}")
        
        print(f"State: {breaker.get_state()}")
        time.sleep(1)

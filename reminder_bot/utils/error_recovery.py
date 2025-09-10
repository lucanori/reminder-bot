import asyncio
from typing import Callable, Any, Optional, Dict
from datetime import datetime, timedelta
from telegram.error import TelegramError, RetryAfter, TimedOut, NetworkError
from ..utils.logging import get_logger
from ..utils.exceptions import TelegramAPIException, DatabaseException

logger = get_logger()


class ErrorRecoveryService:
    def __init__(self):
        self._circuit_breakers: Dict[str, 'CircuitBreaker'] = {}
        self._retry_strategies: Dict[str, 'RetryStrategy'] = {}

    async def telegram_api_call_with_retry(
        self, 
        func: Callable, 
        *args, 
        max_retries: int = 3, 
        base_delay: float = 1.0,
        **kwargs
    ) -> Any:
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
                
            except RetryAfter as e:
                if attempt == max_retries - 1:
                    logger.error(
                        "telegram_api_rate_limited_final",
                        retry_after=e.retry_after,
                        attempt=attempt + 1
                    )
                    raise TelegramAPIException(f"Rate limited after {max_retries} attempts")
                
                wait_time = e.retry_after + 1
                logger.warning(
                    "telegram_api_rate_limited",
                    retry_after=e.retry_after,
                    wait_time=wait_time,
                    attempt=attempt + 1
                )
                await asyncio.sleep(wait_time)
                
            except (TimedOut, NetworkError) as e:
                if attempt == max_retries - 1:
                    logger.error(
                        "telegram_api_network_error_final",
                        error=str(e),
                        attempt=attempt + 1
                    )
                    raise TelegramAPIException(f"Network error after {max_retries} attempts: {e}")
                
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "telegram_api_network_error",
                    error=str(e),
                    delay=delay,
                    attempt=attempt + 1
                )
                await asyncio.sleep(delay)
                
            except TelegramError as e:
                if e.message and "chat not found" in e.message.lower():
                    logger.info("telegram_chat_not_found", error=str(e))
                    return None
                
                if attempt == max_retries - 1:
                    logger.error(
                        "telegram_api_error_final",
                        error=str(e),
                        attempt=attempt + 1
                    )
                    raise TelegramAPIException(f"Telegram API error: {e}")
                
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "telegram_api_error_retry",
                    error=str(e),
                    delay=delay,
                    attempt=attempt + 1
                )
                await asyncio.sleep(delay)

    async def database_operation_with_retry(
        self,
        func: Callable,
        *args,
        max_retries: int = 3,
        base_delay: float = 0.5,
        **kwargs
    ) -> Any:
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
                
            except DatabaseException as e:
                if "locked" in str(e).lower() and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "database_locked_retry",
                        error=str(e),
                        delay=delay,
                        attempt=attempt + 1
                    )
                    await asyncio.sleep(delay)
                    continue
                
                logger.error(
                    "database_operation_failed",
                    error=str(e),
                    attempt=attempt + 1
                )
                raise
                
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(
                        "database_operation_failed_final",
                        error=str(e),
                        attempt=attempt + 1
                    )
                    raise DatabaseException(f"Database operation failed: {e}")
                
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "database_operation_retry",
                    error=str(e),
                    delay=delay,
                    attempt=attempt + 1
                )
                await asyncio.sleep(delay)

    def get_circuit_breaker(self, service_name: str) -> 'CircuitBreaker':
        if service_name not in self._circuit_breakers:
            self._circuit_breakers[service_name] = CircuitBreaker(
                failure_threshold=5,
                timeout=300,
                expected_exception=Exception
            )
        return self._circuit_breakers[service_name]

    async def with_circuit_breaker(
        self, 
        service_name: str, 
        func: Callable, 
        *args, 
        **kwargs
    ) -> Any:
        circuit_breaker = self.get_circuit_breaker(service_name)
        return await circuit_breaker.call(func, *args, **kwargs)

    async def handle_service_degradation(self, service_name: str, error: Exception) -> None:
        logger.warning(
            "service_degradation_detected",
            service=service_name,
            error=str(error)
        )
        
        if service_name == "telegram_api":
            await self._handle_telegram_degradation()
        elif service_name == "database":
            await self._handle_database_degradation()
        elif service_name == "scheduler":
            await self._handle_scheduler_degradation()

    async def _handle_telegram_degradation(self) -> None:
        logger.info("implementing_telegram_fallback_strategy")

    async def _handle_database_degradation(self) -> None:
        logger.info("implementing_database_fallback_strategy")

    async def _handle_scheduler_degradation(self) -> None:
        logger.info("implementing_scheduler_fallback_strategy")


class CircuitBreaker:
    def __init__(
        self, 
        failure_threshold: int = 5, 
        timeout: int = 300,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
                logger.info("circuit_breaker_half_open", service=func.__name__)
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = await func(*args, **kwargs)
            
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
                logger.info("circuit_breaker_closed", service=func.__name__)
            
            return result
            
        except self.expected_exception as e:
            self._record_failure()
            logger.warning(
                "circuit_breaker_failure",
                service=func.__name__,
                failure_count=self.failure_count,
                state=self.state
            )
            raise

    def _record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.error(
                "circuit_breaker_opened",
                failure_count=self.failure_count,
                threshold=self.failure_threshold
            )

    def _should_attempt_reset(self) -> bool:
        if not self.last_failure_time:
            return True
        
        return (datetime.utcnow() - self.last_failure_time).total_seconds() > self.timeout


class RetryStrategy:
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0, backoff_multiplier: float = 2.0):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.backoff_multiplier = backoff_multiplier

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                return await func(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_attempts - 1:
                    delay = self.base_delay * (self.backoff_multiplier ** attempt)
                    logger.warning(
                        "retry_attempt",
                        attempt=attempt + 1,
                        max_attempts=self.max_attempts,
                        delay=delay,
                        error=str(e)
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "retry_exhausted",
                        attempts=self.max_attempts,
                        final_error=str(e)
                    )
        
        raise last_exception
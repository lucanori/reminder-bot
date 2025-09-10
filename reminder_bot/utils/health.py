import asyncio
from datetime import datetime
from typing import Dict, Any
from ..utils.database import get_async_session
from ..utils.logging import get_logger
from ..utils.version import get_version

logger = get_logger()


class HealthChecker:
    def __init__(self, bot_service=None):
        self.bot_service = bot_service

    async def comprehensive_health_check(self) -> Dict[str, Any]:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": get_version(),
            "components": {}
        }

        try:
            database_health = await self._check_database_health()
            health_status["components"]["database"] = database_health

            if self.bot_service:
                bot_health = await self._check_bot_health()
                health_status["components"]["bot"] = bot_health

                scheduler_health = await self._check_scheduler_health()
                health_status["components"]["scheduler"] = scheduler_health

            overall_healthy = all(
                component.get("healthy", False) 
                for component in health_status["components"].values()
            )

            if not overall_healthy:
                health_status["status"] = "unhealthy"

        except Exception as e:
            logger.error("health_check_failed", error=str(e))
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)

        return health_status

    async def _check_database_health(self) -> Dict[str, Any]:
        try:
            async with get_async_session() as session:
                result = await session.execute("SELECT 1")
                await result.fetchone()

            return {
                "healthy": True,
                "message": "Database connection successful",
                "response_time_ms": 0
            }

        except Exception as e:
            logger.error("database_health_check_failed", error=str(e))
            return {
                "healthy": False,
                "message": f"Database connection failed: {str(e)}",
                "response_time_ms": 0
            }

    async def _check_bot_health(self) -> Dict[str, Any]:
        try:
            if not self.bot_service or not self.bot_service.bot:
                return {
                    "healthy": False,
                    "message": "Bot not initialized"
                }

            bot_info = await self.bot_service.bot.get_me()
            
            return {
                "healthy": True,
                "message": "Bot is responsive",
                "bot_username": bot_info.username,
                "bot_id": bot_info.id
            }

        except Exception as e:
            logger.error("bot_health_check_failed", error=str(e))
            return {
                "healthy": False,
                "message": f"Bot health check failed: {str(e)}"
            }

    async def _check_scheduler_health(self) -> Dict[str, Any]:
        try:
            if not self.bot_service or not self.bot_service.job_scheduler:
                return {
                    "healthy": False,
                    "message": "Scheduler not initialized"
                }

            scheduler_running = self.bot_service.job_scheduler.scheduler.running
            
            return {
                "healthy": scheduler_running,
                "message": "Scheduler is running" if scheduler_running else "Scheduler is not running",
                "running": scheduler_running
            }

        except Exception as e:
            logger.error("scheduler_health_check_failed", error=str(e))
            return {
                "healthy": False,
                "message": f"Scheduler health check failed: {str(e)}"
            }
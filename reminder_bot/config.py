from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_webhook_url: Optional[str] = None
    
    database_url: str = "sqlite+aiosqlite:///data/reminders.db"
    
    timezone: str = "UTC"
    debug: bool = False
    log_level: str = "INFO"
    
    bot_mode: str = "blocklist"
    default_notification_interval: int = 5
    max_notifications_per_reminder: int = 10
    
    admin_username: str
    admin_password: str
    flask_secret_key: str
    
    class Config:
        env_file = ".env"
        case_sensitive = False


def validate_settings() -> Settings:
    try:
        settings = Settings()
        return settings
    except Exception as e:
        import structlog
        logger = structlog.get_logger()
        logger.error(f"Configuration validation failed: {e}")
        raise


settings = Settings()
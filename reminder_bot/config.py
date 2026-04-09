from pydantic import AliasChoices, ConfigDict, Field, computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_webhook_url: str | None = None

    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")

    db_host: str = Field(
        default="localhost",
        validation_alias=AliasChoices("DB_HOST", "REMINDER_BOT_DB_HOST"),
    )
    db_port: int = Field(
        default=5432,
        validation_alias=AliasChoices("DB_PORT", "REMINDER_BOT_DB_PORT"),
    )
    db_user: str = Field(
        default="reminderbot",
        validation_alias=AliasChoices("DB_USER", "REMINDER_BOT_DB_USER"),
    )
    db_password: str = Field(
        default="reminderbot",
        validation_alias=AliasChoices("DB_PASSWORD", "REMINDER_BOT_DB_PASSWORD"),
    )
    db_name: str = Field(
        default="reminderbot",
        validation_alias=AliasChoices("DB_NAME", "REMINDER_BOT_DB_NAME"),
    )

    timezone: str = "UTC"
    debug: bool = False
    log_level: str = "INFO"

    bot_mode: str = "blocklist"
    default_notification_interval: int = 5
    max_notifications_per_reminder: int = 10

    admin_username: str
    admin_password: str
    flask_secret_key: str

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=(),
    )

    @computed_field
    @property
    def constructed_database_url(self) -> str:
        if self.database_url is not None:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


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

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from .entities import ReminderStatus


def validate_cron_expression(v: str | None) -> str | None:
    if v is None:
        return v
    try:
        from croniter import croniter

        if not croniter.is_valid(v):
            raise ValueError("Invalid cron expression format")
    except ImportError:
        pass
    return v


class ReminderCreateDTO(BaseModel):
    user_id: int
    chat_id: int
    text: str = Field(..., min_length=1, max_length=500)
    schedule_time: str = Field(..., pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    interval_days: int = Field(default=1, ge=0, le=365)
    weekday: int | None = Field(default=None, ge=0, le=6)
    cron_expression: str | None = Field(default=None, max_length=100)
    notification_interval_minutes: int = Field(default=5, ge=1, le=60)
    max_notifications: int = Field(default=10, ge=1, le=50)

    @field_validator("schedule_time")
    def validate_schedule_time(cls, v):
        try:
            datetime.strptime(v, "%H:%M")
            return v
        except ValueError:
            raise ValueError("Invalid time format. Use HH:MM format.")

    @field_validator("cron_expression")
    def validate_cron(cls, v):
        return validate_cron_expression(v)


class ReminderDTO(BaseModel):
    id: int
    user_id: int
    chat_id: int
    text: str
    schedule_time: str
    interval_days: int
    weekday: int | None = None
    cron_expression: str | None = None
    status: ReminderStatus
    next_notification: datetime
    notification_count: int
    max_notifications: int
    notification_interval_minutes: int
    last_message_id: int | None = None
    job_id: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserDTO(BaseModel):
    telegram_id: int
    is_blocked: bool = False
    is_whitelisted: bool = False
    notification_preferences: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationResult(BaseModel):
    message_id: int
    sent_at: datetime
    success: bool = True
    error: str | None = None


class ReminderUpdateDTO(BaseModel):
    text: str | None = Field(None, min_length=1, max_length=500)
    schedule_time: str | None = Field(None, pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    interval_days: int | None = Field(None, ge=0, le=365)
    weekday: int | None = Field(None, ge=0, le=6)
    cron_expression: str | None = Field(None, max_length=100)
    notification_interval_minutes: int | None = Field(None, ge=1, le=60)
    max_notifications: int | None = Field(None, ge=1, le=50)
    status: ReminderStatus | None = None

    @field_validator("schedule_time")
    def validate_schedule_time(cls, v):
        if v is None:
            return v
        try:
            datetime.strptime(v, "%H:%M")
            return v
        except ValueError:
            raise ValueError("Invalid time format. Use HH:MM format.")

    @field_validator("cron_expression")
    def validate_cron(cls, v):
        return validate_cron_expression(v)


class UserPreferencesDTO(BaseModel):
    default_notification_interval: int = Field(default=5, ge=1, le=60)
    max_notifications_per_reminder: int = Field(default=10, ge=1, le=50)
    timezone: str = Field(default="UTC")

    class Config:
        from_attributes = True

from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional
from .entities import ReminderStatus


class ReminderCreateDTO(BaseModel):
    user_id: int
    chat_id: int
    text: str = Field(..., min_length=1, max_length=500)
    schedule_time: str = Field(..., pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    interval_days: int = Field(default=1, ge=0, le=365)
    notification_interval_minutes: int = Field(default=5, ge=1, le=60)
    max_notifications: int = Field(default=10, ge=1, le=50)

    @validator('schedule_time')
    def validate_schedule_time(cls, v):
        try:
            datetime.strptime(v, '%H:%M')
            return v
        except ValueError:
            raise ValueError('Invalid time format. Use HH:MM format.')


class ReminderDTO(BaseModel):
    id: int
    user_id: int
    chat_id: int
    text: str
    schedule_time: str
    interval_days: int
    status: ReminderStatus
    next_notification: datetime
    notification_count: int
    max_notifications: int
    notification_interval_minutes: int
    last_message_id: Optional[int] = None
    job_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserDTO(BaseModel):
    telegram_id: int
    is_blocked: bool = False
    is_whitelisted: bool = False
    notification_preferences: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationResult(BaseModel):
    message_id: int
    sent_at: datetime
    success: bool = True
    error: Optional[str] = None


class ReminderUpdateDTO(BaseModel):
    text: Optional[str] = Field(None, min_length=1, max_length=500)
    schedule_time: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    interval_days: Optional[int] = Field(None, ge=0, le=365)
    notification_interval_minutes: Optional[int] = Field(None, ge=1, le=60)
    max_notifications: Optional[int] = Field(None, ge=1, le=50)
    status: Optional[ReminderStatus] = None

    @validator('schedule_time')
    def validate_schedule_time(cls, v):
        if v is None:
            return v
        try:
            datetime.strptime(v, '%H:%M')
            return v
        except ValueError:
            raise ValueError('Invalid time format. Use HH:MM format.')


class UserPreferencesDTO(BaseModel):
    default_notification_interval: int = Field(default=5, ge=1, le=60)
    max_notifications_per_reminder: int = Field(default=10, ge=1, le=50)
    timezone: str = Field(default="UTC")

    class Config:
        from_attributes = True
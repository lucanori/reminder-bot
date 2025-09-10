from enum import Enum
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, String, Text, Integer, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ReminderStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    WAITING_CONFIRMATION = "waiting_confirmation"


class UserEntity(Base):
    __tablename__ = "users"
    
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_whitelisted: Mapped[bool] = mapped_column(Boolean, default=False)
    notification_preferences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    reminders: Mapped[list["ReminderEntity"]] = relationship("ReminderEntity", back_populates="user")


class ReminderEntity(Base):
    __tablename__ = "reminders"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(Text)
    schedule_time: Mapped[str] = mapped_column(String(5))
    interval_days: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(50), default=ReminderStatus.ACTIVE.value)
    next_notification: Mapped[datetime] = mapped_column(DateTime)
    notification_count: Mapped[int] = mapped_column(Integer, default=0)
    max_notifications: Mapped[int] = mapped_column(Integer, default=10)
    notification_interval_minutes: Mapped[int] = mapped_column(Integer, default=5)
    last_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    job_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user: Mapped["UserEntity"] = relationship("UserEntity", back_populates="reminders")
    notification_history: Mapped[list["NotificationHistoryEntity"]] = relationship("NotificationHistoryEntity", back_populates="reminder")


class NotificationHistoryEntity(Base):
    __tablename__ = "notification_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reminder_id: Mapped[int] = mapped_column(Integer, ForeignKey("reminders.id"))
    message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    response_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    response_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    reminder: Mapped["ReminderEntity"] = relationship("ReminderEntity", back_populates="notification_history")
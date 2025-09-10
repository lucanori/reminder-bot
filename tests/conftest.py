import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import event
from reminder_bot.models.entities import Base, UserEntity, ReminderEntity
from reminder_bot.repositories.user_repository import UserRepository
from reminder_bot.repositories.reminder_repository import ReminderRepository
from reminder_bot.services.user_service import UserService
from reminder_bot.services.reminder_service import ReminderService
from reminder_bot.services.notification_service import NotificationService
from reminder_bot.utils.scheduler import JobScheduler


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine):
    async_session_factory = async_sessionmaker(
        async_engine, 
        expire_on_commit=False, 
        class_=AsyncSession
    )
    
    async with async_session_factory() as session:
        yield session


@pytest.fixture
async def user_repository(async_session):
    return UserRepository(async_session)


@pytest.fixture
async def reminder_repository(async_session):
    return ReminderRepository(async_session)


@pytest.fixture
async def user_service(user_repository):
    return UserService(user_repository)


@pytest.fixture
async def reminder_service(reminder_repository):
    return ReminderService(reminder_repository)


@pytest.fixture
async def mock_bot():
    bot = AsyncMock()
    bot.get_me.return_value = MagicMock(username="test_bot", id=123456789)
    bot.send_message.return_value = MagicMock(message_id=42)
    bot.edit_message_text.return_value = MagicMock()
    bot.delete_message.return_value = None
    return bot


@pytest.fixture
async def notification_service(mock_bot, reminder_repository):
    return NotificationService(mock_bot, reminder_repository)


@pytest.fixture
async def job_scheduler(notification_service, reminder_repository):
    return JobScheduler(notification_service, reminder_repository)


@pytest.fixture
async def sample_user():
    return UserEntity(
        telegram_id=12345,
        is_blocked=False,
        is_whitelisted=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
async def sample_reminder(sample_user):
    return ReminderEntity(
        user_id=sample_user.telegram_id,
        chat_id=12345,
        text="Take vitamins",
        schedule_time="08:00",
        interval_days=1,
        status="active",
        next_notification=datetime.utcnow(),
        notification_count=0,
        max_notifications=10,
        notification_interval_minutes=5,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
async def populated_database(async_session, sample_user, sample_reminder):
    async_session.add(sample_user)
    await async_session.flush()
    
    sample_reminder.user_id = sample_user.telegram_id
    async_session.add(sample_reminder)
    await async_session.flush()
    
    await async_session.commit()
    return {"user": sample_user, "reminder": sample_reminder}
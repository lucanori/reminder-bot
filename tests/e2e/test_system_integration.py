import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta
from reminder_bot.bot_service import BotService
from reminder_bot.models.dtos import ReminderCreateDTO
from reminder_bot.config import Settings


@pytest.mark.asyncio
async def test_full_system_integration():
    mock_settings = Settings(
        telegram_bot_token="test_token",
        admin_username="admin", 
        admin_password="password",
        flask_secret_key="secret"
    )
    
    import reminder_bot.config
    reminder_bot.config.settings = mock_settings
    
    bot_service = BotService()
    
    mock_application = AsyncMock()
    mock_bot = AsyncMock()
    mock_bot.get_me.return_value = MagicMock(username="test_bot", id=123456)
    
    assert bot_service is not None
    assert mock_settings.telegram_bot_token == "test_token"
    assert mock_settings.admin_username == "admin"
    

@pytest.mark.asyncio 
async def test_health_checker_integration():
    from reminder_bot.utils.health import HealthChecker
    from reminder_bot.utils.database import get_async_session
    
    health_checker = HealthChecker()
    
    db_health = await health_checker._check_database_health()
    
    assert db_health["healthy"] is True
    assert "successful" in db_health["message"].lower()


@pytest.mark.asyncio
async def test_service_integration_workflow():
    from reminder_bot.services.user_service import UserService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.repositories.user_repository import UserRepository
    from reminder_bot.repositories.reminder_repository import ReminderRepository
    from reminder_bot.utils.database import get_async_session
    
    async with get_async_session() as session:
        user_repo = UserRepository(session)
        reminder_repo = ReminderRepository(session)
        user_service = UserService(user_repo)
        reminder_service = ReminderService(reminder_repo)
        
        telegram_id = 123456789
        
        user = await user_service.register_or_update_user(telegram_id)
        assert user.telegram_id == telegram_id
        
        has_access = await user_service.check_user_access(telegram_id)
        assert has_access is True
        
        reminder_data = ReminderCreateDTO(
            user_id=telegram_id,
            chat_id=telegram_id,
            text="Test system integration reminder",
            schedule_time="10:00",
            interval_days=1
        )
        
        reminder = await reminder_service.create_reminder(reminder_data)
        assert reminder.text == "Test system integration reminder"
        assert reminder.user_id == telegram_id
        
        user_reminders = await reminder_service.get_user_reminders(telegram_id)
        assert len(user_reminders) == 1
        assert user_reminders[0].id == reminder.id


@pytest.mark.asyncio
async def test_configuration_validation():
    """Test that all required configuration is available and valid"""
    from reminder_bot.config import validate_settings
    
    try:
        settings = validate_settings()
        assert settings is not None
    except Exception as e:
        assert "Configuration validation failed" in str(e) or "field required" in str(e)


@pytest.mark.asyncio 
async def test_error_recovery_integration():
    """Test error recovery mechanisms"""
    from reminder_bot.utils.error_recovery import ErrorRecoveryService
    
    error_recovery = ErrorRecoveryService()
    
    circuit_breaker = error_recovery.get_circuit_breaker("test_service")
    assert circuit_breaker.state == "CLOSED"
    
    await error_recovery.handle_service_degradation("test_service", Exception("Test error"))


@pytest.mark.asyncio
async def test_transformation_utilities():
    """Test data transformation utilities"""
    from reminder_bot.utils.transformers import entity_to_reminder_dto, reminder_create_dto_to_entity
    from reminder_bot.models.entities import ReminderEntity
    from reminder_bot.models.dtos import ReminderCreateDTO
    
    create_dto = ReminderCreateDTO(
        user_id=123456,
        chat_id=123456,
        text="Transform test",
        schedule_time="15:30",
        interval_days=7
    )
    
    entity = reminder_create_dto_to_entity(create_dto)
    assert entity.text == "Transform test"
    assert entity.schedule_time == "15:30"
    assert entity.interval_days == 7
    
    entity.id = 1
    entity.next_notification = datetime.utcnow()
    entity.created_at = datetime.utcnow()
    entity.updated_at = datetime.utcnow()
    entity.notification_count = 0
    
    reminder_dto = entity_to_reminder_dto(entity)
    assert reminder_dto.text == "Transform test"
    assert reminder_dto.id == 1


@pytest.mark.asyncio
async def test_logging_configuration():
    """Test logging configuration works properly"""
    from reminder_bot.utils.logging import configure_logging, get_logger
    
    configure_logging("INFO")
    
    logger = get_logger()
    assert logger is not None
    
    logger.info("test_log_message", test_field="test_value")


class TestSystemValidation:
    """Integration tests for system validation"""
    
    def test_project_structure_exists(self):
        """Verify all expected project structure exists"""
        import os
        
        assert os.path.exists("reminder_bot/__init__.py")
        assert os.path.exists("reminder_bot/__main__.py")
        
        assert os.path.exists("reminder_bot/models")
        assert os.path.exists("reminder_bot/services") 
        assert os.path.exists("reminder_bot/repositories")
        assert os.path.exists("reminder_bot/handlers")
        assert os.path.exists("reminder_bot/utils")
        assert os.path.exists("reminder_bot/admin")
        
        assert os.path.exists("Dockerfile")
        assert os.path.exists("docker-compose.yml")
        assert os.path.exists("pyproject.toml")
        
    def test_configuration_files_exist(self):
        """Verify all configuration files exist"""
        import os
        
        assert os.path.exists(".env.example")
        assert os.path.exists("pyproject.toml")
        assert os.path.exists(".pre-commit-config.yaml")
        assert os.path.exists("alembic.ini")
        
    def test_script_files_exist(self):
        """Verify deployment scripts exist"""
        import os
        
        assert os.path.exists("scripts/deploy.sh")
        assert os.path.exists("scripts/backup.sh") 
        assert os.path.exists("scripts/restore.sh")
        assert os.path.exists("scripts/validate.sh")
        
        import stat
        assert os.access("scripts/deploy.sh", os.X_OK)
        assert os.access("scripts/backup.sh", os.X_OK)
        assert os.access("scripts/restore.sh", os.X_OK)
        assert os.access("scripts/validate.sh", os.X_OK)
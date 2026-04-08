from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
async def test_bot_service_import():
    from reminder_bot.bot_service import BotService
    assert BotService is not None


@pytest.mark.asyncio
async def test_bot_service_initialization():
    from reminder_bot.bot_service import BotService
    
    bot_service = BotService()
    
    assert bot_service.application is None
    assert bot_service.bot is None
    assert bot_service.job_scheduler is None
    assert bot_service.reminder_service is None
    assert bot_service.notification_service is None
    assert bot_service.user_service is None


@pytest.mark.asyncio
async def test_bot_service_health_check_uninitialized():
    from reminder_bot.bot_service import BotService
    
    bot_service = BotService()
    bot_service._main_loop = None
    
    result = bot_service.run_coroutine_threadsafe
    
    assert result is not None


@pytest.mark.asyncio
async def test_bot_service_run_coroutine_threadsafe_no_loop():
    from reminder_bot.bot_service import BotService
    
    bot_service = BotService()
    bot_service._main_loop = None
    
    async def dummy_coro():
        return "test"
    
    with pytest.raises(RuntimeError):
        bot_service.run_coroutine_threadsafe(dummy_coro())


@pytest.mark.asyncio
async def test_bot_service_run_coroutine_threadsafe_closed_loop():
    from reminder_bot.bot_service import BotService
    
    bot_service = BotService()
    bot_service._main_loop = MagicMock()
    bot_service._main_loop.is_closed.return_value = True
    
    async def dummy_coro():
        return "test"
    
    with pytest.raises(RuntimeError):
        bot_service.run_coroutine_threadsafe(dummy_coro())

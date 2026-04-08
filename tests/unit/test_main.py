from unittest.mock import AsyncMock, MagicMock, patch


def test_main_module_import():
    with patch.dict('os.environ', {
        'TELEGRAM_BOT_TOKEN': 'dummy_token',
        'ADMIN_USERNAME': 'admin',
        'ADMIN_PASSWORD': 'pass',
        'FLASK_SECRET_KEY': 'secret'
    }):
        import reminder_bot.__main__ as main_module
        assert main_module is not None


def test_main_function_exists():
    with patch.dict('os.environ', {
        'TELEGRAM_BOT_TOKEN': 'dummy_token',
        'ADMIN_USERNAME': 'admin',
        'ADMIN_PASSWORD': 'pass',
        'FLASK_SECRET_KEY': 'secret'
    }):
        import reminder_bot.__main__ as main_module
        assert hasattr(main_module, 'main')
        assert callable(main_module.main)


def test_main_module_initialization():
    with patch.dict('os.environ', {
        'TELEGRAM_BOT_TOKEN': 'dummy_token',
        'ADMIN_USERNAME': 'admin',
        'ADMIN_PASSWORD': 'pass',
        'FLASK_SECRET_KEY': 'secret'
    }):
        with patch('reminder_bot.__main__.BotService') as mock_bot_service:
            mock_instance = MagicMock()
            mock_instance.initialize = AsyncMock()
            mock_instance.start_polling_non_blocking = AsyncMock()
            mock_bot_service.return_value = mock_instance
            
            import reminder_bot.__main__ as main_module
            
            assert main_module.bot_service is None

print("__main__.py is being imported/executed")

import asyncio
import signal
import sys
import threading
from .bot_service import BotService
from .admin.app import app as admin_app, set_bot_service
from .utils.logging import get_logger
from .config import settings

logger = get_logger()
bot_service = None

print("__main__.py imports completed")


def run_admin_interface():
    import werkzeug.serving
    werkzeug.serving.run_simple(
        hostname='0.0.0.0',
        port=8000,
        application=admin_app,
        use_reloader=False,
        use_debugger=False,
        threaded=True
    )


async def run_bot_and_admin():
    global bot_service
    
    try:
        bot_service = BotService()
        await bot_service.initialize()
        set_bot_service(bot_service)
        
        admin_thread = threading.Thread(
            target=run_admin_interface,
            daemon=True
        )
        admin_thread.start()
        
        logger.info("admin_interface_started")
        
        logger.info("starting_telegram_bot")
        await bot_service.start_polling_non_blocking()
        
        logger.info("bot_started_keeping_alive")
        await asyncio.Event().wait()
        
    except Exception as e:
        logger.error("bot_and_admin_failed", error=str(e), exc_info=True)
        raise


def main():
    print("MAIN FUNCTION CALLED")
    logger.info("main_function_called")
    
    def signal_handler(signum, frame):
        logger.info("shutdown_signal_received", signal=signum)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        logger.info("main_starting")
        asyncio.run(run_bot_and_admin())
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt_received")
    except Exception as e:
        logger.error("main_failed", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
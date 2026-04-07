try:
    from importlib.metadata import PackageNotFoundError, version
except ImportError:
    from importlib_metadata import PackageNotFoundError, version


def get_version() -> str:
    try:
        return version("telegram-reminder-bot")
    except PackageNotFoundError:
        return "dev"
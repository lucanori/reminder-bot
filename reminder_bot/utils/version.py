try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:
    from importlib_metadata import version, PackageNotFoundError


def get_version() -> str:
    try:
        return version("telegram-reminder-bot")
    except PackageNotFoundError:
        return "dev"
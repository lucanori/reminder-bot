class ReminderBotException(Exception):
    pass


class DatabaseException(ReminderBotException):
    pass


class TelegramAPIException(ReminderBotException):
    pass


class ValidationException(ReminderBotException):
    pass


class SchedulingException(ReminderBotException):
    pass
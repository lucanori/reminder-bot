from ..models.entities import ReminderEntity, UserEntity, ReminderStatus
from ..models.dtos import ReminderDTO, UserDTO, ReminderCreateDTO


def entity_to_reminder_dto(entity: ReminderEntity) -> ReminderDTO:
    return ReminderDTO(
        id=entity.id,
        user_id=entity.user_id,
        chat_id=entity.chat_id,
        text=entity.text,
        schedule_time=entity.schedule_time,
        interval_days=entity.interval_days,
        status=ReminderStatus(entity.status),
        next_notification=entity.next_notification,
        notification_count=entity.notification_count,
        max_notifications=entity.max_notifications,
        notification_interval_minutes=entity.notification_interval_minutes,
        last_message_id=entity.last_message_id,
        job_id=entity.job_id,
        created_at=entity.created_at,
        updated_at=entity.updated_at
    )


def reminder_create_dto_to_entity(dto: ReminderCreateDTO) -> ReminderEntity:
    return ReminderEntity(
        user_id=dto.user_id,
        chat_id=dto.chat_id,
        text=dto.text,
        schedule_time=dto.schedule_time,
        interval_days=dto.interval_days,
        notification_interval_minutes=dto.notification_interval_minutes,
        max_notifications=dto.max_notifications,
        status=ReminderStatus.ACTIVE.value,
        notification_count=0
    )


def entity_to_user_dto(entity: UserEntity) -> UserDTO:
    return UserDTO(
        telegram_id=entity.telegram_id,
        is_blocked=entity.is_blocked,
        is_whitelisted=entity.is_whitelisted,
        notification_preferences=entity.notification_preferences,
        created_at=entity.created_at,
        updated_at=entity.updated_at
    )
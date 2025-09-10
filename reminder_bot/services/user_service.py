from typing import Optional, List
from datetime import datetime, timedelta
from ..repositories.user_repository import UserRepository
from ..models.entities import UserEntity
from ..models.dtos import UserDTO, UserPreferencesDTO
from ..utils.transformers import entity_to_user_dto
from ..utils.logging import get_logger
from ..utils.exceptions import ValidationException, DatabaseException
from ..config import settings

logger = get_logger()


class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo
        self._rate_limit_cache = {}
        self._rate_limit_window = 60
        self._rate_limit_max_requests = 30

    async def register_or_update_user(self, telegram_id: int) -> UserDTO:
        try:
            if self.user_repo is None:
                from ..utils.database import get_async_session
                
                async with get_async_session() as session:
                    user_repo = UserRepository(session)
                    existing_user = await user_repo.get_by_id(telegram_id)
                    
                    if existing_user:
                        existing_user.updated_at = datetime.utcnow()
                        updated_user = await user_repo.update(existing_user)
                        logger.info("user_updated", user_id=telegram_id)
                        return entity_to_user_dto(updated_user)
                    else:
                        new_user = UserEntity(
                            telegram_id=telegram_id,
                            is_blocked=False,
                            is_whitelisted=False,
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow()
                        )
                        created_user = await user_repo.create(new_user)
                        logger.info("user_registered", user_id=telegram_id)
                        return entity_to_user_dto(created_user)
            else:
                existing_user = await self.user_repo.get_by_id(telegram_id)
                
                if existing_user:
                    existing_user.updated_at = datetime.utcnow()
                    updated_user = await self.user_repo.update(existing_user)
                    logger.info("user_updated", user_id=telegram_id)
                    return entity_to_user_dto(updated_user)
                else:
                    new_user = UserEntity(
                        telegram_id=telegram_id,
                        is_blocked=False,
                        is_whitelisted=False,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    created_user = await self.user_repo.create(new_user)
                    logger.info("user_registered", user_id=telegram_id)
                    return entity_to_user_dto(created_user)
                
        except Exception as e:
            logger.error("user_registration_failed", error=str(e), user_id=telegram_id)
            raise DatabaseException(f"Failed to register/update user: {e}")

    async def check_user_access(self, telegram_id: int) -> bool:
        try:
            if not self._check_rate_limit(telegram_id):
                logger.warning("rate_limit_exceeded", user_id=telegram_id)
                return False
            
            if self.user_repo is None:
                from ..utils.database import get_async_session
                from ..repositories.user_repository import UserRepository
                
                async with get_async_session() as session:
                    user_repo = UserRepository(session)
                    user = await user_repo.get_by_id(telegram_id)
                    
                    if not user:
                        if settings.bot_mode == "whitelist":
                            logger.info("user_not_found_whitelist_mode", user_id=telegram_id)
                            return False
                        else:
                            new_user = UserEntity(
                                telegram_id=telegram_id,
                                is_blocked=False,
                                is_whitelisted=False,
                                created_at=datetime.utcnow(),
                                updated_at=datetime.utcnow()
                            )
                            await user_repo.create(new_user)
                            logger.info("user_registered", user_id=telegram_id)
                            return True
                    
                    if user.is_blocked:
                        logger.info("user_blocked", user_id=telegram_id)
                        return False
                    
                    if settings.bot_mode == "whitelist" and not user.is_whitelisted:
                        logger.info("user_not_whitelisted", user_id=telegram_id)
                        return False
                    
                    if settings.bot_mode == "blocklist" and user.is_blocked:
                        logger.info("user_in_blocklist", user_id=telegram_id)
                        return False
                    
                    return True
            else:
                user = await self.user_repo.get_by_id(telegram_id)
                
                if not user:
                    if settings.bot_mode == "whitelist":
                        logger.info("user_not_found_whitelist_mode", user_id=telegram_id)
                        return False
                    else:
                        await self.register_or_update_user(telegram_id)
                        return True
                
                if user.is_blocked:
                    logger.info("user_blocked", user_id=telegram_id)
                    return False
                
                if settings.bot_mode == "whitelist" and not user.is_whitelisted:
                    logger.info("user_not_whitelisted", user_id=telegram_id)
                    return False
                
                if settings.bot_mode == "blocklist" and user.is_blocked:
                    logger.info("user_in_blocklist", user_id=telegram_id)
                    return False
                
                return True
            
        except Exception as e:
            logger.error("access_check_failed", error=str(e), user_id=telegram_id)
            return False

    async def block_user(self, telegram_id: int) -> bool:
        try:
            success = await self.user_repo.update_blocked_status(telegram_id, True)
            if success:
                logger.info("user_blocked", user_id=telegram_id)
            return success
        except Exception as e:
            logger.error("user_blocking_failed", error=str(e), user_id=telegram_id)
            raise DatabaseException(f"Failed to block user: {e}")

    async def unblock_user(self, telegram_id: int) -> bool:
        try:
            success = await self.user_repo.update_blocked_status(telegram_id, False)
            if success:
                logger.info("user_unblocked", user_id=telegram_id)
            return success
        except Exception as e:
            logger.error("user_unblocking_failed", error=str(e), user_id=telegram_id)
            raise DatabaseException(f"Failed to unblock user: {e}")

    async def whitelist_user(self, telegram_id: int) -> bool:
        try:
            success = await self.user_repo.update_whitelisted_status(telegram_id, True)
            if success:
                logger.info("user_whitelisted", user_id=telegram_id)
            return success
        except Exception as e:
            logger.error("user_whitelisting_failed", error=str(e), user_id=telegram_id)
            raise DatabaseException(f"Failed to whitelist user: {e}")

    async def remove_from_whitelist(self, telegram_id: int) -> bool:
        try:
            success = await self.user_repo.update_whitelisted_status(telegram_id, False)
            if success:
                logger.info("user_removed_from_whitelist", user_id=telegram_id)
            return success
        except Exception as e:
            logger.error("user_whitelist_removal_failed", error=str(e), user_id=telegram_id)
            raise DatabaseException(f"Failed to remove user from whitelist: {e}")

    async def get_user(self, telegram_id: int) -> Optional[UserDTO]:
        try:
            user = await self.user_repo.get_by_id(telegram_id)
            return entity_to_user_dto(user) if user else None
        except Exception as e:
            logger.error("get_user_failed", error=str(e), user_id=telegram_id)
            raise DatabaseException(f"Failed to get user: {e}")

    async def get_all_users(self) -> List[UserDTO]:
        try:
            users = await self.user_repo.get_all()
            return [entity_to_user_dto(user) for user in users]
        except Exception as e:
            logger.error("get_all_users_failed", error=str(e))
            raise DatabaseException(f"Failed to get all users: {e}")

    async def get_user_preferences(self, telegram_id: int) -> UserPreferencesDTO:
        try:
            user = await self.user_repo.get_by_id(telegram_id)
            
            if not user or not user.notification_preferences:
                return UserPreferencesDTO()
            
            import json
            prefs_data = json.loads(user.notification_preferences)
            return UserPreferencesDTO(**prefs_data)
            
        except Exception as e:
            logger.error("get_user_preferences_failed", error=str(e), user_id=telegram_id)
            return UserPreferencesDTO()

    async def update_user_preferences(self, telegram_id: int, preferences: UserPreferencesDTO) -> bool:
        try:
            user = await self.user_repo.get_by_id(telegram_id)
            if not user:
                return False
            
            import json
            user.notification_preferences = json.dumps(preferences.dict())
            user.updated_at = datetime.utcnow()
            
            await self.user_repo.update(user)
            logger.info("user_preferences_updated", user_id=telegram_id)
            return True
            
        except Exception as e:
            logger.error("update_user_preferences_failed", error=str(e), user_id=telegram_id)
            raise DatabaseException(f"Failed to update user preferences: {e}")

    async def get_user_statistics(self) -> dict:
        try:
            all_users = await self.user_repo.get_all()
            
            total_users = len(all_users)
            blocked_users = sum(1 for user in all_users if user.is_blocked)
            whitelisted_users = sum(1 for user in all_users if user.is_whitelisted)
            
            recent_users = sum(
                1 for user in all_users 
                if user.created_at > datetime.utcnow() - timedelta(days=30)
            )
            
            return {
                'total_users': total_users,
                'blocked_users': blocked_users,
                'whitelisted_users': whitelisted_users,
                'recent_users': recent_users,
                'active_users': total_users - blocked_users
            }
            
        except Exception as e:
            logger.error("get_user_statistics_failed", error=str(e))
            raise DatabaseException(f"Failed to get user statistics: {e}")

    def _check_rate_limit(self, telegram_id: int) -> bool:
        now = datetime.utcnow()
        
        if telegram_id not in self._rate_limit_cache:
            self._rate_limit_cache[telegram_id] = []
        
        user_requests = self._rate_limit_cache[telegram_id]
        
        cutoff_time = now - timedelta(seconds=self._rate_limit_window)
        user_requests[:] = [req_time for req_time in user_requests if req_time > cutoff_time]
        
        if len(user_requests) >= self._rate_limit_max_requests:
            return False
        
        user_requests.append(now)
        
        if len(self._rate_limit_cache) > 10000:
            self._cleanup_rate_limit_cache()
        
        return True

    def _cleanup_rate_limit_cache(self) -> None:
        now = datetime.utcnow()
        cutoff_time = now - timedelta(seconds=self._rate_limit_window * 2)
        
        users_to_remove = []
        for user_id, requests in self._rate_limit_cache.items():
            if not requests or (requests and max(requests) < cutoff_time):
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del self._rate_limit_cache[user_id]
        
        logger.debug("rate_limit_cache_cleaned", removed_users=len(users_to_remove))
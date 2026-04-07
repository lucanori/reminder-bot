from datetime import datetime

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from ..bot_service import BotService
from ..config import settings
from ..repositories.reminder_repository import ReminderRepository
from ..repositories.user_repository import UserRepository
from ..services.reminder_service import ReminderService
from ..services.user_service import UserService
from ..utils.database import get_async_session
from ..utils.health import HealthChecker
from ..utils.logging import get_logger
from ..utils.version import get_version

logger = get_logger()

app = Flask(__name__)
app.secret_key = settings.flask_secret_key

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

bot_service_instance: BotService | None = None


class AdminUser(UserMixin):
    def __init__(self, username):
        self.id = username


@login_manager.user_loader
def load_user(user_id):
    if user_id == settings.admin_username:
        return AdminUser(user_id)
    return None


def run_async_safely(coro):
    """Execute an async coroutine safely using the bot's main event loop.

    This helper ensures Flask routes (running in a daemon thread) can execute
    async code without creating new event loops or using asyncio.run().
    """
    global bot_service_instance

    if bot_service_instance is None:
        raise RuntimeError("Bot service not initialized")

    return bot_service_instance.run_coroutine_threadsafe(coro)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == settings.admin_username and password == settings.admin_password:
            user = AdminUser(username)
            login_user(user)
            logger.info("admin_login_successful", username=username)
            return redirect(url_for("dashboard"))
        else:
            logger.warning("admin_login_failed", username=username)
            flash("Invalid credentials")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    username = current_user.id
    logout_user()
    logger.info("admin_logout", username=username)
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html", bot_mode=settings.bot_mode)


@app.route("/api/stats")
@login_required
def api_stats():
    try:

        async def get_stats():
            async with get_async_session() as session:
                user_repo = UserRepository(session)
                reminder_repo = ReminderRepository(session)
                user_service = UserService(user_repo)
                reminder_service = ReminderService(reminder_repo)

                user_stats = await user_service.get_user_statistics()
                logger.info("user_stats_retrieved", stats=user_stats)

                active_reminders = await reminder_service.get_active_reminders()
                all_reminders_entities = await reminder_repo.get_all_reminders()

                return {
                    "users": {
                        "total_users": user_stats.get("total_users", 0),
                        "active_users": user_stats.get("active_users", 0),
                        "recent_users": user_stats.get("recent_users", 0),
                        "blocked_users": user_stats.get("blocked_users", 0),
                        "whitelisted_users": user_stats.get("whitelisted_users", 0),
                    },
                    "reminders": {
                        "total_active": len(active_reminders),
                        "total_reminders": len(all_reminders_entities),
                    },
                }

        stats = run_async_safely(get_stats())
        return jsonify(stats)

    except Exception as e:
        logger.error("admin_stats_failed", error=str(e), exc_info=True)
        return jsonify({"error": "Failed to fetch statistics"}), 500


@app.route("/users")
@login_required
def users():
    try:

        async def get_users():
            async with get_async_session() as session:
                user_repo = UserRepository(session)
                user_service = UserService(user_repo)
                all_users = await user_service.get_all_users()
                return all_users

        users_list = run_async_safely(get_users())

        active_users = sorted(
            [u for u in users_list if not u.is_blocked],
            key=lambda u: u.created_at,
            reverse=True,
        )
        blocked_users = sorted(
            [u for u in users_list if u.is_blocked],
            key=lambda u: u.created_at,
            reverse=True,
        )

        return render_template(
            "users.html",
            bot_mode=settings.bot_mode,
            active_users=active_users,
            blocked_users=blocked_users,
        )

    except Exception as e:
        logger.error("admin_users_view_failed", error=str(e), exc_info=True)
        flash("Failed to load users", "error")
        return render_template(
            "users.html",
            bot_mode=settings.bot_mode,
            active_users=[],
            blocked_users=[],
        )


@app.route("/block_user/<int:user_id>", methods=["GET"])
@login_required
def block_user(user_id):
    try:

        async def do_block():
            async with get_async_session() as session:
                user_repo = UserRepository(session)
                user_service = UserService(user_repo)
                return await user_service.block_user(user_id)

        success = run_async_safely(do_block())

        if success:
            logger.info("admin_user_blocked", admin=current_user.id, user_id=user_id)
            flash(f"User {user_id} has been blocked", "success")
        else:
            flash(f"User {user_id} not found", "warning")

    except Exception as e:
        logger.error("admin_block_user_failed", error=str(e), user_id=user_id)
        flash(f"Failed to block user: {str(e)}", "error")

    return redirect(url_for("users"))


@app.route("/unblock_user/<int:user_id>", methods=["GET"])
@login_required
def unblock_user(user_id):
    try:

        async def do_unblock():
            async with get_async_session() as session:
                user_repo = UserRepository(session)
                user_service = UserService(user_repo)
                return await user_service.unblock_user(user_id)

        success = run_async_safely(do_unblock())

        if success:
            logger.info("admin_user_unblocked", admin=current_user.id, user_id=user_id)
            flash(f"User {user_id} has been unblocked", "success")
        else:
            flash(f"User {user_id} not found", "warning")

    except Exception as e:
        logger.error("admin_unblock_user_failed", error=str(e), user_id=user_id)
        flash(f"Failed to unblock user: {str(e)}", "error")

    return redirect(url_for("users"))


@app.route("/whitelist_user/<int:user_id>", methods=["GET"])
@login_required
def whitelist_user(user_id):
    try:

        async def do_whitelist():
            async with get_async_session() as session:
                user_repo = UserRepository(session)
                user_service = UserService(user_repo)
                return await user_service.whitelist_user(user_id)

        success = run_async_safely(do_whitelist())

        if success:
            logger.info(
                "admin_user_whitelisted", admin=current_user.id, user_id=user_id
            )
            flash(f"User {user_id} has been added to whitelist", "success")
        else:
            flash(f"User {user_id} not found", "warning")

    except Exception as e:
        logger.error("admin_whitelist_user_failed", error=str(e), user_id=user_id)
        flash(f"Failed to whitelist user: {str(e)}", "error")

    return redirect(url_for("users"))


@app.route("/remove_whitelist/<int:user_id>", methods=["GET"])
@login_required
def remove_whitelist(user_id):
    try:

        async def do_remove_whitelist():
            async with get_async_session() as session:
                user_repo = UserRepository(session)
                user_service = UserService(user_repo)
                return await user_service.remove_from_whitelist(user_id)

        success = run_async_safely(do_remove_whitelist())

        if success:
            logger.info(
                "admin_user_removed_from_whitelist",
                admin=current_user.id,
                user_id=user_id,
            )
            flash(f"User {user_id} has been removed from whitelist", "success")
        else:
            flash(f"User {user_id} not found", "warning")

    except Exception as e:
        logger.error(
            "admin_remove_whitelist_user_failed", error=str(e), user_id=user_id
        )
        flash(f"Failed to remove user from whitelist: {str(e)}", "error")

    return redirect(url_for("users"))


@app.route("/api/users")
@login_required
def api_users():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 50))

        async def get_users():
            async with get_async_session() as session:
                user_repo = UserRepository(session)
                user_service = UserService(user_repo)
                return await user_service.get_all_users()

        users = run_async_safely(get_users())

        start = (page - 1) * per_page
        end = start + per_page
        paginated_users = users[start:end]

        users_data = []
        for user in paginated_users:
            users_data.append(
                {
                    "telegram_id": user.telegram_id,
                    "is_blocked": user.is_blocked,
                    "is_whitelisted": user.is_whitelisted,
                    "created_at": user.created_at.isoformat(),
                    "updated_at": user.updated_at.isoformat(),
                }
            )

        return jsonify(
            {
                "users": users_data,
                "total": len(users),
                "page": page,
                "per_page": per_page,
                "pages": (len(users) + per_page - 1) // per_page,
            }
        )

    except Exception as e:
        logger.error("admin_users_list_failed", error=str(e), exc_info=True)
        return jsonify({"error": "Failed to fetch users"}), 500


@app.route("/api/users/<int:user_id>/block", methods=["POST"])
@login_required
def api_block_user(user_id):
    try:

        async def block_user():
            async with get_async_session() as session:
                user_repo = UserRepository(session)
                user_service = UserService(user_repo)
                return await user_service.block_user(user_id)

        success = run_async_safely(block_user())

        if success:
            logger.info("admin_user_blocked", admin=current_user.id, user_id=user_id)
            return jsonify({"success": True, "message": "User blocked successfully"})
        else:
            return jsonify({"success": False, "message": "User not found"}), 404

    except Exception as e:
        logger.error("admin_block_user_failed", error=str(e), user_id=user_id)
        return jsonify({"success": False, "message": "Failed to block user"}), 500


@app.route("/api/users/<int:user_id>/unblock", methods=["POST"])
@login_required
def api_unblock_user(user_id):
    try:

        async def unblock_user():
            async with get_async_session() as session:
                user_repo = UserRepository(session)
                user_service = UserService(user_repo)
                return await user_service.unblock_user(user_id)

        success = run_async_safely(unblock_user())

        if success:
            logger.info("admin_user_unblocked", admin=current_user.id, user_id=user_id)
            return jsonify({"success": True, "message": "User unblocked successfully"})
        else:
            return jsonify({"success": False, "message": "User not found"}), 404

    except Exception as e:
        logger.error("admin_unblock_user_failed", error=str(e), user_id=user_id)
        return jsonify({"success": False, "message": "Failed to unblock user"}), 500


@app.route("/static/logo.png")
def logo():
    import os

    logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "templates")
    return send_from_directory(logo_path, "logo.png")


@app.route("/favicon.ico")
def favicon():
    import os

    logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "templates")
    return send_from_directory(logo_path, "logo.png")


@app.route("/health")
def health():
    try:
        version = get_version()

        async def check_health():
            health_status = {
                "status": "healthy",
                "version": version,
                "timestamp": datetime.utcnow().isoformat(),
                "database_connected": False,
                "scheduler_running": False,
                "bot_connected": False,
            }

            try:
                from sqlalchemy import text

                async with get_async_session() as session:
                    await session.execute(text("SELECT 1"))
                health_status["database_connected"] = True
            except Exception as db_err:
                logger.error("health_check_database_failed", error=str(db_err))
                health_status["status"] = "unhealthy"

            if bot_service_instance:
                try:
                    health_checker = HealthChecker(bot_service_instance)
                    detailed_health = await health_checker.comprehensive_health_check()

                    components = detailed_health.get("components", {})
                    if "bot" in components:
                        health_status["bot_connected"] = components["bot"].get(
                            "healthy", False
                        )
                    if "scheduler" in components:
                        health_status["scheduler_running"] = components[
                            "scheduler"
                        ].get("healthy", False)

                    health_status["status"] = detailed_health.get("status", "healthy")

                except Exception as bot_err:
                    logger.error("health_check_bot_failed", error=str(bot_err))
                    health_status["status"] = "degraded"

            if not health_status["database_connected"]:
                health_status["status"] = "unhealthy"

            return health_status

        health_status = run_async_safely(check_health())

        status_code = 200 if health_status["status"] == "healthy" else 503
        return jsonify(health_status), status_code

    except Exception as e:
        logger.error("health_check_failed", error=str(e), exc_info=True)
        return jsonify(
            {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
        ), 503


def set_bot_service(bot_service):
    global bot_service_instance
    bot_service_instance = bot_service


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=settings.debug)

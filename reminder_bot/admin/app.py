import asyncio
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from ..config import settings
from ..utils.database import get_async_session
from ..utils.logging import get_logger
from ..repositories.user_repository import UserRepository
from ..repositories.reminder_repository import ReminderRepository
from ..services.user_service import UserService
from ..services.reminder_service import ReminderService
from ..bot_service import BotService

logger = get_logger()

app = Flask(__name__)
app.secret_key = settings.flask_secret_key

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

bot_service_instance = None


class AdminUser(UserMixin):
    def __init__(self, username):
        self.id = username


@login_manager.user_loader
def load_user(user_id):
    if user_id == settings.admin_username:
        return AdminUser(user_id)
    return None


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == settings.admin_username and password == settings.admin_password:
            user = AdminUser(username)
            login_user(user)
            logger.info("admin_login_successful", username=username)
            return redirect(url_for('dashboard'))
        else:
            logger.warning("admin_login_failed", username=username)
            flash('Invalid credentials')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    username = current_user.id
    logout_user()
    logger.info("admin_logout", username=username)
    return redirect(url_for('login'))


@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')


@app.route('/api/stats')
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
                    'users': {
                        'total_users': user_stats.get('total_users', 0),
                        'active_users': user_stats.get('active_users', 0),
                        'recent_users': user_stats.get('recent_users', 0),
                        'blocked_users': user_stats.get('blocked_users', 0),
                        'whitelisted_users': user_stats.get('whitelisted_users', 0)
                    },
                    'reminders': {
                        'total_active': len(active_reminders),
                        'total_reminders': len(all_reminders_entities)
                    }
                }
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, get_stats())
                    stats = future.result()
            else:
                stats = loop.run_until_complete(get_stats())
        except RuntimeError:
            stats = asyncio.run(get_stats())
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error("admin_stats_failed", error=str(e), exc_info=True)
        return jsonify({'error': 'Failed to fetch statistics'}), 500


@app.route('/users')
@login_required
def users():
    return render_template('users.html')


@app.route('/api/users')
@login_required
def api_users():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        async def get_users():
            async with get_async_session() as session:
                user_repo = UserRepository(session)
                user_service = UserService(user_repo)
                return await user_service.get_all_users()
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, get_users())
                    users = future.result()
            else:
                users = loop.run_until_complete(get_users())
        except RuntimeError:
            users = asyncio.run(get_users())
        
        start = (page - 1) * per_page
        end = start + per_page
        paginated_users = users[start:end]
        
        users_data = []
        for user in paginated_users:
            users_data.append({
                'telegram_id': user.telegram_id,
                'is_blocked': user.is_blocked,
                'is_whitelisted': user.is_whitelisted,
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat()
            })
        
        return jsonify({
            'users': users_data,
            'total': len(users),
            'page': page,
            'per_page': per_page,
            'pages': (len(users) + per_page - 1) // per_page
        })
        
    except Exception as e:
        logger.error("admin_users_list_failed", error=str(e), exc_info=True)
        return jsonify({'error': 'Failed to fetch users'}), 500


@app.route('/api/users/<int:user_id>/block', methods=['POST'])
@login_required
def api_block_user(user_id):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def block_user():
            async with get_async_session() as session:
                user_repo = UserRepository(session)
                user_service = UserService(user_repo)
                return await user_service.block_user(user_id)
        
        success = loop.run_until_complete(block_user())
        loop.close()
        
        if success:
            logger.info("admin_user_blocked", admin=current_user.id, user_id=user_id)
            return jsonify({'success': True, 'message': 'User blocked successfully'})
        else:
            return jsonify({'success': False, 'message': 'User not found'}), 404
            
    except Exception as e:
        logger.error("admin_block_user_failed", error=str(e), user_id=user_id)
        return jsonify({'success': False, 'message': 'Failed to block user'}), 500


@app.route('/api/users/<int:user_id>/unblock', methods=['POST'])
@login_required
def api_unblock_user(user_id):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def unblock_user():
            async with get_async_session() as session:
                user_repo = UserRepository(session)
                user_service = UserService(user_repo)
                return await user_service.unblock_user(user_id)
        
        success = loop.run_until_complete(unblock_user())
        loop.close()
        
        if success:
            logger.info("admin_user_unblocked", admin=current_user.id, user_id=user_id)
            return jsonify({'success': True, 'message': 'User unblocked successfully'})
        else:
            return jsonify({'success': False, 'message': 'User not found'}), 404
            
    except Exception as e:
        logger.error("admin_unblock_user_failed", error=str(e), user_id=user_id)
        return jsonify({'success': False, 'message': 'Failed to unblock user'}), 500


@app.route('/static/logo.png')
def logo():
    import os
    logo_path = os.path.join(os.path.dirname(__file__), '..', '..', 'templates')
    return send_from_directory(logo_path, 'logo.png')

@app.route('/favicon.ico')
def favicon():
    import os
    logo_path = os.path.join(os.path.dirname(__file__), '..', '..', 'templates')
    return send_from_directory(logo_path, 'logo.png')

@app.route('/health')
def health():
    try:
        async def check_health():
            from sqlalchemy import text
            async with get_async_session() as session:
                await session.execute(text("SELECT 1"))
            
            return {
                'status': 'healthy',
                'database_connected': True,
                'timestamp': datetime.utcnow().isoformat(),
                'version': '2.0.0'
            }
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, check_health())
                    health_status = future.result()
            else:
                health_status = loop.run_until_complete(check_health())
        except RuntimeError:
            health_status = asyncio.run(check_health())
        
        return jsonify(health_status), 200
            
    except Exception as e:
        logger.error("health_check_failed", error=str(e), exc_info=True)
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503


def set_bot_service(bot_service):
    global bot_service_instance
    bot_service_instance = bot_service


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=settings.debug)
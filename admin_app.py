import os
from flask import Flask, request, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
import sys # Add this import
from models import SessionLocal, User # Import database session and User model

# --- Configuration ---
ADMIN_USERNAME = os.environ.get('ADMIN_USER', 'admin')
# For simplicity in this example, we're directly using the password.
# In a real application, hash the password and store the hash.
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'password')
SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'a_default_secret_key_change_me') # Needed for sessions

# --- Flask App Setup ---
app = Flask(__name__)
print("Flask app object created successfully.", file=sys.stderr) # Add this log
app.config['SECRET_KEY'] = SECRET_KEY

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Redirect to 'login' view if user tries to access protected page

# Simple User class for the admin
class AdminUser(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    # Since we only have one admin user
    if user_id == ADMIN_USERNAME:
        return AdminUser(user_id)
    return None

# --- Routes ---

# Add this new root route
@app.route('/')
def index():
    # Redirect root access to the admin login page
    return redirect(url_for('login'))

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Basic authentication check (replace with hashed password check in production)
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            user = AdminUser(username)
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')

@app.route('/admin/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
@login_required
def dashboard():
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.telegram_id).all()
    finally:
        db.close()

    bot_mode = os.environ.get('BOT_MODE', 'blocklist')
    return render_template('dashboard.html', users=users, bot_mode=bot_mode)

@app.route('/admin/block/<int:user_id>')
@login_required
def block_user(user_id):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if user:
            user.is_blocked = True
            db.commit()
            flash(f'User {user_id} blocked successfully.', 'success')
        else:
            flash(f'User {user_id} not found.', 'danger')
    except Exception as e:
        db.rollback()
        flash(f'Error blocking user {user_id}: {e}', 'danger')
    finally:
        db.close()
    return redirect(url_for('dashboard'))

@app.route('/admin/unblock/<int:user_id>')
@login_required
def unblock_user(user_id):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if user:
            user.is_blocked = False
            db.commit()
            flash(f'User {user_id} unblocked successfully.', 'success')
        else:
            flash(f'User {user_id} not found.', 'danger')
    except Exception as e:
        db.rollback()
        flash(f'Error unblocking user {user_id}: {e}', 'danger')
    finally:
        db.close()
    return redirect(url_for('dashboard'))

@app.route('/admin/whitelist/<int:user_id>')
@login_required
def whitelist_user(user_id):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if user:
            user.is_whitelisted = True
            db.commit()
            flash(f'User {user_id} whitelisted successfully.', 'success')
        else:
            # If user doesn't exist, create them and whitelist
            new_user = User(telegram_id=user_id, is_whitelisted=True, is_blocked=False)
            db.add(new_user)
            db.commit()
            flash(f'User {user_id} created and whitelisted successfully.', 'success')
            # flash(f'User {user_id} not found.', 'danger') # Original logic if creation isn't desired
    except Exception as e:
        db.rollback()
        flash(f'Error whitelisting user {user_id}: {e}', 'danger')
    finally:
        db.close()
    return redirect(url_for('dashboard'))

# --- Main Execution (for potential direct running, though Docker setup will handle it) ---
if __name__ == '__main__':
    # Use 0.0.0.0 to be accessible within Docker network
    app.run(host='0.0.0.0', port=5011, debug=True) # Use a different port than the bot if run separately
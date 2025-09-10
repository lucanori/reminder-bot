# Telegram Reminder Bot

Advanced Telegram bot for task reminders with persistent notifications, built following 12-factor app principles and modern Python best practices.

## Features

- 🔔 **Smart Notifications**: Escalating notification intervals with automatic suspension
- 📅 **Flexible Scheduling**: One-time, daily, weekly, or custom interval reminders
- 💾 **Persistent Storage**: SQLite database with async operations and migrations
- 🔒 **Access Control**: Whitelist/blocklist modes with rate limiting
- 📊 **Admin Interface**: Web-based dashboard for user management
- 🐳 **Containerized**: Docker support with health checks
- 🧪 **Fully Tested**: Comprehensive test suite with 80%+ coverage
- 📈 **Observability**: Structured logging and health monitoring

## Quick Start

### Prerequisites

- Python 3.11+
- uv (recommended) or pip
- Telegram Bot Token (from @BotFather)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd reminder-bot
```

2. Copy and configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Install dependencies:
```bash
uv sync
```

4. Run the bot:
```bash
uv run python -m reminder_bot
```

### Docker Deployment

1. Build the image locally:
```bash
docker compose -f docker-compose.local.yml up -d --build
```

2. Run the official container from GHCR.io:
```bash
docker compose up -d
```

The bot will be available on port 8000 for the admin interface.

## Configuration

All configuration is done via environment variables (12-factor compliant):

### Required Variables

- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `ADMIN_USERNAME`: Admin interface username
- `ADMIN_PASSWORD`: Admin interface password
- `FLASK_SECRET_KEY`: Secret key for Flask sessions

### Optional Variables

- `DATABASE_URL`: Database connection string (default: SQLite)
- `BOT_MODE`: `blocklist` or `whitelist` (default: blocklist)
- `LOG_LEVEL`: Logging level (default: INFO)
- `DEBUG`: Enable debug mode (default: false)
- `DEFAULT_NOTIFICATION_INTERVAL`: Minutes between notifications (default: 5)
- `MAX_NOTIFICATIONS_PER_REMINDER`: Max attempts before suspension (default: 10)
- `TELEGRAM_WEBHOOK_URL`: Optional webhook URL for production deployments (see Bot Modes below)
- `TIMEZONE`: Bot timezone (default: UTC)

## Versioning

The project uses **automatic semantic versioning** based on Git tags:

- **Development versions**: `1.2.3.dev5+g1a2b3c4` (auto-generated between releases)
- **Release versions**: `1.2.3` (when you create a Git tag like `v1.2.3`)
- **No hardcoded versions**: Version is determined dynamically from Git history

To create a release:
```bash
git tag v1.2.3
git push origin v1.2.3
```

The version is automatically available at runtime and in health checks.

## Bot Modes

The bot supports two operational modes for receiving Telegram updates:

### 🔄 Polling Mode (Default)

**When to use**: Development, testing, small-scale deployments

- Bot actively requests updates from Telegram every few seconds
- No additional infrastructure required
- Works behind NAT/firewalls
- Slightly higher resource usage

**Configuration**: Leave `TELEGRAM_WEBHOOK_URL` empty (default)

### 📡 Webhook Mode

**When to use**: Production deployments, high-traffic bots

- Telegram pushes updates directly to your server
- Lower latency and resource usage
- Requires publicly accessible HTTPS endpoint
- Better for scaling

**Configuration**: Set `TELEGRAM_WEBHOOK_URL=https://yourdomain.com/webhook`

**Requirements**:
- Public domain with valid SSL certificate
- Server accessible from internet on port 443 or 8443
- Reverse proxy (nginx) recommended for SSL termination

## Smart Notification System

The bot features an intelligent escalation system:

### Escalation Timeline
- **1st notification**: 5 minutes after scheduled time
- **2nd notification**: 5 minutes later (10 min total)
- **3rd notification**: 10 minutes later (20 min total)  
- **4th notification**: 15 minutes later (35 min total)
- **5th notification**: 25 minutes later (60 min total)
- **6th+ notifications**: 30 minutes later (max interval cap)

### Automatic Management
- **Max attempts**: 10 notifications by default (configurable 1-50)
- **Auto-suspension**: Reminders automatically suspend after max attempts
- **Clean messaging**: Previous notifications deleted to prevent spam
- **Progress tracking**: Shows attempt count (e.g., "Attempt 3/10")

## Usage

### User Commands

- `/start` - Initialize the bot and get welcome message
- `/help` - Show help and usage examples
- `/set` - Create a new reminder (guided conversation)
- `/view` - List your active reminders
- `/delete` - Delete a reminder by ID

### Creating Reminders

1. Use `/set` command
2. Enter reminder text (e.g., "Take vitamins")
3. Set time in HH:MM format (e.g., "08:30")
4. Choose repeat interval:
   - 0 days: One-time reminder
   - 1 day: Daily
   - 7 days: Weekly
   - Custom: Any number of days

### Interactive Features

- **Action Buttons**: ✅ Complete or ⏰ Snooze (5 minutes)
- **Time Display**: Shows user-set time and next execution time in UTC
- **Status Indicators**: Visual indicators for active reminders and attempt counts

## Admin Interface

Access the web interface at `http://localhost:8000`:

- **Dashboard**: System statistics and overview
- **User Management**: Block/unblock users, view statistics
- **Health Monitoring**: Component status and diagnostics

Default admin credentials are set via environment variables.

## Architecture

The bot follows a clean, modular architecture:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram API  │◄──►│   Bot Service   │◄──►│   Database      │
└─────────────────┘    └─────────────────┘    │   (SQLite)      │
                                │              └─────────────────┘
                                ▼
                       ┌─────────────────┐
                       │  Job Scheduler  │
                       │  (APScheduler)  │
                       └─────────────────┘
```

### Key Components

- **Bot Service**: Main orchestrator and Telegram integration
- **Reminder Service**: Business logic for reminder management  
- **Notification Service**: Smart notification handling with message management
- **User Service**: Access control and user management
- **Job Scheduler**: Persistent job scheduling with recovery
- **Repository Layer**: Data access with async SQLAlchemy

## Development

### Setup Development Environment

```bash
# Install development dependencies
uv sync --dev

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run tests with coverage
pytest --cov=reminder_bot --cov-report=html

# Format code
ruff format .

# Lint code
ruff check .
```

### Project Structure

```
reminder-bot/
├── reminder_bot/          # Main application code
│   ├── models/           # Data models and DTOs
│   ├── services/         # Business logic services
│   ├── repositories/     # Data access layer
│   ├── handlers/         # Telegram command/callback handlers
│   ├── utils/           # Utilities and helpers
│   └── admin/           # Web admin interface
├── tests/               # Test suite
│   ├── unit/           # Unit tests
│   ├── integration/    # Integration tests
│   └── e2e/           # End-to-end tests
├── alembic/            # Database migrations
└── data/              # SQLite database storage
```

### Code Quality Standards

- **Zero Comments Policy**: Code must be self-documenting
- **Type Safety**: Full type hints with Pyright checking
- **Testing**: 80%+ test coverage requirement
- **Linting**: Ruff for formatting and code quality
- **Architecture**: Clean architecture with dependency injection

## Database

The bot uses SQLite by default with async SQLAlchemy:

### Migrations

```bash
# Generate migration
alembic revision --autogenerate -m "Description"

# Run migrations
alembic upgrade head
```

### Schema

- **users**: User profiles and access control
- **reminders**: Reminder definitions and state
- **notification_history**: Notification tracking

## Monitoring & Health Checks

### Health Endpoint

- **URL**: `GET /health`
- **Docker Health Check**: Built-in container health monitoring
- **Components**: Database, Bot API, Scheduler status

### Logging

Structured JSON logging with correlation IDs:

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "info", 
  "event": "reminder_created",
  "user_id": 12345,
  "reminder_id": 67890
}
```

## Security

- **Rate Limiting**: 30 requests per minute per user
- **Access Control**: Whitelist/blocklist modes
- **Input Validation**: Comprehensive data validation
- **Secure Defaults**: Non-root container execution
- **Error Handling**: No sensitive data in logs

## Performance

- **Async Architecture**: Non-blocking I/O throughout
- **Connection Pooling**: Optimized database connections
- **Circuit Breakers**: Fault tolerance for external services
- **Resource Management**: Proper cleanup and memory management

## Deployment

### Docker Production Setup

1. Create production environment file:
```bash
cp .env.example .env.prod
# Configure with production values
```

2. Deploy with Docker Compose:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

3. Monitor logs:
```bash
docker-compose logs -f reminder-bot
```

### Health Monitoring

```bash
# Check health endpoint
curl http://localhost:8000/health

# Check container health
docker inspect --format='{{.State.Health.Status}}' reminder-bot
```

### Backup & Recovery

```bash
# Backup database
cp ./data/reminders.db ./backups/reminders-$(date +%Y%m%d).db

# Restore database
docker-compose down
cp ./backups/reminders-20240101.db ./data/reminders.db
docker-compose up -d
```

## Troubleshooting

### Common Issues

1. **Bot not responding**: Check `TELEGRAM_BOT_TOKEN` is correct
2. **Database read-only errors**: Ensure `./data` directory and files have correct permissions:
   ```bash
   sudo chown -R 65534:65534 data/
   sudo chmod 755 data/ && sudo chmod 664 data/reminders.db
   ```
3. **Admin interface 503**: Check if bot service is running  
4. **Notifications not sent**: Verify scheduler is running in health check
5. **Python 3.13 compatibility**: Ensure using `python-telegram-bot>=22.0` (auto-handled by uv)

### Debug Mode

```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
python -m reminder_bot
```

### Logs Analysis

```bash
# View structured logs
docker-compose logs reminder-bot | jq '.'

# Filter by event type
docker-compose logs reminder-bot | jq 'select(.event == "reminder_created")'
```

## Contributing

1. Follow the existing code style and architecture
2. Add tests for new functionality
3. Update documentation for user-facing changes
4. Use conventional commit messages
5. Ensure all checks pass before submitting PR

## License

This project is licensed under the MIT License.

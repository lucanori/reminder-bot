#!/bin/bash
set -e

# Defaults
DEFAULT_UID=1000
DEFAULT_GID=1000
DEFAULT_UMASK=0022
APP_USER=appuser
APP_GROUP=appgroup
APP_HOME=/app

# Use environment variables or defaults
CURRENT_UID=${UID:-$DEFAULT_UID}
CURRENT_GID=${GID:-$DEFAULT_GID}
CURRENT_UMASK=${UMASK:-$DEFAULT_UMASK}

# Set UMASK
echo "Setting UMASK to $CURRENT_UMASK"
umask "$CURRENT_UMASK"

# Create group if it doesn't exist
echo "Checking if group $CURRENT_GID exists"
if ! getent group "$CURRENT_GID" > /dev/null 2>&1; then
    if ! getent group "$APP_GROUP" > /dev/null 2>&1; then
        echo "Creating group $APP_GROUP with GID $CURRENT_GID"
        groupadd -g "$CURRENT_GID" "$APP_GROUP"
    else
        # If default group name exists, use GID as group name
        APP_GROUP="$CURRENT_GID"
        echo "Creating group $APP_GROUP with GID $CURRENT_GID"
        groupadd -g "$CURRENT_GID" "$APP_GROUP"
    fi
else
    # Group with GID exists, get its name
    APP_GROUP=$(getent group "$CURRENT_GID" | cut -d: -f1)
    echo "Group $CURRENT_GID exists with name $APP_GROUP"
fi

# Create user if it doesn't exist
echo "Checking if user $CURRENT_UID exists"
if ! getent passwd "$CURRENT_UID" > /dev/null 2>&1; then
    if ! getent passwd "$APP_USER" > /dev/null 2>&1; then
        echo "Creating user $APP_USER with UID $CURRENT_UID and GID $CURRENT_GID"
        useradd --shell /bin/bash -u "$CURRENT_UID" -g "$APP_GROUP" -m -d "$APP_HOME" "$APP_USER"
    else
        # If default user name exists, use UID as user name
        APP_USER="$CURRENT_UID"
        echo "Creating user $APP_USER with UID $CURRENT_UID and GID $CURRENT_GID"
        useradd --shell /bin/bash -u "$CURRENT_UID" -g "$APP_GROUP" -m -d "$APP_HOME" "$APP_USER"
    fi
else
    # User with UID exists, get their name
    APP_USER=$(getent passwd "$CURRENT_UID" | cut -d: -f1)
    echo "User $CURRENT_UID exists with name $APP_USER"
    # Ensure user is part of the correct group
    echo "Ensuring user $APP_USER is part of group $APP_GROUP"
    usermod -g "$APP_GROUP" "$APP_USER"
    # Ensure home directory exists and has correct ownership if useradd didn't create it
    echo "Ensuring home directory $APP_HOME exists and has correct ownership"
    mkdir -p "$APP_HOME"
    chown "$CURRENT_UID":"$CURRENT_GID" "$APP_HOME"
fi

# Ensure data directory exists and has correct permissions
mkdir -p "$APP_HOME/data"
chown -R "$CURRENT_UID":"$CURRENT_GID" "$APP_HOME"
chmod +x /app/*.py # Ensure scripts are executable by the user

# Execute the command (supervisord) as root.
# Supervisord will handle user switching for child processes based on its config.
echo "Executing command as root: $@"
exec "$@"
"""Initial migration with weekday and cron support

Revision ID: 001_initial_schema
Revises:
Create Date: 2024-04-08 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("is_blocked", sa.Boolean(), nullable=False),
        sa.Column("is_whitelisted", sa.Boolean(), nullable=False),
        sa.Column("notification_preferences", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("telegram_id"),
    )

    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("schedule_time", sa.String(length=5), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("cron_expression", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("next_notification", sa.DateTime(), nullable=False),
        sa.Column("notification_count", sa.Integer(), nullable=False),
        sa.Column("max_notifications", sa.Integer(), nullable=False),
        sa.Column("notification_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("last_message_id", sa.Integer(), nullable=True),
        sa.Column("job_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.telegram_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )

    op.create_table(
        "notification_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reminder_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("response_type", sa.String(length=50), nullable=True),
        sa.Column("response_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["reminder_id"],
            ["reminders.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("notification_history")
    op.drop_table("reminders")
    op.drop_table("users")

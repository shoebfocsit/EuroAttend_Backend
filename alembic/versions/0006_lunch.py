"""Lunch reminder setting. Run: alembic upgrade head"""
revision = "0006_lunch"
down_revision = "0005_ot"

from alembic import op
import sqlalchemy as sa


def upgrade():
    try:
        op.add_column("settings", sa.Column("lunch_reminder_at", sa.String(5), server_default="13:00"))
    except Exception:
        pass


def downgrade():
    try:
        op.drop_column("settings", "lunch_reminder_at")
    except Exception:
        pass

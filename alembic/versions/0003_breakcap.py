"""45-min break cap. Run: alembic upgrade head"""
revision = "0003_breakcap"
down_revision = "0002_breaks"

from alembic import op
import sqlalchemy as sa


def upgrade():
    try:
        op.add_column("settings", sa.Column("max_break_minutes", sa.Integer, server_default="45"))
    except Exception:
        pass


def downgrade():
    try:
        op.drop_column("settings", "max_break_minutes")
    except Exception:
        pass

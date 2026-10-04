"""Breaks + min-shift-hours policy. Run: alembic upgrade head"""
revision = "0002_breaks"
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "breaks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("attendance_id", sa.Integer, sa.ForeignKey("attendance.id"), index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), index=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_lat", sa.Float, nullable=True),
        sa.Column("start_lng", sa.Float, nullable=True),
        sa.Column("end_lat", sa.Float, nullable=True),
        sa.Column("end_lng", sa.Float, nullable=True),
        sa.Column("duration_minutes", sa.Integer, nullable=True),
    )
    try:
        op.add_column("attendance", sa.Column("break_minutes", sa.Integer, server_default="0"))
    except Exception:
        pass
    try:
        op.add_column("settings", sa.Column("min_shift_hours", sa.Float, server_default="8.0"))
    except Exception:
        pass


def downgrade():
    op.drop_table("breaks")
    try:
        op.drop_column("attendance", "break_minutes")
    except Exception:
        pass
    try:
        op.drop_column("settings", "min_shift_hours")
    except Exception:
        pass

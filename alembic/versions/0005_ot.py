"""Overtime + per-user policy. Run: alembic upgrade head"""
revision = "0005_ot"
down_revision = "0004_gpsacc"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "user_policy",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("shift_start", sa.String(5), nullable=True),
        sa.Column("shift_end", sa.String(5), nullable=True),
        sa.Column("late_after", sa.Integer, nullable=True),
        sa.Column("min_shift_hours", sa.Float, nullable=True),
        sa.Column("max_break_minutes", sa.Integer, nullable=True),
        sa.Column("max_accuracy_m", sa.Float, nullable=True),
        sa.Column("overtime_allowed", sa.Boolean, nullable=True),
        sa.Column("overtime_limit_hours", sa.Float, nullable=True),
    )
    for col, typ, default in [
        ("overtime_started_at", sa.DateTime(timezone=True), None),
        ("overtime_minutes", sa.Integer(), "0"),
        ("overtime_allowed", sa.Boolean(), "1"),
        ("overtime_limit_hours", sa.Float(), "3.0"),
    ]:
        table = "settings" if col.startswith("overtime_") and col != "overtime_started_at" and col != "overtime_minutes" else "attendance"
        if col in ("overtime_allowed", "overtime_limit_hours"):
            table = "settings"
        try:
            op.add_column(table, sa.Column(col, typ, server_default=default))
        except Exception:
            pass


def downgrade():
    op.drop_table("user_policy")
    for table, col in [("attendance", "overtime_started_at"), ("attendance", "overtime_minutes"),
                       ("settings", "overtime_allowed"), ("settings", "overtime_limit_hours")]:
        try:
            op.drop_column(table, col)
        except Exception:
            pass

"""Initial schema: users, attendance, location_logs, events, settings, user_policy."""
revision = "0001_initial"
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("mobile", sa.String(15), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="employee"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "attendance",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), index=True, nullable=False),
        sa.Column("date", sa.Date, index=True, nullable=False),
        sa.Column("punch_in_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("punch_out_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("in_lat", sa.Float, nullable=True),
        sa.Column("in_lng", sa.Float, nullable=True),
        sa.Column("in_accuracy", sa.Float, nullable=True),
        sa.Column("out_lat", sa.Float, nullable=True),
        sa.Column("out_lng", sa.Float, nullable=True),
        sa.Column("out_accuracy", sa.Float, nullable=True),
        sa.Column("in_selfie_url", sa.String(500), nullable=True),
        sa.Column("out_selfie_url", sa.String(500), nullable=True),
        sa.Column("total_minutes", sa.Integer, nullable=True),
        sa.Column("break_minutes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("overtime_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("overtime_minutes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_distance_m", sa.Float, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="Present"),
        sa.Column("is_mock_in", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("outside_geofence", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("auto_punched_out", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("device_info", sa.String(500), nullable=True),
        sa.UniqueConstraint("user_id", "date", name="uq_attendance_user_date"),
    )
    op.create_table(
        "location_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("attendance_id", sa.Integer, sa.ForeignKey("attendance.id"), index=True, nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), index=True, nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lng", sa.Float, nullable=False),
        sa.Column("accuracy", sa.Float, nullable=True),
        sa.Column("speed", sa.Float, nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), index=True, nullable=False),
        sa.Column("is_mock", sa.Boolean, nullable=False, server_default="0"),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("attendance_id", sa.Integer, sa.ForeignKey("attendance.id"), nullable=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), index=True, nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer, primary_key=True, default=1),
        sa.Column("shift_start", sa.String(5), nullable=False, server_default="10:00"),
        sa.Column("shift_end", sa.String(5), nullable=False, server_default="19:00"),
        sa.Column("late_after", sa.Integer, nullable=False, server_default="15"),
        sa.Column("half_day_hours", sa.Float, nullable=False, server_default="4.0"),
        sa.Column("geofence_lat", sa.Float, nullable=False, server_default="28.6139"),
        sa.Column("geofence_lng", sa.Float, nullable=False, server_default="77.2090"),
        sa.Column("geofence_radius", sa.Float, nullable=False, server_default="500"),
        sa.Column("min_shift_hours", sa.Float, nullable=False, server_default="8.0"),
        sa.Column("max_break_minutes", sa.Integer, nullable=False, server_default="45"),
        sa.Column("max_accuracy_m", sa.Float, nullable=False, server_default="200"),
        sa.Column("overtime_allowed", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("overtime_limit_hours", sa.Float, nullable=False, server_default="3.0"),
        sa.Column("lunch_reminder_at", sa.String(5), nullable=False, server_default="13:00"),
    )
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


def downgrade():
    for t in ("user_policy", "settings", "events", "location_logs", "attendance", "users"):
        try:
            op.drop_table(t)
        except Exception:
            pass

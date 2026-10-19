"""Idempotent column patches for existing DBs (dev.db created before a deploy).

create_all() creates new tables but never adds columns to existing ones,
so new fields (breaks, min-shift policy) are added here with plain ALTERs.
Safe to run on every startup; failures are ignored.
"""
from sqlalchemy import text
from app.db.session import engine


_PATCHES = [
    "ALTER TABLE attendance ADD COLUMN break_minutes INTEGER DEFAULT 0",
    "ALTER TABLE attendance ADD COLUMN in_accuracy FLOAT",
    "ALTER TABLE attendance ADD COLUMN out_accuracy FLOAT",
    "ALTER TABLE attendance ADD COLUMN overtime_started_at TIMESTAMP",
    "ALTER TABLE attendance ADD COLUMN overtime_minutes INTEGER DEFAULT 0",
    "ALTER TABLE attendance ADD COLUMN total_minutes INTEGER",
    "ALTER TABLE attendance ADD COLUMN total_distance_m FLOAT DEFAULT 0",
    "ALTER TABLE attendance ADD COLUMN is_mock_in BOOLEAN DEFAULT 0",
    "ALTER TABLE attendance ADD COLUMN outside_geofence BOOLEAN DEFAULT 0",
    "ALTER TABLE attendance ADD COLUMN auto_punched_out BOOLEAN DEFAULT 0",
    "ALTER TABLE attendance ADD COLUMN reopened_at TIMESTAMP",
    "ALTER TABLE attendance ADD COLUMN device_info VARCHAR(500)",
    "ALTER TABLE attendance ADD COLUMN device_in_at TIMESTAMP",
    "ALTER TABLE attendance ADD COLUMN device_out_at TIMESTAMP",
    "ALTER TABLE attendance ADD COLUMN in_selfie_url VARCHAR(500)",
    "ALTER TABLE attendance ADD COLUMN out_selfie_url VARCHAR(500)",
    "ALTER TABLE settings ADD COLUMN min_shift_hours FLOAT DEFAULT 8.0",
    "ALTER TABLE settings ADD COLUMN max_break_minutes INTEGER DEFAULT 45",
    "ALTER TABLE settings ADD COLUMN max_accuracy_m FLOAT DEFAULT 200",
    "ALTER TABLE settings ADD COLUMN overtime_allowed BOOLEAN DEFAULT 1",
    "ALTER TABLE settings ADD COLUMN overtime_limit_hours FLOAT DEFAULT 3.0",
    "ALTER TABLE settings ADD COLUMN lunch_reminder_at VARCHAR(5) DEFAULT '13:00'",
]


def ensure_columns() -> None:
    with engine.begin() as conn:
        for ddl in _PATCHES:
            try:
                conn.execute(text(ddl))
            except Exception:
                pass  # column already exists

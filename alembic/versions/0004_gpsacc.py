"""GPS accuracy gate. Run: alembic upgrade head"""
revision = "0004_gpsacc"
down_revision = "0003_breakcap"

from alembic import op
import sqlalchemy as sa


def upgrade():
    for ddl_col, ddl_type, default in [
        ("in_accuracy", sa.Float(), None),
        ("out_accuracy", sa.Float(), None),
        ("max_accuracy_m", sa.Float(), "200"),
    ]:
        table = "settings" if ddl_col == "max_accuracy_m" else "attendance"
        try:
            op.add_column(table, sa.Column(ddl_col, ddl_type, server_default=default))
        except Exception:
            pass


def downgrade():
    for table, col in [("attendance", "in_accuracy"), ("attendance", "out_accuracy"),
                       ("settings", "max_accuracy_m")]:
        try:
            op.drop_column(table, col)
        except Exception:
            pass

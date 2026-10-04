from logging.config import fileConfig
from alembic import context
from app.db.base import Base
import app.models.user, app.models.attendance, app.models.tracking
from app.core.config import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
fileConfig(config.config_file_name)
target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(url=settings.DATABASE_URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    from sqlalchemy import engine_from_config
    ce = engine_from_config({"sqlalchemy.url": settings.DATABASE_URL}, prefix="sqlalchemy.")
    with ce.connect() as c:
        context.configure(connection=c, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

run_migrations_offline() if context.is_offline_mode() else run_migrations_online()

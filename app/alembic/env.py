import os
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlalchemy import pool

from alembic import context

# Projektverzeichnis (app/) in den Suchpfad, damit die Models importiert werden können
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models import Base

config = context.config

# Logging nur konfigurieren, wenn Alembic über die CLI läuft (nicht beim Start aus der App)
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def get_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://printuser:printpass@db:5432/printcalc")


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

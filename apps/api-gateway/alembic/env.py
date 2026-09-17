"""
Alembic migration environment.

NOTE: GITTY-AI currently manages its SQLite schema via raw CREATE TABLE statements
inside SQLiteGraphRepository.create_database().  Alembic is therefore NOT wired to
any SQLAlchemy models yet.

This file has been cleaned up to remove the misleading stub that shipped with
target_metadata = None while still importing SQLAlchemy machinery.  If you want
to migrate to a full Alembic-managed schema:

  1. Define SQLAlchemy ORM models in a `models.py` module.
  2. Import the declarative Base and set:
         target_metadata = Base.metadata
  3. Replace the raw SQL in SQLiteGraphRepository.create_database() with
     Alembic autogenerate migrations.

Until then, schema changes must be applied manually via the raw SQL in
SQLiteGraphRepository.create_database().
"""
from logging.config import fileConfig
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No SQLAlchemy models are wired yet — see note above.
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection required)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection)."""
    from sqlalchemy import engine_from_config, pool

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

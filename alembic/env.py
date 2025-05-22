import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.models.database_models import Base

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# This is the Alembic Config object, which provides
# access to the values within the .ini file in this directory.
config = context.config

# Set the version_locations to the correct path
config.set_main_option('version_locations', os.path.join(os.path.dirname(__file__), 'versions'))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

# --- Load environment variables for database connection ---
from dotenv import load_dotenv
# Assuming .env is in the project root directory relative to where alembic is run
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

# Get the DATABASE_URL from environment variables via config.py Settings
# This adds a dependency on your application configuration
# Make sure your config.py is importable from here
try:
    from api.core.config import settings
    database_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://") # Ensure psycopg2 driver
except ImportError as e:
    # Fallback if config.py cannot be imported directly (e.g., different runtime env)
    # You might need to adjust this based on your project structure
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
         database_url = database_url.replace("postgresql://", "postgresql+psycopg2://") # Ensure psycopg2 driver for Alembic
    else:
         # This will likely cause issues, but lets Alembic fail gracefully later
         database_url = "postgresql+psycopg2://user:password@localhost/dbname" # Placeholder

if database_url:
    config.set_main_option("sqlalchemy.url", database_url)
else:
    context.log.error("DATABASE_URL not set in environment or .env file.")

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be installed.

    Calls to context.execute() here render the SQL in the
    output, but do not associate with a DB.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Include the enum type for PostgreSQL dialect when scripting offline
        # This requires the enum type definition to be available
        postgresql_autoload_enum=False, # Don't try to load from DB offline
        postgresql_ignore_search_path=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=database_url # Use the URL loaded from env
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Include the enum type for PostgreSQL dialect when running online
            # This helps Alembic recognize your custom ENUM
            postgresql_autoload_enum=True, # Let Alembic attempt to load from DB online
            postgresql_ignore_search_path=True,
            include_schemas=True # Important if you use custom schemas
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

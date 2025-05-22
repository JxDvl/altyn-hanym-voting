from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings
import logging

logger = logging.getLogger(__name__)

# SQLAlchemy Database URL (ensure psycopg2 is used)
# The URL format is specific to psycopg2 driver
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://")

# Create SQLAlchemy engine
# pool_size and max_overflow should be tuned based on load and database limits
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=10, # Adjust pool size based on expected load
    max_overflow=20, # Allow overflow connections up to this limit
    pool_timeout=30, # Time in seconds before giving up establishing a connection
    # Add other connection parameters if necessary, e.g., connect_args={"options": "-c timezone=utc"}
)

# Create a SessionLocal class for database sessions
# autocommit=False: Changes are not committed automatically
# autoflush=False: Objects are not flushed to the database automatically
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for SQLAlchemy models
Base = declarative_base()

# Dependency to get a database session
def get_db():
    """Dependency that provides a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


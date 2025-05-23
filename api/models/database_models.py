from sqlalchemy import Column, UUID, String, Text, DateTime, Index, Boolean, ForeignKey, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import INET
import uuid
import enum
from datetime import datetime

from ..core.database import Base # Import Base from the new core/database.py

# Define the ENUM type for vote processing status
class VoteProcessingStatus(enum.Enum):
    received = "received"
    validating = "validating"
    processed = "processed"
    failed = "failed"

# Map Python enum to database ENUM type
vote_processing_status_enum = SQLEnum(VoteProcessingStatus, name='vote_processing_status', create_type=False) # create_type=False because we define it in SQL migration

class Candidate(Base):
    """SQLAlchemy model for the candidates table."""
    __tablename__ = 'candidates'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Optional: define backref for votes
    # votes = relationship("Vote", back_populates="candidate")


class User(Base):
    """SQLAlchemy model for the users table."""
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_identifier = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Optional: define backref for votes
    # votes = relationship("Vote", back_populates="user")

    # Add the index defined in the SQL schema
    __table_args__ = (
        Index('idx_users_user_identifier', user_identifier),
    )


class Vote(Base):
    """SQLAlchemy model for the votes table."""
    __tablename__ = 'votes'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey('candidates.id'), nullable=False)
    vote_timestamp = Column(DateTime(timezone=True), nullable=False) # Store API reception time
    source_ip = Column(INET) # PostgreSQL INET type
    user_agent = Column(Text)
    is_valid = Column(Boolean, nullable=False, default=True)
    processing_status = Column(vote_processing_status_enum, nullable=False, default=VoteProcessingStatus.received) # Use the mapped ENUM
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # Time recorded in DB

    # Define the unique constraint and indexes from the SQL schema
    __table_args__ = (
        Index('idx_votes_candidate_id', candidate_id),
        Index('idx_votes_user_id', user_id),
        Index('idx_votes_timestamp', vote_timestamp),
        UniqueConstraint(user_id, candidate_id, name='uq_votes_user_candidate'),
    )

    # Relationships (optional but good practice)
    user = relationship("User") # No backref needed if not querying votes from user model
    candidate = relationship("Candidate") # No backref needed if not querying votes from candidate model
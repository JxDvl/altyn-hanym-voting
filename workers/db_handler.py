from sqlalchemy import text, insert # Import insert for potential ORM insert
from sqlalchemy.orm import Session # Import Session type
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from tenacity import retry, stop_after_attempt, wait_fixed, wait_random_exponential, retry_if_exception_type
from uuid import UUID
from typing import Optional
import logging
from datetime import datetime # Need datetime for timestamp conversion if using ORM

from ..api.core.config import settings
from ..api.core.database import SessionLocal, engine # Import SessionLocal and engine
from ..api.models.database_models import User, Vote, VoteProcessingStatus # Import SQLAlchemy models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DB Session management is handled by SessionLocal factory.

class DBHandler:
    def __init__(self):
        pass # No need for explicit connection here, SessionLocal manages

    @retry(
        stop=stop_after_attempt(5), # Retry up to 5 times
        wait=wait_random_exponential(multiplier=1, min=1, max=10), # Exponential backoff with jitter
        # Retry on specific DB transaction errors or connection issues
        retry=retry_if_exception_type((SQLAlchemyError, ConnectionError)),
        before_sleep=lambda retry_state: logger.warning(f"Retrying DB transaction (attempt {retry_state.attempt_number})...")
    )
    def execute_transaction(self, user_identifier: str, candidate_id: UUID, vote_timestamp: str, source_ip: Optional[str], user_agent: Optional[str]) -> str:
        """
        Handles the database operations for a vote using SQLAlchemy ORM and Raw SQL for ON CONFLICT.
        1. Finds or creates user using ORM or SQL UPSERT.
        2. Inserts vote using INSERT ... ON CONFLICT.
        Returns status: 'processed', 'duplicate', or 'failed'.
        """
        db = SessionLocal()
        status = 'failed'
        inserted_vote_id = None # Track if a new vote was inserted

        try:
            # --- Step 1: Find or Create User ---
            # Option A: Use ORM (simpler but requires 2+ queries if not careful)
            # user = db.query(User).filter_by(user_identifier=user_identifier).first()
            # if user is None:
            #     user = User(user_identifier=user_identifier)
            #     db.add(user)
            #     db.flush() # Get the new user.id before next query


            # Option B: Use SQL UPSERT (more efficient/atomic)
            upsert_user_sql = text("""
                INSERT INTO users (id, user_identifier)
                VALUES (gen_random_uuid(), :user_identifier)
                ON CONFLICT (user_identifier)
                DO UPDATE SET user_identifier = users.user_identifier -- Dummy update to return existing row
                RETURNING id;
            """)
            user_result = db.execute(upsert_user_sql, {"user_identifier": user_identifier}).scalar_one()
            user_id = user_result # The ID of the existing or newly created user

            # --- Step 2: Insert Vote using INSERT ... ON CONFLICT ---
            # Use raw SQL for performance and atomic ON CONFLICT ON CONSTRAINT
            # We need the name of the unique constraint on votes table
            # (defined as 'uq_votes_user_candidate' in the model/schema)
            insert_vote_sql = text(f"""
                INSERT INTO votes (id, user_id, candidate_id, vote_timestamp, source_ip, user_agent, is_valid, processing_status)
                VALUES (
                    gen_random_uuid(),
                    :user_id,
                    :candidate_id,
                    :vote_timestamp,
                    :source_ip,
                    :user_agent,
                    TRUE, -- Assuming valid initially, detailed checks in worker logic might change this
                    :processing_status
                )
                ON CONFLICT ON CONSTRAINT uq_votes_user_candidate
                DO NOTHING
                RETURNING id; -- Return vote ID if inserted
            """)

            # Convert vote_timestamp_str to datetime with timezone if needed by SQLAlchemy/PG
            # Assuming vote_timestamp_str is ISO 8601 UTC ('Z') from API
            vote_dt = datetime.fromisoformat(vote_timestamp.replace('Z', '+00:00'))


            params = {
                "user_id": user_id, # Use the obtained user_id
                "candidate_id": candidate_id,
                "vote_timestamp": vote_dt, # Pass as datetime object
                "source_ip": source_ip,
                "user_agent": user_agent,
                "processing_status": VoteProcessingStatus.processed # Assuming 'processed' if inserted successfully
            }

            vote_result = db.execute(insert_vote_sql, params)
            inserted_vote_id = vote_result.scalar_one_or_none()

            db.commit() # Commit the transaction (both user upsert and vote insert)

            if inserted_vote_id is not None:
                status = 'processed'
                logger.info(f"Successfully processed NEW vote for user_identifier={user_identifier}, candidate_id={candidate_id}")
            else:
                # ON CONFLICT DO NOTHING happened
                status = 'duplicate'
                logger.warning(f"Duplicate vote detected and ignored for user_identifier={user_identifier}, candidate_id={candidate_id}")

        except IntegrityError as e:
            # This might catch FK violations (non-existent candidate) if FK is added and not pre-validated
            # Or other constraint violations not covered by ON CONFLICT
            logger.error(f"Database Integrity Error processing vote: {e} for user_identifier={user_identifier}, candidate_id={candidate_id}")
            db.rollback()
            # IntegrityError is usually not transient, re-raise to not retry on same data
            raise e # Let worker handle NACK/DLQ

        except SQLAlchemyError as e:
            logger.error(f"Database Error processing vote: {e} for user_identifier={user_identifier}, candidate_id={candidate_id}")
            db.rollback()
            raise e # Raise to trigger tenacity retry

        except Exception as e:
            # Catch any other unexpected exceptions
            logger.error(f"An unexpected error occurred in DBHandler transaction: {e} for user_identifier={user_identifier}, candidate_id={candidate_id}")
            db.rollback()
            raise e # Raise to trigger tenacity retry (if exception type matches) or worker NACK

        finally:
            db.close()

        # Return status and whether it was a new vote
        return status


     # Method to potentially get candidate names if needed by worker
     # @retry(stop=stop_after_attempt(3), wait=wait_fixed(1), retry=retry_if_exception_type(SQLAlchemyError))
     # def get_candidate_name(self, candidate_id: UUID) -> Optional[str]:
     #      db = SessionLocal()
     #      try:
     #           candidate = db.execute(select(Candidate).filter_by(id=candidate_id)).scalar_one_or_none()
     #           return candidate.name if candidate else None
     #      except SQLAlchemyError as e:
     #           logger.error(f"DB Error fetching candidate {candidate_id}: {e}")
     #           raise # Trigger retry
     #      finally:
     #           db.close()


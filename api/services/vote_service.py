import json
from datetime import datetime
from uuid import UUID
import pika # Using blocking pika as per example, note: async client like aio-pika is better for FastAPI
# from aio_pika import connect_robust # Example: For async FastAPI
from fastapi import HTTPException, status, Depends
from typing import Dict, Any, List, Optional
import redis
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
import logging
from sqlalchemy.orm import Session # Import Session type for type hints
from sqlalchemy import select # Import select for ORM queries
from sqlalchemy.exc import SQLAlchemyError
from tenacity import retry, stop_after_attempt, wait_fixed, wait_random_exponential, retry_if_exception_type

from ..models.schemas import VotePayload, VoteResponse, ResultsResponse, CandidateResult
from ..models.database_models import Candidate # Import SQLAlchemy models
from ..core.config import settings
from ..core.database import get_db # Import DB dependency
from ..core.security import decode_user_token # Example - might need adjustment based on JWT
from .cache_service import CacheService # Import the new CacheService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VoteService:
    def __init__(self):
        self.rabbitmq_connection = None
        self.rabbitmq_channel = None
        self.redis_client = None
        self.cache_service = None
        
        try:
            # Use tenacity for initial connection attempt
            @retry(stop=stop_after_attempt(5), wait=wait_fixed(settings.WORKER_RECONNECT_DELAY_SECONDS/2),
                   retry=retry_if_exception_type(pika.exceptions.AMQPConnectionError))
            def connect_rabbitmq():
                conn = pika.BlockingConnection(pika.URLParameters(settings.RABBITMQ_URL))
                ch = conn.channel()
                # Declare DLX and DLQ first
                ch.exchange_declare(exchange=settings.RABBITMQ_DLX_EXCHANGE, exchange_type='fanout', durable=True)
                ch.queue_declare(settings.RABBITMQ_DLQ_QUEUE, durable=True)
                # Declare main queue with DLX argument
                ch.queue_declare(
                    queue=settings.RABBITMQ_QUEUE_NAME,
                    durable=True,
                    arguments={'x-dead-letter-exchange': settings.RABBITMQ_DLX_EXCHANGE}
                )
                logger.info("Successfully connected to RabbitMQ, declared queue, DLX, and DLQ.")
                return conn, ch

            self.rabbitmq_connection, self.rabbitmq_channel = connect_rabbitmq()

        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"Failed to connect to RabbitMQ after multiple retries: {e}")
            # The application might start but voting will fail. Monitor this error.
        except Exception as e:
            logger.error(f"An unexpected error occurred during initial RabbitMQ setup: {e}")

        try:
            @retry(stop=stop_after_attempt(5), wait=wait_fixed(settings.WORKER_RECONNECT_DELAY_SECONDS/2),
                   retry=retry_if_exception_type(RedisConnectionError))
            def connect_redis():
                client = redis.StrictRedis.from_url(settings.REDIS_URL, decode_responses=True)
                client.ping() # Check connection
                logger.info("Successfully connected to Redis.")
                return client

            self.redis_client = connect_redis()
            self.cache_service = CacheService(self.redis_client, settings.RESULTS_CACHE_TTL_SECONDS)
        except RedisConnectionError as e:
            logger.error(f"Failed to connect to Redis after multiple retries: {e}")
            # Cache will be unavailable, results fallback to DB (if implemented) or fail.
        except Exception as e:
            logger.error(f"An unexpected error occurred during initial Redis setup: {e}")

        if self.rabbitmq_connection is None or not self.rabbitmq_connection.is_open:
             logger.error("VoteService initialized but RabbitMQ is not connected.")
        if self.redis_client is None:
            logger.warning("VoteService initialized but Redis / CacheService is not connected. Cache and Rate Limiting will be unavailable.")

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1), # Short retries for publishing
           retry=retry_if_exception_type(pika.exceptions.AMQPError))
    def _publish_vote_message(self, message_body: bytes):
        """Handles message publishing with retries."""
        if self.rabbitmq_connection is None or not self.rabbitmq_connection.is_open or self.rabbitmq_channel is None or not self.rabbitmq_channel.is_open:
            logger.error("Attempted to publish message but RabbitMQ connection/channel is closed.")
            raise pika.exceptions.AMQPConnectionError("RabbitMQ connection is not open.")

        self.rabbitmq_channel.basic_publish(
            exchange='', # Default exchange for direct-to-queue
            routing_key=settings.RABBITMQ_QUEUE_NAME,
            body=message_body,
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent # Make message durable
            )
        )
        logger.info("Message published to RabbitMQ.")


    async def process_vote_request(self, payload: VotePayload, source_ip: str, user_agent: str) -> VoteResponse:
        """
        Processes the incoming vote request.
        Performs basic validation and publishes message to RabbitMQ.
        Detailed validation and DB/Redis operations are done by workers.
        """
        # *** Basic API-level validation & Authentication (Placeholder) ***
        # As requested, use the user_token from payload for basic validation
        # A standard system would use Authorization: Bearer header for API auth.
        try:
             user_id_from_token = decode_user_token(payload.user_token) # decode_user_token raises 401 on error
             if not user_id_from_token:
                  # This case should not be reached if decode_user_token raises 401, but defensive check
                 raise HTTPException(
                     status_code=status.HTTP_401_UNAUTHORIZED,
                     detail="Could not validate credentials: invalid token",
                     headers={"WWW-Authenticate": "Bearer"},
                 )
        except HTTPException:
            # Re-raise the 401 from decode_user_token
            raise
        except Exception as e:
             logger.error(f"Error during basic user token validation: {e}")
             raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not validate credentials: token processing error",
                # Add error_code if desired
             )

        # 3. Rate Limiting (Optional but recommended for high load)
        # Example using CacheService (needs implementation within CacheService)
        if self.cache_service is not None:
             try:
                 # Assuming user_id_from_token derived above is usable for rate limiting Key
                 # Alternatively, use source_ip
                 if self.cache_service.is_rate_limited(str(user_id_from_token)): # Or use source_ip
                      raise HTTPException(
                           status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                           detail="Too many requests. Please try again later.",
                           # Add error_code if desired
                      )
             except (RedisConnectionError, RedisTimeoutError) as e:
                  logger.error(f"Rate Limiting check failed due to Redis error: {e}. Proceeding without rate limit.")
                  # Decide policy on RL failure: fail open (allow) or fail closed (deny)
                  pass # Fail open: allow request if Redis RL check fails
             except Exception as e:
                  logger.error(f"An unexpected error occurred during Rate Limiting check: {e}. Proceeding without rate limit.")
                  pass # Fail open


        # *** Publish message to RabbitMQ ***
        try:
            message = {
                "candidate_id": str(payload.candidate_id), # Send as string UUID
                "user_token": payload.user_token, # Pass the original token to worker
                "vote_timestamp": datetime.utcnow().isoformat() + 'Z', # ISO 8601 UTC
                "source_ip": source_ip,
                "user_agent": user_agent,
            }
            message_body = json.dumps(message).encode('utf-8')

            # Use the internal retry logic for publishing
            self._publish_vote_message(message_body)

        except pika.exceptions.AMQPError as e:
            logger.error(f"Failed to publish message to RabbitMQ after retries: {e}")
            # Indicate service is unavailable if publishing fails persistently
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, # Use 503 for external service issue
                detail="Voting system is temporarily unavailable due to messaging queue issues. Please try again.",
                # Add error_code if desired
            )
        except Exception as e:
            logger.error(f"An unexpected error occurred while processing vote request: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An internal server error occurred.",
                # Add error_code if desired
            )

        # Return accepted response
        return VoteResponse(
            status="accepted",
            message="Vote accepted for processing",
            timestamp=datetime.utcnow()
        )

    async def get_vote_results(self, db: Session = Depends(get_db), candidate_id: Optional[UUID] = None, page: int = 1, limit: int = 100) -> ResultsResponse:
        """
        Fetches aggregated vote results from Redis cache or PostgreSQL database.
        Uses SQLAlchemy ORM for DB interaction when cache is missed.
        """
        # *** Try fetching from Redis Cache ***
        if self.cache_service is not None:
            try:
                cached_results = self.cache_service.get_results(candidate_id, page, limit)
                if cached_results:
                    logger.info("Fetched results from Redis cache.")
                    # Apply filtering/pagination to cached data happens inside cache_service
                    return cached_results
            except (RedisConnectionError, RedisTimeoutError) as e:
                 logger.error(f"Failed to fetch results from Redis cache (connection error): {e}. Falling back to DB.")
                 # Fall through to DB if cache lookup fails
            except Exception as e:
                logger.error(f"An unexpected error occurred while reading from Redis cache: {e}. Falling back to DB.")
                # Fall through to DB if cache read fails

        logger.warning("Cache miss or Redis unavailable. Fetching results from database.")

        # *** Fetch from PostgreSQL Database using SQLAlchemy ORM ***
        # This fallback queries aggregate data. For very high read load on /results,
        # relying primarily on Redis HASH for counts and joining with cached candidate names
        # is the better architecture, as described in the schema doc.
        # This DB fallback is complex because it needs to aggregate votes.
        # Aggregating millions of votes directly in a single query on every cache miss
        # is NOT scalable.
        # A robust solution would:
        # 1. Fetch counts from Redis HASH 'candidate_votes'.
        # 2. Fetch candidate names from DB (or a different cache/service).
        # 3. Combine these in memory.
        # 4. Apply filtering/pagination to the combined list.
        # 5. Update the full results cache in Redis.

        # Let's implement the preferred method: Fetching counts from Redis HASH first,
        # then candidates from DB if Redis connection is available.
        if self.redis_client is not None:
            try:
                 all_counts: Dict[str, str] = self.redis_client.hgetall("candidate_votes")
                 results_list: List[CandidateResult] = []
                 candidate_ids_from_redis = [UUID(cid) for cid in all_counts.keys()]

                 # Fetch candidate names from PostgreSQL for the IDs found in Redis
                 if candidate_ids_from_redis:
                     try:
                         # Retry DB fetch just in case
                         @retry(stop=stop_after_attempt(3), wait=wait_fixed(1),
                                retry=retry_if_exception_type(SQLAlchemyError))
                         def fetch_candidates_from_db(session: Session, ids: List[UUID]):
                              return session.execute(
                                   select(Candidate).filter(Candidate.id.in_(ids))
                              ).scalars().all()

                         all_candidates_from_db = fetch_candidates_from_db(db, candidate_ids_from_redis)
                         candidate_names = {str(c.id): c.name for c in all_candidates_from_db}

                     except SQLAlchemyError as e:
                         logger.error(f"Failed to fetch candidate names from DB during results query after retries: {e}")
                         # Cannot proceed without candidate names. Raise Exception.
                         raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to fetch candidate data.", # Add error_code
                         )


                     # Combine Redis counts with DB names
                     for cid_str, count_str in all_counts.items():
                          try:
                               count = int(count_str)
                               cid = UUID(cid_str)
                               candidate_name = candidate_names.get(cid_str, f"Unknown Candidate {cid_str}") # Handle missing name
                               results_list.append(CandidateResult(candidate_id=cid, name=candidate_name, vote_count=count))
                          except ValueError:
                               logger.warning(f"Invalid vote count in Redis for candidate {cid_str}: {count_str}")
                               # Skip or default to 0

                 # Apply candidate_id filter if requested
                 if candidate_id:
                      results_list = [res for res in results_list if res.candidate_id == candidate_id]

                 # Apply pagination to the combined list
                 results_list.sort(key=lambda r: r.vote_count, reverse=True) # Sort by votes
                 start = (page - 1) * limit
                 end = start + limit
                 paginated_results = results_list[start:end]

                 response = ResultsResponse(
                     results=paginated_results,
                     last_updated=datetime.utcnow() # Use current time
                 )

                 # Update the full results cache in Redis for subsequent requests
                 # This could be async or done less frequently in a background task
                 # Basic implementation: Update cache with current view if connection is healthy
                 if self.cache_service is not None and not candidate_id and page == 1 and limit > 50: # Heuristic: Cache if fetching potentially large chunk
                      try:
                           # Need the FULL list before filtering/pagination for caching
                           # Re-fetch or use the complete results_list before slicing?
                           # Using the complete list before slicing is simpler here:
                           all_results_for_cache = sorted(results_list, key=lambda r: r.vote_count, reverse=True)
                           self.cache_service.set_results(all_results_for_cache) # Cache the full list
                           logger.info(f"Updated Redis results cache with TTL {settings.RESULTS_CACHE_TTL_SECONDS}s.")
                      except (RedisConnectionError, RedisTimeoutError) as e:
                           logger.error(f"Failed to update Redis results cache: {e}")
                      except Exception as e:
                           logger.error(f"An unexpected error occurred while updating Redis cache: {e}")

                 return response

            except (RedisConnectionError, RedisTimeoutError) as e:
                 logger.error(f"Failed to fetch counts from Redis (connection error): {e}. Cannot fetch results.")
                 # If Redis for counts is unavailable, results cannot be provided efficiently.
                 # Fallback to full PG aggregation is an option but likely too slow.
                 # Raise 503 indicating dependency issue.
                 raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Vote results are temporarily unavailable due to data aggregation issues.",
                    # Add error_code
                 )
            except Exception as e:
                logger.error(f"An unexpected error occurred while fetching results from Redis counts -> DB names: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="An internal server error occurred while fetching results.",
                    # Add error_code
                 )
        else:
            # Redis client is not initialized at all
            logger.error("Redis client is not available. Cannot fetch results.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Vote results service is not fully configured (Redis unavailable).",
                 # Add error_code
            )

    # --- Removed Rate Limiting Placeholder from here --- The logic is now in process_vote_request


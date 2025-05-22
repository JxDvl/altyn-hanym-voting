import redis
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import logging
from uuid import UUID

from ..models.schemas import ResultsResponse, CandidateResult # Assuming schemas are importable

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self, redis_client: redis.Redis, results_cache_ttl_seconds: int):
        self._redis_client = redis_client
        self._results_cache_ttl = results_cache_ttl_seconds
        self._results_cache_key = "voting_results"
        # Rate Limiting Config (Example)
        self._rate_limit_key_prefix = "rate_limit:"
        self._rate_limit_calls = 100 # Example: 100 calls
        self._rate_limit_window_seconds = 60 # Example: per 60 seconds

        if self._redis_client is None:
             logger.warning("CacheService initialized with no Redis client.")

    # --- Results Caching ---
    def get_results(self, candidate_id: Optional[UUID] = None, page: int = 1, limit: int = 100) -> Optional[ResultsResponse]:
        """
        Fetches cached results. Returns None if cache is miss, expired, or error.
        Applies filtering and pagination to the cached data internally.
        """
        if self._redis_client is None:
            logger.warning("Redis client not available in CacheService. Cannot get results from cache.")
            return None

        try:
            cached_results_json = self._redis_client.get(self._results_cache_key)

            if cached_results_json:
                cached_data = json.loads(cached_results_json)
                cached_response = ResultsResponse(**cached_data)

                # Apply candidate_id filter to cached data
                if candidate_id:
                    cached_response.results = [
                        res for res in cached_response.results
                        if res.candidate_id == candidate_id
                    ]

                # Apply pagination to cached data
                # Sort needed before pagination if the cached list isn't guaranteed sorted
                cached_response.results.sort(key=lambda r: r.vote_count, reverse=True) # Assuming sort by votes
                start = (page - 1) * limit
                end = start + limit
                cached_response.results = cached_response.results[start:end]

                # Update last_updated timestamp to NOW before returning? Or keep original cache time?
                # Keeping original cache time reflects when the cache was generated.
                # cached_response.last_updated = datetime.utcnow()

                return cached_response

        except (RedisConnectionError, RedisTimeoutError) as e:
            logger.error(f"Redis error while getting results cache: {e}")
            return None
        except (json.JSONDecodeError, KeyError, ValueError) as e:
             logger.error(f"Failed to decode or parse cached results JSON: {e}. Invalidating cache.")
             try:
                  self._redis_client.delete(self._results_cache_key) # Invalidate bad cache
             except Exception:
                  pass # Ignore error during invalidation
             return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while processing cached results: {e}")
            return None


    def set_results(self, results_list: List[CandidateResult]):
        """
        Sets the full results cache. Expects a list of CandidateResult.
        """
        if self._redis_client is None:
            logger.warning("Redis client not available in CacheService. Cannot set results cache.")
            return

        try:
            # Create a ResultsResponse object to cache
            full_cache_object = ResultsResponse(
                results=results_list,
                last_updated=datetime.utcnow() # Timestamp when the cache is set
            )

            # Serialize and set with TTL
            self._redis_client.setex(
                self._results_cache_key,
                self._results_cache_ttl,
                full_cache_object.model_dump_json() # Use model_dump_json for Pydantic v2
            )
            logger.info(f"Results cache set in Redis with TTL {self._results_cache_ttl}s.")

        except (RedisConnectionError, RedisTimeoutError) as e:
            logger.error(f"Redis error while setting results cache: {e}")
            # Decide logging/alerting policy on cache write failures
        except Exception as e:
            logger.error(f"An unexpected error occurred while setting results cache: {e}")


    # --- Rate Limiting (Example) ---
    # Note: This is a basic Fixed Window implementation
    def is_rate_limited(self, key: str) -> bool:
        """
        Checks and applies rate limit for a given key (e.g., user_id or IP).
        Returns True if rate limited, False otherwise. Fail-open on Redis issues.
        """
        if self._redis_client is None:
            logger.warning("Redis client not available in CacheService. Rate limiting is disabled.")
            return False # Fail open

        redis_key = f"{self._rate_limit_key_prefix}{key}"

        try:
            # Use Redis pipeline for atomic INCR and EXPIRE operations
            pipe = self._redis_client.pipeline()
            pipe.incr(redis_key)
            pipe.ttl(redis_key) # Check TTL

            count, ttl = pipe.execute()

            if ttl == -1: # Key exists but has no expiry (first request in window)
                pipe_expire = self._redis_client.pipeline()
                pipe_expire.expire(redis_key, self._rate_limit_window_seconds)
                pipe_expire.execute() # Execute expire separately

            return count > self._rate_limit_calls

        except (RedisConnectionError, RedisTimeoutError) as e:
            logger.error(f"Redis error during rate limit check for key '{key}': {e}. Rate limiting is deactivated for this request.")
            return False # Fail open on Redis error
        except Exception as e:
            logger.error(f"An unexpected error occurred during rate limit check for key '{key}': {e}")
            return False # Fail open on other errors


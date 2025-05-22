from fastapi import APIRouter, Request, HTTPException, status, Depends
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session # Import Session type

from ..models.schemas import VotePayload, VoteResponse, ResultsResponse, ErrorResponse
from ..services.vote_service import VoteService
from ..core.database import get_db # Import DB dependency

router = APIRouter()

# Initialize VoteService. Dependencies like DB session and cache will be handled
# by FastAPI's dependency injection in get_vote_results if needed there.
vote_service = VoteService()

@router.post(
    "/vote",
    response_model=VoteResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse}, # Add 503 for service unavailable
    }
)
async def post_vote(request: Request, payload: VotePayload):
    """
    Accept a user's vote and queue it for processing.
    Basic validation and authentication check occurs here.
    Detailed validation and uniqueness check are done by asynchronous workers.
    """
    source_ip = request.client.host
    user_agent = request.headers.get("User-Agent", "Unknown")

    try:
        response = await vote_service.process_vote_request(payload, source_ip, user_agent)
        return response
    except HTTPException as e:
        # Re-raise HTTPExceptions raised by the service layer (e.g., 401, 429, 503)
        raise e
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unhandled error in /vote endpoint: {e}", exc_info=True) # Log exception info
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during vote submission.",
             # Add error_code
        )


@router.get(
    "/results",
    response_model=ResultsResponse,
    responses={
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse}, # Add 503 for service unavailable
    }
)
async def get_results(db: Session = Depends(get_db), candidate_id: Optional[UUID] = None, page: int = 1, limit: int = 100):
    """
    Get the current aggregated results of the voting.
    Results are fetched from cache (Redis) or the database.
    """
    # Parameters validation
    if page < 1:
        raise HTTPException(status_code=400, detail="Page number must be 1 or greater.")
    if limit < 1 or limit > 100: # Assuming max limit 100 from schema comment
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 100.")

    try:
        # Pass the DB session dependency to the service method
        results = await vote_service.get_vote_results(db=db, candidate_id=candidate_id, page=page, limit=limit)
        return results
    except HTTPException as e:
         # Re-raise HTTPExceptions from the service (e.g., 500, 503)
         raise e
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unhandled error in /results endpoint: {e}", exc_info=True) # Log exception info
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching results.",
            # Add error_code
        )


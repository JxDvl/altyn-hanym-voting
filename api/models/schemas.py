from pydantic import BaseModel, Field, UUID4
from datetime import datetime
from typing import List, Optional

class VotePayload(BaseModel):
    """Schema for the vote request payload."""
    candidate_id: UUID4 = Field(..., description="Unique identifier of the candidate.")
    user_token: str = Field(..., description="JWT token for user identification.")

class VoteResponse(BaseModel):
    """Schema for the vote accepted response."""
    status: str
    message: str
    timestamp: datetime

class CandidateResult(BaseModel):
    """Schema for a single candidate's result."""
    candidate_id: UUID4
    name: str
    vote_count: int

class ResultsResponse(BaseModel):
    """Schema for the voting results response."""
    results: List[CandidateResult]
    last_updated: datetime

class ErrorResponse(BaseModel):
    """Schema for a standard error response."""
    error_code: str
    message: str
    details: Optional[str] = None

class TokenResponse(BaseModel):
    """Schema for the authentication token response."""
    token: str = Field(..., description="JWT token for user authentication")

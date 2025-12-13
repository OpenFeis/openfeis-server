from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

# --- Scoring Models Only ---
# Note: The Platform Models (User, Feis, etc) are in models_platform.py
# We keep Round and JudgeScore here for now as they are core to the engine,
# but Round needs to know about Competition from models_platform.

# Forward reference string for Competition to avoid circular imports if possible,
# or we just rely on models_platform to define everything.
# For this fix, we are cleaning up models.py to NOT redefine User/Feis/etc.

class Round(SQLModel, table=True):
    """
    Represents a round in a competition.
    """
    id: str = Field(primary_key=True)
    competition_id: UUID = Field(foreign_key="competition.id")
    name: str
    sequence: int
    
    # competition: "Competition" = Relationship(back_populates="rounds") 
    # Note: Relationship defined in models_platform.py side or deferred.
    # For simplicity in this fix, we rely on models_platform.py being the source of truth for relationships.

class JudgeScore(SQLModel, table=True):
    """
    Represents a single raw score given by a judge to a competitor.
    """
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    judge_id: str = Field(index=True)
    competitor_id: str = Field(index=True)  # Entry ID
    round_id: str = Field(index=True)  # Competition ID (using round_id for backwards compat)
    value: float = Field(..., description="The raw score given (e.g., 75, 82.5)")
    notes: Optional[str] = Field(default=None, description="Optional judge notes/comments")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# --- Response Models (Pydantic only, no table=True) ---

class JudgeScoreDetail(SQLModel):
    """Detail of a score from a single judge."""
    judge_id: str
    judge_name: Optional[str] = None
    raw_score: float
    rank: int
    irish_points: float

class RankedResult(SQLModel):
    competitor_id: str
    rank: int 
    irish_points: float
    raw_score_sum: Optional[float] = None
    judge_scores: List[JudgeScoreDetail] = []

class RoundResult(SQLModel):
    round_id: str
    results: List[RankedResult]

from pydantic import BaseModel, Field
from typing import Optional


class RatingBase(BaseModel):
    rated_user_id: str
    rater_user_id: str
    product_id: Optional[str] = None
    order_id: Optional[str] = None
    score: float = Field(..., ge=1.0, le=5.0)
    comment: Optional[str] = None
    comment_bn: Optional[str] = None
    category: str = Field(
        default="general",
        pattern="^(quality|reliability|communication|timeliness|general)$",
    )


class RatingCreate(BaseModel):
    rated_user_id: str
    from_user_id: Optional[str] = None
    rated_entity_type: str = "farmer"  # "farmer", "agent", or "product"
    product_id: Optional[str] = None
    order_id: Optional[str] = None
    score: float = Field(..., ge=1.0, le=5.0)
    comment: Optional[str] = None
    comment_bn: Optional[str] = None
    category: str = "general"


class RatingOut(RatingBase):
    id: str
    created_at: str

    class Config:
        from_attributes = True


class ReputationOut(BaseModel):
    user_id: str
    average_score: float
    total_ratings: int
    score_breakdown: dict[str, float]
    category_scores: dict[str, float]
    badge: Optional[str] = None
    badge_bn: Optional[str] = None

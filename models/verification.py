from pydantic import BaseModel, Field
from typing import Optional


class VerificationBase(BaseModel):
    product_id: str
    agent_id: str
    quality_grade: Optional[str] = None
    notes: Optional[str] = None
    notes_bn: Optional[str] = None
    adjusted_quantity: Optional[float] = None
    adjusted_price: Optional[float] = None
    images: list[str] = []


class VerificationCreate(BaseModel):
    agent_id: str
    quality_grade: Optional[str] = None
    notes: Optional[str] = None
    notes_bn: Optional[str] = None
    images: list[str] = []


class VerificationStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(pending|in_progress|verified|rejected|adjustment_proposed|confirmed|adjusted)$")
    quality_grade: Optional[str] = None
    notes: Optional[str] = None
    notes_bn: Optional[str] = None
    adjusted_quantity: Optional[float] = None
    adjusted_price: Optional[float] = None


class VerificationOut(VerificationBase):
    id: str
    status: str
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True

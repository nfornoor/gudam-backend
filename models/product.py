from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ProductBase(BaseModel):
    name_bn: str
    name_en: Optional[str] = None
    category: str
    quantity: float
    unit: str
    quality_grade: str = Field("A", pattern="^(A|B|C)$")
    price_per_unit: float
    currency: str = "BDT"
    images: list[str] = []
    location: Optional[str] = None
    description_bn: Optional[str] = None


class ProductCreate(ProductBase):
    farmer_id: str


class ProductUpdate(BaseModel):
    name_bn: Optional[str] = None
    name_en: Optional[str] = None
    category: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    quality_grade: Optional[str] = None
    price_per_unit: Optional[float] = None
    images: Optional[list[str]] = None
    location: Optional[str] = None
    description_bn: Optional[str] = None
    status: Optional[str] = None


class ProductOut(ProductBase):
    id: str
    farmer_id: str
    status: str = "pending_verification"
    created_at: str
    verified_by_agent_id: Optional[str] = None
    verification_date: Optional[str] = None

    class Config:
        from_attributes = True


class CategoryOut(BaseModel):
    id: str
    name_en: str
    name_bn: str
    icon: Optional[str] = None

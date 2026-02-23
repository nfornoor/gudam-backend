from pydantic import BaseModel, Field
from typing import Optional


class OrderBase(BaseModel):
    product_id: str
    buyer_id: str
    quantity: float
    unit_price: float
    total_price: float
    currency: str = "BDT"
    delivery_address: Optional[dict] = None
    notes: Optional[str] = None


class OrderCreate(BaseModel):
    product_id: str
    buyer_id: str
    quantity: float
    delivery_address: Optional[dict] = None
    notes: Optional[str] = None


class OrderStatusUpdate(BaseModel):
    status: str = Field(
        ...,
        pattern="^(placed|confirmed|shipped|delivered|completed|canceled)$",
    )
    notes: Optional[str] = None


class OrderOut(OrderBase):
    id: str
    status: str
    farmer_id: str
    agent_id: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True

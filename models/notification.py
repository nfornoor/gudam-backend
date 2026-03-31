from pydantic import BaseModel
from typing import Optional


class NotificationCreate(BaseModel):
    user_id: str
    type: str  # listing_assigned, verification_complete, order_placed, order_status, payment
    title: str
    title_bn: Optional[str] = None
    message: str
    message_bn: Optional[str] = None
    related_id: Optional[str] = None
    send_sms: bool = False


class NotificationOut(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    title_bn: Optional[str] = None
    message: str
    message_bn: Optional[str] = None
    related_id: Optional[str] = None
    is_read: bool = False
    created_at: str

    class Config:
        from_attributes = True

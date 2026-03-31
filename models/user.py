from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class ProfileDetails(BaseModel):
    bio: Optional[str] = None
    farm_size_acres: Optional[float] = None
    crops_grown: Optional[list[str]] = None
    storage_capacity_tons: Optional[float] = None
    storage_type: Optional[str] = None
    gudam_name: Optional[str] = None
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    nid_number: Optional[str] = None
    bank_account: Optional[str] = None
    years_of_experience: Optional[int] = None


class UserBase(BaseModel):
    name: str
    email: Optional[str] = None
    phone: str
    role: str = Field(..., pattern="^(farmer|agent|buyer|admin)$")
    avatar_url: Optional[str] = None
    location: Optional[dict] = None
    profile_details: Optional[ProfileDetails] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    phone: str
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[dict] = None
    profile_details: Optional[ProfileDetails] = None


class ChangePassword(BaseModel):
    user_id: str
    current_password: str
    new_password: str = Field(..., min_length=6)


class ResetPasswordRequest(BaseModel):
    phone: str


class ResetPasswordConfirm(BaseModel):
    phone: str
    otp_code: str
    new_password: str = Field(..., min_length=6)


class UserOut(UserBase):
    id: str
    created_at: str
    is_verified: bool = False

    class Config:
        from_attributes = True

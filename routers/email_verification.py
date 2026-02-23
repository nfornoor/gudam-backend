"""
Email Verification Service - ইমেইল যাচাইকরণ সেবা
Handles marking emails as verified after Supabase Auth OTP verification on the frontend.
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr
from jose import jwt, JWTError
from db import get_supabase
from config import SECRET_KEY, ALGORITHM
from utils.helpers import now_iso

router = APIRouter()


class MarkEmailVerified(BaseModel):
    user_id: str
    email: EmailStr


def get_user_id_from_token(authorization: str) -> str:
    """Extract and validate user_id from Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="অনুমোদন টোকেন প্রয়োজন")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="অবৈধ টোকেন")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="অবৈধ বা মেয়াদোত্তীর্ণ টোকেন")


@router.post("/api/email/mark-verified", tags=["Email Verification"])
def mark_email_verified(
    data: MarkEmailVerified,
    authorization: str = Header(default=None),
):
    """
    ইমেইল যাচাইকৃত হিসেবে চিহ্নিত করুন (Mark email as verified).

    Called by the frontend after Supabase Auth OTP verification succeeds.
    Requires a valid JWT Bearer token matching the user_id.
    """
    try:
        # Validate JWT and ensure user can only mark their own email
        token_user_id = get_user_id_from_token(authorization)
        if token_user_id != data.user_id:
            raise HTTPException(status_code=403, detail="অন্যের ইমেইল যাচাই করার অনুমতি নেই")

        sb = get_supabase()

        # Check if user exists
        user_result = sb.table("users").select("id,email").eq("id", data.user_id).execute()
        if not user_result.data:
            raise HTTPException(status_code=404, detail="ব্যবহারকারী পাওয়া যায়নি")

        # Check if email is already verified by another user
        existing = sb.table("users").select("id").eq("email", data.email).eq("email_verified", True).neq("id", data.user_id).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="এই ইমেইল অন্য অ্যাকাউন্টে যাচাই করা আছে")

        # Update user's email and verification status
        sb.table("users").update({
            "email": data.email,
            "email_verified": True,
            "updated_at": now_iso(),
        }).eq("id", data.user_id).execute()

        return {
            "message": "ইমেইল সফলভাবে যাচাই করা হয়েছে (Email verified successfully)",
            "email_verified": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")


@router.get("/api/email/status/{user_id}", tags=["Email Verification"])
def get_email_status(user_id: str):
    """ইমেইল যাচাইকরণ অবস্থা দেখুন (Check email verification status)."""
    try:
        sb = get_supabase()
        result = sb.table("users").select("email,email_verified").eq("id", user_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="ব্যবহারকারী পাওয়া যায়নি")

        user = result.data[0]
        return {
            "email": user.get("email"),
            "email_verified": user.get("email_verified", False),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")

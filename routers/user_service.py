"""
User Service - গুদাম ব্যবহারকারী সেবা
Handles authentication, user profiles, and user management.
"""

import uuid
import math
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Query
from passlib.context import CryptContext
from jose import jwt

from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from models.user import UserCreate, UserLogin, UserOut, UserUpdate, ChangePassword, ResetPasswordRequest, ResetPasswordConfirm
from db import get_supabase
from utils.helpers import now_iso

router = APIRouter()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

RECYCLE_BIN_DAYS = 30


def _create_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _sanitize_user(user: dict) -> dict:
    """Remove sensitive fields before returning user data."""
    return {k: v for k, v in user.items() if k != "password_hash"}


def _hard_delete_user(sb, user_id: str):
    """Permanently delete a user and all related records."""
    # Ratings
    sb.table("ratings").delete().eq("from_user_id", user_id).execute()
    sb.table("ratings").delete().eq("to_user_id", user_id).execute()
    # Orders
    sb.table("orders").delete().eq("buyer_id", user_id).execute()
    sb.table("orders").delete().eq("farmer_id", user_id).execute()
    sb.table("orders").delete().eq("agent_id", user_id).execute()
    # Verifications & Products (verifications reference products)
    products = sb.table("products").select("id").eq("farmer_id", user_id).execute()
    for p in products.data:
        sb.table("verifications").delete().eq("product_id", p["id"]).execute()
    sb.table("verifications").delete().eq("agent_id", user_id).execute()
    sb.table("verifications").delete().eq("farmer_id", user_id).execute()
    sb.table("products").delete().eq("farmer_id", user_id).execute()
    sb.table("products").delete().eq("verified_by", user_id).execute()
    # Messages & Conversations
    convos1 = sb.table("conversations").select("id").eq("participant_1", user_id).execute()
    for c in convos1.data:
        sb.table("messages").delete().eq("conversation_id", c["id"]).execute()
    convos2 = sb.table("conversations").select("id").eq("participant_2", user_id).execute()
    for c in convos2.data:
        sb.table("messages").delete().eq("conversation_id", c["id"]).execute()
    sb.table("messages").delete().eq("sender_id", user_id).execute()
    sb.table("conversations").delete().eq("participant_1", user_id).execute()
    sb.table("conversations").delete().eq("participant_2", user_id).execute()
    # Finally delete the user
    sb.table("users").delete().eq("id", user_id).execute()


def _auto_purge_expired(sb):
    """Permanently delete users whose deleted_at is older than 30 days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RECYCLE_BIN_DAYS)).isoformat()
    expired = sb.table("users").select("id").not_.is_("deleted_at", "null").lt("deleted_at", cutoff).execute()
    for u in expired.data:
        try:
            _hard_delete_user(sb, u["id"])
        except Exception:
            pass


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/api/auth/register", tags=["Auth"])
def register(user_data: UserCreate):
    """নতুন ব্যবহারকারী নিবন্ধন (Register a new user)."""
    try:
        sb = get_supabase()

        # Check if email already exists (only if email provided)
        if user_data.email:
            existing = sb.table("users").select("id,deleted_at").eq("email", user_data.email).execute()
            if existing.data:
                active = [u for u in existing.data if u.get("deleted_at") is None]
                if active:
                    raise HTTPException(status_code=400, detail="এই ইমেইল আগে থেকেই নিবন্ধিত (Email already registered)")
                # Remove soft-deleted users with this email so re-registration works
                for u in existing.data:
                    _hard_delete_user(sb, u["id"])

        # Check if phone number already exists
        if user_data.phone:
            existing_phone = sb.table("users").select("id,deleted_at").eq("phone", user_data.phone).execute()
            if existing_phone.data:
                active = [u for u in existing_phone.data if u.get("deleted_at") is None]
                if active:
                    raise HTTPException(status_code=400, detail="এই ফোন নম্বর আগে থেকেই নিবন্ধিত (Phone number already registered)")
                # Remove soft-deleted users with this phone so re-registration works
                for u in existing_phone.data:
                    _hard_delete_user(sb, u["id"])

        new_id = f"USR-{uuid.uuid4().hex[:8]}"
        hashed = pwd_context.hash(user_data.password)

        new_user = {
            "id": new_id,
            "name": user_data.name,
            "email": user_data.email,
            "phone": user_data.phone,
            "password_hash": hashed,
            "role": user_data.role,
            "avatar_url": user_data.avatar_url,
            "location": user_data.location,
            "profile_details": user_data.profile_details.model_dump() if user_data.profile_details else None,
            "created_at": now_iso(),
            "is_verified": False,
        }

        result = sb.table("users").insert(new_user).execute()
        inserted = result.data[0] if result.data else new_user

        token = _create_token(inserted)
        return {
            "message": "নিবন্ধন সফল হয়েছে (Registration successful)",
            "user": _sanitize_user(inserted),
            "access_token": token,
            "token_type": "bearer",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.post("/api/auth/login", tags=["Auth"])
def login(credentials: UserLogin):
    """ব্যবহারকারী লগইন (User login)."""
    try:
        sb = get_supabase()

        phone = credentials.phone.strip()
        # Normalize: try exact match, then +880 prefix, then strip +880
        result = sb.table("users").select("*").eq("phone", phone).is_("deleted_at", "null").execute()
        if not result.data and not phone.startswith("+"):
            # 01xxx → +8801xxx (strip leading 0)
            normalized = "+880" + phone.lstrip("0")
            result = sb.table("users").select("*").eq("phone", normalized).is_("deleted_at", "null").execute()
        if not result.data and not phone.startswith("+"):
            # Also try +880 + full number (for numbers without leading 0)
            result = sb.table("users").select("*").eq("phone", "+880" + phone).is_("deleted_at", "null").execute()
        if not result.data and phone.startswith("+"):
            result = sb.table("users").select("*").eq("phone", phone.replace("+880", "")).is_("deleted_at", "null").execute()
        if not result.data:
            raise HTTPException(status_code=401, detail="ভুল ফোন নম্বর বা পাসওয়ার্ড (Invalid phone or password)")

        user = result.data[0]

        pw_hash = user.get("password_hash") or ""
        hash_ok = pwd_context.verify(credentials.password, pw_hash) if pw_hash else False
        if not hash_ok:
            # Fallback: accept demo password
            if credentials.password != "password123":
                raise HTTPException(status_code=401, detail="ভুল ফোন নম্বর বা পাসওয়ার্ড (Invalid phone or password)")

        token = _create_token(user)
        return {
            "message": "লগইন সফল (Login successful)",
            "user": _sanitize_user(user),
            "access_token": token,
            "token_type": "bearer",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.put("/api/auth/change-password", tags=["Auth"])
def change_password(data: ChangePassword):
    """পাসওয়ার্ড পরিবর্তন (Change password - requires current password)."""
    try:
        sb = get_supabase()

        result = sb.table("users").select("*").eq("id", data.user_id).is_("deleted_at", "null").execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="ব্যবহারকারী পাওয়া যায়নি (User not found)")

        user = result.data[0]

        # Verify current password
        pw_hash = user.get("password_hash") or ""
        hash_ok = pwd_context.verify(data.current_password, pw_hash) if pw_hash else False
        is_demo = (data.current_password == "password123")
        if not hash_ok and not is_demo:
            raise HTTPException(status_code=401, detail="বর্তমান পাসওয়ার্ড ভুল (Current password is incorrect)")

        new_hash = pwd_context.hash(data.new_password)
        sb.table("users").update({"password_hash": new_hash}).eq("id", data.user_id).execute()

        return {"message": "পাসওয়ার্ড সফলভাবে পরিবর্তন হয়েছে (Password changed successfully)"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


# In-memory store for password reset OTPs
_reset_otp_store: dict = {}


def _normalize_phone(phone: str):
    """Try multiple phone formats and return matching user."""
    sb = get_supabase()
    phone = phone.strip()
    result = sb.table("users").select("*").eq("phone", phone).is_("deleted_at", "null").execute()
    if not result.data and not phone.startswith("+"):
        result = sb.table("users").select("*").eq("phone", "+880" + phone).is_("deleted_at", "null").execute()
    if not result.data and phone.startswith("+"):
        result = sb.table("users").select("*").eq("phone", phone.replace("+880", "")).is_("deleted_at", "null").execute()
    return result


@router.post("/api/auth/forgot-password", tags=["Auth"])
def forgot_password(data: ResetPasswordRequest):
    """পাসওয়ার্ড রিসেট OTP পাঠান (Send password reset OTP)."""
    import random
    try:
        result = _normalize_phone(data.phone)
        if not result.data:
            raise HTTPException(status_code=404, detail="এই ফোন নম্বরে কোনো একাউন্ট পাওয়া যায়নি (No account found with this phone)")

        user = result.data[0]
        code = f"{random.randint(100000, 999999)}"
        _reset_otp_store[data.phone.strip()] = {
            "code": code,
            "user_id": user["id"],
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        }

        # Dev mode: return OTP in response for testing
        return {
            "message": "পাসওয়ার্ড রিসেট OTP পাঠানো হয়েছে (Password reset OTP sent)",
            "otp_code": code,
            "expires_in_minutes": 10,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.post("/api/auth/reset-password", tags=["Auth"])
def reset_password(data: ResetPasswordConfirm):
    """OTP দিয়ে পাসওয়ার্ড রিসেট করুন (Reset password with OTP)."""
    try:
        phone = data.phone.strip()
        stored = _reset_otp_store.get(phone)
        if not stored:
            raise HTTPException(status_code=400, detail="কোনো OTP পাওয়া যায়নি। আবার পাঠান। (No OTP found. Resend.)")

        if datetime.now(timezone.utc) > stored["expires_at"]:
            _reset_otp_store.pop(phone, None)
            raise HTTPException(status_code=400, detail="OTP এর মেয়াদ শেষ হয়ে গেছে। আবার পাঠান। (OTP expired. Resend.)")

        if stored["code"] != data.otp_code:
            raise HTTPException(status_code=400, detail="ভুল OTP কোড (Invalid OTP code)")

        sb = get_supabase()
        new_hash = pwd_context.hash(data.new_password)
        sb.table("users").update({"password_hash": new_hash}).eq("id", stored["user_id"]).execute()

        _reset_otp_store.pop(phone, None)

        return {"message": "পাসওয়ার্ড সফলভাবে রিসেট হয়েছে (Password reset successfully)"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/users/{user_id}", tags=["Users"])
def get_user(user_id: str):
    """ব্যবহারকারীর প্রোফাইল দেখুন (Get user profile)."""
    try:
        sb = get_supabase()
        result = sb.table("users").select("*").eq("id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="ব্যবহারকারী পাওয়া যায়নি (User not found)")
        return _sanitize_user(result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.put("/api/users/{user_id}", tags=["Users"])
def update_user(user_id: str, update: UserUpdate):
    """ব্যবহারকারীর প্রোফাইল আপডেট (Update user profile)."""
    try:
        sb = get_supabase()

        # Check user exists
        existing = sb.table("users").select("*").eq("id", user_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="ব্যবহারকারী পাওয়া যায়নি (User not found)")

        user = existing.data[0]
        update_data = update.model_dump(exclude_unset=True)

        # Block phone change if already verified
        if "phone" in update_data and update_data["phone"] and update_data["phone"] != user.get("phone"):
            profile_details = user.get("profile_details") or {}
            if profile_details.get("phone_verified"):
                raise HTTPException(status_code=400, detail="যাচাইকৃত নম্বর পরিবর্তন করা যাবে না (Verified phone cannot be changed)")

            existing_phone = sb.table("users").select("id").eq("phone", update_data["phone"]).neq("id", user_id).execute()
            if existing_phone.data:
                raise HTTPException(status_code=400, detail="এই ফোন নম্বর অন্য অ্যাকাউন্টে ব্যবহৃত (Phone number already in use)")

        if "profile_details" in update_data and update_data["profile_details"] is not None:
            existing_pd = user.get("profile_details") or {}
            existing_pd.update({k: v for k, v in update_data["profile_details"].items() if v is not None})
            update_data["profile_details"] = existing_pd

        if not update_data:
            return {
                "message": "প্রোফাইল আপডেট হয়েছে (Profile updated)",
                "user": _sanitize_user(user),
            }

        result = sb.table("users").update(update_data).eq("id", user_id).execute()
        updated_user = result.data[0] if result.data else user

        return {
            "message": "প্রোফাইল আপডেট হয়েছে (Profile updated)",
            "user": _sanitize_user(updated_user),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/users", tags=["Users"])
def list_users(
    role: str | None = Query(None, description="Filter by role: farmer, agent, buyer, admin"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """সকল ব্যবহারকারীর তালিকা (List all active users - admin)."""
    try:
        sb = get_supabase()
        offset = (page - 1) * page_size

        query = sb.table("users").select("*", count="exact").is_("deleted_at", "null")
        if role:
            query = query.eq("role", role)

        result = query.range(offset, offset + page_size - 1).execute()
        total = result.count if result.count is not None else len(result.data)
        sanitized = [_sanitize_user(u) for u in result.data]

        return {
            "items": sanitized,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.put("/api/users/{user_id}/verify", tags=["Users"])
def verify_user(user_id: str):
    """ব্যবহারকারী অনুমোদন করুন - অ্যাডমিন (Admin approve user)."""
    try:
        sb = get_supabase()

        existing = sb.table("users").select("*").eq("id", user_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="ব্যবহারকারী পাওয়া যায়নি (User not found)")

        result = sb.table("users").update({"is_verified": True}).eq("id", user_id).execute()
        updated_user = result.data[0] if result.data else existing.data[0]

        return {
            "message": "ব্যবহারকারী অনুমোদন করা হয়েছে (User approved)",
            "user": _sanitize_user(updated_user),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.put("/api/users/{user_id}/unverify", tags=["Users"])
def unverify_user(user_id: str):
    """ব্যবহারকারীর অনুমোদন বাতিল - অ্যাডমিন (Admin revoke approval)."""
    try:
        sb = get_supabase()

        existing = sb.table("users").select("*").eq("id", user_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="ব্যবহারকারী পাওয়া যায়নি (User not found)")

        result = sb.table("users").update({"is_verified": False}).eq("id", user_id).execute()
        updated_user = result.data[0] if result.data else existing.data[0]

        return {
            "message": "অনুমোদন বাতিল করা হয়েছে (Approval revoked)",
            "user": _sanitize_user(updated_user),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/farmers", tags=["Users"])
def list_farmers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """সকল কৃষকের তালিকা (List all farmers)."""
    try:
        sb = get_supabase()
        offset = (page - 1) * page_size

        result = sb.table("users").select("*", count="exact").eq("role", "farmer").is_("deleted_at", "null").range(offset, offset + page_size - 1).execute()
        total = result.count if result.count is not None else len(result.data)
        sanitized = [_sanitize_user(u) for u in result.data]

        return {
            "items": sanitized,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/agents", tags=["Users"])
def list_agents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """সকল এজেন্টের তালিকা (List all agents)."""
    try:
        sb = get_supabase()
        offset = (page - 1) * page_size

        result = sb.table("users").select("*", count="exact").eq("role", "agent").is_("deleted_at", "null").range(offset, offset + page_size - 1).execute()
        total = result.count if result.count is not None else len(result.data)
        sanitized = [_sanitize_user(u) for u in result.data]

        return {
            "items": sanitized,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/buyers", tags=["Users"])
def list_buyers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """সকল ক্রেতার তালিকা (List all buyers)."""
    try:
        sb = get_supabase()
        offset = (page - 1) * page_size

        result = sb.table("users").select("*", count="exact").eq("role", "buyer").is_("deleted_at", "null").range(offset, offset + page_size - 1).execute()
        total = result.count if result.count is not None else len(result.data)
        sanitized = [_sanitize_user(u) for u in result.data]

        return {
            "items": sanitized,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


# ─── Soft Delete (Recycle Bin) ────────────────────────────────────────────────


@router.delete("/api/users/{user_id}", tags=["Users"])
def delete_user(user_id: str):
    """ব্যবহারকারী রিসাইকেল বিনে পাঠান (Soft delete - move to recycle bin)."""
    try:
        sb = get_supabase()

        existing = sb.table("users").select("id").eq("id", user_id).is_("deleted_at", "null").execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="ব্যবহারকারী পাওয়া যায়নি (User not found)")

        sb.table("users").update({"deleted_at": now_iso()}).eq("id", user_id).execute()

        return {
            "message": "ব্যবহারকারী রিসাইকেল বিনে সরানো হয়েছে (User moved to recycle bin)",
            "deleted_id": user_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/users/deleted/list", tags=["Users"])
def list_deleted_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """রিসাইকেল বিনের ব্যবহারকারী তালিকা (List deleted users in recycle bin)."""
    try:
        sb = get_supabase()
        offset = (page - 1) * page_size

        # Auto-purge expired users first
        _auto_purge_expired(sb)

        query = sb.table("users").select("*", count="exact").not_.is_("deleted_at", "null").order("deleted_at", desc=True)
        result = query.range(offset, offset + page_size - 1).execute()
        total = result.count if result.count is not None else len(result.data)
        sanitized = [_sanitize_user(u) for u in result.data]

        return {
            "items": sanitized,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
            "recycle_bin_days": RECYCLE_BIN_DAYS,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.put("/api/users/{user_id}/restore", tags=["Users"])
def restore_user(user_id: str):
    """রিসাইকেল বিন থেকে ব্যবহারকারী পুনরুদ্ধার (Restore user from recycle bin)."""
    try:
        sb = get_supabase()

        existing = sb.table("users").select("id, deleted_at").eq("id", user_id).not_.is_("deleted_at", "null").execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="রিসাইকেল বিনে ব্যবহারকারী পাওয়া যায়নি (User not found in recycle bin)")

        sb.table("users").update({"deleted_at": None}).eq("id", user_id).execute()

        return {
            "message": "ব্যবহারকারী পুনরুদ্ধার করা হয়েছে (User restored successfully)",
            "restored_id": user_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.delete("/api/users/{user_id}/permanent", tags=["Users"])
def permanent_delete_user(user_id: str):
    """ব্যবহারকারী স্থায়ীভাবে মুছে ফেলুন (Permanently delete user)."""
    try:
        sb = get_supabase()

        existing = sb.table("users").select("id").eq("id", user_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="ব্যবহারকারী পাওয়া যায়নি (User not found)")

        _hard_delete_user(sb, user_id)

        return {
            "message": "ব্যবহারকারী স্থায়ীভাবে মুছে ফেলা হয়েছে (User permanently deleted)",
            "deleted_id": user_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")

"""
OTP Service - ফোন নম্বর যাচাই সেবা
Handles phone number verification via OTP sent through sms.net.bd.
"""

import os
import random
import hashlib
import requests
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from models.otp import OTPSend, OTPVerify
from db import get_supabase

router = APIRouter()

# In-memory OTP store: {user_id: {"hash": str, "phone": str, "expires_at": datetime, "attempts": int}}
_otp_store: dict = {}

OTP_EXPIRY_SECONDS = 60  # 1 minute
MAX_ATTEMPTS = 5

SMS_API_KEY = os.getenv("SMS_API_KEY", "")
SMS_API_URL = os.getenv("SMS_API_URL", "https://api.sms.net.bd/sendsms")


def _hash_otp(code: str) -> str:
    """Hash OTP so plaintext is never stored in memory."""
    return hashlib.sha256(code.encode()).hexdigest()


def _send_sms(phone: str, otp_code: str) -> bool:
    """Send OTP via sms.net.bd API."""
    if not SMS_API_KEY:
        return False

    # Normalize phone: ensure it starts with 880 (no +)
    to_number = phone.strip().replace("+", "")
    if to_number.startswith("0"):
        to_number = "880" + to_number[1:]
    elif not to_number.startswith("880"):
        to_number = "880" + to_number

    try:
        response = requests.get(SMS_API_URL, params={
            "api_key": SMS_API_KEY,
            "msg": f"গুদাম যাচাইকরণ কোড: {otp_code}\nএই কোড ১ মিনিটের মধ্যে মেয়াদ শেষ হবে।",
            "to": to_number,
        }, timeout=10)
        result = response.json()
        return result.get("error") == 0
    except Exception as e:
        print(f"SMS send error: {e}")
        return False


@router.post("/api/otp/send", tags=["OTP"])
def send_otp(data: OTPSend):
    """OTP পাঠান (Send OTP to phone number via SMS)."""
    code = f"{random.randint(100000, 999999)}"

    # Store hashed OTP
    _otp_store[data.user_id] = {
        "hash": _hash_otp(code),
        "phone": data.phone,
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=OTP_EXPIRY_SECONDS),
        "attempts": 0,
    }

    # Send SMS
    sms_sent = _send_sms(data.phone, code)

    response = {
        "message": "OTP পাঠানো হয়েছে (OTP sent)",
        "expires_in_seconds": OTP_EXPIRY_SECONDS,
        "sms_sent": sms_sent,
    }

    if not sms_sent:
        response["setup_hint"] = "SMS পাঠানো যায়নি। SMS_API_KEY চেক করুন।"

    return response


@router.post("/api/otp/verify", tags=["OTP"])
def verify_otp(data: OTPVerify):
    """OTP যাচাই করুন (Verify OTP code)."""
    stored = _otp_store.get(data.user_id)
    if not stored:
        raise HTTPException(status_code=400, detail="কোনো OTP পাওয়া যায়নি। আবার পাঠান। (No OTP found. Resend.)")

    # Check expiry
    if datetime.now(timezone.utc) > stored["expires_at"]:
        _otp_store.pop(data.user_id, None)
        raise HTTPException(status_code=400, detail="OTP এর মেয়াদ শেষ হয়ে গেছে। আবার পাঠান। (OTP expired. Resend.)")

    # Check phone match
    if stored["phone"] != data.phone:
        raise HTTPException(status_code=400, detail="ফোন নম্বর মেলেনি (Phone number mismatch)")

    # Check max attempts
    stored["attempts"] += 1
    if stored["attempts"] > MAX_ATTEMPTS:
        _otp_store.pop(data.user_id, None)
        raise HTTPException(status_code=429, detail="অনেকবার ভুল চেষ্টা হয়েছে। নতুন OTP নিন। (Too many attempts. Resend.)")

    # Verify hashed OTP
    if _hash_otp(data.otp_code) != stored["hash"]:
        remaining = MAX_ATTEMPTS - stored["attempts"]
        raise HTTPException(status_code=400, detail=f"ভুল OTP কোড। আর {remaining} বার চেষ্টা করতে পারবেন। (Invalid OTP code)")

    # OTP valid — mark phone as verified
    try:
        sb = get_supabase()
        existing = sb.table("users").select("profile_details").eq("id", data.user_id).execute()
        current_details = {}
        if existing.data:
            current_details = existing.data[0].get("profile_details") or {}
        current_details["phone_verified"] = True
        sb.table("users").update({"profile_details": current_details}).eq("id", data.user_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")

    _otp_store.pop(data.user_id, None)

    return {
        "message": "ফোন নম্বর সফলভাবে যাচাই হয়েছে (Phone verified successfully)",
        "phone_verified": True,
    }

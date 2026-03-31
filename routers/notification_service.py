"""
Notification Service - গুদাম বিজ্ঞপ্তি সেবা
Handles in-app notifications and optional SMS alerts.
"""

import uuid
import math
import os
import requests
from fastapi import APIRouter, HTTPException, Query
from models.notification import NotificationCreate, NotificationOut
from db import get_supabase
from utils.helpers import now_iso

router = APIRouter()

SMS_API_KEY = os.getenv("SMS_API_KEY", "")
SMS_API_URL = os.getenv("SMS_API_URL", "https://api.sms.net.bd/sendsms")


def _send_sms_message(phone: str, message: str) -> bool:
    """Send an SMS message via sms.net.bd API."""
    if not SMS_API_KEY:
        return False

    to_number = phone.strip().replace("+", "")
    if to_number.startswith("0"):
        to_number = "880" + to_number[1:]
    elif not to_number.startswith("880"):
        to_number = "880" + to_number

    try:
        response = requests.get(SMS_API_URL, params={
            "api_key": SMS_API_KEY,
            "msg": message,
            "to": to_number,
        }, timeout=10)
        result = response.json()
        return result.get("error") == 0
    except Exception as e:
        print(f"SMS send error: {e}")
        return False


def send_notification(
    user_id: str,
    notif_type: str,
    title: str,
    message: str,
    related_id: str = None,
    title_bn: str = None,
    message_bn: str = None,
    sms: bool = False,
):
    """Create a notification record and optionally send SMS."""
    try:
        sb = get_supabase()

        new_id = f"NTF-{uuid.uuid4().hex[:8]}"
        notif = {
            "id": new_id,
            "user_id": user_id,
            "type": notif_type,
            "title": title,
            "title_bn": title_bn or title,
            "message": message,
            "message_bn": message_bn or message,
            "related_id": related_id,
            "is_read": False,
            "created_at": now_iso(),
        }

        sb.table("notifications").insert(notif).execute()

        if sms:
            # Look up user phone
            user_result = sb.table("users").select("phone").eq("id", user_id).execute()
            if user_result.data and user_result.data[0].get("phone"):
                sms_text = f"গুদাম: {message_bn or message}"
                _send_sms_message(user_result.data[0]["phone"], sms_text)

        return notif
    except Exception as e:
        print(f"Notification error: {e}")
        return None


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/api/notifications/{user_id}", tags=["Notifications"])
def get_notifications(
    user_id: str,
    is_read: bool | None = Query(None, description="Filter by read status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """ব্যবহারকারীর বিজ্ঞপ্তি দেখুন (Get user notifications)."""
    try:
        sb = get_supabase()
        offset = (page - 1) * page_size

        query = sb.table("notifications").select("*", count="exact").eq("user_id", user_id)
        if is_read is not None:
            query = query.eq("is_read", is_read)

        result = query.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()
        total = result.count if result.count is not None else len(result.data)

        return {
            "items": result.data or [],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")


@router.get("/api/notifications/{user_id}/unread-count", tags=["Notifications"])
def get_unread_count(user_id: str):
    """অপঠিত বিজ্ঞপ্তির সংখ্যা (Get unread notification count)."""
    try:
        sb = get_supabase()
        result = sb.table("notifications").select("id", count="exact").eq("user_id", user_id).eq("is_read", False).execute()
        count = result.count if result.count is not None else len(result.data)
        return {"unread_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")


@router.put("/api/notifications/{notification_id}/read", tags=["Notifications"])
def mark_as_read(notification_id: str):
    """বিজ্ঞপ্তি পঠিত হিসেবে চিহ্নিত করুন (Mark notification as read)."""
    try:
        sb = get_supabase()
        result = sb.table("notifications").update({"is_read": True}).eq("id", notification_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="বিজ্ঞপ্তি পাওয়া যায়নি (Notification not found)")
        return {"message": "বিজ্ঞপ্তি পঠিত হিসেবে চিহ্নিত হয়েছে (Marked as read)", "notification": result.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")


@router.put("/api/notifications/{user_id}/read-all", tags=["Notifications"])
def mark_all_as_read(user_id: str):
    """সকল বিজ্ঞপ্তি পঠিত হিসেবে চিহ্নিত করুন (Mark all notifications as read)."""
    try:
        sb = get_supabase()
        sb.table("notifications").update({"is_read": True}).eq("user_id", user_id).eq("is_read", False).execute()
        return {"message": "সকল বিজ্ঞপ্তি পঠিত হিসেবে চিহ্নিত হয়েছে (All notifications marked as read)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")

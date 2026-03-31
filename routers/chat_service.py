"""
Chat Service - গুদাম চ্যাট সেবা
Handles real-time messaging between users.
Messages are stored in encrypted form.
"""

import uuid
import base64
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from db import get_supabase
from utils.helpers import now_iso

router = APIRouter()

# Encryption key (in production, use environment variable)
ENCRYPTION_KEY = "gudam_secret_key_2024"


def encrypt_message(message: str) -> str:
    """Encrypt message using XOR cipher with base64 encoding."""
    key_bytes = ENCRYPTION_KEY.encode('utf-8')
    message_bytes = message.encode('utf-8')

    # XOR encryption
    encrypted = bytes([
        message_bytes[i] ^ key_bytes[i % len(key_bytes)]
        for i in range(len(message_bytes))
    ])

    # Base64 encode for storage
    return base64.b64encode(encrypted).decode('utf-8')


def decrypt_message(encrypted: str) -> str:
    """Decrypt message using XOR cipher with base64 decoding."""
    try:
        key_bytes = ENCRYPTION_KEY.encode('utf-8')
        encrypted_bytes = base64.b64decode(encrypted.encode('utf-8'))

        # XOR decryption (same as encryption for XOR)
        decrypted = bytes([
            encrypted_bytes[i] ^ key_bytes[i % len(key_bytes)]
            for i in range(len(encrypted_bytes))
        ])

        return decrypted.decode('utf-8')
    except Exception:
        # Return original if decryption fails (for old unencrypted messages)
        return encrypted


class MessageCreate(BaseModel):
    receiver_id: str
    content: str


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    content: str
    is_read: bool
    created_at: str


# ─── Helpers ───────────────────────────────────────────────────────────────────

def get_or_create_conversation(sb, user1_id: str, user2_id: str) -> str:
    """Get existing conversation or create new one."""
    # Sort IDs to ensure consistent lookup
    p1, p2 = sorted([user1_id, user2_id])

    # Check if conversation exists
    result = sb.table("conversations").select("id").eq("participant_1", p1).eq("participant_2", p2).execute()

    if result.data:
        return result.data[0]["id"]

    # Create new conversation
    conv_id = f"CONV-{uuid.uuid4().hex[:8]}"
    sb.table("conversations").insert({
        "id": conv_id,
        "participant_1": p1,
        "participant_2": p2,
        "created_at": now_iso(),
    }).execute()

    return conv_id


def get_allowed_roles(role: str) -> list:
    """Communication rules: farmer↔agent, buyer↔agent. No farmer↔buyer."""
    if role == "farmer":
        return ["agent"]
    elif role == "buyer":
        return ["agent"]
    elif role == "agent":
        return ["farmer", "buyer"]
    else:
        return ["farmer", "buyer", "agent", "admin"]  # admin can message anyone


def validate_communication(sb, user1_id: str, user2_id: str):
    """Validate that two users are allowed to communicate (farmer↔agent, buyer↔agent only)."""
    users = sb.table("users").select("id,role").in_("id", [user1_id, user2_id]).execute()
    roles = {u["id"]: u.get("role") for u in (users.data or [])}
    r1, r2 = roles.get(user1_id), roles.get(user2_id)
    if not r1 or not r2:
        return  # Allow if role unknown
    pair = {r1, r2}
    if pair == {"farmer", "buyer"}:
        raise HTTPException(status_code=403, detail="কৃষক ও ক্রেতার মধ্যে সরাসরি যোগাযোগ অনুমোদিত নয়। এজেন্টের মাধ্যমে যোগাযোগ করুন।")


# ─── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/api/messages", tags=["Chat"])
def send_message(data: MessageCreate, sender_id: str = Query(..., description="Sender user ID")):
    """মেসেজ পাঠান (Send a message). Messages are encrypted before storage."""
    try:
        sb = get_supabase()

        # Enforce communication rules
        validate_communication(sb, sender_id, data.receiver_id)

        # Get or create conversation
        conv_id = get_or_create_conversation(sb, sender_id, data.receiver_id)

        # Encrypt message content
        encrypted_content = encrypt_message(data.content)

        # Create message with encrypted content
        msg_id = f"MSG-{uuid.uuid4().hex[:8]}"
        new_message = {
            "id": msg_id,
            "conversation_id": conv_id,
            "sender_id": sender_id,
            "content": encrypted_content,  # Store encrypted
            "is_read": False,
            "created_at": now_iso(),
        }

        sb.table("messages").insert(new_message).execute()

        # Update conversation's last message (also encrypted)
        sb.table("conversations").update({
            "last_message": encrypt_message(data.content[:100]),
            "last_message_at": now_iso(),
        }).eq("id", conv_id).execute()

        # Return decrypted for response
        return {
            "message": "মেসেজ পাঠানো হয়েছে (Message sent)",
            "data": {**new_message, "content": data.content},  # Return decrypted
            "conversation_id": conv_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")


@router.get("/api/conversations/search", tags=["Chat"])
def search_users(
    current_user_id: str = Query(..., description="Current user ID"),
    query: str = Query("", description="Search by name or phone"),
):
    """নাম বা ফোন দিয়ে ব্যবহারকারী খুঁজুন (Search users by name or phone)."""
    try:
        sb = get_supabase()

        # Get current user's role
        current_user = sb.table("users").select("role").eq("id", current_user_id).execute()
        current_role = current_user.data[0]["role"] if current_user.data else None
        allowed_roles = get_allowed_roles(current_role) if current_role else []

        # If query is provided, search by name or phone
        if query and len(query) >= 2:
            result = sb.table("users").select("id,name,phone,avatar_url,role").or_(
                f"name.ilike.%{query}%,phone.ilike.%{query}%"
            ).limit(20).execute()
        else:
            result = sb.table("users").select("id,name,phone,avatar_url,role").limit(20).execute()

        users = []
        for user in result.data or []:
            # Don't include current user and enforce communication rules
            if user["id"] != current_user_id and user.get("role") in allowed_roles:
                users.append(user)

        return {"users": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")


@router.get("/api/conversations/{user_id}", tags=["Chat"])
def get_conversations(user_id: str):
    """ব্যবহারকারীর সকল কথোপকথন (Get user's conversations)."""
    try:
        sb = get_supabase()

        # Get conversations where user is participant
        result = sb.table("conversations").select("*").or_(
            f"participant_1.eq.{user_id},participant_2.eq.{user_id}"
        ).order("last_message_at", desc=True).execute()

        conversations = []
        for conv in result.data or []:
            # Get the other participant
            other_id = conv["participant_2"] if conv["participant_1"] == user_id else conv["participant_1"]

            # Get other user's info
            user_result = sb.table("users").select("id,name,avatar_url,role").eq("id", other_id).execute()
            other_user = user_result.data[0] if user_result.data else None

            # Count unread messages
            unread_result = sb.table("messages").select("id", count="exact").eq(
                "conversation_id", conv["id"]
            ).eq("is_read", False).neq("sender_id", user_id).execute()

            # Decrypt last_message for display
            decrypted_last_message = decrypt_message(conv.get("last_message") or "") if conv.get("last_message") else ""

            conversations.append({
                **conv,
                "last_message": decrypted_last_message,
                "other_user": other_user,
                "unread_count": unread_result.count or 0,
            })

        return {"conversations": conversations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")


@router.get("/api/messages/{conversation_id}", tags=["Chat"])
def get_messages(
    conversation_id: str,
    user_id: str = Query(..., description="Current user ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """কথোপকথনের মেসেজসমূহ (Get conversation messages)."""
    try:
        sb = get_supabase()
        offset = (page - 1) * page_size

        # Get messages
        result = sb.table("messages").select("*", count="exact").eq(
            "conversation_id", conversation_id
        ).order("created_at", desc=True).range(offset, offset + page_size - 1).execute()

        # Mark messages as read
        sb.table("messages").update({"is_read": True}).eq(
            "conversation_id", conversation_id
        ).neq("sender_id", user_id).eq("is_read", False).execute()

        # Reverse to show oldest first and decrypt messages
        messages = []
        for msg in reversed(result.data or []):
            decrypted_msg = {**msg, "content": decrypt_message(msg.get("content", ""))}
            messages.append(decrypted_msg)

        return {
            "messages": messages,
            "total": result.count or 0,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")


@router.get("/api/messages/unread/{user_id}", tags=["Chat"])
def get_unread_count(user_id: str):
    """অপঠিত মেসেজের সংখ্যা (Get unread message count)."""
    try:
        sb = get_supabase()

        # Get all conversations for user
        conv_result = sb.table("conversations").select("id").or_(
            f"participant_1.eq.{user_id},participant_2.eq.{user_id}"
        ).execute()

        if not conv_result.data:
            return {"unread_count": 0}

        conv_ids = [c["id"] for c in conv_result.data]

        # Count unread messages not sent by user
        total_unread = 0
        for conv_id in conv_ids:
            result = sb.table("messages").select("id", count="exact").eq(
                "conversation_id", conv_id
            ).eq("is_read", False).neq("sender_id", user_id).execute()
            total_unread += result.count or 0

        return {"unread_count": total_unread}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")


@router.post("/api/conversations/start", tags=["Chat"])
def start_conversation(user1_id: str = Query(..., description="First user ID"), user2_id: str = Query(..., description="Second user ID")):
    """নতুন কথোপকথন শুরু করুন (Start a new conversation)."""
    try:
        sb = get_supabase()

        # Enforce communication rules
        validate_communication(sb, user1_id, user2_id)

        conv_id = get_or_create_conversation(sb, user1_id, user2_id)

        # Get conversation with other user info
        p1, p2 = sorted([user1_id, user2_id])
        conv_result = sb.table("conversations").select("*").eq("id", conv_id).execute()

        other_id = user2_id
        user_result = sb.table("users").select("id,name,avatar_url,role").eq("id", other_id).execute()

        return {
            "conversation": conv_result.data[0] if conv_result.data else None,
            "other_user": user_result.data[0] if user_result.data else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")

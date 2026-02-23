"""
Verification Service - গুদাম পণ্য যাচাই সেবা
Handles product verification workflow by agents.
"""

import uuid
import math
from fastapi import APIRouter, HTTPException, Query
from models.verification import VerificationCreate, VerificationOut, VerificationStatusUpdate
from db import get_supabase
from utils.helpers import now_iso
from routers.notification_service import send_notification

router = APIRouter()


def _enrich_verifications(sb, verifications):
    """Enrich verification records with product and farmer names."""
    if not verifications:
        return verifications

    product_ids = list({v["product_id"] for v in verifications if v.get("product_id")})
    products = {}
    farmer_ids = set()

    if product_ids:
        p_result = sb.table("products").select("id,name_bn,name_en,unit,images,farmer_id").in_("id", product_ids).execute()
        for p in (p_result.data or []):
            products[p["id"]] = p
            if p.get("farmer_id"):
                farmer_ids.add(p["farmer_id"])

    users = {}
    if farmer_ids:
        u_result = sb.table("users").select("id,name").in_("id", list(farmer_ids)).execute()
        users = {u["id"]: u for u in (u_result.data or [])}

    for v in verifications:
        prod = products.get(v.get("product_id"), {})
        v["product_name_bn"] = prod.get("name_bn", "")
        v["product_name_en"] = prod.get("name_en", "")
        v["product_unit"] = prod.get("unit", "")
        v["product_image"] = (prod.get("images") or [None])[0]
        farmer_id = prod.get("farmer_id") or v.get("farmer_id")
        v["farmer_id"] = farmer_id
        v["farmer_name"] = users.get(farmer_id, {}).get("name", "")

    return verifications


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/api/verifications/listings/{product_id}/verify", tags=["Verifications"])
def start_verification(product_id: str, data: VerificationCreate):
    """পণ্য যাচাই শুরু করুন (Start product verification)."""
    try:
        sb = get_supabase()

        # Check product exists
        product_result = sb.table("products").select("*").eq("id", product_id).execute()
        if not product_result.data:
            raise HTTPException(status_code=404, detail="পণ্য পাওয়া যায়নি (Product not found)")

        product = product_result.data[0]

        if product["status"] == "verified":
            raise HTTPException(status_code=400, detail="পণ্য ইতিমধ্যে যাচাই করা হয়েছে (Product already verified)")

        new_id = f"VRF-{uuid.uuid4().hex[:8]}"
        new_verification = {
            "id": new_id,
            "product_id": product_id,
            "agent_id": data.agent_id,
            "status": "in_progress",
            "original_grade": data.quality_grade,
            "notes": data.notes,
            "created_at": now_iso(),
        }

        sb.table("verifications").insert(new_verification).execute()

        # Update product status
        sb.table("products").update({"status": "pending_verification"}).eq("id", product_id).execute()

        # Notify agent about new listing assignment
        send_notification(
            user_id=data.agent_id,
            notif_type="listing_assigned",
            title="New Listing Assignment",
            title_bn="নতুন পণ্য যাচাইয়ের দায়িত্ব",
            message=f"You have been assigned to verify product {product_id}",
            message_bn=f"পণ্য {product.get('name_bn', product_id)} যাচাই করার দায়িত্ব দেওয়া হয়েছে",
            related_id=new_id,
            sms=True,
        )

        return {
            "message": "যাচাই প্রক্রিয়া শুরু হয়েছে (Verification process started)",
            "verification": new_verification,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/verifications", tags=["Verifications"])
def list_verifications(
    status: str | None = Query(None, description="Filter by status"),
    agent_id: str | None = Query(None, description="Filter by agent ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """সকল যাচাইয়ের তালিকা (List all verifications)."""
    try:
        sb = get_supabase()
        offset = (page - 1) * page_size

        query = sb.table("verifications").select("*", count="exact")

        if status:
            query = query.eq("status", status)
        if agent_id:
            query = query.eq("agent_id", agent_id)

        result = query.range(offset, offset + page_size - 1).execute()
        total = result.count if result.count is not None else len(result.data)

        items = _enrich_verifications(sb, result.data or [])

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


# NOTE: /agent/{agent_id} must be defined BEFORE /{verification_id}
# to avoid the catch-all route matching "agent" as a verification_id.

@router.get("/api/verifications/agent/{agent_id}", tags=["Verifications"])
def get_agent_verifications(
    agent_id: str,
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """এজেন্টের যাচাইসমূহ (Get agent's verifications)."""
    try:
        sb = get_supabase()
        offset = (page - 1) * page_size

        query = sb.table("verifications").select("*", count="exact").eq("agent_id", agent_id)
        if status:
            query = query.eq("status", status)

        result = query.range(offset, offset + page_size - 1).execute()
        total = result.count if result.count is not None else len(result.data)

        items = _enrich_verifications(sb, result.data or [])

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/verifications/{verification_id}", tags=["Verifications"])
def get_verification(verification_id: str):
    """যাচাইয়ের বিস্তারিত দেখুন (Get verification details)."""
    try:
        sb = get_supabase()

        v_result = sb.table("verifications").select("*").eq("id", verification_id).execute()
        if not v_result.data:
            raise HTTPException(status_code=404, detail="যাচাই পাওয়া যায়নি (Verification not found)")

        verification = v_result.data[0]

        # Attach product info
        product = None
        p_result = sb.table("products").select("*").eq("id", verification["product_id"]).execute()
        if p_result.data:
            product = p_result.data[0]

        return {
            "verification": verification,
            "product": product,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.put("/api/verifications/{verification_id}/status", tags=["Verifications"])
def update_verification_status(verification_id: str, update: VerificationStatusUpdate):
    """যাচাইয়ের অবস্থা আপডেট করুন (Update verification status)."""
    try:
        sb = get_supabase()

        v_result = sb.table("verifications").select("*").eq("id", verification_id).execute()
        if not v_result.data:
            raise HTTPException(status_code=404, detail="যাচাই পাওয়া যায়নি (Verification not found)")

        verification = v_result.data[0]

        # Build update dict for verification
        v_update = {"status": update.status}

        if update.quality_grade:
            v_update["verified_grade"] = update.quality_grade
        if update.notes:
            v_update["notes"] = update.notes
        if update.adjusted_quantity is not None:
            v_update["verified_quantity"] = update.adjusted_quantity
        if update.status == "verified":
            v_update["verified_at"] = now_iso()

        v_updated = sb.table("verifications").update(v_update).eq("id", verification_id).execute()
        updated_verification = v_updated.data[0] if v_updated.data else verification

        # If verified/confirmed/adjusted, update the product
        if update.status in ("verified", "confirmed", "adjusted"):
            p_update = {
                "status": "verified",
                "verified_by": verification["agent_id"],
                "verification_date": now_iso(),
            }
            if update.quality_grade:
                p_update["quality_grade"] = update.quality_grade
            if update.adjusted_quantity is not None:
                p_update["quantity"] = update.adjusted_quantity
            if update.adjusted_price is not None:
                p_update["price_per_unit"] = update.adjusted_price

            sb.table("products").update(p_update).eq("id", verification["product_id"]).execute()

        elif update.status == "rejected":
            sb.table("products").update({"status": "pending_verification"}).eq("id", verification["product_id"]).execute()

        # Notify farmer about verification result
        if update.status in ("verified", "rejected"):
            farmer_id = verification.get("farmer_id")
            if not farmer_id:
                # Get farmer_id from product
                p_res = sb.table("products").select("farmer_id").eq("id", verification["product_id"]).execute()
                if p_res.data:
                    farmer_id = p_res.data[0].get("farmer_id")

            if farmer_id:
                status_label = "যাচাই সম্পন্ন" if update.status == "verified" else "প্রত্যাখ্যাত"
                send_notification(
                    user_id=farmer_id,
                    notif_type="verification_complete",
                    title=f"Verification {update.status}",
                    title_bn=f"পণ্য যাচাই: {status_label}",
                    message=f"Your product verification has been {update.status}",
                    message_bn=f"আপনার পণ্যের যাচাই {status_label} হয়েছে",
                    related_id=verification_id,
                    sms=True,
                )

        status_messages = {
            "pending": "যাচাই মুলতবি আছে (Verification pending)",
            "in_progress": "যাচাই চলছে (Verification in progress)",
            "verified": "পণ্য যাচাই সম্পন্ন (Product verified successfully)",
            "rejected": "পণ্য প্রত্যাখ্যাত হয়েছে (Product rejected)",
            "adjustment_proposed": "সমন্বয় প্রস্তাব করা হয়েছে (Adjustment proposed)",
        }

        return {
            "message": status_messages.get(update.status, "অবস্থা আপডেট হয়েছে (Status updated)"),
            "verification": updated_verification,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")

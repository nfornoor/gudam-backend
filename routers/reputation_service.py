"""
Reputation Service - গুদাম সুনাম সেবা
Handles ratings, reviews, and reputation scoring.
"""

import uuid
import math
from fastapi import APIRouter, HTTPException, Query
from models.rating import RatingCreate, RatingOut, ReputationOut
from db import get_supabase
from utils.helpers import now_iso

router = APIRouter()


def _compute_reputation(user_id: str) -> dict:
    """Compute reputation metrics for a user from Supabase ratings."""
    sb = get_supabase()
    result = sb.table("ratings").select("*").eq("to_user_id", user_id).execute()
    user_ratings = result.data

    if not user_ratings:
        return {
            "user_id": user_id,
            "average_score": 0.0,
            "total_ratings": 0,
            "score_breakdown": {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0},
            "category_scores": {},
            "badge": None,
            "badge_bn": None,
        }

    total = len(user_ratings)
    avg = round(sum(r["rating"] for r in user_ratings) / total, 2)

    # Score breakdown
    breakdown = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
    for r in user_ratings:
        bucket = str(int(r["rating"]))
        if bucket in breakdown:
            breakdown[bucket] += 1

    # Category scores
    category_scores = {}
    category_counts = {}
    for r in user_ratings:
        cat = r.get("type", "general")
        category_scores[cat] = category_scores.get(cat, 0) + r["rating"]
        category_counts[cat] = category_counts.get(cat, 0) + 1
    for cat in category_scores:
        category_scores[cat] = round(category_scores[cat] / category_counts[cat], 2)

    # Entity type breakdown (farmer/agent/product ratings)
    entity_scores = {}
    entity_counts = {}
    for r in user_ratings:
        etype = r.get("rated_entity_type") or r.get("type", "farmer")
        entity_scores[etype] = entity_scores.get(etype, 0) + r["rating"]
        entity_counts[etype] = entity_counts.get(etype, 0) + 1
    for etype in entity_scores:
        entity_scores[etype] = round(entity_scores[etype] / entity_counts[etype], 2)

    # Badge assignment
    badge = None
    badge_bn = None
    if avg >= 4.5 and total >= 5:
        badge = "Gold Seller"
        badge_bn = "স্বর্ণ বিক্রেতা"
    elif avg >= 4.0 and total >= 3:
        badge = "Trusted Seller"
        badge_bn = "বিশ্বস্ত বিক্রেতা"
    elif avg >= 3.5:
        badge = "Verified Seller"
        badge_bn = "যাচাইকৃত বিক্রেতা"
    elif avg >= 2.5:
        badge = "New Seller"
        badge_bn = "নতুন বিক্রেতা"

    return {
        "user_id": user_id,
        "average_score": avg,
        "total_ratings": total,
        "score_breakdown": breakdown,
        "category_scores": category_scores,
        "entity_scores": entity_scores,
        "badge": badge,
        "badge_bn": badge_bn,
    }


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/api/ratings", tags=["Reputation"])
def submit_rating(rating_data: RatingCreate):
    """রেটিং দিন (Submit a rating)."""
    try:
        sb = get_supabase()

        from_user = rating_data.from_user_id or "USR008"

        # Validate: prevent duplicate ratings for same order + rater + rated user
        if rating_data.order_id:
            existing = sb.table("ratings").select("id", count="exact").eq("order_id", rating_data.order_id).eq("from_user_id", from_user).eq("to_user_id", rating_data.rated_user_id).execute()
            if existing.data:
                raise HTTPException(status_code=400, detail="আপনি ইতিমধ্যে এই অর্ডারে রেটিং দিয়েছেন (You already rated for this order)")

        # Validate order is completed (if order_id provided)
        if rating_data.order_id:
            order_result = sb.table("orders").select("*").eq("id", rating_data.order_id).execute()
            if not order_result.data:
                raise HTTPException(status_code=404, detail="অর্ডার পাওয়া যায়নি (Order not found)")
            order = order_result.data[0]
            if order["status"] not in ("completed", "delivered"):
                raise HTTPException(status_code=400, detail="অর্ডার সম্পন্ন না হলে রেটিং দেওয়া যায় না (Order must be completed to rate)")

            # Validate rater role
            entity_type = rating_data.rated_entity_type
            if entity_type in ("farmer", "agent") and from_user == order.get("buyer_id"):
                pass  # Buyer can rate farmer or agent
            elif entity_type == "agent" and from_user == order.get("farmer_id"):
                pass  # Farmer can rate agent
            else:
                # Allow for demo/testing purposes but log warning
                print(f"Warning: Rater {from_user} rating {entity_type} for order {rating_data.order_id}")

        new_id = f"RTG-{uuid.uuid4().hex[:8]}"
        new_rating = {
            "id": new_id,
            "to_user_id": rating_data.rated_user_id,
            "from_user_id": from_user,
            "order_id": rating_data.order_id,
            "type": rating_data.category,
            "rating": rating_data.score,
            "review": rating_data.comment,
            "created_at": now_iso(),
        }

        # Add rated_entity_type if column exists
        try:
            test_rating = {**new_rating, "rated_entity_type": rating_data.rated_entity_type}
            result = sb.table("ratings").insert(test_rating).execute()
        except Exception:
            result = sb.table("ratings").insert(new_rating).execute()
        inserted = result.data[0] if result.data else new_rating

        return {
            "message": "রেটিং সফলভাবে জমা হয়েছে (Rating submitted successfully)",
            "rating": inserted,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/users/{user_id}/reputation", tags=["Reputation"])
def get_user_reputation(user_id: str):
    """ব্যবহারকারীর সুনাম দেখুন (Get user reputation)."""
    try:
        reputation = _compute_reputation(user_id)
        return reputation
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/ratings/user/{user_id}", tags=["Reputation"])
def get_user_ratings(
    user_id: str,
    category: str | None = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """ব্যবহারকারীর সকল রেটিং দেখুন (Get all ratings for a user)."""
    try:
        sb = get_supabase()
        offset = (page - 1) * page_size

        query = sb.table("ratings").select("*", count="exact").eq("to_user_id", user_id)
        if category:
            query = query.eq("type", category)

        result = query.range(offset, offset + page_size - 1).execute()
        total = result.count if result.count is not None else len(result.data)

        return {
            "items": result.data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/ratings/check/{order_id}/{from_user_id}", tags=["Reputation"])
def check_rating(order_id: str, from_user_id: str):
    """রেটিং দেওয়া হয়েছে কিনা দেখুন (Check if user already rated for an order)."""
    try:
        sb = get_supabase()
        result = sb.table("ratings").select("id,to_user_id,type,rating").eq("order_id", order_id).eq("from_user_id", from_user_id).execute()
        ratings = result.data or []

        # Determine rated entities by looking up to_user_id roles
        rated_farmer = False
        rated_agent = False
        if ratings:
            user_ids = list({r["to_user_id"] for r in ratings})
            users_result = sb.table("users").select("id,role").in_("id", user_ids).execute()
            user_roles = {u["id"]: u["role"] for u in (users_result.data or [])}
            for r in ratings:
                role = user_roles.get(r["to_user_id"], "")
                if role == "farmer":
                    rated_farmer = True
                elif role == "agent":
                    rated_agent = True

        return {
            "has_rated": len(ratings) > 0,
            "ratings": ratings,
            "rated_farmer": rated_farmer,
            "rated_agent": rated_agent,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/ratings/product/{product_id}", tags=["Reputation"])
def get_product_ratings(
    product_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """পণ্যের রেটিং দেখুন (Get product ratings)."""
    try:
        sb = get_supabase()
        offset = (page - 1) * page_size

        # The ratings table doesn't have a direct product_id column,
        # so we join through orders or filter by order_id.
        # For now, fetch ratings linked via order_id to orders for this product.
        order_result = sb.table("orders").select("id").eq("product_id", product_id).execute()
        order_ids = [o["id"] for o in order_result.data] if order_result.data else []

        if not order_ids:
            return {
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
            }

        query = sb.table("ratings").select("*", count="exact").in_("order_id", order_ids)
        result = query.range(offset, offset + page_size - 1).execute()
        total = result.count if result.count is not None else len(result.data)

        return {
            "items": result.data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")

"""
Product Catalog Service - গুদাম পণ্য ক্যাটালগ সেবা
Handles product listings, search, and category management.
"""

import uuid
import math
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Query
from models.product import ProductCreate, ProductOut, ProductUpdate, CategoryOut
from db import get_supabase
from utils.helpers import now_iso
from routers.notification_service import send_notification

router = APIRouter()

RECYCLE_BIN_DAYS = 30

CATEGORIES = [
    {"id": "grains", "name_en": "Grains & Cereals", "name_bn": "শস্য ও খাদ্যশস্য", "icon": "🌾"},
    {"id": "vegetables", "name_en": "Vegetables", "name_bn": "শাকসবজি", "icon": "🥬"},
    {"id": "fruits", "name_en": "Fruits", "name_bn": "ফলমূল", "icon": "🍎"},
    {"id": "pulses", "name_en": "Pulses & Lentils", "name_bn": "ডাল ও শিম", "icon": "🫘"},
    {"id": "spices", "name_en": "Spices", "name_bn": "মসলা", "icon": "🌶️"},
    {"id": "fiber", "name_en": "Fiber Crops", "name_bn": "আঁশ ফসল", "icon": "🧵"},
    {"id": "oilseeds", "name_en": "Oil Seeds", "name_bn": "তৈলবীজ", "icon": "🌻"},
    {"id": "dairy", "name_en": "Dairy & Livestock", "name_bn": "দুগ্ধ ও প্রাণিসম্পদ", "icon": "🥛"},
    {"id": "fish", "name_en": "Fish & Seafood", "name_bn": "মাছ ও সামুদ্রিক খাবার", "icon": "🐟"},
]


def _auto_purge_products(sb):
    """Permanently delete products whose deleted_at is older than 30 days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RECYCLE_BIN_DAYS)).isoformat()
    expired = sb.table("products").select("id").not_.is_("deleted_at", "null").lt("deleted_at", cutoff).execute()
    for p in expired.data:
        try:
            sb.table("verifications").delete().eq("product_id", p["id"]).execute()
            sb.table("products").delete().eq("id", p["id"]).execute()
        except Exception:
            pass


def _enrich_products(sb, products):
    """Enrich products with farmer and agent (verified_by) names."""
    if not products:
        return products

    user_ids = set()
    for p in products:
        if p.get("farmer_id"):
            user_ids.add(p["farmer_id"])
        if p.get("verified_by"):
            user_ids.add(p["verified_by"])

    users = {}
    if user_ids:
        u_result = sb.table("users").select("id,name").in_("id", list(user_ids)).execute()
        users = {u["id"]: u for u in (u_result.data or [])}

    for p in products:
        p["farmer_name"] = users.get(p.get("farmer_id"), {}).get("name", "")
        p["verified_by_name"] = users.get(p.get("verified_by"), {}).get("name", "")

    return products


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/api/products", tags=["Products"])
def create_product(product_data: ProductCreate):
    """নতুন পণ্য তালিকাভুক্ত করুন (Create a new product listing)."""
    try:
        sb = get_supabase()

        new_id = f"PRD-{uuid.uuid4().hex[:8]}"
        new_product = {
            "id": new_id,
            "farmer_id": product_data.farmer_id,
            "name_bn": product_data.name_bn,
            "name_en": product_data.name_en,
            "category": product_data.category,
            "quantity": product_data.quantity,
            "unit": product_data.unit,
            "quality_grade": product_data.quality_grade,
            "price_per_unit": product_data.price_per_unit,
            "currency": product_data.currency,
            "status": "pending_verification",
            "images": product_data.images,
            "location": product_data.location,
            "description_bn": product_data.description_bn,
            "created_at": now_iso(),
            "verified_by": None,
            "verification_date": None,
        }

        result = sb.table("products").insert(new_product).execute()
        inserted = result.data[0] if result.data else new_product

        return {
            "message": "পণ্য সফলভাবে তালিকাভুক্ত হয়েছে (Product listed successfully)",
            "product": inserted,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/categories", tags=["Products"])
def get_categories():
    """পণ্যের বিভাগসমূহ (Get product categories)."""
    return {"categories": CATEGORIES}


@router.get("/api/products/farmer/{farmer_id}", tags=["Products"])
def get_farmer_products(
    farmer_id: str,
    status: str | None = Query(None),
    category: str | None = Query(None),
    quality_grade: str | None = Query(None),
    search: str | None = Query(None),
    sort: str | None = Query(None, description="Sort: price_asc, price_desc, date_asc, date_desc, quantity_desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """কৃষকের পণ্যসমূহ (Get products by farmer)."""
    try:
        sb = get_supabase()
        offset = (page - 1) * page_size

        query = sb.table("products").select("*", count="exact").eq("farmer_id", farmer_id).is_("deleted_at", "null")
        if status:
            query = query.eq("status", status)
        if category:
            query = query.eq("category", category)
        if quality_grade:
            query = query.eq("quality_grade", quality_grade)
        if search:
            query = query.or_(f"name_en.ilike.%{search}%,name_bn.ilike.%{search}%")

        # Sorting
        if sort == "price_asc":
            query = query.order("price_per_unit", desc=False)
        elif sort == "price_desc":
            query = query.order("price_per_unit", desc=True)
        elif sort == "date_asc":
            query = query.order("created_at", desc=False)
        elif sort == "quantity_desc":
            query = query.order("quantity", desc=True)
        else:
            query = query.order("created_at", desc=True)

        result = query.range(offset, offset + page_size - 1).execute()
        total = result.count if result.count is not None else len(result.data)

        items = _enrich_products(sb, result.data or [])

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/products/deleted/list", tags=["Products"])
def list_deleted_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """রিসাইকেল বিনের পণ্য তালিকা (List deleted products in recycle bin)."""
    try:
        sb = get_supabase()
        offset = (page - 1) * page_size

        _auto_purge_products(sb)

        query = sb.table("products").select("*", count="exact").not_.is_("deleted_at", "null").order("deleted_at", desc=True)
        result = query.range(offset, offset + page_size - 1).execute()
        total = result.count if result.count is not None else len(result.data)

        return {
            "items": result.data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
            "recycle_bin_days": RECYCLE_BIN_DAYS,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/products/{product_id}", tags=["Products"])
def get_product(product_id: str):
    """পণ্যের বিস্তারিত দেখুন (Get product details)."""
    try:
        sb = get_supabase()
        result = sb.table("products").select("*").eq("id", product_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="পণ্য পাওয়া যায়নি (Product not found)")
        return _enrich_products(sb, result.data)[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/products", tags=["Products"])
def list_products(
    category: str | None = Query(None, description="Filter by category"),
    status: str | None = Query(None, description="Filter by status: pending_verification, verified, sold"),
    min_price: float | None = Query(None, description="Minimum price per unit (BDT)"),
    max_price: float | None = Query(None, description="Maximum price per unit (BDT)"),
    location: str | None = Query(None, description="Filter by district name (partial match)"),
    search: str | None = Query(None, description="Search in product name (EN or BN)"),
    farmer_id: str | None = Query(None, description="Filter by farmer ID"),
    quality_grade: str | None = Query(None, description="Filter by quality grade: A, B, C"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """পণ্য তালিকা ও অনুসন্ধান (List and search products)."""
    try:
        sb = get_supabase()
        offset = (page - 1) * page_size

        query = sb.table("products").select("*", count="exact").is_("deleted_at", "null")

        if category:
            query = query.eq("category", category)
        if status:
            query = query.eq("status", status)
        if min_price is not None:
            query = query.gte("price_per_unit", min_price)
        if max_price is not None:
            query = query.lte("price_per_unit", max_price)
        if farmer_id:
            query = query.eq("farmer_id", farmer_id)
        if quality_grade:
            query = query.eq("quality_grade", quality_grade)
        if location:
            query = query.ilike("location", f"%{location}%")
        if search:
            query = query.or_(f"name_en.ilike.%{search}%,name_bn.ilike.%{search}%")

        result = query.range(offset, offset + page_size - 1).execute()
        total = result.count if result.count is not None else len(result.data)

        items = _enrich_products(sb, result.data or [])

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.put("/api/products/{product_id}", tags=["Products"])
def update_product(product_id: str, update: ProductUpdate):
    """পণ্যের তথ্য আপডেট করুন (Update product details)."""
    try:
        sb = get_supabase()

        existing = sb.table("products").select("*").eq("id", product_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="পণ্য পাওয়া যায়নি (Product not found)")

        update_data = update.model_dump(exclude_unset=True)
        # Remove None values
        update_data = {k: v for k, v in update_data.items() if v is not None}

        if not update_data:
            return {
                "message": "পণ্য আপডেট হয়েছে (Product updated)",
                "product": existing.data[0],
            }

        result = sb.table("products").update(update_data).eq("id", product_id).execute()
        updated = result.data[0] if result.data else existing.data[0]

        # Send notifications
        prod = existing.data[0]
        name_bn = prod.get("name_bn", "")
        farmer_id = prod.get("farmer_id")
        verified_by = prod.get("verified_by")
        if farmer_id:
            send_notification(
                user_id=farmer_id,
                notif_type="product_updated",
                title="পণ্য আপডেট হয়েছে",
                message=f"আপনার পণ্য '{name_bn}' অ্যাডমিন কর্তৃক আপডেট করা হয়েছে।",
                title_bn="পণ্য আপডেট হয়েছে",
                message_bn=f"আপনার পণ্য '{name_bn}' অ্যাডমিন কর্তৃক আপডেট করা হয়েছে।",
                related_id=product_id,
            )
        if verified_by:
            send_notification(
                user_id=verified_by,
                notif_type="product_updated_agent",
                title="পণ্য আপডেট হয়েছে",
                message=f"'{name_bn}' পণ্যটি অ্যাডমিন কর্তৃক আপডেট করা হয়েছে।",
                title_bn="পণ্য আপডেট হয়েছে",
                message_bn=f"'{name_bn}' পণ্যটি অ্যাডমিন কর্তৃক আপডেট করা হয়েছে।",
                related_id=product_id,
            )

        return {
            "message": "পণ্য আপডেট হয়েছে (Product updated)",
            "product": updated,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


# ─── Soft Delete (Recycle Bin) ────────────────────────────────────────────────


@router.delete("/api/products/{product_id}", tags=["Products"])
def delete_product(product_id: str):
    """পণ্য রিসাইকেল বিনে পাঠান (Soft delete - move to recycle bin)."""
    try:
        sb = get_supabase()

        existing = sb.table("products").select("id,name_bn,farmer_id,verified_by").eq("id", product_id).is_("deleted_at", "null").execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="পণ্য পাওয়া যায়নি (Product not found)")

        prod = existing.data[0]
        name_bn = prod.get("name_bn", "")
        farmer_id = prod.get("farmer_id")
        verified_by = prod.get("verified_by")

        sb.table("products").update({"deleted_at": now_iso()}).eq("id", product_id).execute()

        if farmer_id:
            send_notification(
                user_id=farmer_id,
                notif_type="product_deleted",
                title="পণ্য রিসাইকেল বিনে সরানো হয়েছে",
                message=f"আপনার পণ্য '{name_bn}' অ্যাডমিন কর্তৃক রিসাইকেল বিনে সরানো হয়েছে।",
                title_bn="পণ্য রিসাইকেল বিনে সরানো হয়েছে",
                message_bn=f"আপনার পণ্য '{name_bn}' অ্যাডমিন কর্তৃক রিসাইকেল বিনে সরানো হয়েছে।",
                related_id=product_id,
            )
        if verified_by:
            send_notification(
                user_id=verified_by,
                notif_type="product_deleted_agent",
                title="পণ্য রিসাইকেল বিনে সরানো হয়েছে",
                message=f"'{name_bn}' পণ্যটি অ্যাডমিন কর্তৃক রিসাইকেল বিনে সরানো হয়েছে।",
                title_bn="পণ্য রিসাইকেল বিনে সরানো হয়েছে",
                message_bn=f"'{name_bn}' পণ্যটি অ্যাডমিন কর্তৃক রিসাইকেল বিনে সরানো হয়েছে।",
                related_id=product_id,
            )

        return {
            "message": "পণ্য রিসাইকেল বিনে সরানো হয়েছে (Product moved to recycle bin)",
            "deleted_id": product_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.put("/api/products/{product_id}/restore", tags=["Products"])
def restore_product(product_id: str):
    """রিসাইকেল বিন থেকে পণ্য পুনরুদ্ধার (Restore product from recycle bin)."""
    try:
        sb = get_supabase()

        existing = sb.table("products").select("id,name_bn,farmer_id").eq("id", product_id).not_.is_("deleted_at", "null").execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="রিসাইকেল বিনে পণ্য পাওয়া যায়নি (Product not found in recycle bin)")

        prod = existing.data[0]
        name_bn = prod.get("name_bn", "")
        farmer_id = prod.get("farmer_id")

        sb.table("products").update({"deleted_at": None}).eq("id", product_id).execute()

        if farmer_id:
            send_notification(
                user_id=farmer_id,
                notif_type="product_restored",
                title="পণ্য পুনরুদ্ধার হয়েছে",
                message=f"আপনার পণ্য '{name_bn}' অ্যাডমিন কর্তৃক পুনরুদ্ধার করা হয়েছে।",
                title_bn="পণ্য পুনরুদ্ধার হয়েছে",
                message_bn=f"আপনার পণ্য '{name_bn}' অ্যাডমিন কর্তৃক পুনরুদ্ধার করা হয়েছে।",
                related_id=product_id,
            )

        return {
            "message": "পণ্য পুনরুদ্ধার করা হয়েছে (Product restored successfully)",
            "restored_id": product_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.delete("/api/products/{product_id}/permanent", tags=["Products"])
def permanent_delete_product(product_id: str):
    """পণ্য স্থায়ীভাবে মুছে ফেলুন (Permanently delete product)."""
    try:
        sb = get_supabase()

        existing = sb.table("products").select("id,name_bn,farmer_id,verified_by").eq("id", product_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="পণ্য পাওয়া যায়নি (Product not found)")

        prod = existing.data[0]
        name_bn = prod.get("name_bn", "")
        farmer_id = prod.get("farmer_id")
        verified_by = prod.get("verified_by")

        sb.table("verifications").delete().eq("product_id", product_id).execute()
        sb.table("products").delete().eq("id", product_id).execute()

        if farmer_id:
            send_notification(
                user_id=farmer_id,
                notif_type="product_deleted",
                title="পণ্য স্থায়ীভাবে মুছে ফেলা হয়েছে",
                message=f"আপনার পণ্য '{name_bn}' স্থায়ীভাবে মুছে ফেলা হয়েছে।",
                title_bn="পণ্য স্থায়ীভাবে মুছে ফেলা হয়েছে",
                message_bn=f"আপনার পণ্য '{name_bn}' স্থায়ীভাবে মুছে ফেলা হয়েছে।",
                related_id=product_id,
            )
        if verified_by:
            send_notification(
                user_id=verified_by,
                notif_type="product_deleted_agent",
                title="পণ্য স্থায়ীভাবে মুছে ফেলা হয়েছে",
                message=f"'{name_bn}' পণ্যটি স্থায়ীভাবে মুছে ফেলা হয়েছে।",
                title_bn="পণ্য স্থায়ীভাবে মুছে ফেলা হয়েছে",
                message_bn=f"'{name_bn}' পণ্যটি স্থায়ীভাবে মুছে ফেলা হয়েছে।",
                related_id=product_id,
            )

        return {
            "message": "পণ্য স্থায়ীভাবে মুছে ফেলা হয়েছে (Product permanently deleted)",
            "deleted_id": product_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")

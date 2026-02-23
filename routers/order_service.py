"""
Order Service - গুদাম অর্ডার সেবা
Handles order creation, listing, and status management.
"""

import uuid
import json
import math
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Query

from models.order import OrderCreate, OrderStatusUpdate
from db import get_supabase
from utils.helpers import now_iso
from routers.notification_service import send_notification

router = APIRouter()

RECYCLE_BIN_DAYS = 30


def _auto_purge_orders(sb):
    """Permanently delete orders whose deleted_at is older than 30 days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RECYCLE_BIN_DAYS)).isoformat()
    expired = sb.table("orders").select("id").not_.is_("deleted_at", "null").lt("deleted_at", cutoff).execute()
    for o in expired.data:
        try:
            sb.table("orders").delete().eq("id", o["id"]).execute()
        except Exception:
            pass


@router.post("/api/orders", tags=["Orders"])
def create_order(order_data: OrderCreate):
    """নতুন অর্ডার তৈরি করুন (Create a new order)."""
    try:
        sb = get_supabase()

        # Get the product to find farmer_id, agent_id, and price
        product_result = sb.table("products").select("*").eq("id", order_data.product_id).execute()
        if not product_result.data:
            raise HTTPException(status_code=404, detail="পণ্য পাওয়া যায়নি (Product not found)")

        product = product_result.data[0]
        unit_price = product["price_per_unit"]
        total_price = unit_price * order_data.quantity

        new_order = {
            "id": f"ORD-{uuid.uuid4().hex[:8]}",
            "product_id": order_data.product_id,
            "buyer_id": order_data.buyer_id,
            "farmer_id": product["farmer_id"],
            "agent_id": product.get("verified_by"),
            "quantity": order_data.quantity,
            "unit_price": unit_price,
            "total_price": total_price,
            "status": "placed",
            "delivery_address": json.dumps(order_data.delivery_address, ensure_ascii=False) if order_data.delivery_address else None,
            "notes": order_data.notes,
            "placed_at": now_iso(),
            "created_at": now_iso(),
        }

        result = sb.table("orders").insert(new_order).execute()
        inserted = result.data[0] if result.data else new_order

        # Notify farmer about new order
        if product.get("farmer_id"):
            send_notification(
                user_id=product["farmer_id"],
                notif_type="order_placed",
                title="New Order Received",
                title_bn="নতুন অর্ডার পেয়েছেন",
                message=f"New order for {product.get('name_en', product['id'])}",
                message_bn=f"{product.get('name_bn', '')} পণ্যের জন্য নতুন অর্ডার এসেছে",
                related_id=new_order["id"],
                sms=True,
            )

        # Notify agent about new order
        if product.get("verified_by"):
            send_notification(
                user_id=product["verified_by"],
                notif_type="order_placed",
                title="New Order for Your Listing",
                title_bn="আপনার পণ্যের নতুন অর্ডার",
                message=f"New order placed for product {product.get('name_en', product['id'])}",
                message_bn=f"{product.get('name_bn', '')} পণ্যের জন্য নতুন অর্ডার এসেছে",
                related_id=new_order["id"],
                sms=True,
            )

        return {
            "message": "অর্ডার সফলভাবে দেওয়া হয়েছে (Order placed successfully)",
            "order": inserted,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")


@router.get("/api/orders", tags=["Orders"])
def list_orders(
    farmer_id: str | None = Query(None),
    buyer_id: str | None = Query(None),
    agent_id: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """অর্ডার তালিকা (List orders with filters)."""
    try:
        sb = get_supabase()
        offset = (page - 1) * page_size

        query = sb.table("orders").select("*", count="exact").is_("deleted_at", "null")
        if farmer_id:
            query = query.eq("farmer_id", farmer_id)
        if buyer_id:
            query = query.eq("buyer_id", buyer_id)
        if agent_id:
            query = query.eq("agent_id", agent_id)
        if status:
            query = query.eq("status", status)

        result = query.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()
        total = result.count if result.count is not None else len(result.data)

        # Enrich orders with product and user names
        orders = result.data or []
        if orders:
            product_ids = list({o["product_id"] for o in orders if o.get("product_id")})
            user_ids = list({uid for o in orders for uid in [o.get("farmer_id"), o.get("buyer_id"), o.get("agent_id")] if uid})

            products = {}
            if product_ids:
                p_result = sb.table("products").select("id,name_bn,name_en,unit,images").in_("id", product_ids).execute()
                products = {p["id"]: p for p in (p_result.data or [])}

            users = {}
            if user_ids:
                u_result = sb.table("users").select("id,name").in_("id", user_ids).execute()
                users = {u["id"]: u for u in (u_result.data or [])}

            for o in orders:
                prod = products.get(o.get("product_id"), {})
                o["product_name"] = prod.get("name_en", "")
                o["product_name_bn"] = prod.get("name_bn", "")
                o["product_unit"] = prod.get("unit", "")
                o["product_image"] = (prod.get("images") or [None])[0]
                o["farmer_name"] = users.get(o.get("farmer_id"), {}).get("name", "")
                o["buyer_name"] = users.get(o.get("buyer_id"), {}).get("name", "")
                o["agent_name"] = users.get(o.get("agent_id"), {}).get("name", "")

        return {
            "items": orders,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")


@router.get("/api/orders/deleted/list", tags=["Orders"])
def list_deleted_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """রিসাইকেল বিনের অর্ডার তালিকা (List deleted orders in recycle bin)."""
    try:
        sb = get_supabase()
        offset = (page - 1) * page_size

        _auto_purge_orders(sb)

        query = sb.table("orders").select("*", count="exact").not_.is_("deleted_at", "null").order("deleted_at", desc=True)
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
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")


@router.get("/api/orders/{order_id}", tags=["Orders"])
def get_order(order_id: str):
    """একটি অর্ডারের বিবরণ (Get order details)."""
    try:
        sb = get_supabase()
        result = sb.table("orders").select("*").eq("id", order_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="অর্ডার পাওয়া যায়নি (Order not found)")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")


@router.put("/api/orders/{order_id}/status", tags=["Orders"])
def update_order_status(order_id: str, update: OrderStatusUpdate):
    """অর্ডারের অবস্থা আপডেট করুন (Update order status)."""
    try:
        sb = get_supabase()

        existing = sb.table("orders").select("*").eq("id", order_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="অর্ডার পাওয়া যায়নি (Order not found)")

        update_data = {"status": update.status}

        # Set timestamp fields based on status
        if update.status == "confirmed":
            update_data["confirmed_at"] = now_iso()
        elif update.status == "shipped":
            update_data["shipped_at"] = now_iso()
        elif update.status == "delivered":
            update_data["delivered_at"] = now_iso()

        if update.notes:
            update_data["notes"] = update.notes

        result = sb.table("orders").update(update_data).eq("id", order_id).execute()
        updated = result.data[0] if result.data else existing.data[0]

        order = existing.data[0]
        status_labels = {
            "confirmed": "নিশ্চিত হয়েছে",
            "shipped": "পাঠানো হয়েছে",
            "delivered": "ডেলিভারি হয়েছে",
            "completed": "সম্পন্ন হয়েছে",
            "canceled": "বাতিল হয়েছে",
        }
        status_bn = status_labels.get(update.status, update.status)

        # Notify buyer on all status changes
        if order.get("buyer_id"):
            sms_for_buyer = update.status in ("delivered", "completed")
            send_notification(
                user_id=order["buyer_id"],
                notif_type="order_status",
                title=f"Order {update.status}",
                title_bn=f"অর্ডার {status_bn}",
                message=f"Your order {order_id} has been {update.status}",
                message_bn=f"আপনার অর্ডার {order_id} {status_bn}",
                related_id=order_id,
                sms=sms_for_buyer,
            )

        return {
            "message": "অর্ডারের অবস্থা আপডেট হয়েছে (Order status updated)",
            "order": updated,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")


# ─── Soft Delete (Recycle Bin) ────────────────────────────────────────────────


@router.delete("/api/orders/{order_id}", tags=["Orders"])
def delete_order(order_id: str):
    """অর্ডার রিসাইকেল বিনে পাঠান (Soft delete - move to recycle bin)."""
    try:
        sb = get_supabase()

        existing = sb.table("orders").select("id").eq("id", order_id).is_("deleted_at", "null").execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="অর্ডার পাওয়া যায়নি (Order not found)")

        sb.table("orders").update({"deleted_at": now_iso()}).eq("id", order_id).execute()

        return {
            "message": "অর্ডার রিসাইকেল বিনে সরানো হয়েছে (Order moved to recycle bin)",
            "deleted_id": order_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")


@router.put("/api/orders/{order_id}/restore", tags=["Orders"])
def restore_order(order_id: str):
    """রিসাইকেল বিন থেকে অর্ডার পুনরুদ্ধার (Restore order from recycle bin)."""
    try:
        sb = get_supabase()

        existing = sb.table("orders").select("id").eq("id", order_id).not_.is_("deleted_at", "null").execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="রিসাইকেল বিনে অর্ডার পাওয়া যায়নি (Order not found in recycle bin)")

        sb.table("orders").update({"deleted_at": None}).eq("id", order_id).execute()

        return {
            "message": "অর্ডার পুনরুদ্ধার করা হয়েছে (Order restored successfully)",
            "restored_id": order_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")


@router.delete("/api/orders/{order_id}/permanent", tags=["Orders"])
def permanent_delete_order(order_id: str):
    """অর্ডার স্থায়ীভাবে মুছে ফেলুন (Permanently delete order)."""
    try:
        sb = get_supabase()

        existing = sb.table("orders").select("id").eq("id", order_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="অর্ডার পাওয়া যায়নি (Order not found)")

        sb.table("orders").delete().eq("id", order_id).execute()

        return {
            "message": "অর্ডার স্থায়ীভাবে মুছে ফেলা হয়েছে (Order permanently deleted)",
            "deleted_id": order_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")

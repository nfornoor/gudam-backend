"""
Payment Service - গুদাম পেমেন্ট সেবা
Handles platform settings, dummy bKash payment, fee calculation, and disbursement.

Tables needed (run in Supabase SQL editor):
  CREATE TABLE IF NOT EXISTS platform_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
  );
  CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    payer_id TEXT,
    payee_id TEXT,
    amount REAL,
    commission_amount REAL,
    commission_percent REAL,
    purpose TEXT,
    reference_id TEXT,
    payer_phone TEXT,
    status TEXT DEFAULT 'pending',
    payment_method TEXT DEFAULT 'bkash_dummy',
    bkash_ref TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
  );
"""

import uuid
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from db import get_supabase
from utils.helpers import now_iso

router = APIRouter()

# ─── Defaults (used when DB table doesn't exist yet) ──────────────────────────

DEFAULT_SETTINGS = {
    "platform_fee_percent": 2.5,
    "success_commission_percent": 5.0,
    "listing_fee_taka": 10.0,
    "delivery_charge_taka": 50.0,
}


def get_settings_dict(sb) -> dict:
    """Fetch platform settings from DB; fall back to defaults if table missing."""
    try:
        result = sb.table("platform_settings").select("*").execute()
        if result.data:
            merged = DEFAULT_SETTINGS.copy()
            merged.update({row["key"]: float(row["value"]) for row in result.data})
            return merged
    except Exception:
        pass
    return DEFAULT_SETTINGS.copy()


# ─── Admin Settings ────────────────────────────────────────────────────────────

@router.get("/api/admin/settings", tags=["Admin"])
def get_platform_settings():
    """প্ল্যাটফর্ম সেটিংস দেখুন (Get platform settings)."""
    try:
        sb = get_supabase()
        settings = get_settings_dict(sb)
        return {"settings": settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SettingsUpdate(BaseModel):
    platform_fee_percent: Optional[float] = None
    success_commission_percent: Optional[float] = None
    listing_fee_taka: Optional[float] = None
    delivery_charge_taka: Optional[float] = None


@router.put("/api/admin/settings", tags=["Admin"])
def update_platform_settings(data: SettingsUpdate):
    """প্ল্যাটফর্ম সেটিংস আপডেট করুন (Update platform settings)."""
    try:
        sb = get_supabase()
        updates = data.model_dump(exclude_none=True)
        saved = {}
        for key, value in updates.items():
            try:
                sb.table("platform_settings").upsert(
                    {"key": key, "value": str(value), "updated_at": now_iso()},
                    on_conflict="key"
                ).execute()
                saved[key] = value
            except Exception:
                pass  # Table may not exist yet; values still returned
        return {
            "message": "সেটিংস আপডেট হয়েছে (Settings updated)",
            "saved": saved,
            "settings": get_settings_dict(sb),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Fee Estimation ────────────────────────────────────────────────────────────

@router.get("/api/payments/fee-estimate", tags=["Payments"])
def fee_estimate(
    product_total: float = Query(..., description="Product subtotal in BDT"),
    include_delivery: bool = Query(True),
):
    """চেকআউট ফি হিসাব করুন (Calculate checkout fee breakdown)."""
    try:
        sb = get_supabase()
        settings = get_settings_dict(sb)
        platform_fee = round(product_total * settings["platform_fee_percent"] / 100, 2)
        delivery_charge = round(settings["delivery_charge_taka"], 2) if include_delivery else 0.0
        grand_total = round(product_total + platform_fee + delivery_charge, 2)
        return {
            "product_total": product_total,
            "platform_fee_percent": settings["platform_fee_percent"],
            "platform_fee": platform_fee,
            "delivery_charge": delivery_charge,
            "grand_total": grand_total,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/payments/listing-fee", tags=["Payments"])
def listing_fee():
    """তালিকাভুক্তির ফি (Get listing fee)."""
    try:
        sb = get_supabase()
        settings = get_settings_dict(sb)
        return {
            "listing_fee_taka": settings["listing_fee_taka"],
            "message": "পণ্য তালিকাভুক্তির জন্য একটি ফি প্রযোজ্য",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Dummy bKash Payment ───────────────────────────────────────────────────────

class PaymentInitiate(BaseModel):
    amount: float
    payer_id: str
    payer_phone: str
    purpose: str          # "listing_fee" | "order_payment"
    reference_id: str     # product_id or temp order ref


class PaymentConfirm(BaseModel):
    transaction_id: str
    otp: str              # Any 6-digit number accepted in demo mode


@router.post("/api/payments/initiate", tags=["Payments"])
def initiate_payment(data: PaymentInitiate):
    """পেমেন্ট শুরু করুন (Initiate dummy bKash payment)."""
    try:
        sb = get_supabase()
        txn_id = f"TXN-{uuid.uuid4().hex[:10].upper()}"
        transaction = {
            "id": txn_id,
            "payer_id": data.payer_id,
            "amount": data.amount,
            "purpose": data.purpose,
            "reference_id": data.reference_id,
            "payer_phone": data.payer_phone,
            "status": "pending",
            "payment_method": "bkash_dummy",
            "created_at": now_iso(),
        }
        try:
            sb.table("transactions").insert(transaction).execute()
        except Exception:
            pass  # Table may not exist; txn_id still returned for flow
        return {
            "transaction_id": txn_id,
            "amount": data.amount,
            "bkash_number": "01700000000",
            "message": f"বিকাশ নম্বর 01700000000-এ ৳{data.amount:.0f} পাঠান, তারপর OTP দিয়ে নিশ্চিত করুন",
            "otp_hint": "যেকোনো ৬ সংখ্যার OTP দিন (ডেমো মোড)",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/payments/confirm", tags=["Payments"])
def confirm_payment(data: PaymentConfirm):
    """পেমেন্ট নিশ্চিত করুন (Confirm dummy bKash payment with OTP)."""
    try:
        if not data.otp.isdigit() or len(data.otp) != 6:
            raise HTTPException(status_code=400, detail="ভুল OTP। ৬ সংখ্যার OTP দিন।")

        sb = get_supabase()
        bkash_ref = f"BK{uuid.uuid4().hex[:8].upper()}"
        try:
            sb.table("transactions").update({
                "status": "completed",
                "completed_at": now_iso(),
                "bkash_ref": bkash_ref,
            }).eq("id", data.transaction_id).execute()
        except Exception:
            pass
        return {
            "success": True,
            "transaction_id": data.transaction_id,
            "bkash_ref": bkash_ref,
            "message": "পেমেন্ট সফল হয়েছে ✓ (ডেমো মোড)",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Escrow Disbursement ───────────────────────────────────────────────────────

@router.post("/api/payments/disburse/{order_id}", tags=["Payments"])
def disburse_order(order_id: str):
    """ডেলিভারির পর কৃষককে অর্থ ছাড় করুন (Disburse payment to farmer after delivery)."""
    try:
        sb = get_supabase()

        order_result = sb.table("orders").select("*").eq("id", order_id).execute()
        if not order_result.data:
            raise HTTPException(status_code=404, detail="অর্ডার পাওয়া যায়নি")

        order = order_result.data[0]

        # Parse notes to check if already disbursed
        notes_meta = {}
        try:
            notes_meta = json_parse_notes(order.get("notes") or "{}")
        except Exception:
            pass

        if notes_meta.get("payment_status") == "disbursed":
            raise HTTPException(status_code=400, detail="ইতিমধ্যে অর্থ ছাড় হয়েছে")

        settings = get_settings_dict(sb)
        product_subtotal = notes_meta.get("product_subtotal") or order.get("total_price", 0)
        commission = round(product_subtotal * settings["success_commission_percent"] / 100, 2)
        net_payout = round(product_subtotal - commission, 2)

        disbursement_id = f"DSB-{uuid.uuid4().hex[:8]}"
        disbursement = {
            "id": disbursement_id,
            "payer_id": "platform",
            "payee_id": order.get("farmer_id"),
            "amount": net_payout,
            "commission_amount": commission,
            "commission_percent": settings["success_commission_percent"],
            "purpose": "disbursement",
            "reference_id": order_id,
            "status": "completed",
            "payment_method": "bkash_dummy",
            "created_at": now_iso(),
            "completed_at": now_iso(),
        }
        try:
            sb.table("transactions").insert(disbursement).execute()
        except Exception:
            pass

        # Update notes with disbursement status
        try:
            notes_meta["payment_status"] = "disbursed"
            notes_meta["disbursement_id"] = disbursement_id
            notes_meta["net_payout"] = net_payout
            notes_meta["commission_amount"] = commission
            sb.table("orders").update({
                "notes": json_dump_notes(notes_meta),
            }).eq("id", order_id).execute()
        except Exception:
            pass

        return {
            "success": True,
            "order_id": order_id,
            "product_subtotal": product_subtotal,
            "commission_percent": settings["success_commission_percent"],
            "commission_amount": commission,
            "net_payout": net_payout,
            "farmer_id": order.get("farmer_id"),
            "message": f"কৃষককে ৳{net_payout:.0f} প্রদান করা হয়েছে (ডেমো)",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Transaction List ──────────────────────────────────────────────────────────

@router.get("/api/payments/transactions", tags=["Payments"])
def list_transactions(
    user_id: str | None = Query(None),
    purpose: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """লেনদেনের তালিকা (List transactions)."""
    try:
        sb = get_supabase()
        offset = (page - 1) * page_size
        try:
            query = sb.table("transactions").select("*", count="exact")
            if user_id:
                query = query.eq("payer_id", user_id)
            if purpose:
                query = query.eq("purpose", purpose)
            result = query.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()
            total = result.count if result.count is not None else len(result.data)
            return {
                "items": result.data or [],
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        except Exception:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Helpers ──────────────────────────────────────────────────────────────────

import json


def json_parse_notes(notes_str: str) -> dict:
    """Try to parse notes as JSON dict; return {} on failure."""
    try:
        val = json.loads(notes_str)
        return val if isinstance(val, dict) else {}
    except Exception:
        return {}


def json_dump_notes(meta: dict) -> str:
    return json.dumps(meta, ensure_ascii=False)

"""
Market Service - গুদাম বাজার বিশ্লেষণ সেবা
Aggregated price benchmarking for farmers vs. market averages.
"""

import math
from fastapi import APIRouter, HTTPException, Query
from db import get_supabase

router = APIRouter()


@router.get("/api/market/price-benchmark", tags=["Market"])
def price_benchmark(farmer_id: str = Query(..., description="Farmer's user ID")):
    """
    কৃষকের গড় অর্জিত মূল্য বনাম বাজারের গড় মূল্য (FR-id-14).
    Returns per-category comparison: farmer avg vs market avg from verified products + completed orders.
    """
    try:
        sb = get_supabase()

        # ── 1. Market averages from all verified/listed products ──────────────
        products_res = sb.table("products").select(
            "category,price_per_unit,unit"
        ).in_("status", ["verified", "completed"]).execute()

        market_by_cat = {}  # category → list of prices
        for p in (products_res.data or []):
            cat = p.get("category") or "other"
            price = p.get("price_per_unit") or 0
            if price > 0:
                market_by_cat.setdefault(cat, []).append(price)

        # ── 2. Farmer's completed order prices (achieved prices) ──────────────
        # Get all products belonging to this farmer
        farmer_products_res = sb.table("products").select(
            "id,category,name_bn,unit"
        ).eq("farmer_id", farmer_id).execute()

        farmer_product_ids = [p["id"] for p in (farmer_products_res.data or [])]
        product_meta = {p["id"]: p for p in (farmer_products_res.data or [])}

        farmer_orders_by_cat = {}  # category → list of {unit_price, quantity, product_name_bn}
        if farmer_product_ids:
            orders_res = sb.table("orders").select(
                "product_id,unit_price,quantity,total_price"
            ).in_("product_id", farmer_product_ids).in_(
                "status", ["completed", "delivered"]
            ).execute()

            for o in (orders_res.data or []):
                prod = product_meta.get(o["product_id"], {})
                cat = prod.get("category") or "other"
                price = o.get("unit_price") or 0
                if price > 0:
                    farmer_orders_by_cat.setdefault(cat, []).append({
                        "price": price,
                        "quantity": o.get("quantity", 0),
                        "name_bn": prod.get("name_bn", ""),
                    })

        # ── 3. Also include farmer's current listed product prices ─────────────
        for p in (farmer_products_res.data or []):
            cat = p.get("category") or "other"
            # Get the current listing price
            prod_detail = sb.table("products").select(
                "price_per_unit,status"
            ).eq("id", p["id"]).execute()
            if prod_detail.data:
                price = prod_detail.data[0].get("price_per_unit") or 0
                if price > 0:
                    farmer_orders_by_cat.setdefault(cat, [])
                    # Only add listed price if no completed orders for this category
                    # (listed price = asking price, not achieved)

        # ── 4. Category name map ──────────────────────────────────────────────
        cat_names = {}
        try:
            cats_res = sb.table("categories").select("id,name_bn,name_en,icon").execute()
            for c in (cats_res.data or []):
                cat_names[c["id"]] = {
                    "name_bn": c.get("name_bn") or c.get("name_en", c["id"]),
                    "icon": c.get("icon", ""),
                }
        except Exception:
            pass

        # ── 5. Build response ─────────────────────────────────────────────────
        all_cats = set(list(market_by_cat.keys()) + list(farmer_orders_by_cat.keys()))
        # Filter to only categories the farmer has activity in
        farmer_cats = set(farmer_orders_by_cat.keys())

        result = []
        for cat in sorted(farmer_cats):
            market_prices = market_by_cat.get(cat, [])
            farmer_entries = farmer_orders_by_cat.get(cat, [])

            market_avg = round(sum(market_prices) / len(market_prices), 1) if market_prices else None
            market_min = min(market_prices) if market_prices else None
            market_max = max(market_prices) if market_prices else None

            farmer_prices = [e["price"] for e in farmer_entries]
            farmer_avg = round(sum(farmer_prices) / len(farmer_prices), 1) if farmer_prices else None
            farmer_order_count = len(farmer_entries)

            if farmer_avg and market_avg:
                diff_pct = round((farmer_avg - market_avg) / market_avg * 100, 1)
                if diff_pct > 5:
                    position = "above_market"
                elif diff_pct < -5:
                    position = "below_market"
                else:
                    position = "at_market"
            else:
                diff_pct = None
                position = "no_data"

            cat_info = cat_names.get(cat, {"name_bn": cat, "icon": ""})

            result.append({
                "category": cat,
                "category_name_bn": cat_info["name_bn"],
                "category_icon": cat_info["icon"],
                "farmer_avg_price": farmer_avg,
                "farmer_order_count": farmer_order_count,
                "market_avg_price": market_avg,
                "market_min_price": market_min,
                "market_max_price": market_max,
                "market_listing_count": len(market_prices),
                "diff_percent": diff_pct,
                "position": position,
            })

        # Also include farmer's current listings with no completed orders
        # so they can see market benchmark even before first sale
        for p in (farmer_products_res.data or []):
            cat = p.get("category") or "other"
            if cat not in farmer_cats:
                market_prices = market_by_cat.get(cat, [])
                market_avg = round(sum(market_prices) / len(market_prices), 1) if market_prices else None
                cat_info = cat_names.get(cat, {"name_bn": cat, "icon": ""})
                result.append({
                    "category": cat,
                    "category_name_bn": cat_info["name_bn"],
                    "category_icon": cat_info["icon"],
                    "farmer_avg_price": None,
                    "farmer_order_count": 0,
                    "market_avg_price": market_avg,
                    "market_min_price": min(market_prices) if market_prices else None,
                    "market_max_price": max(market_prices) if market_prices else None,
                    "market_listing_count": len(market_prices),
                    "diff_percent": None,
                    "position": "no_data",
                })

        return {
            "farmer_id": farmer_id,
            "categories": result,
            "total_categories": len(result),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")


@router.get("/api/market/overview", tags=["Market"])
def market_overview():
    """সামগ্রিক বাজার মূল্য সংক্ষেপ (Market-wide price overview by category)."""
    try:
        sb = get_supabase()

        products_res = sb.table("products").select(
            "category,price_per_unit"
        ).in_("status", ["verified", "pending_verification"]).execute()

        by_cat = {}
        for p in (products_res.data or []):
            cat = p.get("category") or "other"
            price = p.get("price_per_unit") or 0
            if price > 0:
                by_cat.setdefault(cat, []).append(price)

        result = []
        for cat, prices in by_cat.items():
            result.append({
                "category": cat,
                "avg_price": round(sum(prices) / len(prices), 1),
                "min_price": min(prices),
                "max_price": max(prices),
                "listing_count": len(prices),
            })

        result.sort(key=lambda x: x["listing_count"], reverse=True)
        return {"categories": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি: {str(e)}")

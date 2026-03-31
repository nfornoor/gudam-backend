"""
Agent Matching Service - গুদাম এজেন্ট ম্যাচিং সেবা
Matches farmers with nearby agents based on proximity, capacity, and reputation.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from db import get_supabase
from utils.helpers import haversine_km
from routers.reputation_service import _compute_reputation
from routers.notification_service import send_notification

router = APIRouter()


class MatchAgentRequest(BaseModel):
    farmer_lat: float
    farmer_lon: float
    product_category: Optional[str] = None
    quantity_tons: Optional[float] = None
    max_distance_km: float = 100.0


class AutoMatchNotifyRequest(BaseModel):
    farmer_id: str
    farmer_lat: float
    farmer_lon: float
    product_id: str
    product_category: Optional[str] = None
    quantity_tons: Optional[float] = None
    max_distance_km: float = 100.0
    top_n: int = 5


class NearbyAgentResult(BaseModel):
    agent_id: str
    name: str
    gudam_name: str
    distance_km: float
    available_capacity_tons: float
    average_rating: float
    match_score: float
    location: dict


def _extract_agent_details(user: dict) -> dict:
    """Extract agent-specific fields from a users-table row using gudam_details JSONB."""
    gudam = user.get("gudam_details") or {}
    loc = user.get("location") or {}
    return {
        "id": user["id"],
        "name": user.get("name", ""),
        "phone": user.get("phone", ""),
        "gudam_name": gudam.get("gudam_name", ""),
        "location": loc,
        "is_active": gudam.get("is_active", False),
        "storage_capacity_tons": gudam.get("storage_capacity_tons", 0),
        "current_stored_tons": gudam.get("current_stored_tons", 0),
        "available_capacity_tons": gudam.get("available_capacity_tons", 0),
        "average_rating": gudam.get("average_rating", 3.0),
        "storage_type": gudam.get("storage_type", ""),
        "commission_rate_percent": gudam.get("commission_rate_percent", 0),
        "resources": gudam.get("resources", {}),
        "operating_hours": gudam.get("operating_hours", ""),
        "service_areas": gudam.get("service_areas", []),
    }


def _fetch_agents() -> list[dict]:
    """Fetch all agent users from Supabase and extract their details."""
    sb = get_supabase()
    result = sb.table("users").select("*").eq("role", "agent").execute()
    return [_extract_agent_details(u) for u in result.data]


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/api/match-agent", tags=["Agent Matching"])
def match_agent(request: MatchAgentRequest):
    """
    কৃষকের জন্য সেরা এজেন্ট খুঁজুন (Find the best agent for a farmer).
    Scores agents based on proximity (40%), available capacity (30%), and reputation (30%).
    """
    try:
        agents = _fetch_agents()

        candidates = []
        for agent in agents:
            if not agent.get("is_active", False):
                continue

            loc = agent.get("location", {})
            agent_lat = loc.get("lat")
            agent_lon = loc.get("lon")
            if agent_lat is None or agent_lon is None:
                continue

            distance = haversine_km(request.farmer_lat, request.farmer_lon, agent_lat, agent_lon)
            if distance > request.max_distance_km:
                continue

            available = agent.get("available_capacity_tons", 0)
            if request.quantity_tons and available < request.quantity_tons:
                continue

            # Scoring: proximity (40%), capacity (30%), rating (30%)
            max_dist = request.max_distance_km
            proximity_score = max(0, (max_dist - distance) / max_dist) * 40

            all_capacities = [a.get("available_capacity_tons", 1) for a in agents]
            max_capacity = max(all_capacities) if all_capacities else 1
            capacity_score = (available / max_capacity) * 30 if max_capacity > 0 else 0

            # Use real reputation score from ratings table
            reputation = _compute_reputation(agent["id"])
            rating = reputation["average_score"] if reputation["average_score"] > 0 else agent.get("average_rating", 3.0)
            rating_score = (rating / 5.0) * 30

            total_score = round(proximity_score + capacity_score + rating_score, 2)

            candidates.append({
                "agent_id": agent["id"],
                "name": agent["name"],
                "gudam_name": agent["gudam_name"],
                "distance_km": round(distance, 2),
                "available_capacity_tons": available,
                "average_rating": rating,
                "match_score": total_score,
                "location": agent["location"],
                "storage_type": agent.get("storage_type", ""),
                "commission_rate_percent": agent.get("commission_rate_percent", 0),
                "phone": agent.get("phone", ""),
            })

        candidates.sort(key=lambda x: x["match_score"], reverse=True)

        if not candidates:
            raise HTTPException(
                status_code=404,
                detail="কাছাকাছি কোনো উপযুক্ত এজেন্ট পাওয়া যায়নি (No suitable agents found nearby)",
            )

        return {
            "message": "এজেন্ট ম্যাচিং সম্পন্ন (Agent matching complete)",
            "best_match": candidates[0],
            "all_matches": candidates,
            "total_matches": len(candidates),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/agents/nearby", tags=["Agent Matching"])
def find_nearby_agents(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    max_distance_km: float = Query(50.0, description="Maximum distance in km"),
    min_capacity_tons: float | None = Query(None, description="Minimum available capacity in tons"),
):
    """কাছাকাছি এজেন্ট খুঁজুন (Find nearby agents)."""
    try:
        agents = _fetch_agents()

        results = []
        for agent in agents:
            if not agent.get("is_active", False):
                continue

            loc = agent.get("location", {})
            agent_lat = loc.get("lat")
            agent_lon = loc.get("lon")
            if agent_lat is None or agent_lon is None:
                continue

            distance = haversine_km(lat, lon, agent_lat, agent_lon)
            if distance > max_distance_km:
                continue

            available = agent.get("available_capacity_tons", 0)
            if min_capacity_tons and available < min_capacity_tons:
                continue

            results.append({
                "agent_id": agent["id"],
                "name": agent["name"],
                "gudam_name": agent["gudam_name"],
                "distance_km": round(distance, 2),
                "available_capacity_tons": available,
                "storage_type": agent.get("storage_type", ""),
                "average_rating": agent.get("average_rating", 0),
                "phone": agent.get("phone", ""),
                "location": agent["location"],
                "resources": agent.get("resources", {}),
                "operating_hours": agent.get("operating_hours", ""),
                "commission_rate_percent": agent.get("commission_rate_percent", 0),
            })

        results.sort(key=lambda x: x["distance_km"])

        return {
            "agents": results,
            "total": len(results),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/agents/top-ranked", tags=["Agent Matching"])
def get_top_ranked_agents(limit: int = Query(10, ge=1, le=100, description="Number of top agents to return")):
    """
    শীর্ষ রেটিংয়ের এজেন্টদের তালিকা (Get top-ranked agents by reputation score).
    """
    try:
        agents = _fetch_agents()

        ranked = []
        for agent in agents:
            if not agent.get("is_active", False):
                continue

            reputation = _compute_reputation(agent["id"])
            ranked.append({
                "agent_id": agent["id"],
                "name": agent["name"],
                "gudam_name": agent["gudam_name"],
                "average_rating": reputation["average_score"],
                "badge": reputation["badge"],
                "badge_bn": reputation["badge_bn"],
                "total_ratings": reputation["total_ratings"],
                "location": agent["location"],
                "phone": agent["phone"],
                "storage_type": agent.get("storage_type", ""),
                "available_capacity_tons": agent.get("available_capacity_tons", 0),
            })

        ranked.sort(key=lambda x: x["average_rating"], reverse=True)
        return ranked[:limit]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.get("/api/agents/{agent_id}/capacity", tags=["Agent Matching"])
def get_agent_capacity(agent_id: str):
    """এজেন্টের ধারণক্ষমতার তথ্য (Get agent capacity info)."""
    try:
        sb = get_supabase()

        result = sb.table("users").select("*").eq("id", agent_id).eq("role", "agent").execute()
        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="এজেন্ট পাওয়া যায়নি (Agent not found)",
            )

        agent = _extract_agent_details(result.data[0])

        total = agent.get("storage_capacity_tons", 0)
        current = agent.get("current_stored_tons", 0)
        available = agent.get("available_capacity_tons", 0)
        utilization = round((current / total) * 100, 1) if total > 0 else 0

        return {
            "agent_id": agent["id"],
            "gudam_name": agent["gudam_name"],
            "storage_type": agent.get("storage_type", ""),
            "total_capacity_tons": total,
            "current_stored_tons": current,
            "available_capacity_tons": available,
            "utilization_percent": utilization,
            "resources": agent.get("resources", {}),
            "operating_hours": agent.get("operating_hours", ""),
            "service_areas": agent.get("service_areas", []),
            "is_accepting_new": available > 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")


@router.post("/api/match-agent/notify", tags=["Agent Matching"])
def auto_match_and_notify(request: AutoMatchNotifyRequest):
    """
    কৃষকের GPS অবস্থান থেকে নিকটতম এজেন্টদের স্বয়ংক্রিয় বিজ্ঞপ্তি পাঠান
    (Auto-match nearest agents and send in-app notifications).
    """
    try:
        sb = get_supabase()

        # Update farmer's location in DB and fetch farmer name
        farmer_result = sb.table("users").select("location,name").eq("id", request.farmer_id).execute()
        farmer_name = "কৃষক"
        if farmer_result.data:
            farmer_name = farmer_result.data[0].get("name", "কৃষক")
            existing_loc = farmer_result.data[0].get("location") or {}
            updated_loc = {**existing_loc, "lat": request.farmer_lat, "lon": request.farmer_lon}
            sb.table("users").update({"location": updated_loc}).eq("id", request.farmer_id).execute()

        agents = _fetch_agents()

        candidates = []
        for agent in agents:
            if not agent.get("is_active", False):
                continue

            loc = agent.get("location", {})
            agent_lat = loc.get("lat")
            agent_lon = loc.get("lon")
            if agent_lat is None or agent_lon is None:
                continue

            distance = haversine_km(request.farmer_lat, request.farmer_lon, agent_lat, agent_lon)
            if distance > request.max_distance_km:
                continue

            available = agent.get("available_capacity_tons", 0)
            if request.quantity_tons and available < request.quantity_tons:
                continue

            # Scoring: proximity (40%), capacity (30%), rating (30%)
            max_dist = request.max_distance_km
            proximity_score = max(0, (max_dist - distance) / max_dist) * 40

            all_capacities = [a.get("available_capacity_tons", 1) for a in agents]
            max_capacity = max(all_capacities) if all_capacities else 1
            capacity_score = (available / max_capacity) * 30 if max_capacity > 0 else 0

            reputation = _compute_reputation(agent["id"])
            rating = reputation["average_score"] if reputation["average_score"] > 0 else agent.get("average_rating", 3.0)
            rating_score = (rating / 5.0) * 30

            total_score = round(proximity_score + capacity_score + rating_score, 2)

            candidates.append({
                "agent_id": agent["id"],
                "name": agent["name"],
                "gudam_name": agent["gudam_name"],
                "distance_km": round(distance, 2),
                "available_capacity_tons": available,
                "average_rating": rating,
                "match_score": total_score,
                "location": agent["location"],
                "phone": agent.get("phone", ""),
            })

        candidates.sort(key=lambda x: x["match_score"], reverse=True)
        top_matches = candidates[: request.top_n]

        # Send in-app notification to each top agent
        notified = []
        for match in top_matches:
            dist_str = f"{match['distance_km']:.1f}"
            notif = send_notification(
                user_id=match["agent_id"],
                notif_type="agent_match_request",
                title="New Product Collection Request",
                message=f"Farmer {farmer_name} has requested product collection from you. Distance: {dist_str} km",
                title_bn="নতুন পণ্য সংগ্রহের অনুরোধ",
                message_bn=f"কৃষক {farmer_name} আপনার কাছে পণ্য সংগ্রহের অনুরোধ করেছেন। দূরত্ব: {dist_str} কিমি",
                related_id=request.product_id,
                sms=False,
            )
            if notif:
                notified.append({**match, "notification_id": notif.get("id")})

        return {
            "message": f"{len(notified)} জন এজেন্টকে বিজ্ঞপ্তি পাঠানো হয়েছে",
            "total_notified": len(notified),
            "notified_agents": notified,
            "matches": candidates,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"সার্ভার ত্রুটি (Server error): {str(e)}")

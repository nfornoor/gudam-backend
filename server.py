"""
গুদাম - কৃষি পণ্যের বাজার (Gudam - Agricultural Marketplace)
Main FastAPI application that wires together all microservice routers.

Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Services: User, Product, Verification, Agent, Reputation, Order, OTP, Notification
"""

import sys
import pathlib

# Ensure the backend directory is on sys.path so that imports work when
# running from any working directory.
_backend_dir = str(pathlib.Path(__file__).parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gudam")


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if response.status_code >= 400:
            logger.warning(
                f"[{response.status_code}] {request.method} {request.url}"
            )
        return response

from config import APP_NAME, APP_VERSION, APP_DESCRIPTION

from routers.user_service import router as user_router
from routers.product_service import router as product_router
from routers.verification_service import router as verification_router
from routers.agent_matching import router as agent_router
from routers.reputation_service import router as reputation_router
from routers.order_service import router as order_router
from routers.otp_service import router as otp_router
from routers.chat_service import router as chat_router
from routers.notification_service import router as notification_router

# ─── Application ──────────────────────────────────────────────────────────────

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── Middleware ───────────────────────────────────────────────────────────────

app.add_middleware(RequestLoggerMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Include Routers ─────────────────────────────────────────────────────────

app.include_router(user_router, tags=["User Service"])
app.include_router(product_router, tags=["Product Catalog Service"])
app.include_router(verification_router, tags=["Verification Service"])
app.include_router(agent_router, tags=["Agent Matching Service"])
app.include_router(reputation_router, tags=["Reputation Service"])
app.include_router(order_router, tags=["Order Service"])
app.include_router(otp_router, tags=["OTP Service"])
app.include_router(chat_router, tags=["Chat Service"])
app.include_router(notification_router, tags=["Notification Service"])

# ─── Root & Health ────────────────────────────────────────────────────────────


@app.get("/", tags=["Health"])
def root():
    return {
        "name": APP_NAME,
        "name_bn": "গুদাম - কৃষি পণ্যের বাজার",
        "version": APP_VERSION,
        "status": "running",
        "message": "স্বাগতম গুদাম প্ল্যাটফর্মে! (Welcome to Gudam Platform!)",
        "docs": "/docs",
        "services": [
            {"name": "User Service", "name_bn": "ব্যবহারকারী সেবা", "prefix": "/api/auth, /api/users"},
            {"name": "Product Catalog", "name_bn": "পণ্য ক্যাটালগ", "prefix": "/api/products"},
            {"name": "Verification", "name_bn": "পণ্য যাচাই", "prefix": "/api/verifications"},
            {"name": "Agent Matching", "name_bn": "এজেন্ট ম্যাচিং", "prefix": "/api/match-agent, /api/agents"},
            {"name": "Reputation", "name_bn": "সুনাম সেবা", "prefix": "/api/ratings"},
        ],
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "version": APP_VERSION}


# ─── Run directly ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

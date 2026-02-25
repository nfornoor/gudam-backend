# গুদাম Backend - Gudam Agricultural Marketplace API

> FastAPI backend for the Gudam agricultural marketplace platform - connecting farmers, agents, and buyers across Bangladesh.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com)
[![Deployed on Vercel](https://img.shields.io/badge/Deployed%20on-Vercel-000000?logo=vercel&logoColor=white)](https://vercel.com)

---

## Live API

| Endpoint | URL |
|---|---|
| Base URL | https://gudam-backend-gifd.vercel.app |
| Swagger UI | https://gudam-backend-gifd.vercel.app/docs |
| ReDoc | https://gudam-backend-gifd.vercel.app/redoc |
| Health Check | https://gudam-backend-gifd.vercel.app/health |

---

## Overview

This is the backend API for **Gudam**, a digital agricultural marketplace. It is built as a **service-organized monolith** - all 9 services run in a single FastAPI application, each in its own router module.

### Services

| Service | Router File | Base Path |
|---|---|---|
| User & Auth | user_service.py | /api/auth, /api/users |
| Product Catalog | product_service.py | /api/products, /api/categories |
| Verification | verification_service.py | /api/verifications |
| Agent Matching | agent_matching.py | /api/match-agent, /api/agents |
| Order Management | order_service.py | /api/orders |
| OTP & Phone Verify | otp_service.py | /api/otp |
| Notifications | notification_service.py | /api/notifications |
| Ratings & Reputation | reputation_service.py | /api/ratings |
| Chat | chat_service.py | /api/messages, /api/conversations |

---

## Tech Stack

| Package | Purpose |
|---|---|
| FastAPI | REST API framework |
| Uvicorn | ASGI server |
| Pydantic v2 | Request/response validation & schemas |
| Supabase Python | PostgreSQL database client |
| bcrypt | Password hashing |
| PyJWT | JWT token generation & validation |
| python-dotenv | Environment variable management |
| sms.net.bd API | OTP & SMS notifications |

---

## Project Structure

```
backend/
├── server.py                   # FastAPI app entry point - wires all routers
├── config.py                   # App config, environment variables
├── db.py                       # Supabase client singleton
├── create_tables.py            # Database schema creation & seeding
├── setup_supabase.py           # Demo data seed script
│
├── models/                     # Pydantic schemas (request/response)
│   ├── user.py
│   ├── product.py
│   ├── verification.py
│   ├── order.py
│   ├── rating.py
│   ├── notification.py
│   └── otp.py
│
├── routers/                    # Service routers (one per domain)
│   ├── user_service.py         # Auth + user management
│   ├── product_service.py      # Product CRUD + categories
│   ├── verification_service.py # Product verification workflow
│   ├── agent_matching.py       # GPS-based agent discovery
│   ├── order_service.py        # Order lifecycle
│   ├── otp_service.py          # OTP send & verify
│   ├── notification_service.py # In-app & SMS notifications
│   ├── reputation_service.py   # Ratings & reputation scores
│   └── chat_service.py         # Encrypted messaging
│
└── utils/
    └── helpers.py              # Shared utility functions
```

---

## Getting Started

### Prerequisites
- Python 3.11+
- Supabase project (with tables created)
- sms.net.bd API key (optional, for OTP/SMS)

### Installation

```bash
git clone https://github.com/nfornoor/gudam-backend.git
cd gudam-backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

### Environment Setup

Create a `.env` file in the root of the backend directory:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SECRET_KEY=your-jwt-secret-key
SMS_API_KEY=your-sms-net-bd-api-key
DEBUG=true
```

### Database Setup

Run the table creation script once to set up your Supabase schema:

```bash
python create_tables.py
```

### Run the Server

```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

API will be live at: http://localhost:8000
Swagger docs at: http://localhost:8000/docs

---

## API Overview

### Auth (/api/auth)
| Method | Path | Description |
|---|---|---|
| POST | /api/auth/register | Register new user |
| POST | /api/auth/login | Login with phone + password |
| PUT | /api/auth/change-password | Change password |
| POST | /api/auth/forgot-password | Request OTP for password reset |
| POST | /api/auth/reset-password | Reset password using OTP |

### Users (/api/users)
| Method | Path | Description |
|---|---|---|
| GET | /api/users/{id} | Get user profile |
| PUT | /api/users/{id} | Update profile |
| GET | /api/users | List all users (paginated) |
| GET | /api/farmers | List all farmers |
| GET | /api/agents | List all agents |
| GET | /api/buyers | List all buyers |
| PUT | /api/users/{id}/verify | Admin: verify user |
| PUT | /api/users/{id}/unverify | Admin: revoke verification |
| DELETE | /api/users/{id} | Soft delete (30-day recycle bin) |
| PUT | /api/users/{id}/restore | Restore from recycle bin |
| DELETE | /api/users/{id}/permanent | Hard delete (cascades all records) |

### Products (/api/products)
| Method | Path | Description |
|---|---|---|
| POST | /api/products | Create new product listing |
| GET | /api/products | List products (filter/search/paginate) |
| GET | /api/products/{id} | Get product details |
| PUT | /api/products/{id} | Update product |
| DELETE | /api/products/{id} | Soft delete |
| PUT | /api/products/{id}/restore | Restore from recycle bin |
| DELETE | /api/products/{id}/permanent | Hard delete |
| GET | /api/products/farmer/{id} | Get farmer's products |
| GET | /api/products/deleted/list | List deleted products |
| GET | /api/categories | Get all product categories |

### Verifications (/api/verifications)
| Method | Path | Description |
|---|---|---|
| POST | /api/verifications/listings/{id}/verify | Start verification (assign agent) |
| GET | /api/verifications | List all verifications |
| GET | /api/verifications/{id} | Get verification details |
| PUT | /api/verifications/{id}/status | Update verification status |
| GET | /api/verifications/agent/{id} | Get agent's verifications |

### Agent Matching (/api/match-agent, /api/agents)
| Method | Path | Description |
|---|---|---|
| POST | /api/match-agent | Find best-matched agents (GPS + score) |
| POST | /api/match-agent/notify | Auto-match and notify top N agents |
| GET | /api/agents/nearby | Find nearby agents by GPS |
| GET | /api/agents/top-ranked | Get top-rated agents |
| GET | /api/agents/{id}/capacity | Get agent storage capacity |

### Orders (/api/orders)
| Method | Path | Description |
|---|---|---|
| POST | /api/orders | Create order |
| GET | /api/orders | List orders (filter by role/status) |
| GET | /api/orders/{id} | Get order details |
| PUT | /api/orders/{id}/status | Update order status |
| DELETE | /api/orders/{id} | Soft delete |
| PUT | /api/orders/{id}/restore | Restore from recycle bin |
| DELETE | /api/orders/{id}/permanent | Hard delete |

### OTP (/api/otp)
| Method | Path | Description |
|---|---|---|
| POST | /api/otp/send | Send OTP via SMS |
| POST | /api/otp/verify | Verify OTP code |

### Notifications (/api/notifications)
| Method | Path | Description |
|---|---|---|
| GET | /api/notifications/{user_id} | Get user notifications |
| GET | /api/notifications/{user_id}/unread-count | Get unread count |
| PUT | /api/notifications/{id}/read | Mark as read |
| PUT | /api/notifications/{user_id}/read-all | Mark all as read |

### Ratings (/api/ratings)
| Method | Path | Description |
|---|---|---|
| POST | /api/ratings | Submit rating (1-5) |
| GET | /api/users/{id}/reputation | Get reputation score & badge |
| GET | /api/ratings/user/{id} | Get all ratings for a user |
| GET | /api/ratings/product/{id} | Get ratings for a product |
| GET | /api/ratings/check/{order_id}/{user_id} | Check if already rated |

### Chat (/api/messages, /api/conversations)
| Method | Path | Description |
|---|---|---|
| POST | /api/messages | Send encrypted message |
| GET | /api/messages/{conv_id} | Get conversation messages |
| GET | /api/messages/unread/{user_id} | Get total unread count |
| GET | /api/conversations/{user_id} | Get user's conversations |
| POST | /api/conversations/start | Start new conversation |
| GET | /api/conversations/search | Search users to chat with |

---

## Database Schema

```
users            - id, name, phone, role, location, profile_details, is_verified, deleted_at
products         - id, farmer_id, name_bn, category, quality_grade, price_per_unit, status, images, deleted_at
verifications    - id, product_id, agent_id, status, verified_grade, verified_quantity, notes
orders           - id, product_id, buyer_id, farmer_id, agent_id, total_price, status, deleted_at
ratings          - id, to_user_id, from_user_id, order_id, type, rating (1-5)
notifications    - id, user_id, type, title_bn, message_bn, is_read
conversations    - id, participant_1, participant_2, last_message (encrypted)
messages         - id, conversation_id, sender_id, content (encrypted), is_read
```

---

## Authentication

- Method: JWT (HS256)
- Token expiry: 24 hours
- Header: Authorization: Bearer <token>
- Passwords: bcrypt hashed, never stored in plaintext

### User Roles
| Role | Key Permissions |
|---|---|
| farmer | Create/edit products, view own orders, chat with agents |
| agent | Verify products, chat with farmers & buyers, view assignments |
| buyer | Browse verified products, place orders, rate after delivery |
| admin | Full CRUD on all resources, manage recycle bins |

---

## Product Verification Workflow

```
POST /api/products            -> status: pending_verification
POST /api/verifications/...   -> Agent assigned, status: in_progress
PUT  /api/verifications/...   -> status: verified   -> product visible in marketplace
                              -> status: rejected    -> product back to pending
                              -> status: adjustment_proposed -> farmer reviews
```

---

## Agent Matching Algorithm

Scores each agent using:
- Proximity (Haversine distance) - 40%
- Available storage capacity - 30%
- Reputation score (avg rating / 5) - 30%

Returns ranked list + notifies top N agents via in-app notification.

---

## Key Design Decisions

| Decision | Detail |
|---|---|
| Soft delete | All major entities use deleted_at timestamp with 30-day recycle bin |
| Pagination | All list endpoints: page, page_size (default 20, max 100) |
| Chat encryption | XOR cipher + base64 (messages encrypted at rest) |
| Image storage | URLs only stored in DB - images uploaded to Supabase Storage |
| Bilingual | All notifications support English + Bengali |
| Error format | {"detail": "message"} - 422 validation errors return array of issues |

---

## Deployment (Vercel)

The backend is deployed as a serverless FastAPI app on Vercel via @vercel/python.
Vercel auto-deploys on every push to the main branch.

---

## Frontend Repository

- Repo: https://github.com/nfornoor/gudam-frontend

---

## Author

nfornoor - https://github.com/nfornoor

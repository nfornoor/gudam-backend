"""
Supabase Database Setup & Seed Script for Gudam Platform.
Run this once to create tables and insert demo data.

Usage:
    python setup_supabase.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in .env")
    sys.exit(1)

from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ──────────────────────────────────────────────────────────────────────────────
# SQL to create tables (run this in Supabase SQL Editor)
# ──────────────────────────────────────────────────────────────────────────────

CREATE_TABLES_SQL = """
-- Users table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_en TEXT,
    email TEXT UNIQUE NOT NULL,
    phone TEXT UNIQUE NOT NULL,
    password_hash TEXT DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('farmer', 'agent', 'buyer', 'admin')),
    avatar_url TEXT,
    location JSONB,
    profile_details JSONB,
    gudam_details JSONB,
    business JSONB,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ DEFAULT NULL
);

-- Products table
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    farmer_id TEXT REFERENCES users(id),
    name_bn TEXT NOT NULL,
    name_en TEXT,
    category TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit TEXT NOT NULL,
    quality_grade TEXT CHECK (quality_grade IN ('A', 'B', 'C')),
    price_per_unit REAL NOT NULL,
    currency TEXT DEFAULT 'BDT',
    status TEXT DEFAULT 'pending_verification',
    images TEXT[] DEFAULT '{}',
    location TEXT,
    description_bn TEXT,
    verified_by TEXT REFERENCES users(id),
    verification_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Verifications table
CREATE TABLE IF NOT EXISTS verifications (
    id TEXT PRIMARY KEY,
    product_id TEXT REFERENCES products(id),
    agent_id TEXT REFERENCES users(id),
    farmer_id TEXT REFERENCES users(id),
    status TEXT DEFAULT 'pending',
    original_quantity REAL,
    verified_quantity REAL,
    original_grade TEXT,
    verified_grade TEXT,
    notes TEXT,
    adjustment_reason TEXT,
    call_duration TEXT,
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    product_id TEXT REFERENCES products(id),
    buyer_id TEXT REFERENCES users(id),
    agent_id TEXT REFERENCES users(id),
    farmer_id TEXT REFERENCES users(id),
    quantity REAL NOT NULL,
    unit_price REAL NOT NULL,
    total_price REAL NOT NULL,
    status TEXT DEFAULT 'placed',
    delivery_address TEXT,
    notes TEXT,
    placed_at TIMESTAMPTZ DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ,
    shipped_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ratings table
CREATE TABLE IF NOT EXISTS ratings (
    id TEXT PRIMARY KEY,
    order_id TEXT,
    from_user_id TEXT REFERENCES users(id),
    to_user_id TEXT REFERENCES users(id),
    type TEXT,
    rating REAL NOT NULL CHECK (rating >= 1 AND rating <= 5),
    review TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS (Row Level Security) but allow all for now
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE ratings ENABLE ROW LEVEL SECURITY;

-- Policies to allow all operations (development only)
CREATE POLICY IF NOT EXISTS "Allow all on users" ON users FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "Allow all on products" ON products FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "Allow all on verifications" ON verifications FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "Allow all on orders" ON orders FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "Allow all on ratings" ON ratings FOR ALL USING (true) WITH CHECK (true);
"""

# ──────────────────────────────────────────────────────────────────────────────
# Demo Data
# ──────────────────────────────────────────────────────────────────────────────

DEMO_USERS = [
    {
        "id": "farmer-001",
        "name": "আব্দুল করিম",
        "name_en": "Abdul Karim",
        "email": "karim@gudam.bd",
        "phone": "+8801712345678",
        "password_hash": "",
        "role": "farmer",
        "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=karim",
        "location": {"district": "রাজশাহী", "upazila": "পবা", "lat": 24.3745, "lng": 88.6042},
        "is_verified": True,
        "profile_details": {"farm_size": "৫ একর", "crops": ["ধান", "আলু", "পেঁয়াজ"], "experience_years": 15}
    },
    {
        "id": "farmer-002",
        "name": "ফাতেমা বেগম",
        "name_en": "Fatema Begum",
        "email": "fatema@gudam.bd",
        "phone": "+8801812345678",
        "password_hash": "",
        "role": "farmer",
        "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=fatema",
        "location": {"district": "রংপুর", "upazila": "মিঠাপুকুর", "lat": 25.7559, "lng": 89.2513},
        "is_verified": True,
        "profile_details": {"farm_size": "৩ একর", "crops": ["আম", "টমেটো", "মরিচ"], "experience_years": 8}
    },
    {
        "id": "farmer-003",
        "name": "মোহাম্মদ রফিক",
        "name_en": "Mohammad Rafiq",
        "email": "rafiq@gudam.bd",
        "phone": "+8801612345678",
        "password_hash": "",
        "role": "farmer",
        "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=rafiq",
        "location": {"district": "বগুড়া", "upazila": "শিবগঞ্জ", "lat": 24.8465, "lng": 89.3773},
        "is_verified": True,
        "profile_details": {"farm_size": "৮ একর", "crops": ["গম", "ভুট্টা", "মসুর ডাল"], "experience_years": 20}
    },
    {
        "id": "farmer-004",
        "name": "সাবিনা খাতুন",
        "name_en": "Sabina Khatun",
        "email": "sabina@gudam.bd",
        "phone": "+8801912345678",
        "password_hash": "",
        "role": "farmer",
        "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=sabina",
        "location": {"district": "ঢাকা", "upazila": "সাভার", "lat": 23.8583, "lng": 90.2636},
        "is_verified": True,
        "profile_details": {"farm_size": "২ একর", "crops": ["ফুলকপি", "বাঁধাকপি", "বেগুন"], "experience_years": 5}
    },
    {
        "id": "agent-001",
        "name": "হাসান আলী",
        "name_en": "Hasan Ali",
        "email": "hasan@gudam.bd",
        "phone": "+8801512345678",
        "password_hash": "",
        "role": "agent",
        "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=hasan",
        "location": {"district": "রাজশাহী", "upazila": "পবা", "lat": 24.3636, "lng": 88.6241},
        "is_verified": True,
        "gudam_details": {
            "name": "হাসান কৃষি গুদাম",
            "capacity": "৫০০ মেট্রিক টন",
            "capacity_num": 500, "available_capacity": 320,
            "resources": ["কোল্ড স্টোরেজ", "প্যাকেজিং", "ওজন মেশিন"],
            "verification_count": 45, "rating": 4.7
        }
    },
    {
        "id": "agent-002",
        "name": "নাসরিন সুলতানা",
        "name_en": "Nasrin Sultana",
        "email": "nasrin@gudam.bd",
        "phone": "+8801312345678",
        "password_hash": "",
        "role": "agent",
        "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=nasrin",
        "location": {"district": "রংপুর", "upazila": "রংপুর সদর", "lat": 25.7439, "lng": 89.2752},
        "is_verified": True,
        "gudam_details": {
            "name": "সুলতানা কৃষি ভাণ্ডার",
            "capacity": "৩০০ মেট্রিক টন",
            "capacity_num": 300, "available_capacity": 180,
            "resources": ["শুকানো গুদাম", "ওজন মেশিন"],
            "verification_count": 28, "rating": 4.5
        }
    },
    {
        "id": "agent-003",
        "name": "তানভীর রহমান",
        "name_en": "Tanvir Rahman",
        "email": "tanvir@gudam.bd",
        "phone": "+8801412345678",
        "password_hash": "",
        "role": "agent",
        "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=tanvir",
        "location": {"district": "বগুড়া", "upazila": "বগুড়া সদর", "lat": 24.8510, "lng": 89.3697},
        "is_verified": True,
        "gudam_details": {
            "name": "রহমান এগ্রো গুদাম",
            "capacity": "৮০০ মেট্রিক টন",
            "capacity_num": 800, "available_capacity": 550,
            "resources": ["কোল্ড স্টোরেজ", "প্যাকেজিং", "পরিবহন সুবিধা", "ওজন মেশিন"],
            "verification_count": 72, "rating": 4.9
        }
    },
    {
        "id": "buyer-001",
        "name": "ঢাকা ফুড সাপ্লায়ার্স",
        "name_en": "Dhaka Food Suppliers",
        "email": "dhakafood@gudam.bd",
        "phone": "+8801112345678",
        "password_hash": "",
        "role": "buyer",
        "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=dhakafood",
        "location": {"district": "ঢাকা", "upazila": "মিরপুর", "lat": 23.8223, "lng": 90.3654},
        "is_verified": True,
        "business": {"type": "পাইকারি", "name": "ঢাকা ফুড সাপ্লায়ার্স লিমিটেড"}
    },
    {
        "id": "buyer-002",
        "name": "মায়ের রান্নাঘর রেস্তোরাঁ",
        "name_en": "Mayer Rannaghor Restaurant",
        "email": "mayer@gudam.bd",
        "phone": "+8801212345678",
        "password_hash": "",
        "role": "buyer",
        "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=mayer",
        "location": {"district": "ঢাকা", "upazila": "গুলশান", "lat": 23.7935, "lng": 90.4145},
        "is_verified": True,
        "business": {"type": "রেস্তোরাঁ", "name": "মায়ের রান্নাঘর"}
    },
    {
        "id": "admin-001",
        "name": "সিস্টেম অ্যাডমিন",
        "name_en": "System Admin",
        "email": "admin@gudam.bd",
        "phone": "+8801012345678",
        "password_hash": "",
        "role": "admin",
        "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=admin",
        "location": {"district": "ঢাকা", "upazila": "মতিঝিল"},
        "is_verified": True
    }
]

DEMO_PRODUCTS = [
    {"id": "prod-001", "farmer_id": "farmer-001", "name_bn": "মিনিকেট চাল", "name_en": "Miniket Rice", "category": "grains", "quantity": 50, "unit": "কুইন্টাল", "quality_grade": "A", "price_per_unit": 2800, "currency": "BDT", "status": "verified", "images": ["https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400"], "location": "রাজশাহী, পবা", "description_bn": "উন্নত মানের মিনিকেট চাল। সম্পূর্ণ জৈব পদ্ধতিতে চাষ করা।", "verified_by": "agent-001", "verification_date": "2025-11-02T10:30:00+00:00"},
    {"id": "prod-002", "farmer_id": "farmer-001", "name_bn": "আলু (ডায়মন্ড)", "name_en": "Diamond Potato", "category": "vegetables", "quantity": 30, "unit": "কুইন্টাল", "quality_grade": "A", "price_per_unit": 1200, "currency": "BDT", "status": "verified", "images": ["https://images.unsplash.com/photo-1590165482129-1b8b27698780?w=400"], "location": "রাজশাহী, পবা", "description_bn": "ডায়মন্ড জাতের আলু। কোল্ড স্টোরেজে সংরক্ষিত।", "verified_by": "agent-001", "verification_date": "2025-10-21T14:00:00+00:00"},
    {"id": "prod-003", "farmer_id": "farmer-002", "name_bn": "হিমসাগর আম", "name_en": "Himsagar Mango", "category": "fruits", "quantity": 20, "unit": "মণ", "quality_grade": "A", "price_per_unit": 3500, "currency": "BDT", "status": "verified", "images": ["https://images.unsplash.com/photo-1553279768-865429fa0078?w=400"], "location": "রংপুর, মিঠাপুকুর", "description_bn": "রসালো হিমসাগর আম। গাছ পাকা।", "verified_by": "agent-002", "verification_date": "2025-06-02T09:00:00+00:00"},
    {"id": "prod-004", "farmer_id": "farmer-002", "name_bn": "টমেটো", "name_en": "Tomato", "category": "vegetables", "quantity": 15, "unit": "কুইন্টাল", "quality_grade": "B", "price_per_unit": 1800, "currency": "BDT", "status": "pending_verification", "images": ["https://images.unsplash.com/photo-1592924357228-91a4daadcfea?w=400"], "location": "রংপুর, মিঠাপুকুর", "description_bn": "তাজা টমেটো। সংগ্রহের জন্য প্রস্তুত।"},
    {"id": "prod-005", "farmer_id": "farmer-003", "name_bn": "গম", "name_en": "Wheat", "category": "grains", "quantity": 40, "unit": "কুইন্টাল", "quality_grade": "A", "price_per_unit": 2200, "currency": "BDT", "status": "verified", "images": ["https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400"], "location": "বগুড়া, শিবগঞ্জ", "description_bn": "উচ্চ মানের গম। আটা তৈরির জন্য আদর্শ।", "verified_by": "agent-003", "verification_date": "2025-04-16T11:30:00+00:00"},
    {"id": "prod-006", "farmer_id": "farmer-003", "name_bn": "মসুর ডাল", "name_en": "Red Lentil", "category": "pulses", "quantity": 25, "unit": "কুইন্টাল", "quality_grade": "A", "price_per_unit": 6500, "currency": "BDT", "status": "verified", "images": ["https://images.unsplash.com/photo-1585032226651-759b368d7246?w=400"], "location": "বগুড়া, শিবগঞ্জ", "description_bn": "দেশি মসুর ডাল। উচ্চ প্রোটিনযুক্ত।", "verified_by": "agent-003", "verification_date": "2025-05-02T16:00:00+00:00"},
    {"id": "prod-007", "farmer_id": "farmer-004", "name_bn": "ফুলকপি", "name_en": "Cauliflower", "category": "vegetables", "quantity": 10, "unit": "কুইন্টাল", "quality_grade": "A", "price_per_unit": 1500, "currency": "BDT", "status": "verified", "images": ["https://images.unsplash.com/photo-1568702846914-96b305d2aaeb?w=400"], "location": "ঢাকা, সাভার", "description_bn": "তাজা ফুলকপি। শীতকালীন ফসল।", "verified_by": "agent-001", "verification_date": "2025-12-02T00:00:00+00:00"},
    {"id": "prod-008", "farmer_id": "farmer-004", "name_bn": "বেগুন", "name_en": "Eggplant", "category": "vegetables", "quantity": 8, "unit": "কুইন্টাল", "quality_grade": "B", "price_per_unit": 1000, "currency": "BDT", "status": "pending_verification", "images": ["https://images.unsplash.com/photo-1615484477778-ca3b77940c25?w=400"], "location": "ঢাকা, সাভার", "description_bn": "বেগুনি রঙের মাঝারি আকারের বেগুন।"},
    {"id": "prod-009", "farmer_id": "farmer-001", "name_bn": "পেঁয়াজ", "name_en": "Onion", "category": "spices", "quantity": 35, "unit": "কুইন্টাল", "quality_grade": "A", "price_per_unit": 3000, "currency": "BDT", "status": "verified", "images": ["https://images.unsplash.com/photo-1618512496248-a07fe83aa8cb?w=400"], "location": "রাজশাহী, পবা", "description_bn": "দেশি পেঁয়াজ। দীর্ঘদিন সংরক্ষণযোগ্য।", "verified_by": "agent-001", "verification_date": "2025-03-11T13:00:00+00:00"},
    {"id": "prod-010", "farmer_id": "farmer-002", "name_bn": "কাঁচা মরিচ", "name_en": "Green Chili", "category": "spices", "quantity": 5, "unit": "কুইন্টাল", "quality_grade": "A", "price_per_unit": 4000, "currency": "BDT", "status": "verified", "images": ["https://images.unsplash.com/photo-1583119022894-919a68a3d0e3?w=400"], "location": "রংপুর, মিঠাপুকুর", "description_bn": "ঝাল কাঁচা মরিচ। তাজা ও সবুজ।", "verified_by": "agent-002", "verification_date": "2025-11-16T10:00:00+00:00"},
    {"id": "prod-011", "farmer_id": "farmer-003", "name_bn": "পাট", "name_en": "Jute", "category": "fiber", "quantity": 60, "unit": "মণ", "quality_grade": "A", "price_per_unit": 2800, "currency": "BDT", "status": "verified", "images": ["https://images.unsplash.com/photo-1590779033100-9f60a05a013d?w=400"], "location": "বগুড়া, শিবগঞ্জ", "description_bn": "উচ্চমানের তোষা পাট।", "verified_by": "agent-003", "verification_date": "2025-08-02T09:30:00+00:00"},
    {"id": "prod-012", "farmer_id": "farmer-004", "name_bn": "বাঁধাকপি", "name_en": "Cabbage", "category": "vegetables", "quantity": 12, "unit": "কুইন্টাল", "quality_grade": "B", "price_per_unit": 800, "currency": "BDT", "status": "pending_verification", "images": ["https://images.unsplash.com/photo-1594282486552-05b4d80fbb9f?w=400"], "location": "ঢাকা, সাভার", "description_bn": "শীতকালীন বাঁধাকপি।"},
    {"id": "prod-013", "farmer_id": "farmer-001", "name_bn": "রসুন", "name_en": "Garlic", "category": "spices", "quantity": 10, "unit": "কুইন্টাল", "quality_grade": "A", "price_per_unit": 8000, "currency": "BDT", "status": "verified", "images": ["https://images.unsplash.com/photo-1540148426945-6cf22a6b2571?w=400"], "location": "রাজশাহী, পবা", "description_bn": "দেশি রসুন। তীব্র গন্ধ ও স্বাদ।", "verified_by": "agent-001", "verification_date": "2025-04-21T00:00:00+00:00"},
    {"id": "prod-014", "farmer_id": "farmer-002", "name_bn": "কলা (সাগর)", "name_en": "Banana (Sagar)", "category": "fruits", "quantity": 15, "unit": "মণ", "quality_grade": "A", "price_per_unit": 1200, "currency": "BDT", "status": "verified", "images": ["https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?w=400"], "location": "রংপুর, মিঠাপুকুর", "description_bn": "সাগর কলা। পাকা ও মিষ্টি।", "verified_by": "agent-002", "verification_date": "2025-10-16T00:00:00+00:00"},
    {"id": "prod-015", "farmer_id": "farmer-003", "name_bn": "পেঁপে", "name_en": "Papaya", "category": "fruits", "quantity": 8, "unit": "মণ", "quality_grade": "B", "price_per_unit": 1500, "currency": "BDT", "status": "verified", "images": ["https://images.unsplash.com/photo-1517282009859-f000ec3b26fe?w=400"], "location": "বগুড়া, শিবগঞ্জ", "description_bn": "শাহী পেঁপে।", "verified_by": "agent-003", "verification_date": "2025-09-11T00:00:00+00:00"},
]

DEMO_VERIFICATIONS = [
    {"id": "ver-001", "product_id": "prod-001", "agent_id": "agent-001", "farmer_id": "farmer-001", "status": "confirmed", "original_quantity": 50, "verified_quantity": 50, "original_grade": "A", "verified_grade": "A", "notes": "কৃষকের দেওয়া তথ্য সম্পূর্ণ সঠিক।", "call_duration": "5:30", "verified_at": "2025-11-02T10:30:00+00:00"},
    {"id": "ver-002", "product_id": "prod-002", "agent_id": "agent-001", "farmer_id": "farmer-001", "status": "adjusted", "original_quantity": 35, "verified_quantity": 30, "original_grade": "A", "verified_grade": "A", "notes": "কিছু আলু পচে গেছে।", "adjustment_reason": "পচা আলু বাদ দেওয়ায় পরিমাণ কমেছে।", "call_duration": "7:15", "verified_at": "2025-10-21T14:00:00+00:00"},
    {"id": "ver-003", "product_id": "prod-003", "agent_id": "agent-002", "farmer_id": "farmer-002", "status": "confirmed", "original_quantity": 20, "verified_quantity": 20, "original_grade": "A", "verified_grade": "A", "notes": "হিমসাগর আম চমৎকার মানের।", "call_duration": "4:45", "verified_at": "2025-06-02T09:00:00+00:00"},
    {"id": "ver-004", "product_id": "prod-005", "agent_id": "agent-003", "farmer_id": "farmer-003", "status": "confirmed", "original_quantity": 40, "verified_quantity": 40, "original_grade": "A", "verified_grade": "A", "notes": "গম শুকনো ও পরিষ্কার।", "call_duration": "6:00", "verified_at": "2025-04-16T11:30:00+00:00"},
    {"id": "ver-005", "product_id": "prod-006", "agent_id": "agent-003", "farmer_id": "farmer-003", "status": "confirmed", "original_quantity": 25, "verified_quantity": 25, "original_grade": "A", "verified_grade": "A", "notes": "মসুর ডাল উচ্চমানের।", "call_duration": "3:30", "verified_at": "2025-05-02T16:00:00+00:00"},
    {"id": "ver-006", "product_id": "prod-009", "agent_id": "agent-001", "farmer_id": "farmer-001", "status": "adjusted", "original_quantity": 40, "verified_quantity": 35, "original_grade": "A", "verified_grade": "A", "notes": "পেঁয়াজের কিছু অংশ ক্ষতিগ্রস্ত।", "adjustment_reason": "আর্দ্রতায় ক্ষতিগ্রস্ত অংশ বাদ।", "call_duration": "8:00", "verified_at": "2025-03-11T13:00:00+00:00"},
    {"id": "ver-007", "product_id": "prod-010", "agent_id": "agent-002", "farmer_id": "farmer-002", "status": "confirmed", "original_quantity": 5, "verified_quantity": 5, "original_grade": "A", "verified_grade": "A", "notes": "কাঁচা মরিচ তাজা।", "call_duration": "3:00", "verified_at": "2025-11-16T10:00:00+00:00"},
    {"id": "ver-008", "product_id": "prod-011", "agent_id": "agent-003", "farmer_id": "farmer-003", "status": "confirmed", "original_quantity": 60, "verified_quantity": 60, "original_grade": "A", "verified_grade": "A", "notes": "তোষা পাট উচ্চমানের।", "call_duration": "5:00", "verified_at": "2025-08-02T09:30:00+00:00"},
]

DEMO_ORDERS = [
    {"id": "order-001", "product_id": "prod-001", "buyer_id": "buyer-001", "agent_id": "agent-001", "farmer_id": "farmer-001", "quantity": 20, "unit_price": 2800, "total_price": 56000, "status": "completed", "delivery_address": "মিরপুর-১০, ঢাকা", "notes": "দ্রুত ডেলিভারি দরকার", "placed_at": "2025-11-05T08:00:00+00:00", "confirmed_at": "2025-11-05T10:00:00+00:00", "shipped_at": "2025-11-06T07:00:00+00:00", "delivered_at": "2025-11-07T14:00:00+00:00"},
    {"id": "order-002", "product_id": "prod-005", "buyer_id": "buyer-001", "agent_id": "agent-003", "farmer_id": "farmer-003", "quantity": 15, "unit_price": 2200, "total_price": 33000, "status": "shipped", "delivery_address": "মিরপুর-১০, ঢাকা", "placed_at": "2025-12-01T09:00:00+00:00", "confirmed_at": "2025-12-01T11:00:00+00:00", "shipped_at": "2025-12-02T08:00:00+00:00"},
    {"id": "order-003", "product_id": "prod-003", "buyer_id": "buyer-002", "agent_id": "agent-002", "farmer_id": "farmer-002", "quantity": 5, "unit_price": 3500, "total_price": 17500, "status": "completed", "delivery_address": "গুলশান-২, ঢাকা", "notes": "রেস্তোরাঁর জন্য", "placed_at": "2025-06-05T10:00:00+00:00", "confirmed_at": "2025-06-05T12:00:00+00:00", "shipped_at": "2025-06-06T06:00:00+00:00", "delivered_at": "2025-06-06T18:00:00+00:00"},
    {"id": "order-004", "product_id": "prod-006", "buyer_id": "buyer-001", "agent_id": "agent-003", "farmer_id": "farmer-003", "quantity": 10, "unit_price": 6500, "total_price": 65000, "status": "confirmed", "delivery_address": "মিরপুর-১০, ঢাকা", "placed_at": "2025-12-05T11:00:00+00:00", "confirmed_at": "2025-12-05T14:00:00+00:00"},
    {"id": "order-005", "product_id": "prod-009", "buyer_id": "buyer-002", "agent_id": "agent-001", "farmer_id": "farmer-001", "quantity": 10, "unit_price": 3000, "total_price": 30000, "status": "placed", "delivery_address": "গুলশান-২, ঢাকা", "notes": "যত দ্রুত সম্ভব", "placed_at": "2025-12-08T15:00:00+00:00"},
    {"id": "order-006", "product_id": "prod-002", "buyer_id": "buyer-001", "agent_id": "agent-001", "farmer_id": "farmer-001", "quantity": 15, "unit_price": 1200, "total_price": 18000, "status": "canceled", "delivery_address": "মিরপুর-১০, ঢাকা", "notes": "ক্রেতার অনুরোধে বাতিল", "placed_at": "2025-10-25T09:00:00+00:00", "confirmed_at": "2025-10-25T11:00:00+00:00"},
]

DEMO_RATINGS = [
    {"id": "rating-001", "order_id": "order-001", "from_user_id": "buyer-001", "to_user_id": "farmer-001", "type": "product", "rating": 5, "review": "চমৎকার মানের চাল। আগামীতেও কিনব।"},
    {"id": "rating-002", "order_id": "order-001", "from_user_id": "buyer-001", "to_user_id": "agent-001", "type": "agent_service", "rating": 5, "review": "দ্রুত যাচাই ও ডেলিভারি। খুবই পেশাদার।"},
    {"id": "rating-003", "order_id": "order-001", "from_user_id": "farmer-001", "to_user_id": "agent-001", "type": "verification", "rating": 4, "review": "যাচাই প্রক্রিয়া ভালো ছিল।"},
    {"id": "rating-004", "order_id": "order-003", "from_user_id": "buyer-002", "to_user_id": "farmer-002", "type": "product", "rating": 5, "review": "অসাধারণ আম!"},
    {"id": "rating-005", "order_id": "order-003", "from_user_id": "buyer-002", "to_user_id": "agent-002", "type": "agent_service", "rating": 4, "review": "ভালো সেবা।"},
    {"id": "rating-006", "order_id": "order-003", "from_user_id": "farmer-002", "to_user_id": "agent-002", "type": "verification", "rating": 5, "review": "নাসরিন আপা খুবই সহযোগী।"},
    {"id": "rating-007", "order_id": "order-002", "from_user_id": "buyer-001", "to_user_id": "farmer-003", "type": "product", "rating": 4, "review": "গমের মান ভালো।"},
    {"id": "rating-008", "order_id": "order-002", "from_user_id": "buyer-001", "to_user_id": "agent-003", "type": "agent_service", "rating": 5, "review": "রহমান এগ্রো গুদামের সেবা অসাধারণ।"},
    {"id": "rating-009", "order_id": "order-004", "from_user_id": "farmer-003", "to_user_id": "agent-003", "type": "verification", "rating": 5, "review": "তানভীর ভাই খুবই পেশাদার।"},
    {"id": "rating-010", "order_id": "order-001", "from_user_id": "farmer-001", "to_user_id": "agent-001", "type": "verification", "rating": 5, "review": "হাসান ভাই সবসময় সময়মতো যাচাই করেন।"},
]


def seed_table(table_name, data):
    """Insert data into a Supabase table, skip if exists."""
    print(f"  Seeding {table_name} ({len(data)} rows)...")
    for row in data:
        try:
            supabase.table(table_name).upsert(row).execute()
        except Exception as e:
            print(f"    Warning: {row.get('id', '?')}: {e}")
    print(f"  ✓ {table_name} done")


def main():
    print("=" * 60)
    print("গুদাম - Supabase Database Setup")
    print("=" * 60)
    print()
    print("IMPORTANT: Before running this script, go to your Supabase")
    print("SQL Editor and run the CREATE TABLE SQL below.")
    print()
    print("─" * 60)
    print(CREATE_TABLES_SQL)
    print("─" * 60)
    print()

    if "--seed-only" not in sys.argv:
        response = input("Have you created the tables in Supabase SQL Editor? (y/n): ")
        if response.lower() != "y":
            print("Please create the tables first, then run this script again.")
            return
    else:
        print("(--seed-only mode, skipping confirmation)")

    print()
    print("Seeding demo data...")
    print()

    seed_table("users", DEMO_USERS)
    seed_table("products", DEMO_PRODUCTS)
    seed_table("verifications", DEMO_VERIFICATIONS)
    seed_table("orders", DEMO_ORDERS)
    seed_table("ratings", DEMO_RATINGS)

    print()
    print("✓ All demo data seeded successfully!")
    print()

    # Verify
    for table in ["users", "products", "verifications", "orders", "ratings"]:
        result = supabase.table(table).select("id", count="exact").execute()
        print(f"  {table}: {result.count} rows")

    print()
    print("Setup complete! You can now run the backend.")


if __name__ == "__main__":
    main()

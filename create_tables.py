"""
Create tables and seed demo data in Supabase using the service_role key.
Tries direct DB connection and pooler connection.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpqcGtsZ291ZGVianphbXltZ2pwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MDI2MTc4NywiZXhwIjoyMDg1ODM3Nzg3fQ.OjYr28kieNXt5sFq4tKKJqpea1zD24m__uxzSU_o38g"
PROJECT_REF = "zjpklgoudebjzamymgjp"

# Try to create tables using the Supabase service_role key via HTTP
import httpx
import json

SUPABASE_URL = os.getenv("SUPABASE_URL", f"https://{PROJECT_REF}.supabase.co")

CREATE_SQL = """
-- Users table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_en TEXT,
    email TEXT UNIQUE,
    phone TEXT UNIQUE NOT NULL,
    password_hash TEXT DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('farmer', 'agent', 'buyer', 'admin')),
    avatar_url TEXT,
    location JSONB,
    profile_details JSONB,
    gudam_details JSONB,
    business JSONB,
    is_verified BOOLEAN DEFAULT FALSE,
    phone_verified BOOLEAN DEFAULT FALSE,
    email_verified BOOLEAN DEFAULT FALSE,
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
    created_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ DEFAULT NULL
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
    created_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ DEFAULT NULL
);

-- Ratings table
CREATE TABLE IF NOT EXISTS ratings (
    id TEXT PRIMARY KEY,
    order_id TEXT,
    from_user_id TEXT REFERENCES users(id),
    to_user_id TEXT REFERENCES users(id),
    type TEXT,
    rated_entity_type TEXT DEFAULT 'farmer',
    rating REAL NOT NULL CHECK (rating >= 1 AND rating <= 5),
    review TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id),
    type TEXT NOT NULL,
    title TEXT,
    title_bn TEXT,
    message TEXT,
    message_bn TEXT,
    related_id TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

RLS_SQL = """
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE ratings ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all on users') THEN
        CREATE POLICY "Allow all on users" ON users FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all on products') THEN
        CREATE POLICY "Allow all on products" ON products FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all on verifications') THEN
        CREATE POLICY "Allow all on verifications" ON verifications FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all on orders') THEN
        CREATE POLICY "Allow all on orders" ON orders FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all on ratings') THEN
        CREATE POLICY "Allow all on ratings" ON ratings FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all on notifications') THEN
        CREATE POLICY "Allow all on notifications" ON notifications FOR ALL USING (true) WITH CHECK (true);
    END IF;
END $$;
"""


def try_pooler_connection():
    """Try connecting via the Supabase session pooler with JWT auth."""
    import psycopg2

    regions = [
        "ap-southeast-1",
        "us-east-1",
        "us-west-1",
        "eu-west-1",
        "eu-central-1",
        "ap-south-1",
        "ap-northeast-1",
        "sa-east-1",
    ]

    for region in regions:
        host = f"aws-0-{region}.pooler.supabase.com"
        user = f"postgres.{PROJECT_REF}"
        print(f"  Trying pooler: {host}...")
        try:
            conn = psycopg2.connect(
                host=host,
                port=5432,
                database="postgres",
                user=user,
                password=SERVICE_ROLE_KEY,
                connect_timeout=10,
                sslmode="require",
            )
            print(f"  Connected via pooler ({region})!")
            return conn
        except Exception as e:
            err = str(e).split('\n')[0]
            print(f"    Failed: {err}")
            continue

    # Also try direct DB connection
    direct_host = f"db.{PROJECT_REF}.supabase.co"
    print(f"  Trying direct: {direct_host}...")
    try:
        conn = psycopg2.connect(
            host=direct_host,
            port=5432,
            database="postgres",
            user="postgres",
            password=SERVICE_ROLE_KEY,
            connect_timeout=10,
            sslmode="require",
        )
        print(f"  Connected directly!")
        return conn
    except Exception as e:
        err = str(e).split('\n')[0]
        print(f"    Failed: {err}")

    return None


def create_tables_via_sql(conn):
    """Execute CREATE TABLE statements."""
    print("\nCreating tables...")
    cur = conn.cursor()
    try:
        cur.execute(CREATE_SQL)
        conn.commit()
        print("  Tables created successfully!")
    except Exception as e:
        conn.rollback()
        print(f"  Error creating tables: {e}")
        raise

    print("Setting up RLS policies...")
    try:
        cur.execute(RLS_SQL)
        conn.commit()
        print("  RLS policies set!")
    except Exception as e:
        conn.rollback()
        print(f"  Warning: RLS setup issue (may already exist): {e}")

    cur.close()


def seed_data_via_supabase():
    """Seed demo data using the Supabase client with service_role key."""
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

    from setup_supabase import DEMO_USERS, DEMO_PRODUCTS, DEMO_VERIFICATIONS, DEMO_ORDERS, DEMO_RATINGS

    tables = [
        ("users", DEMO_USERS),
        ("products", DEMO_PRODUCTS),
        ("verifications", DEMO_VERIFICATIONS),
        ("orders", DEMO_ORDERS),
        ("ratings", DEMO_RATINGS),
    ]

    for table_name, data in tables:
        print(f"  Seeding {table_name} ({len(data)} rows)...")
        for row in data:
            try:
                sb.table(table_name).upsert(row).execute()
            except Exception as e:
                print(f"    Warning {row.get('id', '?')}: {e}")
        print(f"    Done!")

    print("\nVerifying row counts:")
    for table_name, _ in tables:
        try:
            result = sb.table(table_name).select("id", count="exact").execute()
            count = result.count if result.count is not None else len(result.data)
            print(f"  {table_name}: {count} rows")
        except Exception as e:
            print(f"  {table_name}: Error - {e}")


def main():
    print("=" * 60)
    print("Gudam - Database Setup with Service Role Key")
    print("=" * 60)

    # Step 1: Connect and create tables
    print("\nStep 1: Connecting to database...")
    conn = try_pooler_connection()

    if conn:
        create_tables_via_sql(conn)
        conn.close()
    else:
        print("\nCould not connect via psycopg2. Trying HTTP approach...")
        # Fallback: try the Supabase SQL HTTP endpoint
        try:
            resp = httpx.post(
                f"{SUPABASE_URL}/rest/v1/rpc/",
                headers={
                    "apikey": SERVICE_ROLE_KEY,
                    "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
                    "Content-Type": "application/json",
                },
                json={"query": CREATE_SQL},
                timeout=30,
            )
            print(f"  HTTP SQL response: {resp.status_code}")
            if resp.status_code < 300:
                print("  Tables created via HTTP!")
            else:
                print(f"  HTTP response: {resp.text[:200]}")
                print("\n  ERROR: Could not create tables automatically.")
                print("  Please paste the SQL from setup_supabase.py into the Supabase SQL Editor.")
                return
        except Exception as e:
            print(f"  HTTP error: {e}")
            print("\n  ERROR: Could not create tables automatically.")
            print("  Please paste the SQL from setup_supabase.py into the Supabase SQL Editor.")
            return

    # Step 2: Seed data
    print("\nStep 2: Seeding demo data...")
    seed_data_via_supabase()

    print("\n" + "=" * 60)
    print("Setup complete! Database is ready.")
    print("=" * 60)


if __name__ == "__main__":
    main()

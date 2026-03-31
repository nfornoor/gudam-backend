import os
from dotenv import load_dotenv

load_dotenv()

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "gudam-dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# App Configuration
APP_NAME = "Gudam - Agricultural Marketplace"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "গুদাম - কৃষি পণ্যের বাজার (Agricultural Product Marketplace for Bangladesh)"
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# Demo data paths
import pathlib

BASE_DIR = pathlib.Path(__file__).parent
DEMO_DATA_DIR = BASE_DIR / "demo_data"

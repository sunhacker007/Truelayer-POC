import os
from dotenv import load_dotenv

load_dotenv()

# OAuth credentials
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:3000/callback")

# Auth endpoints
AUTH_BASE_URL = os.environ.get("AUTH_BASE_URL", "https://auth.truelayer-sandbox.com")

# Data API
DATA_API_BASE_URL = os.environ.get("DATA_API_BASE_URL", "https://api.truelayer-sandbox.com/data/v1")

# Payments API (kept for reference, not used in BNPL POC)
KID = os.environ.get("KID", "")
PRIVATE_KEY_PATH = os.environ.get("PRIVATE_KEY_PATH", "")
PRIVATE_KEY = b""
if PRIVATE_KEY_PATH and os.path.exists(PRIVATE_KEY_PATH):
    with open(PRIVATE_KEY_PATH, "rb") as f:
        PRIVATE_KEY = f.read()
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.truelayer-sandbox.com")

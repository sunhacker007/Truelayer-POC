import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
KID = os.environ["KID"]
PRIVATE_KEY_PATH = os.environ["PRIVATE_KEY_PATH"]
AUTH_URL = os.environ.get("AUTH_URL", "https://auth.truelayer-sandbox.com/connect/token")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://pay-api.truelayer-sandbox.com")
WEBHOOK_URI = os.environ.get("WEBHOOK_URI", "")

with open(PRIVATE_KEY_PATH, "rb") as f:
    PRIVATE_KEY = f.read()

import requests
import config


def get_access_token(scope: str = "payments") -> str:
    resp = requests.post(
        config.AUTH_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": config.CLIENT_ID,
            "client_secret": config.CLIENT_SECRET,
            "scope": scope,
        },
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    print(f"[auth] Access token obtained (scope={scope})")
    return token

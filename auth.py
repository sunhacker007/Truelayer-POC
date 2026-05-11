"""
TrueLayer OAuth2 Authorization Code flow.

Usage:
  1. Call get_auth_url(scenario) — prints URL for user to open in browser
  2. User logs in with Mock Bank credentials, gets redirected
  3. Call exchange_code(code) — returns (access_token, refresh_token)
  4. Call refresh_access_token(refresh_token) — returns new access_token (or raises on SCA expiry)

Scenarios:
  "uk_standard"  → john / doe       (standard UK flow)
  "uk_permanent" → john / eternal   (UK long-term token, no SCA断链)
  "de_iban"      → john / iban      (IBAN account data, simulates DE structure)
  "de_sca"       → john / doe       (same as uk_standard; refresh will expire, simulates DE SCA断链)
"""

import urllib.parse
import requests
import config

SCOPES = "accounts transactions balance offline_access info"

# Hint text per scenario (shown to user at login prompt)
SCENARIO_HINTS = {
    "uk_standard":  "UK标准: 用户名 john  密码 doe",
    "uk_permanent": "UK永久Token: 用户名 john  密码 eternal",
    "de_iban":      "DE IBAN模拟: 用户名 john  密码 iban",
    "de_sca":       "DE SCA断链模拟: 用户名 john  密码 doe (refresh将模拟到期)",
}


def get_auth_url(scenario: str = "uk_standard") -> str:
    params = {
        "response_type": "code",
        "client_id": config.CLIENT_ID,
        "scope": SCOPES,
        "redirect_uri": config.REDIRECT_URI,
        "providers": "uk-cs-mock",
    }
    url = f"{config.AUTH_BASE_URL}/?{urllib.parse.urlencode(params)}"
    hint = SCENARIO_HINTS.get(scenario, "")
    print(f"\n[auth] 场景: {scenario} — {hint}")
    print(f"[auth] 请在浏览器中打开以下链接完成授权:")
    print(f"\n  {url}\n")
    return url


def _extract_code(redirect_url: str) -> str:
    parsed = urllib.parse.urlparse(redirect_url)
    params = urllib.parse.parse_qs(parsed.query)
    if "code" not in params:
        raise ValueError(f"URL中未找到 code 参数: {redirect_url}")
    return params["code"][0]


def exchange_code(code_or_url: str) -> dict:
    """Accept either the authorization code or the full redirect URL."""
    code = code_or_url
    if code_or_url.startswith("http"):
        code = _extract_code(code_or_url)

    resp = requests.post(
        f"{config.AUTH_BASE_URL}/connect/token",
        data={
            "grant_type": "authorization_code",
            "client_id": config.CLIENT_ID,
            "client_secret": config.CLIENT_SECRET,
            "redirect_uri": config.REDIRECT_URI,
            "code": code,
        },
    )
    if not resp.ok:
        print(f"[auth] Token exchange failed {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    tokens = resp.json()
    print(f"[auth] Token获取成功 — expires_in={tokens.get('expires_in')}s, refresh_token={'✅' if tokens.get('refresh_token') else '❌'}")
    return tokens


def refresh_access_token(refresh_token: str) -> dict:
    """
    Refresh access token. On SCA expiry (DE scenario) TrueLayer returns
    HTTP 400 with error=invalid_grant — caller should catch and record this.
    """
    resp = requests.post(
        f"{config.AUTH_BASE_URL}/connect/token",
        data={
            "grant_type": "refresh_token",
            "client_id": config.CLIENT_ID,
            "client_secret": config.CLIENT_SECRET,
            "refresh_token": refresh_token,
        },
    )
    if resp.status_code == 400:
        err = resp.json().get("error", "unknown")
        print(f"[auth] Token刷新失败 — error={err} (SCA断链或token已过期)")
        resp.raise_for_status()
    resp.raise_for_status()
    tokens = resp.json()
    print(f"[auth] Token刷新成功 — 新token expires_in={tokens.get('expires_in')}s")
    return tokens


def prompt_for_code(scenario: str = "uk_standard") -> dict:
    """Interactive helper: print auth URL, wait for user to paste redirect URL."""
    get_auth_url(scenario)
    redirect_input = input("[auth] 完成授权后，请将浏览器地址栏的完整URL粘贴到此处:\n> ").strip()
    return exchange_code(redirect_input)

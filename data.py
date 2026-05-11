"""TrueLayer Data API v1 — accounts, transactions, balance, info."""

import requests
import config


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def get_accounts(token: str) -> list:
    resp = requests.get(f"{config.DATA_API_BASE_URL}/accounts", headers=_headers(token))
    if not resp.ok:
        print(f"[data] /accounts error {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    results = resp.json().get("results", [])
    print(f"[data] /accounts — {len(results)} account(s) returned")
    return results


def get_transactions(token: str, account_id: str, from_date: str, to_date: str) -> list:
    """
    from_date / to_date format: "2024-01-01T00:00:00"
    """
    params = {"from": from_date, "to": to_date}
    resp = requests.get(
        f"{config.DATA_API_BASE_URL}/accounts/{account_id}/transactions",
        headers=_headers(token),
        params=params,
    )
    if not resp.ok:
        print(f"[data] /transactions error {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    results = resp.json().get("results", [])
    print(f"[data] /transactions ({from_date[:10]} → {to_date[:10]}) — {len(results)} txn(s)")
    return results


def get_balance(token: str, account_id: str) -> dict:
    resp = requests.get(
        f"{config.DATA_API_BASE_URL}/accounts/{account_id}/balance",
        headers=_headers(token),
    )
    if not resp.ok:
        print(f"[data] /balance error {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    results = resp.json().get("results", [])
    balance = results[0] if results else {}
    print(f"[data] /balance — available={balance.get('available')} current={balance.get('current')} {balance.get('currency','')}")
    return balance


def get_info(token: str) -> dict:
    resp = requests.get(f"{config.DATA_API_BASE_URL}/info", headers=_headers(token))
    if not resp.ok:
        print(f"[data] /info error {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    results = resp.json().get("results", [])
    info = results[0] if results else {}
    print(f"[data] /info — full_name={info.get('full_name')} emails={info.get('emails')}")
    return info

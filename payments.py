import json
import uuid

import requests
import truelayer_signing

import auth
import config


def create_payment(
    amount_in_minor: int,
    currency: str,
    beneficiary_name: str,
    beneficiary_sort_code: str,
    beneficiary_account_number: str,
    user_name: str,
    user_email: str,
) -> dict:
    """Create a single immediate payment via TrueLayer Payments API."""
    access_token = auth.get_access_token(scope="payments")
    idempotency_key = str(uuid.uuid4())

    body = {
        "amount_in_minor": amount_in_minor,
        "currency": currency,
        "payment_method": {
            "type": "bank_transfer",
            "provider_selection": {
                "type": "user_selected",
                "filter": {
                    "countries": ["GB"],
                    "release_channel": "general_availability",
                },
            },
            "beneficiary": {
                "type": "external_account",
                "name": beneficiary_name,
                "reference": "POC-Test",
                "scheme_identifier": {
                    "type": "sort_code_account_number",
                    "sort_code": beneficiary_sort_code,
                    "account_number": beneficiary_account_number,
                },
            },
        },
        "user": {
            "name": user_name,
            "email": user_email,
        },
    }

    if config.WEBHOOK_URI:
        body["metadata"] = {}
        body["webhook_uri"] = config.WEBHOOK_URI

    body_bytes = json.dumps(body).encode()

    tl_signature = (
        truelayer_signing.sign_with_pem(config.KID, config.PRIVATE_KEY)
        .method("POST")
        .path("/payments")
        .header("Idempotency-Key", idempotency_key)
        .body(body_bytes)
        .sign()
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Idempotency-Key": idempotency_key,
        "Tl-Signature": tl_signature,
        "Content-Type": "application/json",
    }

    resp = requests.post(
        f"{config.API_BASE_URL}/payments",
        headers=headers,
        data=body_bytes,
    )
    resp.raise_for_status()
    result = resp.json()
    print(f"[payments] Payment created: id={result.get('id')} status={result.get('status')}")
    return result


def get_payment(payment_id: str) -> dict:
    """Retrieve payment status by ID."""
    access_token = auth.get_access_token(scope="payments")

    resp = requests.get(
        f"{config.API_BASE_URL}/payments/{payment_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp.raise_for_status()
    result = resp.json()
    print(f"[payments] Payment status: id={payment_id} status={result.get('status')}")
    return result

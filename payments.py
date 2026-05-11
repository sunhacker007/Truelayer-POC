import json
import uuid

import requests

import auth
import config
import signing


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
                "account_holder_name": beneficiary_name,
                "reference": "POC-Test",
                "account_identifier": {
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
        body["webhook_uri"] = config.WEBHOOK_URI

    body_bytes = json.dumps(body).encode()
    sign_headers = {"Idempotency-Key": idempotency_key}

    tl_signature = signing.sign_request(
        private_key_pem=config.PRIVATE_KEY,
        kid=config.KID,
        method="POST",
        path="/v3/payments",
        headers=sign_headers,
        body=body_bytes,
    )

    resp = requests.post(
        f"{config.API_BASE_URL}/v3/payments",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Idempotency-Key": idempotency_key,
            "Tl-Signature": tl_signature,
            "Content-Type": "application/json",
        },
        data=body_bytes,
    )
    if not resp.ok:
        print(f"[payments] Error {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    result = resp.json()
    print(f"[payments] Payment created: id={result.get('id')} status={result.get('status')}")
    return result


def get_payment(payment_id: str) -> dict:
    """Retrieve payment status by ID."""
    access_token = auth.get_access_token(scope="payments")

    resp = requests.get(
        f"{config.API_BASE_URL}/v3/payments/{payment_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp.raise_for_status()
    result = resp.json()
    print(f"[payments] Payment status: id={payment_id} status={result.get('status')}")
    return result

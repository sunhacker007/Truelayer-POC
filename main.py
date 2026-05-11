"""
TrueLayer Sandbox POC - Main Entry Point

Steps:
  1. Get OAuth access token
  2. Create a payment (signed with ES512)
  3. Poll payment status
"""

import json
import time

import auth
import payments


def main():
    print("=== TrueLayer Sandbox POC ===\n")

    # Step 1: Verify auth works
    print("--- Step 1: Obtain Access Token ---")
    token = auth.get_access_token()
    print(f"Token (first 20 chars): {token[:20]}...\n")

    # Step 2: Create a test payment
    print("--- Step 2: Create Payment ---")
    result = payments.create_payment(
        amount_in_minor=100,           # £1.00 in pence
        currency="GBP",
        beneficiary_name="Test Beneficiary",
        beneficiary_sort_code="040004",  # TrueLayer sandbox sort code
        beneficiary_account_number="12345678",
        user_name="Test User",
        user_email="test@example.com",
    )
    print(json.dumps(result, indent=2))

    payment_id = result.get("id")
    if not payment_id:
        print("[error] No payment ID returned.")
        return

    # Step 3: Poll payment status
    print(f"\n--- Step 3: Poll Payment Status (id={payment_id}) ---")
    for i in range(3):
        time.sleep(2)
        status_result = payments.get_payment(payment_id)
        print(f"  [{i+1}] status: {status_result.get('status')}")

    print("\n=== POC Complete ===")
    print(f"Payment ID: {payment_id}")
    print(f"Final status: {status_result.get('status')}")
    if result.get("resource_token"):
        print(f"\nTo complete payment in browser, use resource_token:")
        print(f"  {result['resource_token'][:40]}...")


if __name__ == "__main__":
    main()

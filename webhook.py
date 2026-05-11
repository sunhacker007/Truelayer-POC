"""
Simple Flask server to receive TrueLayer payment webhooks.
Run:  python webhook.py
Then configure WEBHOOK_URI=http://<your-server-ip>:8080/webhook in .env
"""

import json
from flask import Flask, request, jsonify

app = Flask(__name__)


@app.route("/webhook", methods=["POST"])
def handle_webhook():
    payload = request.get_json(force=True)
    event_type = payload.get("type", "unknown")
    payment_id = payload.get("payment_id", "unknown")

    print(f"[webhook] Received event: type={event_type} payment_id={payment_id}")
    print(json.dumps(payload, indent=2))

    return jsonify({"status": "ok"}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "running"}), 200


if __name__ == "__main__":
    print("[webhook] Server starting on port 8080...")
    app.run(host="0.0.0.0", port=8080)

"""
TrueLayer request signing (v2) — ES512 / JWS with detached content.

Spec: https://docs.truelayer.com/docs/sign-your-requests
"""

import base64
import json

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _der_to_raw_sig(der_sig: bytes) -> bytes:
    """Convert DER-encoded ECDSA signature to raw R||S (JWS format, 132 bytes for P-521)."""
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    r, s = decode_dss_signature(der_sig)
    byte_len = 66  # ceil(521 / 8)
    return r.to_bytes(byte_len, "big") + s.to_bytes(byte_len, "big")


def sign_request(
    private_key_pem: bytes,
    kid: str,
    method: str,
    path: str,
    headers: dict,
    body: bytes,
) -> str:
    """
    Build and return the Tl-Signature header value.

    :param private_key_pem: Raw PEM bytes of the EC private key
    :param kid:             Key UUID from TrueLayer Console
    :param method:          HTTP method in uppercase, e.g. "POST"
    :param path:            Absolute path, e.g. "/payments"
    :param headers:         Dict of headers to include in signature (must contain Idempotency-Key)
    :param body:            Raw request body bytes
    """
    tl_headers = ",".join(headers.keys())

    jose_header = {
        "alg": "ES512",
        "kid": kid,
        "tl_version": "2",
        "tl_headers": tl_headers,
    }
    jose_header_b64 = _b64url(json.dumps(jose_header, separators=(",", ":")).encode())

    # Build payload string per TrueLayer spec
    payload_parts = [f"{method.upper()} {path}"]
    for name, value in headers.items():
        payload_parts.append(f"{name}: {value}")
    payload_bytes = "\n".join(payload_parts).encode() + b"\n" + body

    payload_b64 = _b64url(payload_bytes)
    signing_input = f"{jose_header_b64}.{payload_b64}".encode()

    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    der_sig = private_key.sign(signing_input, ec.ECDSA(hashes.SHA512()))
    raw_sig = _der_to_raw_sig(der_sig)

    return f"{jose_header_b64}..{_b64url(raw_sig)}"

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Tuple, Union

from config import HMAC_ALGORITHM, HMAC_HEADER_NAME, HASH_HEADER_NAME

def compute_hmac(payload_bytes: bytes, secret: bytes) -> str:
    mac = hmac.new(secret, msg=payload_bytes, digestmod=getattr(hashlib, HMAC_ALGORITHM))
    return mac.hexdigest()

def compute_sha256(payload_bytes: bytes) -> str:
    return hashlib.sha256(payload_bytes).hexdigest()

def sign_payload(payload_bytes: bytes, secret: bytes) -> dict:
    return {
        HMAC_HEADER_NAME: compute_hmac(payload_bytes, secret),
        HASH_HEADER_NAME: compute_sha256(payload_bytes),
    }

def verify_hmac(payload_bytes: bytes, expected_hmac: str, secret: bytes) -> bool:
    if not expected_hmac:
        return False
    actual_hmac = compute_hmac(payload_bytes, secret)
    return hmac.compare_digest(actual_hmac, expected_hmac)

def verify_headers(payload_bytes: bytes, headers: dict, secret: bytes) -> bool:
    expected_hmac = headers.get(HMAC_HEADER_NAME) or headers.get(HMAC_HEADER_NAME.lower())
    if not expected_hmac:
        return False
        
    if not verify_hmac(payload_bytes, expected_hmac, secret):
        return False
    
    ts_str = headers.get("X-Timestamp") or headers.get("x-timestamp")
    if not ts_str:
        return False
        
    try:
        sent_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        
        if abs((now - sent_ts).total_seconds()) > 5 * 60:
            return False
    except ValueError:
        return False
        
    return True

def wrap_payload(payload_data: Union[str, bytes], secret: bytes) -> Tuple[bytes, dict]:
    
    if isinstance(payload_data, str):
        payload_bytes = payload_data.encode("utf-8")
    else:
        payload_bytes = payload_data

    integrity_headers = sign_payload(payload_bytes, secret)
    
    headers = {
        "Content-Type":   "application/jsonlines",
        "Content-Length": str(len(payload_bytes)),
        **integrity_headers,
    }

    return payload_bytes, headers


if __name__ == "__main__":

    test_secret  = b"test-secret-key"

    test_payload = '{"timestamp": "2026-05-20T11:00:00Z", "level": "info"}\n{"timestamp": "2026-05-20T11:01:00Z", "level": "warn"}\n'

    payload_bytes, headers = wrap_payload(test_payload, test_secret)

    print(f"\nPayload  :\n{payload_bytes.decode()}")
    print(f"Headers  : {json.dumps(headers, indent=2)}")

    assert verify_headers(payload_bytes, headers, test_secret), "HMAC verify failed!"
    print("\nSelf-test passed!")
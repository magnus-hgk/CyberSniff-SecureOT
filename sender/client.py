import json
import logging
import sys
import ssl
import time
import http.client
from pathlib import Path
from datetime import datetime, timezone

from config import CA_CERT, CLIENT_CERT, CLIENT_KEY, SERVER_HOST, SERVER_PORT, SERVER_ENDPOINT, TLS_MINIMUM_VERSION, HMAC_SECRET, SSL_PASSPHRASE
from integrity import wrap_payload, compute_sha256

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("client.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("bridge.client")

# Retry policy
MAX_RETRIES     = 3
RETRY_DELAY     = 2.0
CONNECT_TIMEOUT = 10


# TLS context
def build_client_ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = TLS_MINIMUM_VERSION

    # Server certificate verification
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.check_hostname = True
    ctx.load_verify_locations(cafile=CA_CERT)

    # mTLS: present client certificate
    ctx.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY, password=SSL_PASSPHRASE)

    log.info("[+] SSL context ready — server=%s  min=%s  verify=%s",
        SERVER_HOST, ctx.minimum_version.name, ctx.verify_mode.name,
    )
    return ctx


# Send function
def send_log_file(log_path: Path, secret: bytes = HMAC_SECRET) -> bool:

    log.info("[+] Loading log file: %s", log_path)
    raw_data = log_path.read_bytes()

    # Add Headers
    payload_bytes, headers = wrap_payload(raw_data, secret=secret)
    headers["X-Timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    log.info(
        "[+] Payload ready — %d bytes  SHA256=%s…",
        len(payload_bytes),
        compute_sha256(payload_bytes)[:16],
    )

    ssl_ctx = build_client_ssl_context()

    delay = RETRY_DELAY
    for attempt in range(1, MAX_RETRIES + 1):
        log.info("[+] Attempt %d/%d — connecting to %s:%d…",
                 attempt, MAX_RETRIES, SERVER_HOST, SERVER_PORT)
        try:
            success = _do_post(ssl_ctx, payload_bytes, headers)
            if success:
                log.info("[+] Log file delivered successfully on attempt %d.", attempt)
                return True
            log.error("[!] Server rejected payload. Not retrying.")
            return False

        except (ssl.SSLError, ssl.CertificateError) as exc:
            log.critical("[!] TLS error (will not retry): %s", exc)
            return False

        except (ConnectionRefusedError, OSError) as exc:
            log.warning("[!] Connection error on attempt %d: %s", attempt, exc)
            if attempt < MAX_RETRIES:
                log.info("[+]Retrying in %.1f s…", delay)
                time.sleep(delay)
                delay *= 2
            else:
                log.error("[-] All %d attempts failed.", MAX_RETRIES)
                return False

    return False


def _do_post(ssl_ctx: ssl.SSLContext, payload: bytes, headers: dict) -> bool:
    conn = http.client.HTTPSConnection(
        host=SERVER_HOST,
        port=SERVER_PORT,
        context=ssl_ctx,
        timeout=CONNECT_TIMEOUT,
    )
    try:
        log.debug("POST %s", SERVER_ENDPOINT)
        conn.request(
            method="POST", url=SERVER_ENDPOINT,
            body=payload, headers=headers,
        )
        response = conn.getresponse()
        response_body = response.read().decode("utf-8")

        tls_ver = conn.sock.version() if conn.sock else "?"
        log.info(
            "[+] Response: HTTP %d  TLS=%s  body=%s",
            response.status, tls_ver, response_body[:200],
        )

        if response.status == 200:
            return True

        log.error("[!] Unexpected HTTP status: %d", response.status)
        return False

    finally:
        conn.close()


# Local Integrity Check
def validate_log_locally(log_path: Path) -> tuple[bool, str]:
    try:
        content = log_path.read_text(encoding="utf-8").strip()
        if not content:
            return False, "[?] File is empty."

        lines = [line for line in content.split("\n") if line.strip()]
        for i, line in enumerate(lines):
            json.loads(line)
        return True, f"[+] OK ({len(lines)} log entries)"

    except json.JSONDecodeError as exc:
        return False, f"[-] Invalid JSON on line {i+1}: {exc}"
    except Exception as exc:
        return False, f"[!] Failed to read file: {exc}"


def main() -> None:
    if len(sys.argv) < 2:
        print("[+] Usage: python client.py <path_to_log_file> (e.g., python client.py LOG_FILE.jsonl)")
        sys.exit(1)

    log_path = Path(sys.argv[1])
    if not log_path.exists():
        print(f"[!] Error: file not found — {log_path}")
        sys.exit(1)

    valid, message = validate_log_locally(log_path)
    if not valid:
        log.error("[!] Local validation failed: %s", message)
        sys.exit(1)

    log.info("[+] Local validation passed: %s", message)

    success = send_log_file(log_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
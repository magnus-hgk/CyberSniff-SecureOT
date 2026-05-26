import json
import ssl
import logging
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from config import (
    CA_CERT, SERVER_CERT, SERVER_KEY,
    SERVER_PORT, SERVER_ENDPOINT,
    TLS_MINIMUM_VERSION, HMAC_SECRET, SSL_PASSPHRASE
)
from integrity import verify_headers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("server.log", encoding="utf-8"),
    ],
)

log = logging.getLogger("bridge.server")

RECEIVED_DIR = Path("received_logs")
RECEIVED_DIR.mkdir(exist_ok=True)
AUDIT_LOG    = Path("audit.jsonl")   


def build_server_ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = TLS_MINIMUM_VERSION

    try:
        ctx.load_cert_chain(
            certfile=SERVER_CERT,
            keyfile=SERVER_KEY,
            password=SSL_PASSPHRASE
        )
    except ssl.SSLError as e:
        log.error("[+] Failed to load the certificate chain. Check SSL_PASSPHRASE.")
        raise e

    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.load_verify_locations(cafile=CA_CERT)

    log.info(
        "SSL context ready — min=%s  verify=%s",
        ctx.minimum_version.name,
        ctx.verify_mode.name,
    )
    return ctx


def _extract_client_cn(handler: "BridgeRequestHandler") -> str:
    try:
        peer_cert = handler.connection.getpeercert()
        for field in peer_cert.get("subject", []):
            for key, value in field:
                if key == "commonName":
                    return value
    except Exception:
        pass
    return "UNKNOWN"



class BridgeRequestHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):  
        pass

    def do_POST(self) -> None:  
        if self.path != SERVER_ENDPOINT:
            self._send_error(404, "Not Found")
            return

        client_cn = _extract_client_cn(self)
        log.info("[+] POST %s <-- client CN=%s", self.path, client_cn)

        try:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                self._send_error(400, "Empty body")
                return
            if length > 100 * 1024 * 1024:
                self._send_error(413, "Payload too large")
                return
            body = self.rfile.read(length)
        except Exception as exc:
            log.exception("[!] Failed to read request body")
            self._send_error(400, str(exc))
            return

        headers_dict = {k.lower(): v for k, v in self.headers.items()}
        if not verify_headers(body, headers_dict, secret=HMAC_SECRET):
            log.error("[!] Integrity check failed for request from CN=%s", client_cn)
            self._send_error(403, "Integrity verification failed")
            self._audit(client_cn, "REJECTED_INTEGRITY", body, 0)
            return

        try:
            body_str = body.decode("utf-8").strip()
            parsed_lines = [json.loads(line) for line in body_str.split("\n") if line.strip()]
            line_count = len(parsed_lines)
        except json.JSONDecodeError as exc:
            log.error("[!] JSONL parse error: %s", exc)
            self._send_error(400, f"Invalid JSONL format: {exc}")
            self._audit(client_cn, "REJECTED_FORMAT", body, 0)
            return
        
        log.info("[+] Accepted: Valid JSONL payload with %d lines", line_count)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename  = RECEIVED_DIR / f"log_{timestamp}_{client_cn}.jsonl"

        filename.write_bytes(body)

        log.info("[+] Saved: %s", filename)    
        
        self._audit(client_cn, "ACCEPTED", body, line_count)

        response_body = json.dumps({
            "status":    "accepted",
            "message":   f"Successfully received {line_count} log entries.",
            "timestamp": timestamp,
            "file":      str(filename),
        }).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def do_GET(self) -> None:  
        if self.path == "/health":
            body = b'{"status": "ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._send_error(404, "Not Found")


    def _send_error(self, code: int, message: str) -> None:
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _audit(self, client_cn: str, outcome: str, raw_body: bytes, line_count: int) -> None:
        entry = {
            "timestamp":     datetime.now(timezone.utc).isoformat(),
            "outcome":       outcome,
            "client_cn":     client_cn,
            "client_addr":   self.client_address[0],
            "payload_bytes": len(raw_body),
            "log_lines":     line_count,
        }
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


def main() -> None:
    ssl_ctx = build_server_ssl_context()

    httpd = HTTPServer(("0.0.0.0", SERVER_PORT), BridgeRequestHandler)
    httpd.socket = ssl_ctx.wrap_socket(httpd.socket, server_side=True)

    print(f"""
            Secure Pipeline — Receiver Server
            Listening : https://{"0.0.0.0"}:{SERVER_PORT}{SERVER_ENDPOINT:<20}
            Hostname  : {"0.0.0.0":<43}
            TLS       : {ssl_ctx.minimum_version.name:<43}
            mTLS      : {ssl_ctx.verify_mode.name:<43}
            Output    : {str(RECEIVED_DIR):<43}
    """)

    log.info("[+] Server started")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("[+] Server stopped by user.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
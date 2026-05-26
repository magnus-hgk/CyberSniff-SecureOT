import logging
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path

# File path seeting - Used when accessing LOG_FILE.jsonl in /app/sniffer
BASE_DIR = Path(__file__).parent.resolve()
sys.path.append(str(BASE_DIR))

from client import send_log_file, validate_log_locally

# Configuration
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(BASE_DIR / "log_manager.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("bridge.manager")

# File Settings
LOG_FILE_NAME = "LOG_FILE.jsonl"
LOG_FILE_PATH = Path("/app/sniffer") / LOG_FILE_NAME
# 
MAX_BYTES_LIMIT = 1 * 1024 * 1024

# Send segmented logs from /app/sniffer
def process_pending_chunks() -> None:
    chunks = list(BASE_DIR.glob("log_chunk_*.jsonl"))
    if not chunks:
        return

    log.info("[+] Found %d logs waiting for transmission.", len(chunks))

    for chunk_path in chunks:
        log.info("[+] Sending chunk: %s", chunk_path.name)

        # Validate before sending
        valid, message = validate_log_locally(chunk_path)
        if not valid:
            log.error("[!] Local validation failed for %s: %s. Skipping.", chunk_path.name, message)
            continue

        # Send
        transfer_success = send_log_file(chunk_path)
        if transfer_success:
            log.info("[+] Chunk successfully delivered. Removing local file: %s", chunk_path.name)
            try:
                chunk_path.unlink()
            except OSError as exc:
                log.warning("[+] Failed to delete %s: %s", chunk_path.name, exc)
        else:
            log.error("[!] Failed to transmit %s", chunk_path.name)


def check_active_log_rotation() -> None:
    if not LOG_FILE_PATH.exists():
        log.debug("[!] Active log file %s does not exist", LOG_FILE_PATH)
        return

    current_size = LOG_FILE_PATH.stat().st_size
    log.debug("[+] Active log file size: %d bytes", current_size)

    if current_size < MAX_BYTES_LIMIT:
        return

    log.info("[+] Active log file above threshold: Rotating...")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rotated_chunk_path = BASE_DIR / f"log_chunk_{timestamp}.jsonl"

    try:
        # Copy active log file to /app/sender
        shutil.copy2(LOG_FILE_PATH, rotated_chunk_path)

        # Remove content from active log file
        with open(LOG_FILE_PATH, "w") as f:
            f.truncate(0)

        log.info("[+] Rotation successful. Created chunk: %s", rotated_chunk_path.name)
    except Exception as exc:
        log.error("[!] Failed to rotate log file: %s", exc)


if __name__ == "__main__":
    log.info("--- Starting Log Manager Cycle ---")

    # 1. Clear out anything that failed previously
    process_pending_chunks()

    # 2. Check if the active file needs to be frozen into a new chunk
    check_active_log_rotation()

    log.info("--- Log Manager Cycle Finished ---")
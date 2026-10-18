"""Run the dashboard and Guava inbound Expert in one shared process."""
import argparse
import logging
import os
os.environ.setdefault('GUAVA_DISABLE_TELEMETRY','true')
from pathlib import Path
import threading
import time
import tomllib
import socket
from contextlib import ExitStack
import uvicorn
from backend.runtime_lock import process_lock


class VoiceConnectionLog(logging.Handler):
    def emit(self, record):
        message = record.getMessage()
        if "Started listing on phone number" in message:
            store.connection = "connected"
            store.connection_error = None
        elif (record.name.startswith("guava.socket") or record.name == "websockets.client") and record.levelno >= logging.ERROR:
            store.connection = "reconnecting"


def run_voice():
    from backend.agent.conversation import build_agent
    logging.getLogger("guava").addHandler(VoiceConnectionLog())
    logging.getLogger("websockets.client").addHandler(VoiceConnectionLog())
    while True:
        try:
            store.connection = "connecting"
            build_agent().listen_phone(store.phone_number)
            store.connection = "reconnecting"
        except Exception:
            store.connection = "error"
            store.connection_error = "Voice connection unavailable. Check Guava login and network, then restart."
            logging.getLogger("medic").exception("Guava listener disconnected")
        time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard-only", action="store_true")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    db_path = Path(os.getenv('MEDIC_DB_PATH', root / 'runtime' / 'medic.sqlite3')).resolve()
    locks = ExitStack()
    locks.enter_context(process_lock(db_path.with_suffix('.server.lock')))
    if not args.dashboard_only:
        locks.enter_context(process_lock(root / 'runtime' / 'guava-inbound.lock'))
    try:
        with socket.socket() as port_check:
            port_check.bind(('127.0.0.1', args.port))
    except OSError as exc:
        raise SystemExit(f'Port {args.port} is already in use. No Guava listener was started.') from exc
    # Only the authoritative process may restore/recover persistent call state.
    from backend.store import store
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger('httpx').setLevel(logging.WARNING)
    # Avoid logging caller transcripts through the SDK during ordinary demos.
    logging.getLogger("guava.call").setLevel(logging.WARNING)
    config_path = Path(__file__).parent / "guava.toml"
    config = tomllib.loads(config_path.read_text()) if config_path.exists() else {}
    store.phone_number = os.getenv("GUAVA_AGENT_NUMBER", config.get("phone_number"))
    if not args.dashboard_only:
        if not store.phone_number:
            raise SystemExit("Set GUAVA_AGENT_NUMBER or configure phone_number in guava.toml.")
        threading.Thread(target=run_voice, daemon=True, name="guava-inbound").start()
    with locks:
        uvicorn.run("backend.api.server:app", host="127.0.0.1", port=args.port, log_level="warning",
                    proxy_headers=True, forwarded_allow_ips='127.0.0.1')

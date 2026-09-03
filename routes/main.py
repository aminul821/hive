from pathlib import Path
import json
import logging
from copy import deepcopy
from uuid import uuid4
from datetime import datetime

from flask import Blueprint, jsonify, render_template, request

main_bp = Blueprint("main", __name__)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "data" / "database.json"

# Safe defaults for an empty database
DEFAULT_DB = {"schema_version": "0.7-demo", "bottles": [], "gateways": [], "devices": []}


def load_database():
    """Load the local JSON database used by the demo.

    This is defensive: it returns a safe default if the file is missing or malformed.
    """
    try:
        if not DB_FILE.exists():
            return deepcopy(DEFAULT_DB)
        with DB_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load database from %s: %s", DB_FILE, exc)
        return deepcopy(DEFAULT_DB)


def save_database(db: dict):
    """Atomically save the JSON database back to disk."""
    try:
        DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = DB_FILE.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        tmp.replace(DB_FILE)
    except OSError as exc:
        logger.error("Failed to save database to %s: %s", DB_FILE, exc)
        raise


def public_database(db: dict) -> dict:
    """Return a sanitized copy of the database suitable for public preview.

    This removes any private lid codes ("code") from bottle records and
    never exposes server-only secrets.
    """
    pub = deepcopy(db)
    for b in pub.get("bottles", []):
        if isinstance(b, dict):
            b.pop("code", None)
    return pub


def find_bottle(db: dict, token: str):
    if not token:
        return None
    return next((b for b in db.get("bottles", []) if b.get("token") == token), None)


@main_bp.get("/")
def index():
    return render_template("index.html")


@main_bp.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "HiveTrust AI",
        "python_database": "JSON local demo",
    })


@main_bp.get("/api/database")
def api_database():
    db = load_database()
    return jsonify(public_database(db))


@main_bp.get("/api/bottles/<token>")
def api_bottle(token):
    db = load_database()
    b = find_bottle(db, token)
    if not b:
        return jsonify({"error": "not_found"}), 404
    pub = deepcopy(b)
    pub.pop("code", None)
    return jsonify(pub)


@main_bp.post("/api/verify")
def api_verify():
    """Verify a bottle by token + code.

    Expected JSON body: {"token": "HTV-...", "code": "X7K9-P4M2"}

    The server records the verification event and returns a compact report.
    """
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "invalid_json"}), 400
    token = payload.get("token", "")
    code = (payload.get("code") or "").strip().upper()

    db = load_database()
    b = find_bottle(db, token)
    if not b:
        return jsonify({"error": "unknown_token"}), 404

    # Create a session id for this verification
    session_id = "S-" + uuid4().hex[:8].upper()
    now = datetime.now().strftime("%d %b %Y, %H:%M")

    # Default result
    if code != (b.get("code") or "").upper():
        result = "FAILED_CODE"
        note = "Incorrect hidden code"
    else:
        # Determine suspicious reuse / clone heuristics (same as demo client)
        recent = (b.get("verificationEvents") or [])[-5:]
        suspicious = sum(1 for e in recent if e.get("result") in ("AUTHENTIC", "AUTHENTIC_FIRST_SCAN")) >= 2 or (b.get("scans") or 0) >= 4
        result = "POSSIBLE_CLONE" if suspicious else "AUTHENTIC"
        note = "Repeated credential use flagged" if suspicious else "Valid physical credential"

    # Record the event server-side
    b["scans"] = (b.get("scans") or 0) + 1
    b["lastScan"] = now
    b.setdefault("verificationEvents", []).append({"time": now, "result": result, "session": session_id, "note": note})

    # Persist the DB
    try:
        save_database(db)
    except Exception:
        logger.exception("Failed to persist verification event")
        # Don't fail the verification — persist failure shouldn't block the API result

    # Return a sanitized report
    report = {
        "result": result,
        "session": session_id,
        "note": note,
        "bottle": {k: v for k, v in b.items() if k != "code"},
    }
    return jsonify(report)

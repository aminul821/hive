from pathlib import Path
import json
import logging
import io
from copy import deepcopy
from uuid import uuid4
from datetime import datetime

from flask import Blueprint, jsonify, render_template, request, send_file
import qrcode

import blockchain
import ml_predictor

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


@main_bp.get("/api/qr/<token>")
def api_qr(token):
    """Generates a real, scannable QR code PNG for a bottle's public verification link.

    Scanning it opens this app with ?v=<token>, which the frontend already
    reads (see tokenFromURL/openBottleToken in app.js) to jump straight to
    that bottle's Bottle Authenticity page.
    """
    db = load_database()
    if not find_bottle(db, token):
        return jsonify({"error": "not_found"}), 404

    verify_url = f"{request.host_url.rstrip('/')}/?v={token}"
    img = qrcode.make(verify_url, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@main_bp.post("/api/sensor-data")
def api_sensor_data():
    """Ingests one sensor reading from a hive device (real hardware or the simulator script).

    Expected JSON body:
    {
        "device_id": "HT-HIVE-001",
        "temperature": 33.2, "humidity": 61, "weight": 42.5, "activity": 72,
        "battery": 88
    }

    Optional header "X-Device-Key" is checked against DEVICE_INGEST_KEY if that
    env var is set, so ingestion can be authenticated in a real deployment.
    """
    import os
    expected_key = os.environ.get("DEVICE_INGEST_KEY")
    if expected_key and request.headers.get("X-Device-Key") != expected_key:
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not payload or "device_id" not in payload:
        return jsonify({"error": "invalid_json", "detail": "device_id is required"}), 400

    device_id = payload["device_id"]
    try:
        temperature = float(payload.get("temperature"))
        humidity = float(payload.get("humidity"))
        weight = float(payload.get("weight"))
        activity = float(payload.get("activity"))
    except (TypeError, ValueError):
        return jsonify({"error": "temperature, humidity, weight and activity must all be numbers"}), 400

    db = load_database()
    device = next((d for d in db.get("devices", []) if d.get("id") == device_id), None)
    if not device:
        return jsonify({"error": "unknown_device"}), 404

    now = datetime.now().strftime("%d %b %Y, %H:%M")
    reading = {
        "time": now,
        "temperature": temperature,
        "humidity": humidity,
        "weight": weight,
        "activity": activity,
    }
    device.setdefault("readings", []).append(reading)
    device["readings"] = device["readings"][-50:]  # keep the last 50 readings
    device["lastReading"] = now
    if "battery" in payload:
        try:
            device["battery"] = float(payload["battery"])
        except (TypeError, ValueError):
            pass
    device["status"] = "ONLINE"

    # Run the real ML model on this reading right away, so the reading and its
    # AI assessment are captured together.
    prediction = None
    try:
        prediction = ml_predictor.predict(temperature, humidity, weight, activity)
        reading["prediction"] = prediction
    except RuntimeError:
        pass  # model not trained yet — ingestion still succeeds

    try:
        save_database(db)
    except Exception:
        logger.exception("Failed to persist sensor reading for %s", device_id)
        return jsonify({"error": "storage_failed"}), 500

    return jsonify({"stored": True, "device_id": device_id, "reading": reading, "prediction": prediction})


@main_bp.get("/api/sensor-data/<device_id>")
def api_sensor_history(device_id):
    """Returns recent readings for one device, for dashboard charts."""
    db = load_database()
    device = next((d for d in db.get("devices", []) if d.get("id") == device_id), None)
    if not device:
        return jsonify({"error": "unknown_device"}), 404
    return jsonify({"device_id": device_id, "readings": device.get("readings", [])})


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

    # Record a tamper-evident fingerprint of this verification on the blockchain.
    # This is best-effort: if the testnet is slow/unavailable, the demo must not break.
    blockchain_info = None
    if blockchain.is_configured():
        try:
            blockchain_info = blockchain.add_record(
                "BOTTLE_VERIFICATION",
                {"token": token, "result": result, "session": session_id, "time": now},
            )
        except Exception:
            logger.exception("Blockchain write failed for verification %s", session_id)

    # Return a sanitized report
    report = {
        "result": result,
        "session": session_id,
        "note": note,
        "bottle": {k: v for k, v in b.items() if k != "code"},
        "blockchain": blockchain_info,  # None if blockchain isn't configured or the write failed
    }
    return jsonify(report)


@main_bp.get("/api/blockchain/status")
def api_blockchain_status():
    """Lets the frontend show live blockchain ledger stats on the Blockchain & Security page."""
    if not blockchain.is_configured():
        return jsonify({"configured": False})
    try:
        total = blockchain.get_total_records()
        return jsonify({"configured": True, "total_records": total})
    except Exception:
        logger.exception("Failed to read blockchain status")
        return jsonify({"configured": True, "error": "unreachable"}), 503


@main_bp.post("/api/predict")
def api_predict():
    """Real ML-based hive health/yield prediction.

    Expected JSON body: {"temperature": 33, "humidity": 60, "weight": 40, "activity": 70}
    """
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "invalid_json"}), 400
    try:
        temperature = float(payload.get("temperature"))
        humidity = float(payload.get("humidity"))
        weight = float(payload.get("weight"))
        activity = float(payload.get("activity"))
    except (TypeError, ValueError):
        return jsonify({"error": "temperature, humidity, weight and activity must all be numbers"}), 400

    try:
        result = ml_predictor.predict(temperature, humidity, weight, activity)
        return jsonify(result)
    except RuntimeError as exc:
        logger.error("ML model not available: %s", exc)
        return jsonify({"error": "model_not_trained", "detail": str(exc)}), 503
    except Exception:
        logger.exception("Prediction failed")
        return jsonify({"error": "prediction_failed"}), 500

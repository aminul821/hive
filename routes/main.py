"""
routes/main.py
--------------
Same endpoints, same response shapes, Postgres underneath instead of
data/database.json.

static/js/app.js needs no changes for anything that already worked. The
only additions are the /api/harvests endpoints, which replace the
browser-local harvest history.
"""

from pathlib import Path
import io
import logging
import os
from uuid import uuid4

from flask import Blueprint, jsonify, render_template, request, send_file
import qrcode

import blockchain
import ml_predictor
import integrity
import store
from models import db

main_bp = Blueprint("main", __name__)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------

@main_bp.get("/")
def index():
    return render_template("index.html")


@main_bp.get("/api/health")
def health():
    """Also what the Supabase keepalive workflow pings -- it runs a real
    query, which is what counts as activity against the 7-day pause."""
    try:
        db.session.execute(db.text("SELECT 1"))
        database = "up"
    except Exception:                                    # noqa: BLE001
        logger.exception("Database health check failed")
        database = "down"

    return jsonify({
        "status": "ok" if database == "up" else "degraded",
        "service": "HiveTrust AI",
        "python_database": "Postgres (Supabase)",
        "database": database,
        "blockchain_configured": blockchain.is_configured(),
        "ml_model_loaded": ml_predictor.is_available(),
    }), (200 if database == "up" else 503)


@main_bp.get("/api/database")
def api_database():
    """Unchanged shape. Lid codes are never included."""
    return jsonify(store.public_database())


@main_bp.get("/api/stats")
def api_stats():
    return jsonify(store.stats())


# --------------------------------------------------------------------------
# bottles
# --------------------------------------------------------------------------

@main_bp.get("/api/bottles/<token>")
def api_bottle(token):
    bottle = store.find_bottle(token)
    if not bottle:
        return jsonify({"error": "not_found"}), 404
    return jsonify(bottle.to_dict())


@main_bp.post("/api/bottles")
def api_create_bottle():
    payload = request.get_json(silent=True) or {}
    if not payload.get("batch"):
        return jsonify({"error": "batch is required"}), 400

    if not store.find_batch(payload["batch"]):
        return jsonify({"error": "unknown_batch"}), 404

    try:
        bottle = store.create_bottle(payload)
    except Exception:                                    # noqa: BLE001
        db.session.rollback()
        logger.exception("Failed to create bottle for batch %s",
                         payload.get("batch"))
        return jsonify({"error": "storage_failed"}), 500

    # The lid code IS returned here, once, because whoever registers the
    # bottle has to physically print it. It is never served again.
    return jsonify(bottle.to_dict(include_code=True)), 201


# --------------------------------------------------------------------------
# batches
# --------------------------------------------------------------------------

@main_bp.post("/api/batches")
def api_create_batch():
    payload = request.get_json(silent=True) or {}
    batch_id = payload.get("id") or ("HC-" + uuid4().hex[:8].upper())

    if store.find_batch(batch_id):
        return jsonify({"error": "batch_id_exists"}), 409

    try:
        batch = store.create_batch({**payload, "id": batch_id})
    except Exception:                                    # noqa: BLE001
        db.session.rollback()
        logger.exception("Failed to persist batch %s", batch_id)
        return jsonify({"error": "storage_failed"}), 500

    return jsonify(batch.to_dict()), 201


@main_bp.get("/api/batches/<batch_id>")
def api_get_batch(batch_id):
    batch = store.find_batch(batch_id)
    if not batch:
        return jsonify({"error": "not_found"}), 404
    return jsonify(batch.to_dict())


# --------------------------------------------------------------------------
# QR
# --------------------------------------------------------------------------

@main_bp.get("/api/qr/<token>")
def api_qr(token):
    if not store.find_bottle(token):
        return jsonify({"error": "not_found"}), 404

    verify_url = f"{request.host_url.rstrip('/')}/?v={token}"
    img = qrcode.make(verify_url, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


# --------------------------------------------------------------------------
# sensors
# --------------------------------------------------------------------------

@main_bp.post("/api/sensor-data")
def api_sensor_data():
    expected_key = os.environ.get("DEVICE_INGEST_KEY")
    if expected_key and request.headers.get("X-Device-Key") != expected_key:
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not payload or "device_id" not in payload:
        return jsonify({"error": "invalid_json",
                        "detail": "device_id is required"}), 400

    try:
        temperature = float(payload.get("temperature"))
        humidity = float(payload.get("humidity"))
        weight = float(payload.get("weight"))
        activity = float(payload.get("activity"))
    except (TypeError, ValueError):
        return jsonify({"error": "temperature, humidity, weight and activity "
                                 "must all be numbers"}), 400

    device = store.find_device(payload["device_id"])
    if not device:
        return jsonify({"error": "unknown_device"}), 404

    prediction = None
    try:
        prediction = ml_predictor.predict(temperature, humidity, weight, activity)
    except RuntimeError:
        pass          # model not trained yet; ingestion still succeeds

    try:
        reading = store.add_reading(
            device, temperature, humidity, weight, activity,
            battery=payload.get("battery"), prediction=prediction,
        )
    except Exception:                                    # noqa: BLE001
        db.session.rollback()
        logger.exception("Failed to persist reading for %s", device.id)
        return jsonify({"error": "storage_failed"}), 500

    return jsonify({"stored": True, "device_id": device.id,
                    "reading": reading, "prediction": prediction})


@main_bp.get("/api/sensor-data/<device_id>")
def api_sensor_history(device_id):
    if not store.find_device(device_id):
        return jsonify({"error": "unknown_device"}), 404
    limit = min(int(request.args.get("limit", 50)), 500)
    return jsonify({"device_id": device_id,
                    "readings": store.recent_readings(device_id, limit)})


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------

@main_bp.post("/api/verify")
def api_verify():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "invalid_json"}), 400

    token = payload.get("token", "")
    code = (payload.get("code") or "").strip().upper()

    bottle = store.find_bottle(token)
    if not bottle:
        return jsonify({"error": "unknown_token"}), 404

    session_id = "S-" + uuid4().hex[:8].upper()

    if code != (bottle.code or "").upper():
        result, note = "FAILED_CODE", "Incorrect hidden code"
    else:
        recent = bottle.events[-5:]
        suspicious = (
            sum(1 for e in recent
                if e.result in ("AUTHENTIC", "AUTHENTIC_FIRST_SCAN")) >= 2
            or (bottle.scans or 0) >= 4
        )
        result = "POSSIBLE_CLONE" if suspicious else "AUTHENTIC"
        note = ("Repeated credential use flagged" if suspicious
                else "Valid physical credential")

    # Anchor to Sepolia first so the tx hash is stored with the event
    # rather than floating loose. Best-effort: a slow testnet must never
    # break verification.
    blockchain_info = None
    tx_hash = None
    if blockchain.is_configured():
        try:
            blockchain_info = blockchain.add_record(
                "BOTTLE_VERIFICATION",
                {"token": token, "result": result,
                 "session": session_id, "time": store.display_now()},
            )
            tx_hash = blockchain_info.get("tx_hash")
        except Exception:                                # noqa: BLE001
            logger.exception("Blockchain write failed for %s", session_id)

    try:
        store.record_verification(bottle, result, session_id, note, tx_hash)
    except Exception:                                    # noqa: BLE001
        db.session.rollback()
        logger.exception("Failed to persist verification event")

    return jsonify({
        "result": result,
        "session": session_id,
        "note": note,
        "bottle": bottle.to_dict(),
        "blockchain": blockchain_info,
    })


# --------------------------------------------------------------------------
# harvest integrity -- previously localStorage only
# --------------------------------------------------------------------------

@main_bp.get("/api/harvests")
def api_list_harvests():
    """Every harvest event, shared across devices and operators."""
    return jsonify({
        "harvests": store.list_harvests(),
        "mismatch_counts": store.hive_mismatch_counts(),
    })


@main_bp.post("/api/harvests")
def api_create_harvest():
    """
    Record a harvest and run the integrity rules server-side.

    The verdict is computed here, not in the browser. Previously the
    operator being audited could edit the audit; now the status and
    reasons are assigned by the server and the client cannot override
    them -- any `status` in the request body is ignored.
    """
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "invalid_json"}), 400

    hives = payload.get("hives") or []
    if not hives:
        return jsonify({"error": "at least one hive is required"}), 400

    if payload.get("drop") is None:
        payload["drop"] = integrity.total_drop(hives)

    status, reasons, evidence = integrity.evaluate(payload)

    tx_hash = None
    blockchain_info = None
    if blockchain.is_configured():
        try:
            blockchain_info = blockchain.add_record(
                "HARVEST_VERIFICATION",
                {"hives": hives, "drop": payload["drop"],
                 "extracted": payload.get("extracted"),
                 "recorded": payload.get("recorded"),
                 "status": status, "time": store.display_now()},
            )
            tx_hash = blockchain_info.get("tx_hash")
        except Exception:                                # noqa: BLE001
            logger.exception("Blockchain write failed for harvest")

    try:
        record = store.create_harvest(
            payload, status, reasons,
            block_hash=(blockchain_info or {}).get("data_hash"),
            tx_hash=tx_hash,
        )
    except Exception:                                    # noqa: BLE001
        db.session.rollback()
        logger.exception("Failed to persist harvest record")
        return jsonify({"error": "storage_failed"}), 500

    return jsonify({
        "harvest": record.to_dict(),
        "status": status,
        "reasons": reasons,
        "evidence": evidence,
        "blockchain": blockchain_info,
    }), 201


@main_bp.get("/api/integrity/audit")
def api_integrity_audit():
    """
    Supply-chain-wide audit.

    Everything under /api/harvests asks "was THIS harvest honest?". This
    asks a different and harder question: "where in this supply chain
    does the arithmetic fail?"

    The checks are cross-record, which is the point. An individual
    harvest can be made internally consistent by anyone willing to write
    three numbers that agree. A whole season of records that still agree
    with each other, and with the number of hives on the ground, is much
    harder to fabricate.
    """
    harvests = store.list_harvests()
    batches = store.public_database()["batches"]
    report = integrity.audit_all(harvests, batches)
    report["batches_checked"] = len(batches)
    report["harvests_checked"] = len(harvests)
    return jsonify(report)


@main_bp.post("/api/harvests/evaluate")
def api_evaluate_harvest():
    """Dry run: check a harvest without saving it, for live UI feedback."""
    payload = request.get_json(silent=True) or {}
    status, reasons, evidence = integrity.evaluate(payload)
    return jsonify({"status": status, "reasons": reasons,
                    "evidence": evidence})


# --------------------------------------------------------------------------
# blockchain + ML
# --------------------------------------------------------------------------

@main_bp.get("/api/blockchain/status")
def api_blockchain_status():
    problem = blockchain.config_problem()
    if problem:
        # 200, not an error status: the app is working fine, on-chain
        # anchoring is simply switched off. The UI says so plainly.
        return jsonify({"configured": False, "reason": problem})
    try:
        return jsonify({"configured": True,
                        "total_records": blockchain.get_total_records()})
    except Exception as exc:                             # noqa: BLE001
        logger.warning("Blockchain unreachable: %s", exc)
        return jsonify({"configured": True, "error": "unreachable"}), 503


@main_bp.post("/api/predict")
def api_predict():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "invalid_json"}), 400
    try:
        temperature = float(payload.get("temperature"))
        humidity = float(payload.get("humidity"))
        weight = float(payload.get("weight"))
        activity = float(payload.get("activity"))
    except (TypeError, ValueError):
        return jsonify({"error": "temperature, humidity, weight and activity "
                                 "must all be numbers"}), 400

    try:
        return jsonify(ml_predictor.predict(temperature, humidity,
                                            weight, activity))
    except RuntimeError as exc:
        logger.error("ML model not available: %s", exc)
        return jsonify({"error": "model_not_trained", "detail": str(exc)}), 503
    except Exception:                                    # noqa: BLE001
        logger.exception("Prediction failed")
        return jsonify({"error": "prediction_failed"}), 500

"""
store.py
--------
Database access layer. Replaces load_database() / save_database() in
routes/main.py.

Design goal: routes/main.py and static/js/app.js should not need to care
that storage changed. Every function here returns the same dict shapes
the JSON file produced, so /api/database keeps returning exactly what the
frontend already parses.

The old pattern was read-whole-file, mutate in Python, write-whole-file.
That is replaced by targeted queries and writes, which fixes two real
bugs at once:

  * Lost updates. Two requests arriving together both read the file, both
    mutated their own copy, and whichever wrote last erased the other's
    change. A bottle scan and a batch creation at the same moment meant
    one of them silently never happened.
  * Data loss on deploy. The file sat on an ephemeral filesystem.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from models import (
    db, Batch, Bottle, VerificationEvent, Gateway, Device, Reading,
    HarvestRecord, Meta,
)

SCHEMA_VERSION = "1.0-postgres"
NOTE = "Postgres (Supabase). Lid codes are stored server-side and never served to clients."


def display_now() -> str:
    return datetime.now().strftime("%d %b %Y, %H:%M")


def display_date() -> str:
    return datetime.now().strftime("%d %b %Y")


# --------------------------------------------------------------------------
# Whole-database view (what /api/database returns)
# --------------------------------------------------------------------------

def public_database() -> dict:
    """
    The sanitised snapshot the frontend loads at startup.

    Lid codes are never included: Bottle.to_dict() omits them unless
    explicitly asked. The previous implementation built a full copy then
    popped the secret out, which is one forgotten pop away from leaking
    every bottle's credential.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "note": NOTE,
        "batches": [b.to_dict() for b in
                    Batch.query.order_by(Batch.created_at).all()],
        "bottles": [b.to_dict() for b in
                    Bottle.query.order_by(Bottle.created_at).all()],
        "gateways": [g.to_dict() for g in Gateway.query.all()],
        "devices": [d.to_dict() for d in Device.query.all()],
    }


# --------------------------------------------------------------------------
# Lookups
# --------------------------------------------------------------------------

def find_bottle(token: str) -> Bottle | None:
    if not token:
        return None
    return db.session.get(Bottle, token)


def find_batch(batch_id: str) -> Batch | None:
    if not batch_id:
        return None
    return db.session.get(Batch, batch_id)


def find_device(device_id: str) -> Device | None:
    if not device_id:
        return None
    return db.session.get(Device, device_id)


# --------------------------------------------------------------------------
# Writes
# --------------------------------------------------------------------------

def create_batch(payload: dict) -> Batch:
    batch = Batch(
        id=payload.get("id") or ("HC-" + uuid4().hex[:8].upper()),
        hive=payload.get("hive", ""),
        location=payload.get("location", ""),
        qty=payload.get("qty"),
        date=payload.get("date") or display_date(),
        quality=payload.get("quality", "Verified Demo"),
    )
    db.session.add(batch)
    db.session.commit()
    return batch


def create_bottle(payload: dict) -> Bottle:
    bottle = Bottle(
        token="HTV-" + uuid4().hex[:9].upper(),
        code=f"{uuid4().hex[:4].upper()}-{uuid4().hex[:4].upper()}",
        batch=payload.get("batch"),
        harvest=payload.get("harvest") or payload.get("batch"),
        hive=payload.get("hive", ""),
        product=payload.get("product", "Honey"),
        origin=payload.get("origin", ""),
        harvest_date=payload.get("harvestDate") or display_date(),
        moisture=payload.get("moisture"),
        status=payload.get("status", "ACTIVE"),
        scans=0,
    )
    db.session.add(bottle)
    db.session.commit()
    return bottle


def record_verification(bottle: Bottle, result: str, session: str,
                        note: str, tx_hash: str | None = None) -> dict:
    """
    Append a scan event and bump the counters, in one transaction.

    Under the old file store these three mutations could interleave with
    another request's write and be lost. Here they commit together or not
    at all.
    """
    now = display_now()
    event = VerificationEvent(
        bottle_token=bottle.token, time=now, result=result,
        session=session, note=note, tx_hash=tx_hash,
    )
    db.session.add(event)
    bottle.scans = (bottle.scans or 0) + 1
    bottle.last_scan = now
    db.session.commit()
    return event.to_dict()


def add_reading(device: Device, temperature: float, humidity: float,
                weight: float, activity: float,
                battery=None, prediction=None) -> dict:
    now = display_now()
    reading = Reading(
        device_id=device.id, time=now, temperature=temperature,
        humidity=humidity, weight=weight, activity=activity,
        prediction=prediction,
    )
    db.session.add(reading)
    device.last_reading = now
    device.status = "ONLINE"
    if battery is not None:
        try:
            device.battery = float(battery)
        except (TypeError, ValueError):
            pass
    db.session.commit()
    return reading.to_dict()


def recent_readings(device_id: str, limit: int = 50) -> list[dict]:
    """
    The old store capped at 50 by slicing the list before writing, which
    threw history away permanently. Here everything is kept and the cap
    applies only to what we return.
    """
    rows = (Reading.query.filter_by(device_id=device_id)
            .order_by(Reading.created_at.desc()).limit(limit).all())
    return [r.to_dict() for r in reversed(rows)]


# --------------------------------------------------------------------------
# Harvest records — previously localStorage only
# --------------------------------------------------------------------------

def list_harvests(limit: int = 500) -> list[dict]:
    rows = (HarvestRecord.query.order_by(HarvestRecord.created_at.desc())
            .limit(limit).all())
    return [h.to_dict() for h in reversed(rows)]


def create_harvest(payload: dict, status: str, reasons: list[str],
                   block_hash: str | None = None,
                   tx_hash: str | None = None) -> HarvestRecord:
    record = HarvestRecord(
        id=payload.get("id") or ("HI-" + uuid4().hex[:8].upper()),
        time=payload.get("time") or display_now(),
        hives=payload.get("hives") or [],
        drop=payload.get("drop"),
        extracted=payload.get("extracted"),
        recorded=payload.get("recorded"),
        moisture=payload.get("moisture"),
        status=status,
        reasons=reasons,
        block_hash=block_hash,
        tx_hash=tx_hash,
    )
    db.session.add(record)
    db.session.commit()
    return record


def hive_mismatch_counts() -> dict:
    """
    How many mismatched harvests each hive appears in.

    Used by the Alerts page to surface repeat offenders. Computed
    server-side now, so it reflects every operator's records rather than
    only what this browser happens to have stored.
    """
    counts: dict[str, int] = {}
    for record in HarvestRecord.query.filter_by(status="MISMATCH").all():
        for entry in (record.hives or []):
            hive = entry.get("hive") if isinstance(entry, dict) else None
            if hive:
                counts[hive] = counts.get(hive, 0) + 1
    return counts


# --------------------------------------------------------------------------
# Stats
# --------------------------------------------------------------------------

def stats() -> dict:
    total_harvests = HarvestRecord.query.count()
    mismatches = HarvestRecord.query.filter_by(status="MISMATCH").count()
    return {
        "batches": Batch.query.count(),
        "bottles": Bottle.query.count(),
        "devices": Device.query.count(),
        "gateways": Gateway.query.count(),
        "readings": Reading.query.count(),
        "harvests": total_harvests,
        "harvest_mismatches": mismatches,
        "total_scans": db.session.query(
            db.func.coalesce(db.func.sum(Bottle.scans), 0)).scalar(),
    }

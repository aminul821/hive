"""
migrate_to_db.py
----------------
Creates the Postgres schema and imports everything from the old
data/database.json.

    python migrate_to_db.py                 # create tables, import JSON
    python migrate_to_db.py --no-import     # create tables only
    python migrate_to_db.py --reset         # drop everything first

Idempotent: records that already exist are skipped, so running it twice
does not duplicate your demo data.

Keep data/database.json in the repo after migrating. It is the seed for a
fresh database, and it is what you re-import if you ever need to rebuild.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app import create_app
from models import (
    db, Batch, Bottle, VerificationEvent, Gateway, Device, Reading,
)

BASE_DIR = Path(__file__).resolve().parent
JSON_FILE = BASE_DIR / "data" / "database.json"


def load_json() -> dict:
    if not JSON_FILE.exists():
        print(f"  {JSON_FILE} not found — nothing to import")
        return {}
    try:
        with JSON_FILE.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"  {JSON_FILE} is not valid JSON: {exc}")
        return {}


def import_data(data: dict) -> None:
    counts = {"batches": 0, "bottles": 0, "events": 0,
              "gateways": 0, "devices": 0, "readings": 0}

    # -- batches ---------------------------------------------------------
    for row in data.get("batches", []):
        if not row.get("id") or db.session.get(Batch, row["id"]):
            continue
        db.session.add(Batch(
            id=row["id"], hive=row.get("hive", ""),
            location=row.get("location", ""), qty=row.get("qty"),
            date=row.get("date"), quality=row.get("quality", "Verified Demo"),
        ))
        counts["batches"] += 1
    db.session.commit()

    # -- gateways --------------------------------------------------------
    for row in data.get("gateways", []):
        if not row.get("id") or db.session.get(Gateway, row["id"]):
            continue
        db.session.add(Gateway(
            id=row["id"], apiary=row.get("apiary"),
            backhaul=row.get("backhaul"), network=row.get("network"),
            status=row.get("status", "ONLINE"), battery=row.get("battery"),
            signal=row.get("signal"), last_seen=row.get("lastSeen"),
            hives=row.get("hives", 0),
        ))
        counts["gateways"] += 1
    db.session.commit()

    # -- devices and their readings --------------------------------------
    for row in data.get("devices", []):
        if not row.get("id"):
            continue
        if not db.session.get(Device, row["id"]):
            db.session.add(Device(
                id=row["id"], hive=row.get("hive"),
                gateway=row.get("gateway"), status=row.get("status", "ONLINE"),
                last_reading=row.get("lastReading"), battery=row.get("battery"),
            ))
            counts["devices"] += 1
        db.session.commit()

        # Readings were stored as a nested array and capped at 50.
        for reading in (row.get("readings") or []):
            db.session.add(Reading(
                device_id=row["id"], time=reading.get("time"),
                temperature=reading.get("temperature"),
                humidity=reading.get("humidity"),
                weight=reading.get("weight"),
                activity=reading.get("activity"),
                prediction=reading.get("prediction"),
            ))
            counts["readings"] += 1
    db.session.commit()

    # -- bottles and their verification events ---------------------------
    for row in data.get("bottles", []):
        token = row.get("token")
        if not token or db.session.get(Bottle, token):
            continue
        db.session.add(Bottle(
            token=token,
            code=row.get("code"),               # the private lid secret
            batch=row.get("batch"), harvest=row.get("harvest"),
            hive=row.get("hive", ""), product=row.get("product", "Honey"),
            origin=row.get("origin", ""),
            harvest_date=row.get("harvestDate"),
            moisture=row.get("moisture"),
            status=row.get("status", "ACTIVE"),
            scans=row.get("scans", 0) or 0,
            last_scan=row.get("lastScan"),
        ))
        counts["bottles"] += 1
        db.session.commit()

        for event in (row.get("verificationEvents") or []):
            db.session.add(VerificationEvent(
                bottle_token=token, time=event.get("time"),
                result=event.get("result"), session=event.get("session"),
                note=event.get("note"),
            ))
            counts["events"] += 1
        db.session.commit()

    for name, n in counts.items():
        print(f"  {name:10} {n:4} imported")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-import", action="store_true",
                        help="create tables without importing JSON")
    parser.add_argument("--reset", action="store_true",
                        help="DROP ALL TABLES first (destructive)")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        print(f"Database: {app.config.get('DB_LABEL')}")

        if args.reset:
            if input("  this deletes all data. type 'yes': ").strip().lower() != "yes":
                print("  aborted")
                return 1
            db.drop_all()
            print("  tables dropped")

        db.create_all()
        print("  schema created")

        if not args.no_import:
            data = load_json()
            if data:
                import_data(data)

        # Verify by reading back through the same path the API uses.
        import store
        snapshot = store.public_database()
        print(f"  verify: {len(snapshot['batches'])} batches, "
              f"{len(snapshot['bottles'])} bottles, "
              f"{len(snapshot['devices'])} devices")

        leaked = [b for b in snapshot["bottles"] if "code" in b]
        if leaked:
            print(f"  WARNING: {len(leaked)} bottles exposed their lid code")
            return 1
        print("  verify: no lid codes in the public snapshot")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

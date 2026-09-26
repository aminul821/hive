"""
smoke_test.py
-------------
Verifies the database layer end to end against a throwaway SQLite file,
so you can confirm the migration works before pointing it at Supabase.

    python smoke_test.py

Runs the same code paths the API uses: creates a batch, registers a
bottle, verifies it, ingests a reading, files a clean harvest and a
fraudulent one, and checks that lid codes never leak into the public
snapshot.

This does NOT touch your real database. It builds a temp file, uses it,
and deletes it.
"""

from __future__ import annotations

import os
import sys
import tempfile

# Point the app at a throwaway database BEFORE importing it.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["FLASK_ENV"] = "development"
os.environ.setdefault("HIVETRUST_SECRET_KEY", "smoke-test-key")

from app import create_app          # noqa: E402
from models import db               # noqa: E402
import store                        # noqa: E402
import integrity                    # noqa: E402

PASS = FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok    {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def run():
    app = create_app()
    with app.app_context():
        db.create_all()

        print("\nSchema")
        check("tables created", len(db.metadata.tables) >= 7,
              f"got {len(db.metadata.tables)}")

        print("\nBatches")
        batch = store.create_batch({
            "id": "HC-SMOKE-001", "hive": "H001", "location": "Tripura",
            "qty": 12.4, "quality": "Verified",
        })
        check("batch created", batch.id == "HC-SMOKE-001")
        check("batch is findable", store.find_batch("HC-SMOKE-001") is not None)
        check("unknown batch returns None", store.find_batch("NOPE") is None)
        check("batch dict shape matches the old JSON",
              set(batch.to_dict()) == {"id", "hive", "location", "qty",
                                       "date", "quality"},
              str(set(batch.to_dict())))

        print("\nBottles")
        bottle = store.create_bottle({
            "batch": "HC-SMOKE-001", "hive": "H001",
            "product": "Tripura Forest Honey", "origin": "Tripura",
            "moisture": 17.2,
        })
        check("bottle got a token", bottle.token.startswith("HTV-"))
        check("bottle got a lid code", bool(bottle.code))
        check("lid code hidden by default", "code" not in bottle.to_dict())
        check("lid code available on request",
              "code" in bottle.to_dict(include_code=True))
        check("verificationEvents key present for the frontend",
              "verificationEvents" in bottle.to_dict())
        check("harvestDate key uses the original camelCase",
              "harvestDate" in bottle.to_dict())

        print("\nVerification")
        store.record_verification(bottle, "AUTHENTIC", "S-SMOKE01",
                                  "Valid physical credential")
        refreshed = store.find_bottle(bottle.token)
        check("scan counter incremented", refreshed.scans == 1,
              f"got {refreshed.scans}")
        check("event recorded", len(refreshed.to_dict()["verificationEvents"]) == 1)
        check("lastScan set", refreshed.last_scan is not None)

        store.record_verification(bottle, "POSSIBLE_CLONE", "S-SMOKE02",
                                  "Repeated credential use")
        check("second scan counted", store.find_bottle(bottle.token).scans == 2)

        print("\nPublic snapshot")
        snapshot = store.public_database()
        check("snapshot has the expected top-level keys",
              set(snapshot) == {"schema_version", "note", "batches",
                                "bottles", "gateways", "devices"},
              str(set(snapshot)))
        check("batch appears in snapshot", len(snapshot["batches"]) == 1)
        check("bottle appears in snapshot", len(snapshot["bottles"]) == 1)
        leaked = [b for b in snapshot["bottles"] if "code" in b]
        check("NO lid codes leak into the public snapshot", not leaked,
              f"{len(leaked)} leaked")

        print("\nSensors")
        gw = None
        from models import Gateway, Device
        db.session.add(Gateway(id="GW-SMOKE", apiary="Test", status="ONLINE"))
        db.session.add(Device(id="DEV-SMOKE", hive="H001", gateway="GW-SMOKE"))
        db.session.commit()

        device = store.find_device("DEV-SMOKE")
        check("device findable", device is not None)
        store.add_reading(device, 33.2, 61.0, 48.2, 86.0, battery=88)
        store.add_reading(device, 33.4, 60.0, 47.9, 84.0, battery=87)
        readings = store.recent_readings("DEV-SMOKE")
        check("two readings stored", len(readings) == 2, f"got {len(readings)}")
        check("readings are chronological",
              readings[0]["weight"] == 48.2, str(readings[0]))
        check("device battery updated",
              store.find_device("DEV-SMOKE").battery == 87)

        print("\nHarvest integrity")
        clean = {
            "hives": [{"hive": "H001", "before": 48.2, "after": 40.1}],
            "extracted": 7.9, "recorded": 8.0, "moisture": 17.5,
        }
        clean["drop"] = integrity.total_drop(clean["hives"])
        status, reasons, _ = integrity.evaluate(clean)
        check("clean harvest passes", status == "MATCH", str(reasons))
        store.create_harvest(clean, status, reasons)

        fraud = {
            "hives": [{"hive": "H002", "before": 44.0, "after": 42.0}],
            "extracted": 9.0, "recorded": 14.0,
        }
        fraud["drop"] = integrity.total_drop(fraud["hives"])
        status, reasons, evidence = integrity.evaluate(fraud)
        check("fraudulent harvest flagged", status == "MISMATCH")
        check("reasons explain why", len(reasons) >= 2, str(reasons))
        store.create_harvest(fraud, status, reasons)

        harvests = store.list_harvests()
        check("both harvests persisted", len(harvests) == 2,
              f"got {len(harvests)}")
        check("harvest keys match what app.js expects",
              {"id", "time", "hives", "drop", "extracted", "recorded",
               "status", "reasons"} <= set(harvests[0]),
              str(set(harvests[0])))

        counts = store.hive_mismatch_counts()
        check("mismatch attributed to the right hive",
              counts.get("H002") == 1 and "H001" not in counts, str(counts))

        print("\nStats")
        s = store.stats()
        check("batch count", s["batches"] == 1)
        check("bottle count", s["bottles"] == 1)
        check("harvest count", s["harvests"] == 2)
        check("mismatch count", s["harvest_mismatches"] == 1)
        check("total scans aggregated", s["total_scans"] == 2,
              f"got {s['total_scans']}")

        print("\nAPI routes")
        client = app.test_client()
        r = client.get("/api/health")
        check("/api/health responds 200", r.status_code == 200,
              f"got {r.status_code}")
        check("/api/health reports the database up",
              r.get_json().get("database") == "up")

        r = client.get("/api/database")
        check("/api/database responds 200", r.status_code == 200)
        check("/api/database hides lid codes",
              all("code" not in b for b in r.get_json()["bottles"]))

        r = client.get("/api/harvests")
        check("/api/harvests responds 200", r.status_code == 200)
        check("/api/harvests returns both records",
              len(r.get_json()["harvests"]) == 2)

        r = client.post("/api/harvests/evaluate", json=fraud)
        check("/api/harvests/evaluate flags fraud",
              r.get_json()["status"] == "MISMATCH")

        # A client must not be able to declare its own verdict.
        r = client.post("/api/harvests", json={**fraud, "status": "OK"})
        check("client cannot forge a clean verdict",
              r.get_json()["status"] == "MISMATCH",
              str(r.get_json().get("status")))

        r = client.get("/api/batches/HC-SMOKE-001")
        check("/api/batches/<id> responds 200", r.status_code == 200)
        r = client.get("/api/batches/DOES-NOT-EXIST")
        check("unknown batch returns 404", r.status_code == 404)


def main() -> int:
    try:
        run()
    finally:
        os.unlink(_tmp.name)

    print("\n" + "=" * 50)
    print(f"  {PASS} passed, {FAIL} failed")
    print("=" * 50)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())

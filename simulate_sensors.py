"""
simulate_sensors.py
--------------------
Simulates real hive IoT sensors sending periodic readings to the Flask backend,
so judges can see the full ingestion -> storage -> AI-prediction pipeline
working live, without needing physical hardware.

Usage:
    python simulate_sensors.py                     # sends one round of readings for every device
    python simulate_sensors.py --loop               # keeps sending every 15 seconds (demo speed)
    python simulate_sensors.py --url http://127.0.0.1:5000   # point at a different server
"""

import argparse
import json
import random
import time
import urllib.request
import urllib.error


def get_devices(base_url):
    with urllib.request.urlopen(f"{base_url}/api/database") as resp:
        db = json.loads(resp.read().decode())
    return [d["id"] for d in db.get("devices", [])]


def send_reading(base_url, device_id):
    payload = {
        "device_id": device_id,
        "temperature": round(random.uniform(28, 38), 1),
        "humidity": round(random.uniform(40, 80), 1),
        "weight": round(random.uniform(25, 55), 1),
        "activity": round(random.uniform(40, 95), 1),
        "battery": round(random.uniform(60, 100), 1),
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/sensor-data",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
            pred = result.get("prediction") or {}
            print(f"[{device_id}] sent reading -> risk={pred.get('risk')} "
                  f"confidence={pred.get('confidence')}% yield={pred.get('predicted_yield_kg')}kg")
    except urllib.error.HTTPError as e:
        print(f"[{device_id}] FAILED: {e.code} {e.read().decode()}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5000")
    parser.add_argument("--loop", action="store_true", help="keep sending every 15 seconds")
    args = parser.parse_args()

    devices = get_devices(args.url)
    if not devices:
        print("No devices found in the database yet. Provision a hive device from the IoT Gateway page first.")
        return

    while True:
        for device_id in devices:
            send_reading(args.url, device_id)
        if not args.loop:
            break
        time.sleep(15)


if __name__ == "__main__":
    main()

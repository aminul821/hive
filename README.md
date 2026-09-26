# HiveTrust AI

Honey supply-chain traceability and smart beekeeping management.

Built for **Smart India Hackathon 2026, problem statement SIH26021**
(Ministry of MSME) — *"Honey Chain: A blockchain-based system for honey
traceability and smart beekeeping management."*

---

## What it does

Honey is one of India's most adulterated food products. The usual fraud is
simple: buy cheap syrup or imported honey, blend it into a genuine batch,
and sell the whole thing with authentic paperwork. Paperwork alone cannot
catch this, because the paperwork is what the fraudster controls.

HiveTrust attacks it with a physical argument instead. Honey removed from a
hive must equal the hive's weight drop, and what gets bottled must equal
what was harvested. Where those numbers disagree, something entered the
chain that did not come from a bee.

**Monitor → Analyze → Predict → Verify → Track**

## Architecture

```
Hive sensors ──► Flask API ──► Postgres (Supabase)
                    │
                    ├─► RandomForest  ─ hive risk + yield prediction
                    ├─► Integrity engine ─ weight-based fraud detection
                    └─► HoneyLedger contract (Ethereum Sepolia)
                              │
Consumer QR ──────────────────┘
```

Records live in Postgres, not in the browser. Integrity verdicts are
computed server-side, so the operator being audited cannot author their own
result. Each verification is anchored on-chain and returns a real
transaction hash.

## Components

| File | Role |
|---|---|
| `routes/main.py` | REST API |
| `models.py` | Postgres schema |
| `store.py` | data access |
| `integrity.py` | harvest fraud rules |
| `ml_predictor.py` / `train_model.py` | RandomForest risk + yield |
| `blockchain.py` | HoneyLedger contract on Sepolia |
| `simulate_sensors.py` | feeds the ingest endpoint |
| `smoke_test.py` | 44 tests over the storage layer |

## The integrity engine

`integrity.py` compares three independently-sourced numbers:

- **hive weight drop** — from the scale, not the operator
- **honey extracted** — measured at extraction
- **weight recorded** — what the operator wrote down

It flags:

| Rule | Catches |
|---|---|
| recorded > extracted | honey with no origin entering the batch |
| recorded < extracted | diversion before weighing |
| extracted > weight drop | honey from an unrecorded source |
| large extraction shortfall | unaccounted loss |
| hive gained weight | physically impossible record |
| moisture > 20% | unripe or watered honey |

The scale comparison is the strongest, because the corroborating number
comes from a sensor rather than from the person being checked.

## Two-factor bottle verification

Each bottle carries a **public QR token** and a **hidden lid code** under the
cap. Scanning the QR shows provenance. Entering the lid code proves physical
possession of a sealed jar.

The lid code is stored server-side and returned exactly once, when the
bottle is registered and the code must be printed. No read endpoint ever
returns it. `smoke_test.py` asserts this.

Repeated verification of the same credential is flagged as a possible
cloned label.

## Running it

```bash
pip install -r requirements.txt
cp env.example .env          # add DATABASE_URL and HIVETRUST_SECRET_KEY

python smoke_test.py         # verify storage (uses a temp database)
python migrate_to_db.py      # create schema, import seed data
python train_model.py        # generate models/*.pkl
python app.py
```

Open http://127.0.0.1:5000

With `DATABASE_URL` unset it falls back to local SQLite, so the app runs
with no Supabase account.

**Supabase:** use the **Session pooler** string (port 5432), not "Direct
connection" — the direct host is IPv6-only on the free tier and most hosts
are IPv4-only. See `MIGRATION.md`.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | service + database + model status |
| `GET /api/database` | full snapshot (lid codes excluded) |
| `POST /api/batches` · `GET /api/batches/<id>` | batch registry |
| `POST /api/bottles` · `GET /api/bottles/<token>` | bottle registry |
| `GET /api/qr/<token>` | scannable QR PNG |
| `POST /api/verify` | two-factor verification |
| `POST /api/sensor-data` · `GET /api/sensor-data/<id>` | telemetry |
| `POST /api/harvests` · `GET /api/harvests` | harvest records + verdict |
| `POST /api/harvests/evaluate` | dry-run check, nothing saved |
| `POST /api/predict` | RandomForest risk + yield |
| `GET /api/blockchain/status` | on-chain record count |

## Honest limitations

Stated plainly, because they are the questions worth asking:

- **Sensors are simulated.** `simulate_sensors.py` posts to the same ingest
  endpoint real hardware would use. No hive is currently instrumented.
- **The model is trained on synthetic data.** `train_model.py` generates
  4,000 samples from apiculture domain rules with noise. Real multi-season
  hive logs are not publicly available at the scale needed.
- **The contract is on Sepolia testnet.** Real chain, test currency.
- **Roles are client-side.** Role selection is not yet authenticated; write
  endpoints are not access-controlled.
- **The Security Lab ledger is a local demonstration**, clearly labelled as
  such in the UI. Production anchoring is the Sepolia contract.

## Team

HexaDevelopers — SIH 2026, PS SIH26021, Agriculture/FoodTech & Rural
Development.

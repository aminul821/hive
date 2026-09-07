# HoneyChain (HiveTrust AI)

**Blockchain-based smart beekeeping and honey traceability platform** — built for Smart India Hackathon 2026.

HoneyChain combines IoT hive monitoring, a real trained AI model for hive health/yield prediction, and blockchain-backed honey provenance so consumers can verify authenticity from hive to bottle.

---

## Feature status (honest, judge-friendly)

| Feature | Status | Notes |
|---|---|---|
| Bottle authenticity verification | ✅ Real | Server-side (`/api/verify`), backed by a JSON data store |
| Blockchain record of bottle verification | ✅ Real | Written live to a `HoneyLedger` smart contract on Ethereum **Sepolia testnet** (see `blockchain.py`) |
| QR code for bottle verification | ✅ Real | Generated server-side (`/api/qr/<token>`), scans open the live verification page |
| AI hive health / yield prediction | ✅ Real | Trained scikit-learn RandomForest model (`train_model.py`), not a hardcoded formula |
| IoT sensor ingestion | ✅ Real pipeline / 🔶 Simulated hardware | `/api/sensor-data` is a real, working endpoint; `simulate_sensors.py` stands in for physical sensors we don't have yet |
| Internal harvest/tamper-audit ledger (Blockchain & Security page) | 🔶 Simulated | A demo tamper-evident hash-chain, separate from the real Ethereum ledger above — kept for demonstrating the[...] |
| Authentication / role enforcement | 🔶 Demo-only | Role switching (Owner/Auditor/Consumer) is UI-level for demo purposes; not backend-enforced yet |
| Database | 🔶 JSON file (`data/database.json`) | Sufficient for demo scale; a real deployment would move to Postgres/SQLite |

---

## Architecture

```
Browser (role-based dashboard)
        │
        ▼
Flask backend (app.py, routes/main.py)
        │
        ├── data/database.json  ── bottles, gateways, devices, sensor readings
        ├── ml_predictor.py     ── loads trained scikit-learn models
        │        └── models/hive_risk_model.pkl, hive_yield_model.pkl
        └── blockchain.py       ── web3.py → Ethereum Sepolia → HoneyLedger.sol
```

**Data flow (bottle verification):**
`Consumer scans QR → opens /?v=<token> → enters hidden lid code → POST /api/verify → result saved to database.json → event hashed and written to HoneyLedger on Sepolia → tx hash + Ethe[...]`

**Data flow (sensor → AI):**
`Sensor (real or simulate_sensors.py) → POST /api/sensor-data → reading stored → RandomForest model runs immediately → risk/yield returned and stored alongside the reading`

---

## Tech Stack

- **Frontend:** JavaScript, HTML, CSS (role-based dashboard UI)
- **Backend:** Python, Flask (REST API)
- **ML/AI:** scikit-learn (RandomForest models)
- **Blockchain:** Solidity, Web3.py, Ethereum Sepolia testnet
- **Database:** JSON (demo), future: PostgreSQL/SQLite

**Language Composition:**
- JavaScript: 62.7%
- Python: 34.6%
- HTML: 2.1%
- Other: 0.6%

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# One-time: train the AI model
python train_model.py

# Configure secrets
cp .env.example .env
# then edit .env with your real values (see below)
python app.py
```

### Environment variables (`.env`)

| Variable | Required | Purpose |
|---|---|---|
| `HIVETRUST_SECRET_KEY` | Yes (non-dev) | Flask session secret |
| `FLASK_ENV` | Yes | `development` or `production` |
| `INFURA_SEPOLIA_URL` | For blockchain features | Sepolia RPC endpoint (Infura, or a free public RPC) |
| `HONEYCHAIN_PRIVATE_KEY` | For blockchain features | Wallet private key used to sign ledger transactions (test wallet only — never a real-funds wallet) |
| `HONEYLEDGER_CONTRACT_ADDRESS` | For blockchain features | Deployed `HoneyLedger.sol` contract address |
| `DEVICE_INGEST_KEY` | Optional | If set, `/api/sensor-data` requires this in the `X-Device-Key` header |

---

## API reference

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/database` | Public (sanitized) view of the demo database |
| GET | `/api/bottles/<token>` | Public bottle preview |
| GET | `/api/qr/<token>` | Real QR code PNG for a bottle's verification link |
| POST | `/api/verify` | Verify a bottle (`{token, code}`) — writes to blockchain if configured |
| GET | `/api/blockchain/status` | Total records on the ledger |
| POST | `/api/predict` | AI prediction from sensor values (`{temperature, humidity, weight, activity}`) |
| POST | `/api/sensor-data` | Ingest one sensor reading for a device; runs AI prediction automatically |
| GET | `/api/sensor-data/<device_id>` | Recent readings for one device |

---

## Demoing without hardware

```bash
python simulate_sensors.py --loop
```
This sends realistic sensor readings for every provisioned device every 15 seconds, so the IoT → AI pipeline can be shown live even without physical hive sensors.

---

## Known limitations

- Demo-scale JSON storage, not a production database
- Role-based access is UI-level, not backend-enforced
- IoT hardware is simulated (no physical LoRaWAN deployment yet)
- Internal harvest/tamper ledger is a simulated hash-chain, separate from the real Sepolia ledger used for bottle verification
- AI model is trained on domain-informed synthetic data (no historical real-world hive dataset yet)

---

## 👥 Team

| Member | Role | GitHub |
|--------|------|--------|
| **Aminul Haque** | Project Lead & Full Stack Developer | [@aminul821](https://github.com/aminul821) |
| **Veeru Shukla** | Backend Developer | [@veerushukla](https://github.com/veerushukla) |
| **Aditya Anand** | Vibe Coder & Frontend Developer | [@adiianand](https://github.com/adiianand) |
| **Anas Khan** | Analyst & Data Scientist | [@1anas1](https://github.com/1anas1) |
| **Muskan** | Research & Documentation | [@muskansahu479](https://github.com/muskansahu479) |
| **Siddharth** | Research & Development (R&D) | - |

**Contributing:** We welcome contributions! Please fork this repository and submit pull requests with improvements.

---

## License

MIT License — See LICENSE file for details.

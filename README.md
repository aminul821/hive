# 🍯 HoneyChain (HiveTrust AI)

**Blockchain-based smart beekeeping and honey traceability platform** — built for Smart India Hackathon 2026.

> 🚀 HoneyChain combines IoT hive monitoring, a real trained AI model for hive health/yield prediction, and blockchain-backed honey provenance so consumers can verify authenticity from hive to bottle.

---

## ✨ Feature Status (Honest, Judge-Friendly)

| Feature | Status | Notes |
|---|---|---|
| 🍁 Bottle authenticity verification | ✅ Real | Server-side (`/api/verify`), backed by a JSON data store |
| ⛓️ Blockchain record of bottle verification | ✅ Real | Written live to a `HoneyLedger` smart contract on Ethereum **Sepolia testnet** (see `blockchain.py`) |
| 📱 QR code for bottle verification | ✅ Real | Generated server-side (`/api/qr/<token>`), scans open the live verification page |
| 🤖 AI hive health / yield prediction | ✅ Real | Trained scikit-learn RandomForest model (`train_model.py`), not a hardcoded formula |
| 📡 IoT sensor ingestion | ✅ Real pipeline / 🔶 Simulated hardware | `/api/sensor-data` is a real, working endpoint; `simulate_sensors.py` stands in for physical sensors we don't have yet |
| 🔐 Internal harvest/tamper-audit ledger | 🔶 Simulated | A demo tamper-evident hash-chain, separate from the real Ethereum ledger above |
| 🔑 Authentication / role enforcement | 🔶 Demo-only | Role switching (Owner/Auditor/Consumer) is UI-level for demo purposes |
| 💾 Database | 🔶 JSON file | Sufficient for demo scale; future: PostgreSQL/SQLite |

---

## 🏗️ Architecture

```
    🌐 Browser (role-based dashboard)
        │
        ▼
    🔧 Flask Backend (app.py, routes/main.py)
        │
        ├── 📁 data/database.json  ── bottles, gateways, devices, sensor readings
        ├── 🤖 ml_predictor.py     ── loads trained scikit-learn models
        │        └── 📊 models/hive_risk_model.pkl, hive_yield_model.pkl
        └── ⛓️ blockchain.py       ── web3.py → Ethereum Sepolia → HoneyLedger.sol
```

**📊 Data Flow (Bottle Verification):**
```
🔍 Consumer scans QR → 🌐 opens /?v=<token> → 🔐 enters hidden lid code 
→ 📤 POST /api/verify → 💾 result saved → ⛓️ HoneyLedger on Sepolia
```

**📈 Data Flow (Sensor → AI):**
```
📡 Sensor → 📤 POST /api/sensor-data → 💾 reading stored 
→ 🤖 RandomForest model → 📊 risk/yield returned
```

---

## 🛠️ Tech Stack

```
┌─────────────────────────────────────────────────┐
│  🎨 FRONTEND                                    │
│  • JavaScript (62.7%)                           │
│  • HTML (2.1%)                                  │
│  • CSS - Role-based Dashboard UI                │
└─────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────┐
│  ⚙️ BACKEND                                     │
│  • Python (34.6%)                               │
│  • Flask REST API                               │
└─────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────┐
│  🔬 ML/AI & BLOCKCHAIN                          │
│  • scikit-learn (RandomForest models)           │
│  • Solidity Smart Contracts                     │
│  • Web3.py - Ethereum Sepolia testnet           │
└─────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────┐
│  💾 DATABASE                                    │
│  • JSON (demo) → PostgreSQL/SQLite (production) │
└─────────────────────────────────────────────────┘
```

---

## 🚀 Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Train the AI model (one-time)
python train_model.py

# Configure environment variables
cp .env.example .env
# Edit .env with your credentials

# Start the server
python app.py
```

### 🔐 Environment Variables (`.env`)

| Variable | Required | Purpose |
|---|---|---|
| `HIVETRUST_SECRET_KEY` | ✅ Non-dev | Flask session secret |
| `FLASK_ENV` | ✅ | `development` or `production` |
| `INFURA_SEPOLIA_URL` | ⛓️ Blockchain | Sepolia RPC endpoint |
| `HONEYCHAIN_PRIVATE_KEY` | ⛓️ Blockchain | Test wallet private key |
| `HONEYLEDGER_CONTRACT_ADDRESS` | ⛓️ Blockchain | Deployed contract address |
| `DEVICE_INGEST_KEY` | 📡 Optional | Sensor data endpoint key |

---

## 📡 API Reference

| Method | Endpoint | Purpose |
|---|---|---|
| 🟢 GET | `/api/health` | Health check |
| 🟢 GET | `/api/database` | Public database view |
| 🟢 GET | `/api/bottles/<token>` | Bottle preview |
| 🟢 GET | `/api/qr/<token>` | QR code PNG |
| 🔵 POST | `/api/verify` | Verify bottle & write to blockchain |
| 🟢 GET | `/api/blockchain/status` | Ledger records count |
| 🔵 POST | `/api/predict` | AI prediction from sensor values |
| 🔵 POST | `/api/sensor-data` | Ingest sensor reading + AI prediction |
| 🟢 GET | `/api/sensor-data/<device_id>` | Recent device readings |

---

## 🎮 Demo Without Hardware

```bash
python simulate_sensors.py --loop
```

📊 This sends realistic sensor readings every 15 seconds, so you can see the IoT → AI pipeline live! 

---

## ⚠️ Known Limitations

- 📊 Demo-scale JSON storage (not production-ready)
- 🔑 Role-based access is UI-level only
- 📡 IoT hardware is simulated (no LoRaWAN deployment yet)
- 🔗 Internal harvest ledger is a simulated hash-chain
- 🤖 AI model trained on synthetic domain data (no historical real-world dataset yet)

---

## 👥 Team

<table>
  <tr>
    <th>👤 Member</th>
    <th>💼 Role</th>
    <th>🔗 GitHub</th>
  </tr>
  <tr>
    <td><b>Aminul Haque</b> ⭐</td>
    <td>Project Lead & Full Stack Developer</td>
    <td><a href="https://github.com/aminul821">@aminul821</a></td>
  </tr>
  <tr>
    <td><b>Veeru Shukla</b> 🔧</td>
    <td>Backend Developer</td>
    <td><a href="https://github.com/veerushukla">@veerushukla</a></td>
  </tr>
  <tr>
    <td><b>Aditya Anand</b> 🎨</td>
    <td>Vibe Coder & Frontend Developer</td>
    <td><a href="https://github.com/adiianand">@adiianand</a></td>
  </tr>
  <tr>
    <td><b>Anas Khan</b> 📊</td>
    <td>Analyst & Data Scientist</td>
    <td><a href="https://github.com/1anas1">@1anas1</a></td>
  </tr>
  <tr>
    <td><b>Muskan</b> 📚</td>
    <td>Research & Documentation</td>
    <td><a href="https://github.com/muskansahu479">@muskansahu479</a></td>
  </tr>
  <tr>
    <td><b>Siddharth</b> 🔬</td>
    <td>Research & Development (R&D)</td>
    <td>📝 Coming Soon</td>
  </tr>
</table>

---

## 🤝 Contributing

```
  Fork → Branch → Commit → Push → Pull Request ✨
```

We welcome contributions! Please fork this repository and submit pull requests with improvements.

---

## 📜 License

MIT License — See [LICENSE](LICENSE) file for details.

---

<div align="center">

### ⭐ If you find HoneyChain helpful, please consider giving us a star! ⭐

**Made with ❤️ by Team HoneyChain**

```
🐝 Protecting authenticity, one bottle at a time 🍯
```

</div>

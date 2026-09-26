# What changed in this round

## static/js/app.js  (the main one)

**Harvest records moved to the server.** `hivetrust_harvest_records` is
gone. `loadHarvests()` reads from `/api/harvests`, and `verifyHarvest()`
now POSTs — it became `async` to do so.

**The server decides the verdict.** The client still computes a
provisional MATCH/MISMATCH so something shows if the request fails, but
the server's answer overwrites it. `POST /api/harvests` ignores any
`status` in the request body. The operator being audited can no longer
author their own result.

**Real model wired to the dashboard.** `predictor()` was a JS heuristic
that bypassed your RandomForest entirely. It is now `heuristicPredictor()`
and only runs as a fallback; `refreshPredictions()` calls `/api/predict`
for every hive at startup and caches the answers, so `render()` stays
synchronous. Each result carries a `source` field — `model` or `heuristic`
— so you can tell which produced a number.

**The fake hash is labelled.** `hash()` was a 32-bit FNV-1a value
`.repeat(8)`'d into something that looked like SHA-256. Renamed
`demoHash()` with a comment saying exactly what it is. The Ledger page now
shows real Sepolia status from `/api/blockchain/status` above the local
chain, and the local chain is labelled "Local Demonstration Chain".

The tamper test is kept — it is a good demo of the principle, and now it
is honestly framed rather than passing itself off as the production ledger.

**Fixed an on-screen claim that had become false.** The Consumer Verify
page said *"In this static demo the JSON/localStorage database is
browser-side. A real deployment must keep the lid secret server-side."*
Both halves are now untrue. Replaced with a description of what the app
actually does.

**Offline banner.** If the server is unreachable, a red bar says so. Before
this, a dropped connection rendered identically to a working app.

## README.md

Rewritten. The old one said all logic runs in the browser with
localStorage and a demo ledger — a description of the app from two
migrations ago, and the first thing anyone opening your repo would read.
Saved as `README_OLD.md` in your git history if you want it.

Includes an "Honest limitations" section naming the simulated sensors,
synthetic training data, testnet contract, and client-side roles. Stating
these yourself is stronger than being asked.

## config.py

Three fixes from this session, re-applied: `.env` loads inside `config.py`
so import order cannot break it; square brackets left in from the Supabase
template are stripped; the secret-key error tells you what to do.

## What's still in localStorage — and why that's fine

- `hivetrust_role` — role selection. Cosmetic until there's real auth.
- `DB_KEY` — a cache of the last server snapshot, used only when offline.
  Overwritten on every successful load, never read while online.

Neither is a source of truth. All actual records are in Postgres.

## Test it

```bash
python smoke_test.py       # 44 backend tests
python app.py
```

Record a harvest in Chrome. Open the same URL in incognito. The harvest
should be there.

Then try to cheat: enter numbers that obviously mismatch, and watch the
server return MISMATCH regardless of what the client computed.

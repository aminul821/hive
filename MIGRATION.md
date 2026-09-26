# Moving HiveTrust to Supabase Postgres

## What changed

| File | Change |
|---|---|
| `models.py` | **new** — Postgres schema mirroring `database.json` |
| `store.py` | **new** — replaces `load_database()` / `save_database()` |
| `integrity.py` | **new** — harvest rules, moved out of the browser |
| `migrate_to_db.py` | **new** — creates tables, imports your JSON |
| `smoke_test.py` | **new** — verifies the DB layer before you trust it |
| `config.py` | rewritten — Supabase connection handling |
| `app.py` | rewritten — initialises the database |
| `routes/main.py` | rewritten — same endpoints, Postgres underneath |
| `routes/main.py.ORIGINAL` | your original, kept for diffing |
| `ml_predictor.py` | added `is_available()` |
| `blockchain.py` | **untouched** |
| `train_model.py`, `simulate_sensors.py` | **untouched** |

Every existing API response keeps its exact shape, so `static/js/app.js`
works unchanged — except for harvests, which were never server-side.
See `FRONTEND_PATCH.md` for those three edits.

## Why this was necessary

`data/database.json` is a file on disk. Render, Railway and Fly all give
you an **ephemeral filesystem**: every redeploy and every container
restart resets that file to whatever is committed in git. You would demo,
push a CSS fix, and lose every batch created that day.

`save_database()` also rewrote the whole file per request. Two requests
arriving together both read, both mutated their own copy, and the second
write erased the first. A bottle scan landing at the same moment as a
batch creation meant one of them silently never happened.

## Steps

### 1. Supabase project

supabase.com → new project → region **Mumbai (ap-south-1)**. Save the
database password; it's shown once.

### 2. Connection string

Dashboard → **Connect**. Three options appear:

| Option | Port | Use it? |
|---|---|---|
| Direct connection | 5432 | **No.** IPv6-only on free tier; Render is IPv4-only. Fails with "Network is unreachable". |
| **Session pooler** | 5432 | **Yes.** Built for persistent servers like gunicorn. |
| Transaction pooler | 6543 | Serverless only. Works, but no benefit here. |

Copy the Session pooler URI verbatim. Two things you cannot guess: the
pooler hostname isn't derivable from your region, and the username is
`postgres.<project-ref>`, not `postgres`. URL-encode any `@ : / #` in
your password.

### 3. Local

```bash
pip install -r requirements.txt
cp env.example .env          # paste DATABASE_URL into it

python smoke_test.py         # verify the DB layer (uses a temp file)
python migrate_to_db.py      # create tables + import database.json
python train_model.py        # generate models/*.pkl
python app.py
```

`smoke_test.py` runs first on purpose — it exercises every storage path
against a throwaway SQLite file and checks that lid codes never leak into
the public snapshot. If it fails, don't point it at Supabase yet.

With `DATABASE_URL` unset it falls back to local SQLite, so teammates can
work without a Supabase account.

### 4. Verify

```bash
curl localhost:5000/api/health      # database: up
curl localhost:5000/api/database    # batches + bottles, no "code" fields
curl localhost:5000/api/harvests    # [] until you record one
```

**The real test:** create a batch in Chrome, then open the same URL in
incognito. If the batch is there, you're on the database. If not,
something is still local.

### 5. Deploy (Render, free)

render.com → New → Blueprint → connect repo. Set `DATABASE_URL` to the
session pooler string, and `HIVETRUST_SECRET_KEY` (Render can generate
it). The blueprint runs `train_model.py` at build and `migrate_to_db.py`
at start.

Free services sleep after ~15 min idle, ~50s cold start. **Hit your URL a
few minutes before you present.**

### 6. Keepalive — do not skip

Supabase pauses free projects after **7 days of inactivity**, and a paused
project is unreachable until restored by hand. Build now, present in three
weeks, database asleep.

Repo → Settings → Secrets and variables → Actions → New repository secret:
- Name `APP_URL`, value your deployed URL

Then Actions → "Keep Supabase awake" → Run workflow to confirm.

## Security note

The bottle lid code is now `include_code=False` by default —
`to_dict()` omits it unless explicitly asked. The old `public_database()`
built a full copy and popped the secret out on the way, which is one
forgotten `pop` away from leaking every bottle's credential. It's only
returned once, at `POST /api/bottles`, because you have to print it.

`smoke_test.py` asserts this. Keep that test.

## Still worth doing

- **Roles are still `localStorage`.** Anyone can devtools into any role.
  Supabase Auth is free and would fix it properly.
- **The JS ledger at app.js:211 is fake.** See `FRONTEND_PATCH.md`.
- **`predictor()` at app.js:210** bypasses your real RandomForest.

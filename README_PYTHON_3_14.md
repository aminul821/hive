# HiveTrust AI — Python 3.14 Local Version

## Requirements
- Python 3.14
- pip
- Flask 3.1+

## Recommended setup (Windows / VS Code)

Open the HiveTrust_Flask folder in VS Code, then run:

```powershell
py -3.14 -m venv .venv
.venv\\Scripts\\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Open:

`http://127.0.0.1:5000`

## Quick Windows option

Double-click `run.bat`.

## API checks

- `/api/health` — confirms the Flask backend is running.
- `/api/database` — returns the demo database without exposing lid verification codes.

## Current database

The local demo database is:

`data/database.json`

This is intentionally simple for now. Later it can be replaced by PostgreSQL without redesigning the frontend.

## Important security note

The current project is a local prototype. In the production anti-cloning system, hidden lid codes must remain server-side and must never be shipped to the browser or public API.

## Python 3.14 note

The project uses standard Python modules plus Flask. It does not depend on sqlite3, numpy, pandas, or other packages that can create unnecessary Python 3.14 compatibility problems for this stage.

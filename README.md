# HiveTrust AI — Flask (local) version

This is the same HiveTrust AI prototype (Dashboard, Smart Hives, Honey
Batches, Harvest Integrity Engine, Alerts, Blockchain & Security ledger,
Consumer Verify, Research Concept) that previously ran as a single
`index.html` file on Netlify. Nothing about the app's features or
behavior was changed — it's now just organized as a proper Flask
project so it can run on a local server, and the Python code is split
into a few small, easy-to-follow files.

## Project layout

```
HiveTrust_Flask/
├── app.py              # entry point — creates and runs the Flask app
├── config.py           # app configuration
├── routes/
│   ├── __init__.py     # registers blueprints
│   └── main.py         # the "/" route that serves the page
├── templates/
│   └── index.html      # page markup (same structure as the original)
├── static/
│   ├── css/style.css   # extracted, unmodified from the original <style>
│   └── js/app.js       # extracted, unmodified from the original <script>
├── requirements.txt
└── README.md
```

The app is still a client-side single-page app: switching between
Dashboard / Smart Hives / Batches / Harvest Integrity / Alerts /
Ledger / Verify / About all happens in the browser via
`static/js/app.js`, exactly as before. Flask's only job right now is
to serve the page and its assets from a local server instead of
Netlify.

## Run it locally

```bash
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

## Notes

- All logic (hive health prediction, the demo blockchain ledger,
  harvest weight-mismatch checks, CSV export, etc.) is unchanged and
  still runs entirely in the browser (localStorage is still used for
  the role and harvest history, same as the Netlify version).
- Since this is now a real Flask app, it's set up so that any of this
  logic *could* be moved to the backend later (e.g. real routes/API
  endpoints, a database, real authentication) — just say the word for
  whichever piece you want ported over.

## Environment notes and local dev

- The app requires a `SECRET_KEY` in non-development environments. For local development you can set:
  `export HIVETRUST_SECRET_KEY="your-dev-secret"`
  `export FLASK_ENV=development`

- To run locally:
  `python -m venv .venv && . .venv/bin/activate`
  `pip install -r requirements.txt`
  `export HIVETRUST_SECRET_KEY="dev-key" FLASK_ENV=development`
  `python app.py`

- Quick health check:
  `python -c "from app import create_app; print(create_app().test_client().get('/api/health').json)"`

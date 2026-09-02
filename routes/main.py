from pathlib import Path
import json

from flask import Blueprint, jsonify, render_template

main_bp = Blueprint("main", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "data" / "database.json"


def load_database():
    """Load the local JSON database used by the demo."""
    if not DB_FILE.exists():
        return {"schema_version": "0.1-local-demo"}
    with DB_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


@main_bp.get("/")
def index():
    return render_template("index.html")


@main_bp.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "HiveTrust AI",
        "python_database": "JSON local demo",
    })


@main_bp.get("/api/database")
def database():
    # Demo/local phase only. Do not expose secrets in production.
    db = load_database()
    public_db = dict(db)
    for bottle in public_db.get("bottles", []):
        bottle.pop("lid_code", None)
    return jsonify(public_db)

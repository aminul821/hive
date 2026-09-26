"""
config.py
---------
Configuration. Supabase Postgres in production, SQLite locally.

Supabase gives you three connection strings and only one is right here:

  Direct         db.<ref>.supabase.co:5432        IPv6 ONLY on the free tier
  Session pool   <host>.pooler.supabase.com:5432  IPv4 + IPv6, persistent apps
  Transaction    <host>.pooler.supabase.com:6543  IPv4 + IPv6, serverless

Flask under gunicorn is a persistent app, so use SESSION MODE (5432).
Pasting the Direct string into Render or Railway fails with "Network is
unreachable" -- those platforms are IPv4-only and the direct host resolves
to IPv6 only. That error looks like a bug in your code and isn't.

Copy the string from the dashboard (Connect -> Session pooler). Do not
hand-assemble it: the pooler hostname cannot be derived from your region,
and the pooler username is postgres.<project-ref>, not postgres.
"""

import os
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# Load .env HERE, not in app.py.
#
# Everything below reads os.environ at import time, and Python executes a
# class body the moment the module is imported. If .env were loaded in
# app.py after "from config import Config", this module would already have
# run against an empty environment -- so the secret-key check would fire
# even with a perfectly good .env sitting next to it.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass          # python-dotenv is optional; real env vars still work

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _strip_placeholder_brackets(url: str) -> str:
    """
    Remove square brackets left over from Supabase's connection template.

    The dashboard shows the string as
        postgresql://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@[HOST]:5432/postgres
    and it is easy to substitute the values while leaving the brackets in
    place. In a URI, brackets around a host mean an IPv6 literal, so
    urlsplit then tries to parse a domain name as an IPv6 address and dies
    with a message that mentions neither Supabase nor brackets.

    A genuine IPv6 host always contains colons, so brackets whose contents
    have no colon are never a real address -- those we strip.
    """
    at = url.rfind("@")
    if at == -1:
        return url

    userinfo, hostpart = url[:at + 1], url[at + 1:]

    if hostpart.startswith("["):
        close = hostpart.find("]")
        if close != -1 and ":" not in hostpart[1:close]:
            hostpart = hostpart[1:close] + hostpart[close + 1:]

    if "[" in userinfo or "]" in userinfo:
        raise RuntimeError(
            "DATABASE_URL still contains square brackets before the '@'.\n"
            "  [PROJECT-REF] and [YOUR-PASSWORD] are placeholders -- replace\n"
            "  them with your real values and delete the brackets too."
        )

    return userinfo + hostpart


def _normalise_db_url(raw: str):
    """Make a Supabase URL SQLAlchemy-safe and derive engine options."""
    url = raw.strip().strip('"').strip("'")

    # Non-Postgres (sqlite) is returned untouched: round-tripping it
    # through urlsplit collapses the triple slash in sqlite:///path.
    if not url.startswith(("postgres://", "postgresql://", "postgresql+")):
        return url, {}

    # SQLAlchemy dropped the postgres:// alias; Supabase still shows it.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]

    url = _strip_placeholder_brackets(url)

    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise RuntimeError(
            f"DATABASE_URL could not be parsed: {exc}\n"
            "  Most likely cause: square brackets left in from the Supabase\n"
            "  template. [PROJECT-REF], [YOUR-PASSWORD] and [POOLER-HOST] are\n"
            "  placeholders -- delete the brackets along with the text inside."
        ) from exc

    query = dict(parse_qsl(parts.query))
    host = parts.hostname or ""
    is_transaction_mode = "pooler.supabase.com" in host and parts.port == 6543

    # Supabase terminates non-TLS connections. Be explicit rather than
    # relying on libpq defaults, which differ across environments.
    query.setdefault("sslmode", "require")
    # Fail fast instead of hanging for two minutes if the project is paused.
    query.setdefault("connect_timeout", "10")
    query.setdefault("application_name", "hivetrust")

    url = urlunsplit((parts.scheme, parts.netloc, parts.path,
                      urlencode(query), parts.fragment))

    options = {"pool_pre_ping": True}    # pooler drops idle connections
    if is_transaction_mode:
        # Transaction mode gives a different backend per statement, so a
        # client-side pool is harmful and prepared statements break.
        try:
            from sqlalchemy.pool import NullPool
            options["poolclass"] = NullPool
        except ImportError:
            pass
    else:
        # Keep the pool small: gunicorn multiplies this by worker count,
        # and the free tier allows fewer connections than you'd guess.
        options["pool_size"] = int(os.getenv("DB_POOL_SIZE", "5"))
        options["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "2"))
        options["pool_recycle"] = 1800

    return url, options


def _resolve_database():
    raw = (os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL") or "").strip()

    if not raw:
        # Local fallback so teammates can run the app with no Supabase account.
        path = os.path.join(BASE_DIR, "data", "hivetrust.db")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return f"sqlite:///{path}", {}, "sqlite (local file)"

    url, options = _normalise_db_url(raw)

    if "pooler.supabase.com" in url:
        mode = "transaction pooler" if ":6543" in url else "session pooler"
        label = f"supabase ({mode})"
    elif ".supabase.co" in url:
        label = "supabase (DIRECT -- IPv6 only, fails on IPv4 hosts)"
    elif url.startswith("postgresql"):
        label = "postgres"
    else:
        label = "sqlite"

    return url, options, label


class Config:
    """Configuration for HiveTrust AI."""

    ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    SECRET_KEY = os.environ.get("HIVETRUST_SECRET_KEY", "dev-only-change-me")

    if ENV != "development" and SECRET_KEY == "dev-only-change-me":
        raise RuntimeError(
            "HIVETRUST_SECRET_KEY is not set and FLASK_ENV is not "
            "'development'.\n"
            "  Local fix:  put these two lines in .env --\n"
            "                FLASK_ENV=development\n"
            "                HIVETRUST_SECRET_KEY=any-random-string\n"
            "  Deploy fix: set HIVETRUST_SECRET_KEY in your host's "
            "environment variables.\n"
            f"  (.env expected at: {os.path.join(BASE_DIR, '.env')})"
        )

    SQLALCHEMY_DATABASE_URI, SQLALCHEMY_ENGINE_OPTIONS, DB_LABEL = _resolve_database()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JSON_SORT_KEYS = False

    @staticmethod
    def warn_if_fragile(app):
        """
        Shout about configurations that will lose data.

        SQLite on a free host is the trap: the app boots, works in
        testing, then silently resets on every redeploy because the
        filesystem is ephemeral. Better to see it in the logs on day one.
        """
        uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        env = app.config.get("ENV", "production")

        if env != "development" and uri.startswith("sqlite"):
            app.logger.warning(
                "DATABASE_URL is not set. Falling back to SQLite, which is "
                "EPHEMERAL on Render/Railway/Fly -- every record will be lost "
                "on the next deploy. Set DATABASE_URL to your Supabase "
                "session pooler string."
            )

        if ".supabase.co:" in uri and "pooler" not in uri:
            app.logger.warning(
                "Using the Supabase DIRECT connection (IPv6 only). If this "
                "host is IPv4-only the connection will fail. Switch to the "
                "Session pooler string on port 5432."
            )

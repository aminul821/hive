import os


class Config:
    """Configuration for the local HiveTrust AI demo."""

    # Use FLASK_ENV to detect production vs development. Default to 'production'
    ENV = os.environ.get("FLASK_ENV", "production")

    # Do not enable debug by default. Use FLASK_DEBUG=1 to enable for development.
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    # Secret key is required in production. A dev-only fallback exists for local testing,
    # but the app will refuse to start in non-development environments when the
    # default dev key is still present.
    SECRET_KEY = os.environ.get("HIVETRUST_SECRET_KEY", "dev-only-change-me")

    if ENV != "development" and SECRET_KEY == "dev-only-change-me":
        raise RuntimeError(
            "HIVETRUST_SECRET_KEY must be set in production (set the environment variable)."
        )

import os


class Config:
    """Configuration for the local HiveTrust AI demo."""

    SECRET_KEY = os.environ.get("HIVETRUST_SECRET_KEY", "dev-only-change-me")
    DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"

from flask import Flask
from config import Config
from models import db
from routes import register_blueprints
import logging
import os
from dotenv import load_dotenv

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    register_blueprints(app)

    logging.basicConfig(level=logging.INFO)
    Config.warn_if_fragile(app)
    app.logger.info("Database: %s", app.config.get("DB_LABEL"))

    return app


app = create_app()


if __name__ == "__main__":
    # The Flask dev server is not safe for production; gunicorn is used
    # there instead (see Procfile).
    if app.config.get("ENV") == "development":
        port = int(os.environ.get("PORT", 5000))
        app.run(host="127.0.0.1", port=port,
                debug=app.config.get("DEBUG", False))
    else:
        raise RuntimeError(
            "Refusing to run the Flask development server in a "
            "non-development environment. Use a WSGI server instead."
        )

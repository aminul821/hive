from flask import Flask
from config import Config
from routes import register_blueprints
import logging


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    register_blueprints(app)
    logging.basicConfig(level=logging.INFO)
    return app


app = create_app()


if __name__ == "__main__":
    # Only run the Flask development server in development
    if app.config.get("ENV") == "development":
        app.run(host="127.0.0.1", port=5000, debug=app.config.get("DEBUG", False))
    else:
        raise RuntimeError("Refusing to run the Flask development server in a non-development environment. Use a WSGI server instead.")

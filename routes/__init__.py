"""
routes/__init__.py
-------------------
Collects and registers all Flask blueprints for the app.
Add new page/route modules here as the project grows.
"""

from .main import main_bp


def register_blueprints(app):
    app.register_blueprint(main_bp)

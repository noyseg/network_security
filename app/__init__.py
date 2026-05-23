"""Application factory.

The factory builds a Flask app from a configuration object. It is responsible
for:

* applying configuration,
* ensuring the data directory exists,
* initializing the SQLite schema,
* registering each feature module's blueprint,
* registering the request-teardown DB connection close.

Feature modules are imported lazily inside ``create_app`` so this file does
not need to know their internals.
"""

import os

from flask import Flask

from config import Config


def create_app(config_object: type = Config) -> Flask:
    """Build and return a configured Flask app."""

    if not getattr(config_object, "DB_PATH", None):
        raise ValueError("Config must define DB_PATH")

    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "..", "static"),
    )
    app.config.from_object(config_object)

    # Make sure the data directory exists before the schema bootstrap runs.
    db_dir = os.path.dirname(app.config["DB_PATH"])
    os.makedirs(db_dir, exist_ok=True)

    # Initialize the database schema (idempotent).
    from app import db as db_module

    db_module.init_schema()

    # Close the per-request DB connection on teardown.
    app.teardown_appcontext(db_module.close_connection)

    # --- Register feature blueprints ------------------------------------
    # Imported here (not at module top) so that each feature module can
    # itself import from ``app`` without circular imports.

    # Feature modules will be added in subsequent commits:
    #   - app.campaign.routes
    #   - app.message.routes
    #   - app.landing.routes
    #   - app.logging_mod.routes
    #   - app.dashboard.routes

    @app.get("/")
    def _index():
        return (
            "Phishing simulation platform — local/lab use only. "
            "See /admin/campaigns once that blueprint is wired up.",
            200,
        )

    return app

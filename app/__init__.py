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

from flask import Flask, redirect

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

    db_dir = os.path.dirname(app.config["DB_PATH"])
    os.makedirs(db_dir, exist_ok=True)

    from app import db as db_module
    db_module.init_schema()
    app.teardown_appcontext(db_module.close_connection)

    from app.campaign.routes import bp as campaign_bp
    from app.message.routes import bp as message_bp

    app.register_blueprint(campaign_bp)
    app.register_blueprint(message_bp)

    # Feature modules still to be added in subsequent commits:
    #   - app.landing.routes
    #   - app.logging_mod.routes
    #   - app.dashboard.routes

    @app.get("/")
    def _index():
        return redirect("/admin/campaigns")

    return app

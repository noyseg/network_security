"""Entry point for the phishing-simulation platform.

This module exists to keep run-time concerns (host, port) separate from the
application factory in ``app/__init__.py``. The server **always** binds to
``127.0.0.1`` — this is part of the project's ethical safety contract.
"""

from app import create_app
from config import Config


app = create_app()


if __name__ == "__main__":
    # Bind to localhost ONLY. Do not change this without updating
    # PLANNING.md, IMPLEMENTATION_PLAN.md, and the ethics tests.
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)

"""Entry point for the phishing-simulation platform.

This module exists to keep run-time concerns (host, port) separate from the
application factory in ``app/__init__.py``. The server **always** binds to
``127.0.0.1`` — this is part of the project's ethical safety contract.

A tiny ``.env`` loader runs first so per-machine settings (e.g. SMTP
credentials for the opt-in mail mode) can live in a gitignored ``.env``
file rather than being typed into the shell every run.
"""

import os


def _load_dotenv(path: str = ".env") -> None:
    """Populate ``os.environ`` from a simple KEY=VALUE file.

    Stdlib only (no python-dotenv dependency). Lines starting with ``#`` are
    comments; blank lines are ignored; surrounding quotes are stripped. An
    existing value in the real environment always wins, so anything you set
    in the shell overrides the file.
    """
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key, value)


_load_dotenv()

from app import create_app  # noqa: E402  (env must be loaded before imports)
from config import Config   # noqa: E402


app = create_app()


if __name__ == "__main__":
    # Bind to localhost ONLY. Do not change this without updating
    # PLANNING.md, IMPLEMENTATION_PLAN.md, and the ethics tests.
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)

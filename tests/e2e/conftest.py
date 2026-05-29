"""Fixtures for the browser-driven end-to-end tests.

``live_server`` runs the real Flask app in a background thread against a
fresh temporary SQLite database on an OS-assigned port, so a real browser
(driven by Playwright) can exercise the whole stack over HTTP. DEMO_MODE
stays off, so the database starts empty and the first campaign created in
a test gets id 1.
"""

import os
import socket
import tempfile
import threading
import time

import pytest


@pytest.fixture
def live_server():
    from config import Config
    from werkzeug.serving import make_server

    fd, db_path = tempfile.mkstemp(prefix="phishing_e2e_", suffix=".sqlite")
    os.close(fd)
    os.remove(db_path)  # let create_app's init_schema build a fresh DB

    original_db = Config.DB_PATH
    Config.DB_PATH = db_path
    try:
        from app import create_app
        app = create_app()

        # Port 0 -> OS-assigned ephemeral port, so this never collides with a
        # dev server already running on 5000. threaded=True lets the browser
        # load sub-resources (CSS/JS/pixel) concurrently with the page.
        server = make_server("127.0.0.1", 0, app, threaded=True)
        port = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        _wait_until_listening("127.0.0.1", port)

        try:
            yield {"url": f"http://127.0.0.1:{port}", "db_path": db_path}
        finally:
            server.shutdown()
            thread.join(timeout=5)
    finally:
        Config.DB_PATH = original_db
        try:
            os.remove(db_path)
        except OSError:
            pass


def _wait_until_listening(host: str, port: int, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(f"live server did not start on {host}:{port}")

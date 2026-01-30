import os
from flask import Flask

def configure_session(app: Flask, cookie_secure: bool) -> None:
    # Harden session cookies
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if cookie_secure:
        app.config["SESSION_COOKIE_SECURE"] = True

def add_security_headers(app: Flask) -> None:
    pod = os.environ.get("HOSTNAME", "unknown")

    @app.after_request
    def _headers(resp):
        # Helps debug pod switching / LB behaviour
        resp.headers["X-Pod"] = pod

        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return resp


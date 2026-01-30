import os
from flask import Flask, request

def configure_session(app: Flask, cookie_secure: bool) -> None:
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
        # Debug headers
        resp.headers["X-Pod"] = pod

        # Best-effort client IP (for debugging only; may be LB/node IP depending on topology)
        xff = request.headers.get("X-Forwarded-For", "")
        client_ip = xff.split(",")[0].strip() if xff else (request.remote_addr or "unknown")
        resp.headers["X-Client-IP"] = client_ip

        # Security headers
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return resp


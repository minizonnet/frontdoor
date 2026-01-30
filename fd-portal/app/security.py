import os
from flask import Flask

def add_security_headers(app: Flask) -> None:
    pod = os.environ.get("HOSTNAME", "unknown")
    @app.after_request
    def _headers(resp):
        resp.headers["X-Pod"] = pod
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return resp


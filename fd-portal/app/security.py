from flask import Flask

def configure_session(app: Flask, cookie_secure: bool) -> None:
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if cookie_secure:
        app.config["SESSION_COOKIE_SECURE"] = True

def add_security_headers(app: Flask) -> None:
    @app.after_request
    def _headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return resp

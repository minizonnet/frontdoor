import os
from flask import Flask
from config import Settings
from keystone import KeystoneClient
from ratelimit import RateLimiter
from security import configure_session, add_security_headers
from routes import build_blueprint

def create_app() -> Flask:
    app = Flask(__name__)

    # Flask session signing key
    app.secret_key = os.environ.get("FLASK_SECRET", "CHANGE_ME_LONG_RANDOM")

    settings = Settings()

    configure_session(app, cookie_secure=settings.session_cookie_secure)
    add_security_headers(app)

    keystone_client = KeystoneClient(settings.keystone_url, settings.user_domain)
    limiter = RateLimiter(settings.login_window_sec, settings.login_max_attempts)

    # Provide brand variables to all templates
    @app.context_processor
    def _brand():
        return {
            "brand_name": settings.brand_name,
            "product_name": settings.product_name,
            "logo_url": settings.logo_url,
            "bg_img_url": settings.bg_img_url,
            "accent_img_url": settings.accent_img_url,
            "hero_img_url": settings.hero_img_url,
        }

    app.register_blueprint(build_blueprint(settings, keystone_client, limiter))

    return app

# Gunicorn entrypoint: gunicorn -b 0.0.0.0:8000 app:app
app = create_app()

if __name__ == "__main__":
    app.run("127.0.0.1", 8000, debug=False)

import os
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Settings
from keystone import KeystoneClient
from security import configure_session, add_security_headers
from routes import build_blueprint
from ratelimit import LoginDefense


def create_app() -> Flask:
    app = Flask(__name__)

    # Respect X-Forwarded-* headers when behind LB/Ingress
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Flask session signing key
    app.secret_key = os.environ.get("FLASK_SECRET", "CHANGE_ME_LONG_RANDOM")

    settings = Settings()

    configure_session(app, cookie_secure=settings.session_cookie_secure)
    add_security_headers(app)

    keystone_client = KeystoneClient(settings.keystone_url, settings.user_domain)

    defense = LoginDefense(
        window_sec=settings.defense_window_sec,
        soft_lockout_sec=settings.defense_soft_lockout_sec,
        captcha_after_failures=settings.defense_captcha_after_failures,
        max_failures_before_block=settings.defense_max_failures_before_block,
    )

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

    app.register_blueprint(build_blueprint(settings, keystone_client, defense))
    return app


# Gunicorn entrypoint: app:app
app = create_app()

if __name__ == "__main__":
    app.run("127.0.0.1", 8000, debug=False)


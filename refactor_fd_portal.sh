#!/usr/bin/env bash
set -euo pipefail

APPDIR="fd-portal/app"

if [[ ! -d "${APPDIR}" ]]; then
  echo "ERROR: ${APPDIR} not found. Run from repo root where fd-portal/ exists."
  exit 1
fi

# Backup old single-file app if present
if [[ -f "${APPDIR}/app.py" ]]; then
  cp -a "${APPDIR}/app.py" "${APPDIR}/app_legacy.py"
  echo "Backed up ${APPDIR}/app.py -> ${APPDIR}/app_legacy.py"
fi

# Create structure
mkdir -p \
  "${APPDIR}/templates" \
  "${APPDIR}/static/css" \
  "${APPDIR}/static/img"

# requirements.txt
cat > "${APPDIR}/requirements.txt" <<'EOF'
flask==3.0.3
gunicorn==22.0.0
requests==2.32.3
EOF

# config.py
cat > "${APPDIR}/config.py" <<'EOF'
import os
from dataclasses import dataclass

def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")

@dataclass(frozen=True)
class Settings:
    # OpenStack / portal config
    keystone_url: str = os.environ.get("KEYSTONE_URL", "https://keystone.example.com/v3").rstrip("/")
    user_domain: str = os.environ.get("USER_DOMAIN", "Default")
    horizon_url: str = os.environ.get("HORIZON_URL", "https://opole.minizon.net/")

    # Branding (can point to your website, or host locally under /static/img)
    brand_name: str = os.environ.get("BRAND_NAME", "MINIZON")
    product_name: str = os.environ.get("PRODUCT_NAME", "Front Door")
    logo_url: str = os.environ.get("LOGO_URL", "https://www.minizon.net/wp-content/uploads/2024/04/removal.ai_70e9af3b-2239-4e31-9862-895263aa24ef-minizon-e1713863761615.png")
    bg_img_url: str = os.environ.get("BG_IMG_URL", "https://www.minizon.net/wp-content/themes/bizboost/assets/images/promotional-contact.jpg")
    accent_img_url: str = os.environ.get("ACCENT_IMG_URL", "https://www.minizon.net/wp-content/uploads/2024/08/cloudstorage-349x349-1.png")
    hero_img_url: str = os.environ.get("HERO_IMG_URL", "https://www.minizon.net/wp-content/themes/bizboost/assets/images/hero-content.png")

    # Security / sessions
    session_cookie_secure: bool = _env_bool("SESSION_COOKIE_SECURE", True)

    # Rate limiting (in-memory, per pod)
    login_window_sec: int = int(os.environ.get("LOGIN_WINDOW_SEC", "60"))
    login_max_attempts: int = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "10"))
    trust_x_forwarded_for: bool = _env_bool("TRUST_X_FORWARDED_FOR", True)
EOF

# keystone.py
cat > "${APPDIR}/keystone.py" <<'EOF'
import requests

class KeystoneClient:
    def __init__(self, keystone_url: str, user_domain: str):
        self.keystone_url = keystone_url.rstrip("/")
        self.user_domain = user_domain

    def validate_password(self, username: str, password: str) -> None:
        """
        Validate Keystone credentials using POST /v3/auth/tokens.
        Success: HTTP 201 and X-Subject-Token header.
        We do NOT store the token (this portal is a gate, not SSO).
        """
        url = f"{self.keystone_url}/auth/tokens"
        payload = {
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {
                            "name": username,
                            "domain": {"name": self.user_domain},
                            "password": password,
                        }
                    },
                }
            }
        }

        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 201:
            raise ValueError("Invalid credentials")
        if not r.headers.get("X-Subject-Token"):
            raise ValueError("Missing Keystone token header")
EOF

# ratelimit.py
cat > "${APPDIR}/ratelimit.py" <<'EOF'
import time
from collections import defaultdict, deque

class RateLimiter:
    """
    Simple in-memory rate limiter (per pod). Good enough for stage-1.
    For multi-replica strictness, move state to Redis later.
    """
    def __init__(self, window_sec: int, max_attempts: int):
        self.window_sec = window_sec
        self.max_attempts = max_attempts
        self._hits = defaultdict(lambda: deque())

    def limited(self, key: str) -> bool:
        now = time.time()
        q = self._hits[key]
        while q and (now - q[0]) > self.window_sec:
            q.popleft()
        return len(q) >= self.max_attempts

    def note(self, key: str) -> None:
        self._hits[key].append(time.time())
EOF

# security.py
cat > "${APPDIR}/security.py" <<'EOF'
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
EOF

# routes.py
cat > "${APPDIR}/routes.py" <<'EOF'
from flask import Blueprint, request, session, redirect, url_for, render_template

def _client_ip(trust_xff: bool) -> str:
    if trust_xff:
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"

def build_blueprint(settings, keystone_client, limiter):
    bp = Blueprint("fd", __name__)

    @bp.get("/")
    def home():
        if not session.get("logged_in"):
            return redirect(url_for("fd.login"))
        return render_template(
            "home.html",
            username=session.get("username"),
            horizon_url=settings.horizon_url,
        )

    @bp.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            return render_template("login.html", error=None)

        ip = _client_ip(settings.trust_x_forwarded_for)
        if limiter.limited(ip):
            return render_template("login.html", error="Too many attempts. Try again later."), 429

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render_template("login.html", error="Missing username/password"), 400

        try:
            keystone_client.validate_password(username, password)
        except Exception:
            limiter.note(ip)
            return render_template("login.html", error="Invalid credentials"), 401

        session.clear()
        session["logged_in"] = True
        session["username"] = username
        return redirect(url_for("fd.home"))

    @bp.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("fd.login"))

    return bp
EOF

# templates/base.html
cat > "${APPDIR}/templates/base.html" <<'EOF'
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ product_name }} • {{ brand_name }}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/main.css') }}">
</head>
<body style="--bg-img: url('{{ bg_img_url }}'); --hero-img: url('{{ hero_img_url }}'); --accent-img: url('{{ accent_img_url }}');">
  <div class="floaters" aria-hidden="true">
    <div class="floater" style="left: 8%; top: 18%; animation-delay: -1s;"></div>
    <div class="floater" style="left: 16%; top: 72%; animation-delay: -6s;"></div>
    <div class="floater" style="left: 32%; top: 38%; animation-delay: -3s;"></div>
    <div class="floater" style="left: 52%; top: 16%; animation-delay: -8s;"></div>
    <div class="floater" style="left: 72%; top: 30%; animation-delay: -4s;"></div>
    <div class="floater" style="left: 86%; top: 66%; animation-delay: -10s;"></div>
    <div class="floater" style="left: 92%; top: 22%; animation-delay: -2s;"></div>
    <div class="floater" style="left: 40%; top: 84%; animation-delay: -12s;"></div>
  </div>

  <div class="scene">
    <div class="wrap">
      <div class="brand">
        <div class="logoBox">
          <img class="logoImg" src="{{ logo_url }}" alt="{{ brand_name }} logo">
        </div>
        <div>
          <p class="title">{{ product_name }}</p>
          <p class="subtitle">{% block subtitle %}{% endblock %}</p>
        </div>
      </div>

      <div class="card">
        {% block card %}{% endblock %}
      </div>
    </div>

    <div class="side">
      <h3>{{ brand_name }} Cloud Console</h3>
      <p>
        Controlled entry point for Horizon. Next: project/role authorization and then real WebSSO when you’re ready.
      </p>
      <div class="chips">
        <div class="chip">Kubernetes</div>
        <div class="chip">OpenStack</div>
        <div class="chip">Keystone v3</div>
        <div class="chip">Horizon</div>
      </div>
    </div>
  </div>
</body>
</html>
EOF

# templates/login.html
cat > "${APPDIR}/templates/login.html" <<'EOF'
{% extends "base.html" %}
{% block subtitle %}Sign in with Keystone credentials to reach your cloud console{% endblock %}

{% block card %}
  <div class="topline">
    <div class="pill">{{ brand_name }}</div>
    <div class="pill">Keystone v3 • Password</div>
  </div>

  {% if error %}
    <div class="alert">{{ error }}</div>
  {% endif %}

  <form method="post" autocomplete="on">
    <div class="row">
      <label>Username</label>
      <input name="username" autocomplete="username" required>
    </div>

    <div class="row">
      <label>Password</label>
      <input name="password" type="password" autocomplete="current-password" required>
    </div>

    <div class="row">
      <button class="btn" type="submit">Sign in</button>
    </div>
  </form>

  <div class="muted">
    This validates Keystone credentials and opens the portal. It does not create an SSO session in Horizon yet.
  </div>
{% endblock %}
EOF

# templates/home.html
cat > "${APPDIR}/templates/home.html" <<'EOF'
{% extends "base.html" %}
{% block subtitle %}Access granted{% endblock %}

{% block card %}
  <div class="topline">
    <div class="pill">User: {{ username }}</div>
    <div class="pill">{{ brand_name }}</div>
  </div>

  <div class="row">
    <a class="link" href="{{ horizon_url }}">Open Horizon</a>
  </div>

  <div class="row">
    <form method="post" action="/logout">
      <button class="btn" type="submit">Logout</button>
    </form>
  </div>

  <div class="muted">
    Next: enforce authorization (project/role allowlist) before granting access.
  </div>
{% endblock %}
EOF

# static/css/main.css
cat > "${APPDIR}/static/css/main.css" <<'EOF'
:root {
  --bg0: #070b14;
  --bg1: #0b1220;
  --card: rgba(255,255,255,0.06);
  --text: #e8eefc;
  --muted: rgba(232,238,252,0.72);
  --accent: #6ee7ff;
  --accent2: #a78bfa;
  --danger: #ff6b6b;
  --shadow: 0 18px 50px rgba(0,0,0,0.45);
  --radius: 18px;
  --ring: rgba(110,231,255,0.14);

  /* passed in via <body style="--bg-img: url(...)"> */
  --bg-img: none;
  --hero-img: none;
  --accent-img: none;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  min-height: 100vh;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, "Noto Sans", Arial;
  color: var(--text);
  background:
    radial-gradient(1200px 700px at 15% 15%, rgba(110,231,255,0.18), transparent 55%),
    radial-gradient(900px 600px at 85% 25%, rgba(167,139,250,0.18), transparent 50%),
    radial-gradient(900px 700px at 50% 90%, rgba(110,231,255,0.10), transparent 55%),
    linear-gradient(180deg, var(--bg0), var(--bg1));
  display: grid;
  place-items: center;
  padding: 28px;
  overflow: hidden;
}

body::before {
  content: "";
  position: fixed;
  inset: 0;
  background-image: var(--bg-img);
  background-size: cover;
  background-position: center;
  opacity: 0.08;
  filter: saturate(0.7) contrast(1.1);
  pointer-events: none;
  z-index: 0;
}

.scene {
  position: relative;
  width: 100%;
  max-width: 980px;
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 18px;
  align-items: stretch;
  z-index: 1;
}

@media (max-width: 900px) {
  .scene { grid-template-columns: 1fr; max-width: 520px; }
  .side { display: none; }
}

.wrap { width: 100%; max-width: 520px; }

.brand {
  display:flex; align-items:center; gap:12px;
  margin: 0 0 14px 0;
}

.logoBox {
  width: 46px; height: 46px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(110,231,255,0.18), rgba(167,139,250,0.18));
  border: 1px solid rgba(255,255,255,0.12);
  display: grid;
  place-items: center;
  box-shadow: 0 10px 25px rgba(0,0,0,0.35);
  overflow: hidden;
}

.logoImg {
  width: 44px;
  height: 44px;
  object-fit: contain;
  filter: invert(1) brightness(1.25) contrast(1.05);
  opacity: 0.95;
}

.title { font-size: 20px; font-weight: 800; margin:0; letter-spacing: 0.3px; }
.subtitle { margin: 4px 0 0 0; color: var(--muted); font-size: 13px; line-height: 1.3; }

.card {
  position: relative;
  background: linear-gradient(180deg, var(--card), rgba(255,255,255,0.04));
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 18px;
  backdrop-filter: blur(10px);
  overflow: hidden;
}

.card::before {
  content: "";
  position: absolute;
  right: -60px;
  bottom: -70px;
  width: 260px;
  height: 260px;
  background-image: var(--accent-img);
  background-size: contain;
  background-repeat: no-repeat;
  opacity: 0.12;
  transform: rotate(-10deg);
  pointer-events: none;
}

.topline { display:flex; justify-content: space-between; align-items:center; gap:10px; flex-wrap: wrap; }
.pill {
  font-size: 11px;
  color: rgba(232,238,252,0.85);
  border: 1px solid rgba(255,255,255,0.14);
  background: rgba(255,255,255,0.06);
  padding: 6px 10px;
  border-radius: 999px;
  white-space: nowrap;
}

.row { margin-top: 12px; }
label { display:block; font-size: 12px; color: var(--muted); margin: 0 0 6px; }
input {
  width: 100%;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(0,0,0,0.20);
  color: var(--text);
  padding: 12px 12px;
  outline: none;
}
input:focus {
  border-color: rgba(110,231,255,0.55);
  box-shadow: 0 0 0 4px var(--ring);
}

.btn {
  width: 100%;
  border: 0;
  border-radius: 12px;
  padding: 12px 14px;
  color: #06101c;
  font-weight: 800;
  cursor: pointer;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  box-shadow: 0 14px 30px rgba(0,0,0,0.35);
  transition: transform 0.08s ease, filter 0.08s ease;
}
.btn:hover { filter: brightness(1.03); }
.btn:active { transform: translateY(1px); }

.alert {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(255,107,107,0.35);
  background: rgba(255,107,107,0.10);
  color: #ffd1d1;
  font-size: 13px;
}

.muted {
  margin-top: 12px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.35;
}

.link {
  display: inline-block;
  padding: 10px 12px;
  border-radius: 12px;
  text-decoration: none;
  color: var(--text);
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(255,255,255,0.06);
}
.link:hover { border-color: rgba(110,231,255,0.35); }

/* Right-side hero panel */
.side {
  position: relative;
  border-radius: var(--radius);
  border: 1px solid rgba(255,255,255,0.10);
  background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.03));
  box-shadow: var(--shadow);
  overflow: hidden;
  padding: 18px;
  backdrop-filter: blur(10px);
}
.side::before {
  content: "";
  position: absolute;
  inset: -40px -60px -40px -60px;
  background-image: var(--hero-img);
  background-repeat: no-repeat;
  background-size: 520px;
  background-position: 70% 40%;
  opacity: 0.25;
  filter: saturate(1.0) contrast(1.1);
  pointer-events: none;
}
.side h3 { margin: 0; font-size: 16px; letter-spacing: 0.2px; }
.side p {
  margin: 8px 0 0 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.35;
  max-width: 320px;
}
.side .chips { margin-top: 14px; display:flex; flex-wrap:wrap; gap:10px; }
.chip {
  border-radius: 999px;
  padding: 8px 10px;
  font-size: 12px;
  border: 1px solid rgba(255,255,255,0.14);
  background: rgba(255,255,255,0.06);
  color: rgba(232,238,252,0.85);
}

/* Floating blobs */
.floaters {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  opacity: 0.9;
}

.floater {
  position: absolute;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: radial-gradient(circle at 30% 30%, rgba(110,231,255,0.85), rgba(167,139,250,0.35));
  box-shadow: 0 0 0 10px rgba(110,231,255,0.06);
  animation: drift 10s ease-in-out infinite;
}

.floater:nth-child(2n) {
  width: 12px;
  height: 12px;
  background: radial-gradient(circle at 30% 30%, rgba(167,139,250,0.9), rgba(110,231,255,0.25));
  box-shadow: 0 0 0 12px rgba(167,139,250,0.05);
  animation-duration: 13s;
}

.floater:nth-child(3n) {
  width: 22px;
  height: 22px;
  animation-duration: 16s;
  box-shadow: 0 0 0 16px rgba(110,231,255,0.04);
  opacity: 0.85;
}

@keyframes drift {
  0%   { transform: translate3d(0, 0, 0) scale(1); }
  50%  { transform: translate3d(0, -22px, 0) scale(1.08); }
  100% { transform: translate3d(0, 0, 0) scale(1); }
}
EOF

# app.py (entrypoint for gunicorn: app:app)
cat > "${APPDIR}/app.py" <<'EOF'
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
EOF

echo "Refactor complete."
echo "What changed:"
echo "  - Old fd-portal/app/app.py backed up to fd-portal/app/app_legacy.py (if it existed)"
echo "  - New modules: config.py, keystone.py, ratelimit.py, security.py, routes.py"
echo "  - Templates: fd-portal/app/templates/*.html"
echo "  - CSS: fd-portal/app/static/css/main.css"
echo ""
echo "Next:"
echo "  docker build -t tomtek/fd-portal:01 -f fd-portal/container/Dockerfile fd-portal"
echo "  docker run --rm -p 8000:8000 tomtek/fd-portal:01"


import os
import requests
from flask import Flask, request, session, redirect, url_for, render_template_string

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "CHANGE_ME_LONG_RANDOM")

KEYSTONE_URL = os.environ.get("KEYSTONE_URL", "https://keystone.example.com/v3").rstrip("/")
USER_DOMAIN = os.environ.get("USER_DOMAIN", "Default")
HORIZON_URL = os.environ.get("HORIZON_URL", "https://opole.minizon.net/")

# Branding / images (defaults are from minizon.net; override via env if you want)
BRAND_NAME = os.environ.get("BRAND_NAME", "MINIZON")
LOGO_URL = os.environ.get(
    "LOGO_URL",
    "https://www.minizon.net/wp-content/uploads/2024/04/removal.ai_70e9af3b-2239-4e31-9862-895263aa24ef-minizon-e1713863761615.png",
)
HERO_IMG_URL = os.environ.get(
    "HERO_IMG_URL",
    "https://www.minizon.net/wp-content/themes/bizboost/assets/images/hero-content.png",
)
ACCENT_IMG_URL = os.environ.get(
    "ACCENT_IMG_URL",
    "https://www.minizon.net/wp-content/uploads/2024/08/cloudstorage-349x349-1.png",
)
BG_IMG_URL = os.environ.get(
    "BG_IMG_URL",
    "https://www.minizon.net/wp-content/themes/bizboost/assets/images/promotional-contact.jpg",
)

BASE_CSS = """
<style>
  :root {
    --bg0: #070b14;
    --bg1: #0b1220;
    --card: rgba(255,255,255,0.06);
    --card2: rgba(255,255,255,0.08);
    --text: #e8eefc;
    --muted: rgba(232,238,252,0.72);
    --accent: #6ee7ff;
    --accent2: #a78bfa;
    --danger: #ff6b6b;
    --shadow: 0 18px 50px rgba(0,0,0,0.45);
    --radius: 18px;
    --ring: rgba(110,231,255,0.14);
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

  /* subtle background photo wash (optional) */
  body::before {
    content: "";
    position: fixed;
    inset: 0;
    background-image: url("__BG_IMG_URL__");
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
    /* logo is dark-on-transparent; invert helps on dark background */
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

  /* watermark image inside card */
  .card::before {
    content: "";
    position: absolute;
    right: -60px;
    bottom: -70px;
    width: 260px;
    height: 260px;
    background-image: url("__ACCENT_IMG_URL__");
    background-size: contain;
    background-repeat: no-repeat;
    opacity: 0.12;
    filter: saturate(1.1);
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
    background-image: url("__HERO_IMG_URL__");
    background-repeat: no-repeat;
    background-size: 520px;
    background-position: 70% 40%;
    opacity: 0.25;
    filter: saturate(1.0) contrast(1.1);
    pointer-events: none;
    transform: translateZ(0);
  }
  .side h3 {
    margin: 0;
    font-size: 16px;
    letter-spacing: 0.2px;
  }
  .side p {
    margin: 8px 0 0 0;
    color: var(--muted);
    font-size: 13px;
    line-height: 1.35;
    max-width: 320px;
  }
  .side .chips {
    margin-top: 14px;
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }
  .chip {
    border-radius: 999px;
    padding: 8px 10px;
    font-size: 12px;
    border: 1px solid rgba(255,255,255,0.14);
    background: rgba(255,255,255,0.06);
    color: rgba(232,238,252,0.85);
  }

  /* Floating “vector” blobs */
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
    filter: blur(0.1px);
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
</style>
"""

LOGIN_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Front Door</title>
  __BASE_CSS__
</head>
<body>
  <div class="floaters">
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
          <img class="logoImg" src="__LOGO_URL__" alt="__BRAND_NAME__ logo">
        </div>
        <div>
          <p class="title">Front Door</p>
          <p class="subtitle">Sign in with Keystone credentials to reach your cloud console</p>
        </div>
      </div>

      <div class="card">
        <div class="topline">
          <div class="pill">__BRAND_NAME__</div>
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
          This validates your Keystone credentials and opens the portal.
          It does not create an SSO session in Horizon yet.
        </div>
      </div>
    </div>

    <div class="side">
      <h3>Minizon Cloud Console</h3>
      <p>
        Use the portal as a controlled entry point. Next iteration: add role/project checks and
        then move to real WebSSO when you’re ready.
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
"""

HOME_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Front Door</title>
  __BASE_CSS__
</head>
<body>
  <div class="floaters">
    <div class="floater" style="left: 10%; top: 24%; animation-delay: -2s;"></div>
    <div class="floater" style="left: 22%; top: 78%; animation-delay: -7s;"></div>
    <div class="floater" style="left: 44%; top: 34%; animation-delay: -4s;"></div>
    <div class="floater" style="left: 58%; top: 18%; animation-delay: -9s;"></div>
    <div class="floater" style="left: 76%; top: 36%; animation-delay: -5s;"></div>
    <div class="floater" style="left: 88%; top: 70%; animation-delay: -11s;"></div>
  </div>

  <div class="scene">
    <div class="wrap">
      <div class="brand">
        <div class="logoBox">
          <img class="logoImg" src="__LOGO_URL__" alt="__BRAND_NAME__ logo">
        </div>
        <div>
          <p class="title">Front Door</p>
          <p class="subtitle">Access granted</p>
        </div>
      </div>

      <div class="card">
        <div class="topline">
          <div class="pill">User: {{ username }}</div>
          <div class="pill">__BRAND_NAME__</div>
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
      </div>
    </div>

    <div class="side">
      <h3>Console shortcut</h3>
      <p>
        This link goes to your Horizon URL. If you later proxy Horizon behind the portal,
        we can enforce “no-bypass” access.
      </p>
      <div class="chips">
        <div class="chip">console.minizon.net</div>
        <div class="chip">opole.minizon.net</div>
      </div>
    </div>
  </div>
</body>
</html>
"""


def _render(template: str, **ctx) -> str:
    # Inject CSS and brand assets into the templates
    css = (
        BASE_CSS.replace("__BG_IMG_URL__", BG_IMG_URL)
        .replace("__ACCENT_IMG_URL__", ACCENT_IMG_URL)
        .replace("__HERO_IMG_URL__", HERO_IMG_URL)
    )
    t = (
        template.replace("__BASE_CSS__", css)
        .replace("__LOGO_URL__", LOGO_URL)
        .replace("__BRAND_NAME__", BRAND_NAME)
    )
    return render_template_string(t, **ctx)


def keystone_password_auth(username: str, password: str) -> None:
    """
    Validate Keystone credentials.
    Success is HTTP 201 with X-Subject-Token.
    We do NOT persist the token (portal is a gate, not SSO).
    """
    url = f"{KEYSTONE_URL}/auth/tokens"
    payload = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": username,
                        "domain": {"name": USER_DOMAIN},
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


@app.get("/")
def home():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return _render(HOME_HTML, username=session.get("username"), horizon_url=HORIZON_URL)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return _render(LOGIN_HTML, error=None)

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        return _render(LOGIN_HTML, error="Missing username/password"), 400

    try:
        keystone_password_auth(username, password)
    except Exception:
        return _render(LOGIN_HTML, error="Invalid credentials"), 401

    session.clear()
    session["logged_in"] = True
    session["username"] = username
    return redirect(url_for("home"))


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run("127.0.0.1", 8000, debug=False)


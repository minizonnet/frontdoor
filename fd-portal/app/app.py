import os
import requests
from flask import Flask, request, session, redirect, url_for, render_template_string

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "CHANGE_ME_LONG_RANDOM")

KEYSTONE_URL = os.environ.get("KEYSTONE_URL", "https://keystone.example.com/v3").rstrip("/")
USER_DOMAIN = os.environ.get("USER_DOMAIN", "Default")
HORIZON_URL = os.environ.get("HORIZON_URL", "https://opole.minizon.net/")

BASE_CSS = """
<style>
  :root {
    --bg: #0b1220;
    --card: rgba(255,255,255,0.06);
    --text: #e8eefc;
    --muted: rgba(232,238,252,0.72);
    --accent: #6ee7ff;
    --accent2: #a78bfa;
    --danger: #ff6b6b;
    --shadow: 0 18px 50px rgba(0,0,0,0.45);
    --radius: 18px;
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
      var(--bg);
    display: grid;
    place-items: center;
    padding: 28px;
  }

  .wrap { width: 100%; max-width: 460px; }
  .brand {
    display:flex; align-items:center; gap:12px;
    margin: 0 0 14px 0;
  }
  .logo {
    width: 42px; height: 42px; border-radius: 12px;
    background: linear-gradient(135deg, rgba(110,231,255,0.9), rgba(167,139,250,0.9));
    box-shadow: 0 10px 25px rgba(0,0,0,0.35);
  }
  .title { font-size: 20px; font-weight: 700; margin:0; letter-spacing: 0.2px; }
  .subtitle { margin: 4px 0 0 0; color: var(--muted); font-size: 13px; }

  .card {
    background: linear-gradient(180deg, var(--card), rgba(255,255,255,0.04));
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 18px;
    backdrop-filter: blur(10px);
  }

  .row { margin-top: 12px; }
  label { display:block; font-size: 12px; color: var(--muted); margin: 0 0 6px; }
  input {
    width: 100%;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.12);
    background: rgba(0,0,0,0.18);
    color: var(--text);
    padding: 12px 12px;
    outline: none;
  }
  input:focus {
    border-color: rgba(110,231,255,0.55);
    box-shadow: 0 0 0 4px rgba(110,231,255,0.12);
  }

  .btn {
    width: 100%;
    border: 0;
    border-radius: 12px;
    padding: 12px 14px;
    color: #06101c;
    font-weight: 700;
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
    background: rgba(255,255,255,0.05);
  }
  .link:hover { border-color: rgba(110,231,255,0.35); }

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
</style>
"""

LOGIN_HTML = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Front Door</title>
  {BASE_CSS}
</head>
<body>
  <div class="wrap">
    <div class="brand">
      <div class="logo"></div>
      <div>
        <p class="title">Front Door</p>
        <p class="subtitle">Authenticate against Keystone to access your console</p>
      </div>
    </div>

    <div class="card">
      <div class="topline">
        <div class="pill">Keystone Password</div>
        <div class="pill">v3</div>
      </div>

      {{% if error %}}
        <div class="alert">{{{{ error }}}}</div>
      {{% endif %}}

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
        Note: this validates credentials and grants portal access; it does not create an SSO session in Horizon yet.
      </div>
    </div>
  </div>
</body>
</html>
"""

HOME_HTML = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Front Door</title>
  {BASE_CSS}
</head>
<body>
  <div class="wrap">
    <div class="brand">
      <div class="logo"></div>
      <div>
        <p class="title">Front Door</p>
        <p class="subtitle">Access granted</p>
      </div>
    </div>

    <div class="card">
      <div class="topline">
        <div class="pill">User: {{{{ username }}}}</div>
        <div class="pill">Ready</div>
      </div>

      <div class="row">
        <a class="link" href="{{{{ horizon_url }}}}">Open Horizon</a>
      </div>

      <div class="row">
        <form method="post" action="/logout">
          <button class="btn" type="submit">Logout</button>
        </form>
      </div>

      <div class="muted">
        Next: add project/role authorization checks before allowing access.
      </div>
    </div>
  </div>
</body>
</html>
"""


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
    return render_template_string(
        HOME_HTML,
        username=session.get("username"),
        horizon_url=HORIZON_URL,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template_string(LOGIN_HTML, error=None)

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        return render_template_string(LOGIN_HTML, error="Missing username/password"), 400

    try:
        keystone_password_auth(username, password)
    except Exception:
        return render_template_string(LOGIN_HTML, error="Invalid credentials"), 401

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


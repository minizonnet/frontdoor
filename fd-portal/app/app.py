import os
import requests
from flask import Flask, request, session, redirect, url_for, render_template_string, abort

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "CHANGE_ME_LONG_RANDOM")

KEYSTONE_URL = os.environ.get("KEYSTONE_URL", "https://keystone.example.com/v3")
USER_DOMAIN = os.environ.get("USER_DOMAIN", "Default")

# If you proxy Horizon behind the portal:
HORIZON_URL = os.environ.get("HORIZON_URL", "https://opole.minizon.net/")

LOGIN_HTML = """
<!doctype html>
<title>Portal Login</title>
<h2>OpenStack Portal</h2>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
<form method="post">
  <label>Username</label><br>
  <input name="username" autocomplete="username" required><br><br>
  <label>Password</label><br>
  <input name="password" type="password" autocomplete="current-password" required><br><br>
  <button type="submit">Login</button>
</form>
"""

HOME_HTML = """
<!doctype html>
<title>Portal</title>
<h2>Portal</h2>
<p>Logged in as: {{ username }}</p>
<ul>
  <li><a href="{{ horizon_url }}">Open Horizon</a></li>
</ul>
<form method="post" action="/logout"><button type="submit">Logout</button></form>
"""

def keystone_password_auth(username: str, password: str) -> str:
    """Return X-Subject-Token if credentials are valid; raises on failure."""
    url = f"{KEYSTONE_URL}/auth/tokens"
    payload = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": username,
                        "domain": {"name": USER_DOMAIN},
                        "password": password
                    }
                }
            }
        }
    }
    r = requests.post(url, json=payload, timeout=10)
    if r.status_code != 201:
        raise ValueError(f"Keystone auth failed: {r.status_code}")
    token = r.headers.get("X-Subject-Token")
    if not token:
        raise ValueError("Missing X-Subject-Token")
    return token

@app.get("/")
def home():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template_string(HOME_HTML, username=session.get("username"), horizon_url=HORIZON_URL)
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template_string(LOGIN_HTML, error=None)

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        return render_template_string(LOGIN_HTML, error="Missing username/password"), 400

    try:
        token = keystone_password_auth(username, password)
    except Exception:
        # Do not leak details to attacker
        return render_template_string(LOGIN_HTML, error="Invalid credentials"), 401

    # Create portal session; DO NOT store the Keystone token client-side.
    session.clear()
    session["logged_in"] = True
    session["username"] = username

    # If you want periodic revalidation, store a short-lived server-side token in Redis instead.
    # For now, simple session is enough for a gate.

    return redirect(url_for("home"))

@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.before_request
def gate_horizon():
    # If Horizon is reverse-proxied behind this Flask app path, you can gate it here:
    if request.path.startswith("/horizon/") and not session.get("logged_in"):
        return redirect(url_for("login"))

if __name__ == "__main__":
    app.run("127.0.0.1", 8000, debug=False)


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

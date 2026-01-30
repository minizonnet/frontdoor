import random
from flask import Blueprint, request, session, redirect, url_for, render_template

def _client_ip(trust_xff: bool) -> str:
    if trust_xff:
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"

def _ensure_captcha():
    # Store captcha in session (simple math). Regenerate if missing.
    if "captcha_q" in session and "captcha_a" in session:
        return
    a = random.randint(2, 9)
    b = random.randint(2, 9)
    session["captcha_q"] = f"What is {a} + {b}?"
    session["captcha_a"] = str(a + b)

def _clear_captcha():
    session.pop("captcha_q", None)
    session.pop("captcha_a", None)

def _warning_for_state(state):
    """
    Return (message, css_class) based on number of failures and stage.
    """
    f = state.failures

    # Locked (simulated)
    if state.locked_out:
        msg = (
            f"Too many incorrect attempts. Your IP would be blocked now "
            f"(blocking module later). Try again in ~{state.lockout_seconds_left}s."
        )
        return (msg, "danger")

    # Failures 1..3: "you have N more tries"
    if 1 <= f <= 3:
        remaining = 3 - f
        if remaining == 2:
            return ("Invalid credentials. You have 2 more tries.", "warn")
        if remaining == 1:
            return ("Invalid credentials. You have 1 more try.", "warn")
        return ("Invalid credentials. This was your last try before captcha is enabled.", "warn")

    # Failure 4: warn captcha next
    if f == 4:
        return ("Invalid credentials. Next attempt will require a captcha.", "warn")

    # Failures 5..6: captcha stage warning, in red
    if f == 5:
        return ("Captcha is now required. 2 more incorrect attempts and your IP will be blocked.", "danger")
    if f == 6:
        return ("Captcha is required. 1 more incorrect attempt and your IP will be blocked.", "danger")

    # f==0 (no warning)
    return (None, None)

def build_blueprint(settings, keystone_client, defense):
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
        ip = _client_ip(settings.trust_x_forwarded_for)
        st = defense.state(ip)

        # If locked out, show login with a red message (no attempts processed)
        warn, warn_class = _warning_for_state(st)
        require_captcha = st.captcha_required and not st.locked_out
        if require_captcha:
            _ensure_captcha()

        if request.method == "GET":
            return render_template(
                "login.html",
                error=None,
                warning=warn,
                warning_class=warn_class,
                captcha_required=require_captcha,
                captcha_question=session.get("captcha_q"),
            )

        # POST
        if st.locked_out:
            return render_template(
                "login.html",
                error=None,
                warning=warn,
                warning_class=warn_class,
                captcha_required=True,
                captcha_question=session.get("captcha_q"),
            ), 429

        # If captcha required, validate it first
        if require_captcha:
            user_captcha = request.form.get("captcha", "").strip()
            expected = session.get("captcha_a", "")
            if not user_captcha or user_captcha != expected:
                st2 = defense.record_failure(ip)
                _ensure_captcha()  # keep a captcha present
                w2, wc2 = _warning_for_state(st2)
                return render_template(
                    "login.html",
                    error="Incorrect captcha.",
                    warning=w2,
                    warning_class=wc2 or "danger",
                    captcha_required=True,
                    captcha_question=session.get("captcha_q"),
                ), 401

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render_template(
                "login.html",
                error="Missing username/password",
                warning=warn,
                warning_class=warn_class,
                captcha_required=require_captcha,
                captcha_question=session.get("captcha_q"),
            ), 400

        try:
            keystone_client.validate_password(username, password)
        except Exception:
            st2 = defense.record_failure(ip)
            # If we just transitioned into captcha stage, ensure captcha exists
            if st2.captcha_required:
                _ensure_captcha()
            w2, wc2 = _warning_for_state(st2)
            return render_template(
                "login.html",
                error="Invalid credentials",
                warning=w2,
                warning_class=wc2,
                captcha_required=st2.captcha_required and not st2.locked_out,
                captcha_question=session.get("captcha_q"),
            ), 401

        # Success: reset defense for IP + clear captcha + create portal session
        defense.reset(ip)
        _clear_captcha()

        session.clear()
        session["logged_in"] = True
        session["username"] = username
        return redirect(url_for("fd.home"))

    @bp.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("fd.login"))

    return bp


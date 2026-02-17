import secrets
import random
from flask import Blueprint, request, session, redirect, url_for, render_template


def _client_key() -> str:
    """
    Stable per-browser key stored in the session cookie.
    Avoids incorrect counting when client IP is NATed/changes via Octavia/kube-proxy.
    """
    if "client_id" not in session:
        session["client_id"] = secrets.token_urlsafe(16)
    return session["client_id"]

def _client_ip(trust_xff: bool) -> str:
    """
    Best-effort client IP for future IP-based blocking/logging.
    Note: behind Octavia/kube-proxy the true client IP may be lost unless
    externalTrafficPolicy=Local or X-Forwarded-For is trustworthy.
    """
    if trust_xff:
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"

def _ensure_captcha():
    if "captcha_q" in session and "captcha_a" in session:
        return
    a = random.randint(2, 9)
    b = random.randint(2, 9)
    session["captcha_q"] = f"What is {a} + {b}?"
    session["captcha_a"] = str(a + b)


def _clear_captcha():
    session.pop("captcha_q", None)
    session.pop("captcha_a", None)


def _ui_for_state(policy, state):
    """
    Returns (warning_message, warning_class, require_captcha, http_status_if_locked)
    """
    f = state.failures

    if state.locked_out:
        return (
            f"{policy.msg_would_block} Try again in ~{state.lockout_seconds_left}s.",
            "danger",
            True,
            429,
        )

    require_captcha = state.captcha_required

    # warnings for tries remaining BEFORE captcha
    if 1 <= f < policy.warn_until_failures:
        remaining = policy.warn_until_failures - f
        return (f"You have {remaining} more {'tries' if remaining != 1 else 'try'}.", "warn", require_captcha, None)

    # warning at the point captcha is announced
    if f == policy.captcha_warn_failure:
        # show a guidance warning only (error is always "Invalid credentials")
        return ("Next attempt will require a captcha.", "warn", require_captcha, None)

    # captcha phase: countdown to block
    if f >= policy.block_warn_from_failure and f < policy.block_after_failure:
        remaining = policy.block_after_failure - f
        return (policy.msg_block_countdown.format(n=remaining), "danger", require_captcha, None)

    return (None, None, require_captcha, None)


def build_blueprint(settings, keystone_client, defense):
    bp = Blueprint("fd", __name__)
    policy = settings.login_policy

    @bp.get("/")
    def home():
        if not session.get("logged_in"):
            return redirect(url_for("fd.login"))
        return render_template(
            "home.html",
            username=session.get("username"),
            horizon_url=settings.horizon_url,
            skyline_url=settings.skyline_url,
        )

    @bp.route("/login", methods=["GET", "POST"])
    def login():
        key = _client_key()
        st = defense.state(key)
        ip = _client_ip(settings.trust_x_forwarded_for)

        warn, warn_class, require_captcha, locked_status = _ui_for_state(policy, st)
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
                warning_class=warn_class or "danger",
                captcha_required=True,
                captcha_question=session.get("captcha_q"),
            ), (locked_status or 429)

        # Captcha validation if required
        if require_captcha:
            user_captcha = request.form.get("captcha", "").strip()
            expected = session.get("captcha_a", "")
            if not user_captcha or user_captcha != expected:
                st2 = defense.record_failure(key)
                _ensure_captcha()
                w2, wc2, req2, locked2 = _ui_for_state(policy, st2)
                return render_template(
                    "login.html",
                    error="Incorrect captcha.",
                    warning=w2,
                    warning_class=wc2 or "danger",
                    captcha_required=req2 and not st2.locked_out,
                    captcha_question=session.get("captcha_q"),
                ), (locked2 or 401)

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

        # Keystone auth
        try:
            keystone_client.validate_password(username, password)
        except Exception:
            st2 = defense.record_failure(key)
            if st2.captcha_required:
                _ensure_captcha()
            w2, wc2, req2, locked2 = _ui_for_state(policy, st2)

            return render_template(
                "login.html",
                error=policy.msg_invalid_generic,   # "Invalid credentials."
                warning=w2,
                warning_class=wc2,
                captcha_required=req2 and not st2.locked_out,
                captcha_question=session.get("captcha_q"),
            ), (locked2 or 401)

        # SUCCESS
        defense.reset(key)
        _clear_captcha()

        # Do NOT session.clear() (it would delete client_id and break counting consistency)
        session["logged_in"] = True
        session["username"] = username
        return redirect(url_for("fd.home"))

    @bp.post("/logout")
    def logout():
        # Keep client_id stable across logout/login cycles
        client_id = session.get("client_id")
        session.clear()
        if client_id:
            session["client_id"] = client_id
        return redirect(url_for("fd.login"))

    return bp


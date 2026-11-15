"""Signing in to the hub: login form, CSRF tokens, and blocking addresses that guess passwords."""

import secrets
import threading
import time

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import config, storage

bp = Blueprint("auth", __name__)

fails = {}  # key -> (count, time of last failure)
fails_lock = threading.Lock()
DUMMY_HASH = generate_password_hash("not-a-real-password", method=config.PASSWORD_METHOD)


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def csrf_ok(sent):
    return bool(sent) and secrets.compare_digest(sent.encode(), session.get("csrf", "").encode())


def blocked(key):
    with fails_lock:
        count, last = fails.get(key, (0, 0))
        if count >= config.MAX_FAILS and time.time() - last < config.LOCK_SECONDS:
            return True
        if count >= config.MAX_FAILS:
            fails.pop(key, None)
        return False


def record_fail(key):
    with fails_lock:
        now = time.time()
        if len(fails) > 10_000:                   # forget stale entries so this can't grow forever
            for k in [k for k, (_, t) in fails.items() if now - t > config.LOCK_SECONDS]:
                fails.pop(k, None)
        count, _ = fails.get(key, (0, 0))
        fails[key] = (count + 1, now)


def clear_fails(key):
    with fails_lock:
        fails.pop(key, None)


def api_guard():
    """Return an error response if the caller may not use the API, else None."""
    if "user" not in session:
        return jsonify(error="not signed in"), 401
    if request.method == "POST" and not csrf_ok(request.headers.get("X-CSRF", "")):
        return jsonify(error="bad csrf token"), 400
    return None


def page(error=None, status=200, template="app.html"):
    return render_template(template, user=session.get("user"), csrf=csrf_token(), error=error), status


@bp.get("/")
def home():
    return page()


@bp.get("/classic")
def classic():
    """The old one-table page, kept until the new app has been used for a while (ARCHITECTURE.md, S6)."""
    return page(template="index.html")


def sign_in(name, password):
    """Check a login and start the session. Returns None, or (message, status) to show the person."""
    ip = request.remote_addr
    if blocked(ip):
        return "Too many attempts. Wait a minute.", 429
    stored = storage.load_users().get(name)
    # Check a hash even for unknown users so both cases take similar time.
    ok = check_password_hash(stored or DUMMY_HASH, password) and stored is not None
    if not ok:
        record_fail(ip)
        return "Wrong username or password.", 401
    clear_fails(ip)
    session.clear()           # new session after login
    session["user"] = name
    csrf_token()
    return None


@bp.post("/login")
def login():
    if not csrf_ok(request.form.get("csrf", "")):
        return page("Session expired, try again.", 400)
    problem = sign_in(request.form.get("username", "").strip(), request.form.get("password", ""))
    if problem:
        return page(*problem)
    return redirect(url_for("auth.home"))


# ---- the same sign-in as JSON, for the phone app (mobile/), which has no HTML form to read a token from

def session_json():
    return jsonify(user=session.get("user"), csrf=csrf_token())


@bp.get("/api/session")
def session_info():
    """Who is signed in (user is null if nobody), and the CSRF token to send with every POST."""
    return session_json()


@bp.post("/api/session")
def session_login():
    # Only JSON is accepted: a form on another website can't send it, which is what the form's
    # CSRF token guards against.
    data = request.get_json(silent=True) if request.is_json else None
    if not isinstance(data, dict):
        return jsonify(error="Send the username and password as JSON."), 400
    problem = sign_in(str(data.get("username", "")).strip(), str(data.get("password", "")))
    if problem:
        return jsonify(error=problem[0]), problem[1]
    return session_json()


@bp.delete("/api/session")
def session_logout():
    if not csrf_ok(request.headers.get("X-CSRF", "")):
        return jsonify(error="bad csrf token"), 400
    session.clear()
    return jsonify(ok=True)


@bp.post("/logout")
def logout():
    if csrf_ok(request.form.get("csrf", "")):
        session.clear()
    return redirect(url_for("auth.home"))

"""Very small login-protected web app.

Run it on your PC, open it from any device on the same LAN, sign in,
and see a welcome message. It does nothing else yet.

Usage:
    python app.py adduser <name>   # create or change a user (asks for a password)
    python app.py                  # open the app in a native window and serve it on port 8000
    python app.py --headless       # serve only, no window
"""

import getpass
import json
import os
import secrets
import socket
import sys
import threading
import time
from pathlib import Path

from flask import Flask, redirect, render_template_string, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE = Path(__file__).resolve().parent
USERS_FILE = BASE / "users.json"      # {"name": "<password hash>"}
SECRET_FILE = BASE / ".secret_key"    # signs the login cookie
PORT = int(os.environ.get("PORT", "8000"))

MAX_FAILS = 5          # wrong attempts allowed ...
LOCK_SECONDS = 60      # ... before that address is blocked for this long


def load_users():
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    return {}


def get_secret_key():
    if not SECRET_FILE.exists():
        SECRET_FILE.write_text(secrets.token_hex(32))
        os.chmod(SECRET_FILE, 0o600)
    return SECRET_FILE.read_text().strip()


app = Flask(__name__)
app.secret_key = get_secret_key()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

fails = {}  # ip -> (count, time of last failure)
DUMMY_HASH = generate_password_hash("not-a-real-password")

PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Swarm Hub</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 22rem; margin: 4rem auto; padding: 0 1rem; }
    input, button { width: 100%; padding: .6rem; margin: .3rem 0 .8rem; box-sizing: border-box; font-size: 1rem; }
    .error { color: #b00020; }
  </style>
</head>
<body>
{% if user %}
  <h1>Welcome, {{ user }}</h1>
  <p>You are signed in. Nothing else is built yet.</p>
  <form method="post" action="{{ url_for('logout') }}">
    <input type="hidden" name="csrf" value="{{ csrf }}">
    <button type="submit">Sign out</button>
  </form>
{% else %}
  <h1>Sign in</h1>
  {% if error %}<p class="error">{{ error }}</p>{% endif %}
  <form method="post" action="{{ url_for('login') }}">
    <input type="hidden" name="csrf" value="{{ csrf }}">
    <label>Username<input name="username" autocomplete="username" autofocus required></label>
    <label>Password<input name="password" type="password" autocomplete="current-password" required></label>
    <button type="submit">Sign in</button>
  </form>
{% endif %}
</body>
</html>
"""


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def csrf_ok():
    sent = request.form.get("csrf", "")
    return bool(sent) and secrets.compare_digest(sent, session.get("csrf", ""))


def blocked(ip):
    count, last = fails.get(ip, (0, 0))
    if count >= MAX_FAILS and time.time() - last < LOCK_SECONDS:
        return True
    if count >= MAX_FAILS:
        fails.pop(ip, None)
    return False


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/")
def home():
    return render_template_string(PAGE, user=session.get("user"), csrf=csrf_token(), error=None)


@app.post("/login")
def login():
    ip = request.remote_addr
    if not csrf_ok():
        return render_template_string(PAGE, user=None, csrf=csrf_token(), error="Session expired, try again."), 400
    if blocked(ip):
        return render_template_string(PAGE, user=None, csrf=csrf_token(), error="Too many attempts. Wait a minute."), 429

    name = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    stored = load_users().get(name)
    # Check a hash even for unknown users so both cases take similar time.
    ok = check_password_hash(stored or DUMMY_HASH, password) and stored is not None

    if not ok:
        count, _ = fails.get(ip, (0, 0))
        fails[ip] = (count + 1, time.time())
        return render_template_string(PAGE, user=None, csrf=csrf_token(), error="Wrong username or password."), 401

    fails.pop(ip, None)
    session.clear()           # new session after login
    session["user"] = name
    csrf_token()
    return redirect(url_for("home"))


@app.post("/logout")
def logout():
    if csrf_ok():
        session.clear()
    return redirect(url_for("home"))


def add_user(name):
    password = getpass.getpass("Password: ")
    if len(password) < 8:
        sys.exit("Use at least 8 characters.")
    if getpass.getpass("Repeat password: ") != password:
        sys.exit("Passwords do not match.")
    users = load_users()
    users[name] = generate_password_hash(password)
    USERS_FILE.write_text(json.dumps(users, indent=2))
    os.chmod(USERS_FILE, 0o600)
    print(f"Saved user '{name}'.")


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # no traffic is sent
        return s.getsockname()[0]
    except OSError:
        return "your-pc-address"
    finally:
        s.close()


def run_server():
    app.run(host="0.0.0.0", port=PORT)


def wait_for_server(timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "adduser":
        add_user(sys.argv[2])
        sys.exit()
    if not load_users():
        sys.exit("No users yet. Create one first:  python app.py adduser <name>")
    print(f"Open  http://{lan_ip()}:{PORT}  from any device on your network")
    if "--headless" in sys.argv:
        run_server()          # server only, no window
    else:
        import webview        # native window; needs: pip install pywebview

        threading.Thread(target=run_server, daemon=True).start()
        if not wait_for_server():
            sys.exit("The server did not start.")
        webview.create_window("Swarm Hub", f"http://127.0.0.1:{PORT}", width=900, height=700)
        webview.start()       # returns when you close the window; the server stops too
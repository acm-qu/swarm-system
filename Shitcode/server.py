"""Swarm Hub: a login-protected app that installs, watches and controls robots.

Run it on your computer, sign in, and press "Add robot". Give it the robot's IP
address, username and password; the hub connects over SSH, copies
robot_agent.py onto the robot and installs it as a service that starts on
every boot, sets status_ui.py to open on the robot's desktop, then reboots the
robot and waits for it to come back and connect.

Usage:
    python server.py adduser <name>   # create or change a login (asks for a password)
    python server.py token            # show the token robots use to connect
    python server.py                  # open the app in a window and serve it on port 8000
    python server.py --headless       # serve only, no window (open the printed URL in a browser)
"""

import getpass
import json
import logging
import math
import os
import re
import secrets
import shlex
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template_string, request, session, url_for
from flask_sock import Sock
from simple_websocket import ConnectionClosed
from werkzeug.security import check_password_hash, generate_password_hash

BASE = Path(__file__).resolve().parent
USERS_FILE = BASE / "users.json"        # {"name": "<password hash>"}
SECRET_FILE = BASE / ".secret_key"      # signs the login cookie
TOKEN_FILE = BASE / "robot_token.txt"   # shared secret that robots must send
REGISTRY_FILE = BASE / "robots.json"    # robots this hub has installed (no passwords)
HUB_KEY_FILE = BASE / "hub_ssh_key"     # the hub's SSH key, added to each robot it installs
AGENT_FILE = BASE / "robot_agent.py"    # the program copied onto each robot
STATUS_UI_FILE = BASE / "status_ui.py"  # the status screen copied onto each robot
PORT = int(os.environ.get("PORT", "8000"))

MAX_FAILS = 5          # wrong attempts allowed ...
LOCK_SECONDS = 60      # ... before that address is blocked for this long

ONLINE_WITHIN = 3.0    # robot counts as connected if heard from this recently (seconds)
SILENCE_LIMIT = 5.0    # hub drops a robot that sends nothing for this long (seconds)
CONNECT_WAIT = 25      # after installing, wait this long for the robot to connect (seconds)
REBOOT_WAIT = 180      # after rebooting a robot, wait this long for it to come back (seconds)
TERM_TIMEOUT = 30      # a terminal command is stopped after this many seconds
TERM_MAX_OUTPUT = 100_000   # most output (bytes) returned for one terminal command
TERM_MARK = "__SWARM_CWD__"  # printed after each command so the hub learns the folder it ended in

NAME_RE = re.compile(r"[A-Za-z0-9_-]{1,32}")
HOST_RE = re.compile(r"[A-Za-z0-9.:_-]{1,253}")
USER_RE = re.compile(r"[A-Za-z0-9._-]{1,32}")
PATH_RE = re.compile(r"/[A-Za-z0-9._/-]*")

SERVICE = "swarm-agent"            # systemd service name on the robot
REMOTE_DIR = "swarm-agent"         # folder in the robot user's home
AUTOSTART = ".config/autostart/swarm-status.desktop"   # opens the status screen at desktop login
DEFAULT_PREFIX = "masterpi-"       # robots get named masterpi-01, masterpi-02, ...

logging.getLogger("paramiko").setLevel(logging.CRITICAL)   # errors are reported in the app instead


def load_users():
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    return {}


def write_private(path, data):
    """Write a file that only this user can read."""
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w" if isinstance(data, str) else "wb") as f:
        f.write(data)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def get_secret_key():
    if not SECRET_FILE.exists():
        write_private(SECRET_FILE, secrets.token_hex(32))
    return SECRET_FILE.read_text().strip()


def get_robot_token():
    if not TOKEN_FILE.exists():
        write_private(TOKEN_FILE, secrets.token_urlsafe(24))
    return TOKEN_FILE.read_text().strip()


def load_registry():
    if REGISTRY_FILE.exists():
        try:
            return json.loads(REGISTRY_FILE.read_text())
        except ValueError:
            print(f"Warning: {REGISTRY_FILE.name} is damaged; starting with an empty robot list.")
    return {}


app = Flask(__name__)
app.secret_key = get_secret_key()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
sock = Sock(app)
ROBOT_TOKEN = get_robot_token()

fails = {}  # key -> (count, time of last failure)
DUMMY_HASH = generate_password_hash("not-a-real-password")

robots = {}  # name -> live connection record (see robot_socket)
robots_lock = threading.Lock()

registry = load_registry()   # name -> {"host", "user", "home", "host_key", "machine_id", ...}
registry_lock = threading.Lock()
pending_names = set()        # names picked by installs that are still running

jobs = {}    # id -> install / update / remove job, shown live in the app
jobs_lock = threading.Lock()
key_lock = threading.Lock()

PAGE = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Swarm Hub</title>
  <style>
    :root {
      --bg: #f6f7f9; --card: #ffffff; --text: #1d2330; --muted: #667085; --line: #e4e7ec;
      --accent: #2f5bea; --accent-text: #ffffff; --ok: #157f3b; --ok-bg: #e6f4ea;
      --warn: #a15c00; --warn-bg: #fdf1dc; --bad: #b42318; --bad-bg: #fde8e7; --idle-bg: #eef0f3;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #14171c; --card: #1c2027; --text: #e7e9ee; --muted: #98a2b3; --line: #2c323c;
        --accent: #6d8dff; --accent-text: #0d1220; --ok: #6fd391; --ok-bg: #173323;
        --warn: #f4b860; --warn-bg: #3a2a12; --bad: #ff8a80; --bad-bg: #3d1c1a; --idle-bg: #262b33;
      }
    }
    * { box-sizing: border-box; }
    [hidden] { display: none !important; }
    body { font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text);
           max-width: 64rem; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
    h1 { font-size: 1.4rem; margin: 0; }
    h2 { font-size: 1.15rem; margin: 0 0 .25rem; }
    .muted { color: var(--muted); }
    .bar { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.25rem; }
    .bar form { display: flex; align-items: center; gap: .6rem; margin: 0; }
    button { font: inherit; padding: .45rem .9rem; border-radius: 8px; border: 1px solid var(--line);
             background: var(--card); color: var(--text); cursor: pointer; }
    button:hover:not(:disabled) { border-color: var(--muted); }
    button:disabled { opacity: .45; cursor: default; }
    button.primary { background: var(--accent); color: var(--accent-text); border-color: var(--accent); font-weight: 600; }
    button.danger { color: var(--bad); }
    button.small { padding: .25rem .6rem; font-size: .85rem; }
    .card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 1rem 1.1rem; }
    .head { display: flex; justify-content: space-between; align-items: center; gap: 1rem; margin-bottom: .5rem; }
    .scroll { overflow-x: auto; }
    table { border-collapse: collapse; width: 100%; }
    th, td { text-align: left; padding: .55rem .5rem; border-bottom: 1px solid var(--line); white-space: nowrap; }
    th { font-size: .78rem; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); font-weight: 600; }
    tr:last-child td { border-bottom: 0; }
    td .actions { display: flex; gap: .35rem; }
    td .sub { font-size: .8rem; color: var(--muted); }
    .pill { display: inline-block; padding: .15rem .55rem; border-radius: 999px; font-size: .82rem; font-weight: 600; }
    .pill.connected { color: var(--ok); background: var(--ok-bg); }
    .pill.unresponsive { color: var(--warn); background: var(--warn-bg); }
    .pill.offline { color: var(--muted); background: var(--idle-bg); }
    .pill.busy { color: var(--accent); background: var(--idle-bg); }
    .empty { text-align: center; padding: 2.5rem 1rem; }
    .narrow { max-width: 22rem; margin: 3rem auto; }
    label { display: block; font-size: .9rem; font-weight: 600; margin: .8rem 0 0; }
    label input:not([type=checkbox]) { display: block; width: 100%; margin-top: .3rem; padding: .55rem .6rem; font: inherit;
             border: 1px solid var(--line); border-radius: 8px; background: var(--bg); color: var(--text); }
    label.check { display: flex; gap: .5rem; align-items: flex-start; font-weight: 400; }
    .narrow button { width: 100%; margin-top: 1rem; }
    .error { color: var(--bad); }
    .hint { font-size: .85rem; color: var(--muted); margin: .35rem 0 0; }
    .overlay { position: fixed; inset: 0; background: rgba(10, 14, 22, .55); display: flex;
               align-items: center; justify-content: center; padding: 1rem; z-index: 10; }
    .overlay[hidden] { display: none; }
    .dialog { background: var(--card); border: 1px solid var(--line); border-radius: 14px; width: 100%;
              max-width: 30rem; padding: 1.3rem 1.4rem; max-height: 90vh; overflow-y: auto; }
    .dialog .buttons { display: flex; justify-content: flex-end; gap: .5rem; margin-top: 1.2rem; }
    .steps { list-style: none; padding: 0; margin: 1rem 0 0; }
    .steps li { display: flex; gap: .55rem; padding: .25rem 0; font-size: .92rem; }
    .steps li .icon { width: 1.1rem; flex: none; text-align: center; font-weight: 700; }
    .steps li.ok .icon { color: var(--ok); }
    .steps li.fail .icon, .steps li.fail { color: var(--bad); }
    .steps li.run .icon { color: var(--accent); }
    .steps li.info { color: var(--muted); font-size: .85rem; padding-left: 1.65rem; font-family: ui-monospace, monospace; white-space: pre-wrap; }
    .note { margin: 1rem 0 0; padding: .6rem .75rem; border-radius: 8px; font-size: .92rem; }
    .note.good { color: var(--ok); background: var(--ok-bg); }
    .note.warn { color: var(--warn); background: var(--warn-bg); }
    .note.bad { color: var(--bad); background: var(--bad-bg); }
    .pad { display: grid; grid-template-columns: repeat(3, 1fr); gap: .5rem; max-width: 15rem; margin: 1rem auto; }
    .pad button { padding: .8rem 0; font-size: 1.2rem; touch-action: none; user-select: none; -webkit-user-select: none; }
    .pad button small { display: block; font-size: .65rem; opacity: .7; }
    .pad button.on { background: var(--accent); color: var(--accent-text); border-color: var(--accent); }
    .dialog.term { max-width: 46rem; }
    .term-out { background: var(--bg); border: 1px solid var(--line); border-radius: 8px; height: 45vh; overflow: auto;
                padding: .6rem .7rem; font: .85rem/1.4 ui-monospace, monospace; }
    .term-out .cmd { color: var(--accent); margin-top: .5rem; white-space: pre-wrap; word-break: break-all; }
    .term-out pre { margin: 0; white-space: pre-wrap; word-break: break-all; font: inherit; }
    .term-out .meta { color: var(--muted); }
    .term-out .meta.bad { color: var(--bad); }
    .term-line { display: flex; gap: .5rem; align-items: center; margin-top: .6rem; }
    .term-line .prompt { max-width: 40%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font: .85rem ui-monospace, monospace; }
    .term-line input { flex: 1; min-width: 0; font: .9rem ui-monospace, monospace; padding: .45rem .6rem;
                       border: 1px solid var(--line); border-radius: 8px; background: var(--bg); color: var(--text); }
  </style>
</head>
<body>
{% if user %}
  <div class="bar">
    <h1>Swarm Hub</h1>
    <form method="post" action="{{ url_for('logout') }}">
      <input type="hidden" name="csrf" value="{{ csrf }}">
      <span class="muted">Signed in as {{ user }}</span>
      <button type="submit" class="small">Sign out</button>
    </form>
  </div>

  <div class="card">
    <div class="head">
      <div>
        <h2>Robots</h2>
        <span class="muted" id="summary"></span>
      </div>
      <button class="primary" id="add">+ Add robot</button>
    </div>
    <div class="empty muted" id="none">No robots yet. Press <b>Add robot</b> to set one up.</div>
    <div class="scroll">
      <table id="robots" hidden>
        <thead><tr><th>Robot</th><th>Status</th><th>Address</th><th>Last seen</th><th>Latency</th><th>Last event</th><th></th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </div>

  <div class="overlay" id="overlay" hidden>
    <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="dlg-title">
      <h2 id="dlg-title"></h2>
      <p class="muted" id="dlg-intro"></p>
      <form id="dlg-form" autocomplete="off">
        <div id="f-add">
          <label>IP address<input name="host" placeholder="192.168.149.1" spellcheck="false"></label>
          <label>Username<input name="user" value="pi" spellcheck="false"></label>
        </div>
        <label id="f-pass">Password<input name="password" type="password" autocomplete="new-password"></label>
        <p class="hint" id="pass-hint"></p>
        <label id="f-name">Name <span class="muted">(optional)</span><input name="name" placeholder="picked for you, e.g. masterpi-01" spellcheck="false"></label>
        <label class="check" id="f-reboot"><input type="checkbox" name="reboot">
          <span>Reboot the robot when done<span class="hint" style="display:block">Proves it starts by itself and opens the status screen on its desktop. Takes about a minute.</span></span></label>
        <label class="check" id="f-forget"><input type="checkbox" name="forget"> The robot is gone or can't be reached. Just take it off this list.</label>
        <p class="error" id="dlg-error"></p>
      </form>
      <ol class="steps" id="dlg-steps"></ol>
      <div class="note" id="dlg-note" hidden></div>
      <div class="buttons">
        <button type="button" id="dlg-close">Cancel</button>
        <button type="submit" form="dlg-form" class="primary" id="dlg-go">Install</button>
      </div>
    </div>
  </div>

  <div class="overlay" id="drive-overlay" hidden>
    <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="drive-title">
      <h2 id="drive-title">Drive</h2>
      <p class="muted">Hold a button or key to move; let go and the robot stops. Keys: W A S D to move, Q and E to turn, Space to stop.</p>
      <div class="pad" id="drive-pad">
        <button type="button" data-key="q">&#10226;<small>Q</small></button>
        <button type="button" data-key="w">&#9650;<small>W</small></button>
        <button type="button" data-key="e">&#10227;<small>E</small></button>
        <button type="button" data-key="a">&#9664;<small>A</small></button>
        <button type="button" class="danger" id="drive-stop">&#9632;<small>Space</small></button>
        <button type="button" data-key="d">&#9654;<small>D</small></button>
        <span></span>
        <button type="button" data-key="s">&#9660;<small>S</small></button>
        <span></span>
      </div>
      <label>Speed <span class="muted" id="drive-speed-label">40%</span>
        <input id="drive-speed" type="range" min="10" max="100" value="40"></label>
      <p class="error" id="drive-error"></p>
      <div class="buttons"><button type="button" id="drive-close">Close</button></div>
    </div>
  </div>

  <div class="overlay" id="term-overlay" hidden>
    <div class="dialog term" role="dialog" aria-modal="true" aria-labelledby="term-title">
      <h2 id="term-title">Terminal</h2>
      <p class="muted">Runs one command at a time on the robot over SSH, as the robot's user. A folder change (cd) is remembered. Programs that need typing (nano, top, sudo asking for a password) won't work, and each command stops after 30 seconds.</p>
      <div class="term-out" id="term-out"></div>
      <form class="term-line" id="term-form" autocomplete="off">
        <span class="muted prompt" id="term-prompt">~ $</span>
        <input id="term-input" spellcheck="false" autocapitalize="off" autocomplete="off" aria-label="Command">
        <button type="submit" class="primary small" id="term-run">Run</button>
      </form>
      <div class="buttons">
        <button type="button" id="term-clear">Clear</button>
        <button type="button" id="term-close">Close</button>
      </div>
    </div>
  </div>

  <script>
    const csrf = {{ csrf|tojson }};
    const $ = id => document.getElementById(id);
    const body = document.querySelector('#robots tbody');
    const form = $('dlg-form');
    let dlg = null;          // {mode, name, job, timer}

    function post(url, data) {
      return fetch(url, {
        method: 'POST',
        headers: { 'X-CSRF': csrf, 'Content-Type': 'application/json' },
        body: JSON.stringify(data || {}),
      }).then(async res => {
        if (res.status === 401) { location.reload(); throw new Error('signed out'); }
        const out = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(out.error || ('HTTP ' + res.status));
        return out;
      });
    }

    function cell(row, text, cls) {
      const td = document.createElement('td');
      if (cls) {
        const span = document.createElement('span');
        span.className = 'pill ' + cls;
        span.textContent = text;
        td.appendChild(span);
      } else {
        td.textContent = text;
      }
      row.appendChild(td);
      return td;
    }

    function button(parent, label, onclick, opts) {
      const b = document.createElement('button');
      b.textContent = label;
      b.className = 'small' + (opts && opts.danger ? ' danger' : '');
      b.disabled = !!(opts && opts.disabled);
      b.onclick = onclick;
      parent.appendChild(b);
    }

    function render(list) {
      $('none').hidden = list.length > 0;
      $('robots').hidden = list.length === 0;
      const online = list.filter(r => r.status === 'connected').length;
      $('summary').textContent = list.length ? online + ' of ' + list.length + ' connected' : '';
      body.replaceChildren();
      for (const r of list) {
        const tr = document.createElement('tr');
        const nameTd = cell(tr, r.name);
        if (r.hostname) {
          const sub = document.createElement('div');
          sub.className = 'sub';
          sub.textContent = r.hostname;
          sub.title = "The robot's own name";
          nameTd.appendChild(sub);
        }
        if (r.job) cell(tr, 'working…', 'busy');
        else cell(tr, r.status, r.status);
        cell(tr, r.address || '-');
        cell(tr, r.seen_ago === null ? '-' : (r.seen_ago < 1 ? 'now' : Math.round(r.seen_ago) + ' s ago'));
        cell(tr, r.latency_ms === null ? '-' : r.latency_ms + ' ms');
        cell(tr, r.job || r.event || '-');
        const cellTd = document.createElement('td');
        const td = document.createElement('div');
        td.className = 'actions';
        cellTd.appendChild(td);
        const live = r.status !== 'offline';
        button(td, 'Ping', () => post('/api/robots/' + encodeURIComponent(r.name) + '/ping').then(refresh, () => {}), { disabled: !live });
        button(td, 'Drive', () => openDrive(r.name), { disabled: !live });
        button(td, 'Stop', () => post('/api/robots/' + encodeURIComponent(r.name) + '/stop').then(refresh, () => {}), { disabled: !live });
        if (r.installed) {
          button(td, 'Terminal', () => openTerm(r.name), { disabled: !!r.job });
          button(td, 'Update', () => openDialog('update', r.name), { disabled: !!r.job });
          button(td, 'Remove', () => openDialog('remove', r.name), { disabled: !!r.job, danger: true });
        }
        tr.appendChild(cellTd);
        body.appendChild(tr);
      }
    }

    function refresh() {
      fetch('/api/robots').then(res => {
        if (res.status === 401) { location.reload(); return null; }
        return res.json();
      }).then(list => { if (list) render(list); }).catch(() => {});
    }

    // ---- dialog for Add / Update / Remove

    const TEXT = {
      add: {
        title: 'Add robot',
        intro: 'The hub will log in to the robot over SSH, copy the agent onto it, and set it to start on every boot.',
        hint: 'Used once to install. It is not saved.',
        go: 'Install',
      },
      update: {
        title: 'Update ',
        intro: 'Copies the current robot_agent.py and connection settings to the robot and restarts it.',
        hint: 'Usually not needed. Fill it in only if the robot asks for it.',
        go: 'Update',
      },
      remove: {
        title: 'Remove ',
        intro: 'Stops the agent, removes the start-on-boot service and the hub\'s files from the robot, and takes it off this list.',
        hint: 'Usually not needed. Fill it in only if the robot asks for it.',
        go: 'Remove',
      },
    };

    function openDialog(mode, name) {
      if (dlg && dlg.timer) clearTimeout(dlg.timer);
      dlg = { mode, name, job: null, timer: null };
      $('dlg-go').onclick = null;
      const t = TEXT[mode];
      $('dlg-title').textContent = t.title + (name || '');
      $('dlg-intro').textContent = t.intro;
      $('pass-hint').textContent = t.hint;
      $('f-add').hidden = mode !== 'add';
      $('f-name').hidden = mode !== 'add';
      $('f-forget').hidden = mode !== 'remove';
      $('f-reboot').hidden = mode === 'remove';
      form.password.required = mode === 'add';
      form.host.required = mode === 'add';
      form.password.value = '';
      form.forget.checked = false;
      form.reboot.checked = mode === 'add';
      if (mode === 'add') { form.host.value = ''; form.user.value = 'pi'; form.name.value = ''; }
      showForm(true);
      $('dlg-go').textContent = t.go;
      $('dlg-go').className = mode === 'remove' ? 'danger' : 'primary';
      $('overlay').hidden = false;
      (mode === 'add' ? form.host : form.password).focus();
    }

    function showForm(show) {
      form.hidden = !show;
      $('dlg-error').textContent = '';
      $('dlg-steps').replaceChildren();
      $('dlg-note').hidden = true;
      $('dlg-go').hidden = !show;
      $('dlg-go').disabled = false;
      $('dlg-close').textContent = show ? 'Cancel' : 'Close';
    }

    function closeDialog() {
      if (dlg && dlg.timer) clearTimeout(dlg.timer);
      dlg = null;
      $('overlay').hidden = true;
      refresh();
    }

    form.onsubmit = event => {
      event.preventDefault();
      if (!dlg) return;
      const data = { password: form.password.value, reboot: form.reboot.checked };
      let url;
      if (dlg.mode === 'add') {
        Object.assign(data, { host: form.host.value.trim(), user: form.user.value.trim(), name: form.name.value.trim() });
        url = '/api/robots';
      } else {
        data.forget = form.forget.checked;
        url = '/api/robots/' + encodeURIComponent(dlg.name) + '/' + dlg.mode;
      }
      $('dlg-go').disabled = true;
      $('dlg-error').textContent = '';
      post(url, data).then(out => {
        dlg.job = out.job;
        showForm(false);
        $('dlg-close').textContent = 'Hide';
        pollJob();
      }, err => {
        $('dlg-go').disabled = false;
        $('dlg-error').textContent = err.message;
      });
    };

    function pollJob() {
      if (!dlg || !dlg.job) return;
      const current = dlg;
      fetch('/api/jobs/' + current.job).then(res => res.json()).then(job => {
        if (dlg !== current) return;
        const list = $('dlg-steps');
        list.replaceChildren();
        for (const s of job.steps) {
          const li = document.createElement('li');
          li.className = s.state;
          const icon = document.createElement('span');
          icon.className = 'icon';
          icon.textContent = { ok: '✓', fail: '✕', run: '…', info: '' }[s.state];
          const text = document.createElement('span');
          text.textContent = s.text;
          if (s.state !== 'info') li.appendChild(icon);
          li.appendChild(text);
          list.appendChild(li);
        }
        if (job.state === 'running') {
          current.timer = setTimeout(pollJob, 600);
          return;
        }
        const note = $('dlg-note');
        note.hidden = false;
        if (job.state === 'done') {
          note.className = 'note good';
          note.textContent = job.message;
        } else {
          note.className = 'note ' + (job.state === 'warning' ? 'warn' : 'bad');
          note.textContent = job.message;
          if (job.state === 'failed') {          // let them fix the form and try again
            $('dlg-go').hidden = false;
            $('dlg-go').disabled = false;
            $('dlg-go').textContent = 'Try again';
            $('dlg-go').onclick = () => { $('dlg-go').onclick = null; showForm(true); $('dlg-go').textContent = TEXT[current.mode].go; return false; };
          }
        }
        $('dlg-close').textContent = 'Close';
        refresh();
      }).catch(() => { current.timer = setTimeout(pollJob, 1500); });
    }

    // ---- manual drive panel
    // While a button or key is held, the page sends a drive command about 10 times a second.
    // The robot stops by itself if they stop arriving, so a closed tab or dropped link is safe.

    // [forward, strafe, rotate] for each key; strafe + is right, rotate + is clockwise
    const DIRS = { w: [1, 0, 0], s: [-1, 0, 0], a: [0, -1, 0], d: [0, 1, 0], q: [0, 0, -1], e: [0, 0, 1] };
    const drv = { name: null, held: new Set(), moving: false, timer: null };

    function driveVector() {
      const speed = $('drive-speed').value / 100;
      const sum = [0, 0, 0];
      for (const k of drv.held) DIRS[k].forEach((x, i) => { sum[i] += x; });
      return sum.map(x => Math.max(-1, Math.min(1, x)) * speed);
    }

    function sendStop() {
      drv.moving = false;
      if (drv.name) post('/api/robots/' + encodeURIComponent(drv.name) + '/stop').catch(() => {});
    }

    function driveTick() {
      if (!drv.name) return;
      const v = driveVector();
      if (v.every(x => x === 0)) {
        if (drv.moving) sendStop();
        return;
      }
      drv.moving = true;
      post('/api/robots/' + encodeURIComponent(drv.name) + '/drive', { forward: v[0], strafe: v[1], rotate: v[2] })
        .then(() => { $('drive-error').textContent = ''; })
        .catch(err => { $('drive-error').textContent = err.message; });
    }

    function paintPad() {
      document.querySelectorAll('#drive-pad [data-key]').forEach(b => b.classList.toggle('on', drv.held.has(b.dataset.key)));
    }

    function release() { drv.held.clear(); paintPad(); }

    function openDrive(name) {
      drv.name = name;
      drv.moving = false;
      release();
      $('drive-title').textContent = 'Drive ' + name;
      $('drive-error').textContent = '';
      $('drive-overlay').hidden = false;
      clearInterval(drv.timer);
      drv.timer = setInterval(driveTick, 100);
    }

    function closeDrive() {
      release();
      sendStop();
      clearInterval(drv.timer);
      drv.timer = null;
      drv.name = null;
      $('drive-overlay').hidden = true;
    }

    document.querySelectorAll('#drive-pad [data-key]').forEach(b => {
      const key = b.dataset.key;
      b.onpointerdown = e => { e.preventDefault(); drv.held.add(key); paintPad(); };
      for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) {
        b['on' + ev] = () => { drv.held.delete(key); paintPad(); };
      }
    });
    $('drive-stop').onclick = () => { release(); sendStop(); };
    $('drive-close').onclick = closeDrive;
    $('drive-speed').oninput = () => { $('drive-speed-label').textContent = $('drive-speed').value + '%'; };
    document.addEventListener('keydown', e => {
      if ($('drive-overlay').hidden) return;
      const k = e.key.toLowerCase();
      if (e.key === 'Escape') { closeDrive(); return; }
      if (k === ' ') { e.preventDefault(); release(); sendStop(); return; }
      if (DIRS[k]) { e.preventDefault(); if (!e.repeat) { drv.held.add(k); paintPad(); } }
    });
    document.addEventListener('keyup', e => { drv.held.delete(e.key.toLowerCase()); paintPad(); });
    window.addEventListener('blur', () => { if (drv.name) release(); });
    document.addEventListener('visibilitychange', () => { if (document.hidden && drv.name) release(); });

    // ---- terminal: one command at a time over SSH; the server tells us which folder it ended in

    const term = { name: null, cwd: '', busy: false, history: [], pos: 0 };

    function termAdd(command, output, meta, bad) {
      const out = $('term-out');
      const line = document.createElement('div');
      line.className = 'cmd';
      line.textContent = command;
      out.appendChild(line);
      if (output) {
        const pre = document.createElement('pre');
        pre.textContent = output;             // text only, so robot output can't inject markup
        out.appendChild(pre);
      }
      if (meta) {
        const m = document.createElement('div');
        m.className = 'meta' + (bad ? ' bad' : '');
        m.textContent = meta;
        out.appendChild(m);
      }
      out.scrollTop = out.scrollHeight;
    }

    function setPrompt() { $('term-prompt').textContent = (term.cwd || '~') + ' $'; }

    function openTerm(name) {
      if (drv.name) closeDrive();
      term.name = name;
      term.cwd = '';
      term.busy = false;
      setPrompt();
      $('term-title').textContent = 'Terminal: ' + name;
      $('term-out').replaceChildren();
      $('term-input').value = '';
      $('term-overlay').hidden = false;
      $('term-input').focus();
    }

    function closeTerm() {
      term.name = null;
      $('term-overlay').hidden = true;
    }

    $('term-form').onsubmit = event => {
      event.preventDefault();
      const command = $('term-input').value.trim();
      if (!command || term.busy || !term.name) return;
      const name = term.name;
      const prompt = $('term-prompt').textContent;
      term.history.push(command);
      if (term.history.length > 200) term.history.shift();
      term.pos = term.history.length;
      term.busy = true;
      $('term-run').disabled = true;
      $('term-run').textContent = 'Running…';
      $('term-input').value = '';
      post('/api/robots/' + encodeURIComponent(name) + '/exec', { command: command, cwd: term.cwd }).then(out => {
        if (term.name !== name) return;       // the panel was closed or switched meanwhile
        if (out.cwd) term.cwd = out.cwd;
        setPrompt();
        let meta = '';
        if (out.timed_out) meta = 'stopped: it took longer than ' + out.limit + ' seconds';
        else if (out.code) meta = 'exit code ' + out.code;
        if (out.truncated) meta += (meta ? ' · ' : '') + 'output cut short';
        termAdd(prompt + ' ' + command, out.output, meta, !!out.code || !!out.timed_out);
      }, err => {
        if (term.name === name) termAdd(prompt + ' ' + command, '', err.message, true);
      }).finally(() => {
        term.busy = false;
        $('term-run').disabled = false;
        $('term-run').textContent = 'Run';
        if (term.name) $('term-input').focus();
      });
    };

    $('term-input').onkeydown = e => {         // Up / Down walk through earlier commands
      if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
      if (!term.history.length) return;
      e.preventDefault();
      term.pos = e.key === 'ArrowUp' ? Math.max(0, term.pos - 1) : Math.min(term.history.length, term.pos + 1);
      e.target.value = term.history[term.pos] || '';
    };
    $('term-clear').onclick = () => $('term-out').replaceChildren();
    $('term-close').onclick = closeTerm;
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('term-overlay').hidden) closeTerm(); });

    $('add').onclick = () => openDialog('add');
    $('dlg-close').onclick = closeDialog;
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('overlay').hidden) closeDialog(); });

    refresh();
    setInterval(refresh, 1000);
  </script>
{% else %}
  <div class="narrow card">
    <h1>Sign in</h1>
    {% if error %}<p class="error">{{ error }}</p>{% endif %}
    <form method="post" action="{{ url_for('login') }}">
      <input type="hidden" name="csrf" value="{{ csrf }}">
      <label>Username<input name="username" autocomplete="username" autofocus required></label>
      <label>Password<input name="password" type="password" autocomplete="current-password" required></label>
      <button type="submit" class="primary">Sign in</button>
    </form>
  </div>
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


def blocked(key):
    count, last = fails.get(key, (0, 0))
    if count >= MAX_FAILS and time.time() - last < LOCK_SECONDS:
        return True
    if count >= MAX_FAILS:
        fails.pop(key, None)
    return False


def record_fail(key):
    count, _ = fails.get(key, (0, 0))
    fails[key] = (count + 1, time.time())


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------------------------------------------------------------- web login

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
        record_fail(ip)
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


# ------------------------------------------------------------ robot link

def robot_send(rec, msg):
    """Send one JSON message to a robot. Returns False if the send failed."""
    try:
        with rec["send_lock"]:
            rec["ws"].send(json.dumps(msg))
        return True
    except Exception:
        return False


@sock.route("/robot")
def robot_socket(ws):
    """One WebSocket per robot. The robot speaks first with a 'hello' message."""
    key = "robot:" + str(request.remote_addr)
    rec = None
    try:
        if blocked(key):
            ws.send(json.dumps({"type": "refused", "reason": "too many attempts"}))
            return
        try:
            hello = json.loads(ws.receive(timeout=5) or "null")
        except ValueError:
            hello = None
        if not isinstance(hello, dict) or hello.get("type") != "hello":
            record_fail(key)
            ws.send(json.dumps({"type": "refused", "reason": "expected hello"}))
            return
        token_ok = secrets.compare_digest(str(hello.get("token", "")).encode(), ROBOT_TOKEN.encode())
        if not token_ok:
            record_fail(key)
            ws.send(json.dumps({"type": "refused", "reason": "bad token"}))
            return
        name = hello.get("name")
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            ws.send(json.dumps({"type": "refused", "reason": "bad name (use letters, digits, - and _)"}))
            return
        fails.pop(key, None)

        now = time.time()
        rec = {
            "name": name, "ws": ws, "send_lock": threading.Lock(), "online": True,
            "address": request.remote_addr, "robot_type": str(hello.get("robot_type", ""))[:32],
            "hostname": re.sub(r"[^A-Za-z0-9._-]", "", str(hello.get("hostname", "")))[:64],
            "connected_at": now, "last_seen": now, "latency_ms": None,
            "ping_sent": {}, "event": "connected",
        }
        with robots_lock:
            old = robots.get(name)
            robots[name] = rec
        if old is not None and old["online"]:
            old["online"] = False      # same name connected again: newest wins
            try:
                old["ws"].close()
            except Exception:
                pass
        robot_send(rec, {"type": "welcome", "name": name, "seen_as": request.remote_addr})

        while True:
            raw = ws.receive(timeout=SILENCE_LIMIT)
            if raw is None:
                rec["event"] = "went silent"
                break
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(msg, dict):
                continue
            rec["last_seen"] = time.time()
            kind = msg.get("type")
            if kind == "heartbeat":
                # The ack carries the swarm list, which the robot's status screen shows.
                robot_send(rec, {"type": "heartbeat_ack", "swarm": swarm_for_robots()})
            elif kind == "pong":
                sent = rec["ping_sent"].pop(msg.get("id"), None)
                if sent is not None:
                    rec["latency_ms"] = round((time.time() - sent) * 1000)
                    rec["event"] = "ping ok"
            elif kind == "stop_ack":
                rec["event"] = "stop acknowledged"
    except ConnectionClosed:
        pass
    finally:
        if rec is not None:
            with robots_lock:
                if robots.get(rec["name"]) is rec:
                    rec["online"] = False
                    if rec["event"] != "went silent":
                        rec["event"] = "disconnected"


# ------------------------------------------------- installing robots (SSH)

class DeployError(Exception):
    """A problem to show the user, in plain words."""


class HostKeyChanged(Exception):
    pass


def paramiko_module():
    try:
        import paramiko
    except ImportError:
        raise DeployError("The SSH library is missing. In Terminal, in the swarm-hub folder, run:  "
                          "pip install -r serverrequirements.txt")
    return paramiko


def hub_key():
    """The hub's own SSH key. Each robot it installs trusts it, so later updates need no password."""
    paramiko = paramiko_module()
    with key_lock:
        if not HUB_KEY_FILE.exists():
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import ed25519
            private = ed25519.Ed25519PrivateKey.generate()
            write_private(HUB_KEY_FILE, private.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption()))
        key = paramiko.Ed25519Key.from_private_key_file(str(HUB_KEY_FILE))
    return key, f"{key.get_name()} {key.get_base64()} swarm-hub"


def ssh_connect(host, user, password, expected_host_key=None):
    """Log in to a robot. Returns (client, the robot's host key as text).

    With expected_host_key set (updates and removals), refuse to talk to a
    machine whose SSH identity differs from the one recorded when it was added.
    """
    paramiko = paramiko_module()
    from paramiko.ssh_exception import NoValidConnectionsError
    pkey, _ = hub_key()
    seen = {}

    class Policy(paramiko.MissingHostKeyPolicy):
        def missing_host_key(self, client, hostname, key):
            seen["key"] = f"{key.get_name()} {key.get_base64()}"
            if expected_host_key and seen["key"] != expected_host_key:
                raise HostKeyChanged()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(Policy())
    try:
        client.connect(host, port=22, username=user, password=password or None, pkey=pkey,
                       look_for_keys=False, allow_agent=False,
                       timeout=8, banner_timeout=10, auth_timeout=15)
    except HostKeyChanged:
        client.close()
        raise DeployError(f"A different machine is answering at {host} (its SSH identity changed). "
                          "If you reinstalled this robot's system, remove it here and add it again. "
                          "If several robots share this address (hotspot mode), connect to the right one.")
    except paramiko.AuthenticationException:
        client.close()
        if password:
            raise DeployError("The robot rejected that username or password.")
        raise DeployError("The robot didn't accept the hub's key. Enter the robot's password and try again.")
    except (NoValidConnectionsError, socket.timeout, TimeoutError, ConnectionError) as err:
        client.close()
        raise DeployError(f"Couldn't reach {host}. Check the robot is on and this computer is on "
                          f"the same network as it. ({err})")
    except socket.gaierror:
        client.close()
        raise DeployError(f"'{host}' isn't a known address. Check the IP address.")
    except (paramiko.SSHException, OSError) as err:
        client.close()
        raise DeployError(f"SSH failed: {err}")
    return client, seen.get("key", "")


def run(client, command, stdin_data=None, timeout=60):
    """Run a shell command on the robot. Returns (exit code, stdout, stderr)."""
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    if stdin_data is not None:
        stdin.write(stdin_data)
        stdin.flush()
    stdin.channel.shutdown_write()
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    return stdout.channel.recv_exit_status(), out, err


def run_capped(client, command, timeout, cap):
    """Run a command, collecting stdout and stderr together. Stops waiting after `timeout`
    seconds or `cap` bytes. Returns (exit code or None, output, timed_out, truncated)."""
    chan = client.get_transport().open_session()
    chan.set_combine_stderr(True)
    chan.exec_command(command)
    chan.shutdown_write()                   # nothing to type: commands that wait for input just end
    out = bytearray()
    deadline = time.time() + timeout
    timed_out = truncated = False
    try:
        while True:
            if chan.recv_ready():
                data = chan.recv(65536)
                room = cap - len(out)
                out += data[:room]
                if len(data) > room:
                    truncated = True
                    break
                continue
            if chan.exit_status_ready() or chan.closed:
                break
            if time.time() > deadline:
                timed_out = True
                break
            time.sleep(0.05)
        code = None if (timed_out or truncated) else chan.recv_exit_status()
    finally:
        chan.close()
    return code, out.decode(errors="replace"), timed_out, truncated


def run_terminal(entry, command, cwd):
    """Run one terminal command on an installed robot over SSH.

    Each command is its own login, so the hub passes the current folder in (cwd) and reads
    the folder the command ended in, which makes `cd` stick between commands."""
    client, _ = ssh_connect(entry["host"], entry["user"], None, entry.get("host_key"))
    try:
        script = (f"cd {shlex.quote(cwd)} 2>/dev/null || cd ~\n" if cwd else "") + command + (
            f"\n__rc=$?\necho\necho {TERM_MARK}$(pwd)\nexit $__rc")
        remote = f"timeout -k 2 {TERM_TIMEOUT} bash -c {shlex.quote(script)}"
        code, text, timed_out, truncated = run_capped(client, remote, TERM_TIMEOUT + 5, TERM_MAX_OUTPUT)
    except Exception as err:
        raise DeployError(f"Running the command failed: {err}")
    finally:
        client.close()
    timed_out = timed_out or code in (124, 137)
    new_cwd = cwd
    at = text.rfind(TERM_MARK)
    if at != -1:
        lines = text[at + len(TERM_MARK):].splitlines()
        if lines:
            new_cwd = lines[0].strip() or cwd
        text = text[:at].rstrip("\n")       # also drops the blank line the marker adds
    return {"output": text, "code": None if timed_out else code, "cwd": new_cwd,
            "timed_out": timed_out, "truncated": truncated, "limit": TERM_TIMEOUT}


def run_as_root(client, command, password):
    """Run a command with sudo, typing the password for sudo only if the robot asks for one."""
    script = shlex.quote(command)
    code, _, _ = run(client, "sudo -n true")
    if code == 0:
        return run(client, f"sudo -n sh -c {script}")
    if not password:
        raise DeployError("This step needs administrator rights, and the robot wants its password for that. "
                          "Enter the robot's password and try again.")
    code, out, err = run(client, f"sudo -S -p '' sh -c {script}", stdin_data=password + "\n")
    low = err.lower()
    if "incorrect password" in low or "sorry, try again" in low:
        raise DeployError("sudo on the robot rejected the password.")
    if "not in the sudoers" in low or "not allowed to" in low:
        raise DeployError("This robot user isn't allowed to use sudo, which is needed to set up start-on-boot.")
    return code, out, err


def robot_facts(client):
    probe = (
        'echo "user=$(id -un)"; echo "home=$HOME"; '
        'echo "python=$(command -v python3)"; '
        'echo "pyver=$(python3 -c \'import sys; print(\"%d.%d\" % sys.version_info[:2])\' 2>/dev/null)"; '
        'echo "machine=$(cat /etc/machine-id 2>/dev/null)"; '
        'echo "hostname=$(hostname)"; echo "systemd=$(command -v systemctl)"; '
        'echo "tk=$(python3 -c \'import tkinter\' >/dev/null 2>&1 && echo yes)"; '
        'echo "desktop=$([ -d /etc/xdg/autostart ] && echo yes)"'
    )
    _, out, _ = run(client, probe)
    facts = {}
    for line in out.splitlines():
        k, sep, v = line.partition("=")
        if sep and k in ("user", "home", "python", "pyver", "machine", "hostname", "systemd", "tk", "desktop"):
            facts[k] = v.strip()
    if not facts.get("python"):
        raise DeployError("This robot has no python3, which the agent needs.")
    try:
        version = tuple(int(x) for x in facts.get("pyver", "").split("."))
    except ValueError:
        version = ()
    if len(version) != 2 or version < (3, 7):
        raise DeployError(f"This robot has Python {facts.get('pyver') or '(unknown)'}; the agent needs 3.7 or newer.")
    if not facts.get("systemd"):
        raise DeployError("This robot doesn't use systemd, so the hub can't set up start-on-boot.")
    for k, pattern in (("user", USER_RE), ("home", PATH_RE), ("python", PATH_RE)):
        if not pattern.fullmatch(facts.get(k, "")):
            raise DeployError(f"Unexpected {k} on the robot: {facts.get(k)!r}")
    return facts


def hub_addresses(client):
    """Where the robot should reach this hub: the address this computer used to
    reach the robot, plus this Mac's .local name as a fallback if the IP changes."""
    local_ip = client.get_transport().sock.getsockname()[0]
    addrs = [f"[{local_ip}]:{PORT}" if ":" in local_ip else f"{local_ip}:{PORT}"]
    if sys.platform == "darwin":
        try:
            name = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True,
                                  text=True, timeout=3).stdout.strip()
            if re.fullmatch(r"[A-Za-z0-9-]{1,63}", name):
                addrs.append(f"{name}.local:{PORT}")
        except Exception:
            pass
    return addrs


def service_unit(facts):
    folder = f"{facts['home']}/{REMOTE_DIR}"
    return (
        "[Unit]\n"
        "Description=Swarm Hub robot agent\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n"
        "\n"
        "[Service]\n"
        f"User={facts['user']}\n"
        f"WorkingDirectory={folder}\n"
        f"ExecStart={facts['python']} -u {folder}/robot_agent.py\n"
        "Restart=always\n"
        "RestartSec=2\n"
        "\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )


def autostart_entry(facts):
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Swarm status\n"
        "Comment=Shows this robot's Swarm Hub connection\n"
        f"Exec={facts['python']} {facts['home']}/{REMOTE_DIR}/status_ui.py\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def agent_log(client, password):
    """Last lines the agent printed on the robot, to explain a failure."""
    cmd = f"journalctl -u {SERVICE}.service -n 12 --no-pager -o cat"
    code, out, _ = run(client, cmd + " 2>/dev/null")
    if not out.strip():
        try:
            code, out, _ = run_as_root(client, cmd, password)
        except DeployError:
            out = ""
    return [line for line in out.splitlines() if line.strip()][-12:]


def pick_name(wanted, machine_id):
    """Choose the robot's name: the one it already has, the one asked for, or the next free one."""
    with registry_lock:
        for name, entry in registry.items():
            if machine_id and entry.get("machine_id") == machine_id:
                return name, True
        with robots_lock:
            taken = set(registry) | set(robots) | pending_names
        if wanted:
            if wanted in taken:
                raise DeployError(f"The name '{wanted}' is already used by another robot. Pick another name.")
            name = wanted
        else:
            n = 1
            while f"{DEFAULT_PREFIX}{n:02d}" in taken:
                n += 1
            name = f"{DEFAULT_PREFIX}{n:02d}"
        pending_names.add(name)
        return name, False


def save_registry_entry(name, entry):
    with registry_lock:
        registry[name] = entry
        write_private(REGISTRY_FILE, json.dumps(registry, indent=2))


def wait_for_robot(name, since, timeout=CONNECT_WAIT):
    end = time.time() + timeout
    while time.time() < end:
        with robots_lock:
            rec = robots.get(name)
        if rec and rec["online"] and rec["connected_at"] >= since:
            return True
        time.sleep(0.5)
    return False


def do_install(job, host, user, password, wanted_name=None, existing=None, reboot=False):
    """Install the agent on a robot (Add), or re-install it (Update); optionally reboot it after."""
    if not AGENT_FILE.exists():
        raise DeployError(f"{AGENT_FILE.name} is missing. Put it in the same folder as server.py.")
    _, public_key = hub_key()
    step(job, f"Connecting to {user}@{host}")
    client, host_key = ssh_connect(host, user, password, existing and existing.get("host_key"))
    reserved = None
    try:
        step(job, "Checking the robot")
        facts = robot_facts(client)
        if existing:
            name = job["robot"]
        else:
            name, known = pick_name(wanted_name, facts.get("machine") or host_key)
            if known:
                info(job, f"This robot was already added as {name}; updating it.")
            else:
                reserved = name
            job["robot"] = name
        folder = f"{facts['home']}/{REMOTE_DIR}"

        step(job, "Letting the hub log in without a password next time")
        add_key = (
            'mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && '
            'chmod 600 ~/.ssh/authorized_keys && '
            '{ [ ! -s ~/.ssh/authorized_keys ] || [ -z "$(tail -c1 ~/.ssh/authorized_keys)" ] '
            '|| echo >> ~/.ssh/authorized_keys; } && '
            f'{{ grep -qxF {shlex.quote(public_key)} ~/.ssh/authorized_keys '
            f'|| echo {shlex.quote(public_key)} >> ~/.ssh/authorized_keys; }}'
        )
        code, _, err = run(client, add_key)
        if code != 0:
            info(job, f"Couldn't add the key ({err.strip() or 'unknown error'}); updates will need the password.")

        screen = STATUS_UI_FILE.exists() and facts.get("tk") == "yes" and facts.get("desktop") == "yes"
        step(job, f"Copying the agent{' and status screen' if screen else ''} to {folder}")
        addrs = hub_addresses(client)
        config = {"hub": addrs, "name": name, "token": ROBOT_TOKEN, "robot_type": "masterpi"}
        if screen:
            run(client, "mkdir -p ~/.config/autostart")
        sftp = client.open_sftp()
        try:
            try:
                sftp.mkdir(folder, 0o755)
            except IOError:
                pass                                      # already there
            sftp.put(str(AGENT_FILE), f"{folder}/robot_agent.py")
            with sftp.open(f"{folder}/config.json", "w") as f:
                f.chmod(0o600)                            # private before the token goes in
                f.write(json.dumps(config, indent=2))
            with sftp.open(f"{folder}/{SERVICE}.service", "w") as f:
                f.write(service_unit(facts))
            if screen:
                sftp.put(str(STATUS_UI_FILE), f"{folder}/status_ui.py")
                with sftp.open(f"{facts['home']}/{AUTOSTART}", "w") as f:
                    f.write(autostart_entry(facts))
        finally:
            sftp.close()
        info(job, "Robot will connect to " + " or ".join(addrs))
        if not screen:
            missing = ("status_ui.py isn't next to server.py" if not STATUS_UI_FILE.exists()
                       else "this robot has no desktop" if facts.get("desktop") != "yes"
                       else "this robot's Python has no tkinter")
            info(job, f"Skipped the status screen: {missing}.")

        step(job, "Setting it to start on every boot")
        since = time.time()
        code, out, err = run_as_root(client, (
            f"install -m 644 {shlex.quote(folder)}/{SERVICE}.service /etc/systemd/system/{SERVICE}.service && "
            f"systemctl daemon-reload && systemctl enable --quiet {SERVICE}.service && "
            f"systemctl restart {SERVICE}.service"
        ), password)
        if code != 0:
            raise DeployError("Installing the service failed: " + (err.strip() or out.strip() or f"exit code {code}"))
        time.sleep(1.5)
        _, state, _ = run(client, f"systemctl is-active {SERVICE}.service")
        if state.strip() != "active":
            for line in agent_log(client, password):
                info(job, line)
            raise DeployError(f"The agent didn't start on the robot (service is {state.strip() or 'unknown'}). "
                              "Its last messages are above.")

        with registry_lock:
            prior = registry.get(name) or {}
        save_registry_entry(name, {
            "host": host, "user": facts["user"], "home": facts["home"], "host_key": host_key,
            "machine_id": facts.get("machine", ""), "hostname": facts.get("hostname", ""),
            "added": prior.get("added", time.time()), "updated": time.time(),
        })

        step(job, "Waiting for the robot to connect to the hub")
        if not wait_for_robot(name, since):
            log = agent_log(client, password)
            for line in log:
                info(job, line)
            latest = log[-3:]                     # older lines may be from an earlier run
            if any(re.match(r"(Traceback|\w+(Error|Exception)\b|Missing config|config\.json)", ln) for ln in latest):
                why = ("The agent is crashing on the robot (see its messages above). "
                       "If you edited robot_agent.py, fix it and press Update.")
            elif any("hub refused" in ln for ln in latest):
                why = "The hub refused it (see above). Press Update to send it fresh settings."
            else:
                why = ("The robot can't reach this computer. Make sure macOS allows incoming connections "
                       "for Python (System Settings > Network > Firewall), then wait a few seconds.")
            if reboot:
                why += " (It wasn't rebooted, since that wouldn't fix this.)"
            job["warning"] = f"{name} is installed and will start on every boot, but it hasn't connected yet. {why}"
            return

        if not reboot:
            job["message"] = f"{name} is installed, connected, and will start by itself whenever the robot boots."
            if screen:
                job["message"] += (" If its status screen is open it updates itself; otherwise it opens "
                                   "the next time the robot starts.")
            return

        step(job, "Rebooting the robot")
        reboot_at = time.time()
        try:
            run_as_root(client, "systemctl --no-block reboot", password)
        except DeployError:
            raise
        except Exception:
            pass                                          # the link can drop as the robot shuts down
        client.close()

        step(job, "Waiting for it to start up and reconnect by itself (about a minute)")
        if not wait_for_robot(name, reboot_at, timeout=REBOOT_WAIT):
            job["warning"] = (
                f"{name} rebooted but hasn't reconnected after {REBOOT_WAIT // 60} minutes. If this computer "
                "switched Wi-Fi networks while the robot restarted (it happens in hotspot mode), join the "
                "robot's Wi-Fi again and it will reconnect by itself.")
            return
        job["message"] = f"{name} rebooted, started by itself and reconnected."
        if screen:
            job["message"] += " Its status screen is open on the robot's desktop."
    finally:
        client.close()
        if reserved:
            with registry_lock:
                pending_names.discard(reserved)


def do_remove(job, password, forget=False):
    name = job["robot"]
    with registry_lock:
        entry = registry.get(name)
    if entry and not forget:
        _, public_key = hub_key()
        step(job, f"Connecting to {entry['user']}@{entry['host']}")
        client, _ = ssh_connect(entry["host"], entry["user"], password, entry.get("host_key"))
        try:
            step(job, "Stopping the agent and removing the start-on-boot service")
            code, out, err = run_as_root(client, (
                f"systemctl disable --now {SERVICE}.service 2>/dev/null; "
                f"rm -f /etc/systemd/system/{SERVICE}.service; systemctl daemon-reload"
            ), password)
            if code != 0:
                raise DeployError("Removing the service failed: " + (err.strip() or out.strip() or f"exit code {code}"))
            step(job, "Closing the status screen and deleting the hub's files and key")
            folder = f"{entry['home']}/{REMOTE_DIR}"
            key_b64 = public_key.split()[1]
            run(client, (
                # "[s]tatus" so pkill doesn't match this very shell command
                f"pkill -f {shlex.quote(folder + '/[s]tatus_ui.py')}; rm -f ~/{AUTOSTART}; "
                f"rm -rf {shlex.quote(folder)}; f=~/.ssh/authorized_keys; "
                f'if [ -f "$f" ]; then grep -vF {shlex.quote(key_b64)} "$f" > "$f.swarm-tmp"; '
                f'cat "$f.swarm-tmp" > "$f"; rm -f "$f.swarm-tmp"; fi'
            ))
        finally:
            client.close()
    step(job, "Taking it off the list")
    with registry_lock:
        registry.pop(name, None)
        write_private(REGISTRY_FILE, json.dumps(registry, indent=2))
    with robots_lock:
        rec = robots.pop(name, None)
    if rec is not None and rec["online"]:
        rec["online"] = False
        try:
            rec["ws"].close()
        except Exception:
            pass
    if forget and entry:
        job["message"] = (f"{name} is off the list. If the robot still has the agent, it will reappear "
                          "when it connects; use Add robot then Remove to uninstall it properly.")
    else:
        job["message"] = f"{name} has been removed."


# ---- jobs: installs/updates/removals run in the background and report steps to the app

def step(job, text):
    for s in job["steps"]:
        if s["state"] == "run":
            s["state"] = "ok"
    job["steps"].append({"text": text, "state": "run"})


def info(job, text):
    job["steps"].append({"text": text, "state": "info"})


def start_job(action, robot, fn, **kwargs):
    job = {"id": secrets.token_hex(8), "action": action, "robot": robot, "state": "running",
           "steps": [], "message": "", "warning": None, "started": time.time()}
    with jobs_lock:
        if robot and any(j["robot"] == robot and j["state"] == "running" for j in jobs.values()):
            return None
        jobs[job["id"]] = job
        for old in sorted(jobs.values(), key=lambda j: j["started"])[:-30]:
            if old["state"] != "running":
                jobs.pop(old["id"], None)

    def runner():
        try:
            fn(job, **kwargs)
            final = "warning" if job["warning"] else "done"
            for s in job["steps"]:
                if s["state"] == "run":
                    s["state"] = "fail" if final == "warning" else "ok"
            job["message"] = job["warning"] or job["message"] or "Done."
            job["state"] = final
        except Exception as err:
            if not isinstance(err, DeployError):
                err = f"Unexpected error: {type(err).__name__}: {err}"
            for s in job["steps"]:
                if s["state"] == "run":
                    s["state"] = "fail"
            job["message"] = str(err)
            job["state"] = "failed"
        finally:
            kwargs.clear()          # drop the password

    threading.Thread(target=runner, daemon=True).start()
    return job


# ---------------------------------------------------------------- web API

def api_guard():
    """Return an error response if the caller may not use the API, else None."""
    if "user" not in session:
        return jsonify(error="not signed in"), 401
    if request.method == "POST":
        sent = request.headers.get("X-CSRF", "").encode()
        if not sent or not secrets.compare_digest(sent, session.get("csrf", "").encode()):
            return jsonify(error="bad csrf token"), 400
    return None


def robot_rows():
    """Every robot the hub knows (installed here or connected now), with its status."""
    now = time.time()
    with registry_lock:
        reg = dict(registry)
    with robots_lock:
        live = dict(robots)
    rows = []
    for name in sorted(set(reg) | set(live)):
        r, entry = live.get(name), reg.get(name)
        if r is None:
            status, ago, latency = "offline", None, None
            event = "installed, hasn't connected yet"
        else:
            ago = now - r["last_seen"]
            if not r["online"]:
                status = "offline"
            elif ago < ONLINE_WITHIN:
                status = "connected"
            else:
                status = "unresponsive"
            ago, latency, event = round(ago, 1), r["latency_ms"], r["event"]
        rows.append({
            "name": name, "status": status, "seen_ago": ago, "latency_ms": latency, "event": event,
            "hostname": (r and r.get("hostname")) or (entry and entry.get("hostname")) or "",
            "address": (r["address"] if r else None) or (entry["host"] if entry else None),
            "installed": entry is not None,
        })
    return rows


_swarm_cache = {"at": 0.0, "rows": []}


def swarm_for_robots():
    """The swarm list sent to robots (refreshed at most twice a second)."""
    now = time.time()
    if now - _swarm_cache["at"] > 0.5:
        _swarm_cache["rows"] = [{k: r[k] for k in ("name", "hostname", "address", "status")}
                                for r in robot_rows()]
        _swarm_cache["at"] = now
    return _swarm_cache["rows"]


@app.get("/api/robots")
def api_robots():
    bad = api_guard()
    if bad:
        return bad
    with jobs_lock:
        busy = {}
        for j in jobs.values():
            if j["state"] == "running" and j["robot"]:
                current = [s["text"] for s in j["steps"] if s["state"] == "run"]
                busy[j["robot"]] = (current[-1] + "…") if current else "working…"
    rows = robot_rows()
    for r in rows:
        r["job"] = busy.get(r["name"])
    return jsonify(rows)


@app.post("/api/robots")
def api_add_robot():
    bad = api_guard()
    if bad:
        return bad
    data = request.get_json(silent=True) or {}
    host = str(data.get("host", "")).strip()
    user = str(data.get("user", "")).strip() or "pi"
    password = str(data.get("password", ""))
    name = str(data.get("name", "")).strip()
    if not HOST_RE.fullmatch(host):
        return jsonify(error="Enter the robot's IP address, for example 192.168.149.1."), 400
    if not USER_RE.fullmatch(user):
        return jsonify(error="That username doesn't look right."), 400
    if not password:
        return jsonify(error="Enter the robot's password."), 400
    if name and not NAME_RE.fullmatch(name):
        return jsonify(error="Names can use letters, digits, - and _ (up to 32)."), 400
    job = start_job("add", None, do_install, host=host, user=user, password=password,
                    wanted_name=name or None, reboot=bool(data.get("reboot", True)))
    return jsonify(job=job["id"])


@app.get("/api/jobs/<job_id>")
def api_job(job_id):
    bad = api_guard()
    if bad:
        return bad
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return jsonify(error="no such job"), 404
        out = {k: job[k] for k in ("state", "robot", "message", "action")}
        out["steps"] = list(job["steps"])
        return jsonify(out)


@app.post("/api/robots/<name>/<cmd>")
def api_robot_command(name, cmd):
    bad = api_guard()
    if bad:
        return bad
    if cmd in ("update", "remove"):
        data = request.get_json(silent=True) or {}
        password = str(data.get("password", ""))
        with registry_lock:
            entry = registry.get(name)
        if cmd == "update":
            if entry is None:
                return jsonify(error="This robot wasn't installed by the hub."), 404
            job = start_job("update", name, do_install, host=entry["host"], user=entry["user"],
                            password=password, existing=entry, reboot=bool(data.get("reboot", False)))
        else:
            job = start_job("remove", name, do_remove, password=password, forget=bool(data.get("forget")))
        if job is None:
            return jsonify(error="Something is already running for this robot. Wait for it to finish."), 409
        return jsonify(job=job["id"])
    if cmd == "exec":
        # Terminal: run one command on the robot over SSH (works even if its agent is offline).
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}
        command, cwd = data.get("command"), data.get("cwd") or ""
        if not isinstance(command, str) or not command.strip():
            return jsonify(error="Type a command."), 400
        if len(command) > 4000 or "\0" in command:
            return jsonify(error="That command is too long."), 400
        if not isinstance(cwd, str) or len(cwd) > 500 or "\0" in cwd:
            cwd = ""
        with registry_lock:
            entry = registry.get(name)
        if entry is None:
            return jsonify(error="This robot wasn't installed by the hub, so the hub can't log in to it."), 404
        try:
            return jsonify(run_terminal(entry, command, cwd))
        except DeployError as err:
            return jsonify(error=str(err)), 502
    if cmd not in ("ping", "stop", "drive"):
        return jsonify(error="unknown command"), 404
    with robots_lock:
        rec = robots.get(name)
    if rec is None or not rec["online"]:
        return jsonify(error="robot is offline"), 409
    if cmd == "drive":
        # Manual control: forward, strafe and rotate, each from -1 to 1. The page repeats this
        # about 10 times a second while a button is held; the robot stops if it stops arriving.
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}
        try:
            values = [float(data.get(k, 0)) for k in ("forward", "strafe", "rotate")]
        except (TypeError, ValueError):
            return jsonify(error="forward, strafe and rotate must be numbers from -1 to 1"), 400
        if not all(math.isfinite(v) for v in values):
            return jsonify(error="forward, strafe and rotate must be numbers from -1 to 1"), 400
        forward, strafe, rotate = (max(-1.0, min(1.0, v)) for v in values)
        ok = robot_send(rec, {"type": "drive", "forward": forward, "strafe": strafe, "rotate": rotate})
        rec["event"] = "driving" if any((forward, strafe, rotate)) else "drive stopped"
        return jsonify(ok=ok)
    if cmd == "ping":
        ping_id = secrets.randbelow(10 ** 9)
        if len(rec["ping_sent"]) > 20:
            rec["ping_sent"].clear()
        rec["ping_sent"][ping_id] = time.time()
        ok = robot_send(rec, {"type": "ping", "id": ping_id})
    else:
        ok = robot_send(rec, {"type": "stop"})
        rec["event"] = "stop sent"
    return jsonify(ok=ok)


# ------------------------------------------------------------------- setup

def add_user(name):
    password = getpass.getpass("Password: ")
    if len(password) < 8:
        sys.exit("Use at least 8 characters.")
    if getpass.getpass("Repeat password: ") != password:
        sys.exit("Passwords do not match.")
    users = load_users()
    users[name] = generate_password_hash(password)
    write_private(USERS_FILE, json.dumps(users, indent=2))
    print(f"Saved user '{name}'.")


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no traffic is sent
        return s.getsockname()[0]
    except OSError:
        return "your-computer's-address"
    finally:
        s.close()


def run_server():
    app.run(host="0.0.0.0", port=PORT, threaded=True)


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
    if len(sys.argv) == 2 and sys.argv[1] == "token":
        print(ROBOT_TOKEN)
        sys.exit()
    if not load_users():
        sys.exit("No users yet. Create one first:  python server.py adduser <name>")
    if not AGENT_FILE.exists():
        print(f"Warning: {AGENT_FILE.name} is missing from this folder, so Add robot won't work.")
    print(f"Web page:  http://{lan_ip()}:{PORT}  (any device on your network)")
    if "--headless" in sys.argv:
        run_server()          # server only, no window
    else:
        import webview        # native window; needs: pip install pywebview

        threading.Thread(target=run_server, daemon=True).start()
        if not wait_for_server():
            sys.exit("The server did not start.")
        webview.create_window("Swarm Hub", f"http://127.0.0.1:{PORT}", width=1100, height=720)
        webview.start()       # returns when you close the window; the server stops too

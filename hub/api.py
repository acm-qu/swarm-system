"""The JSON API the web page uses. Every route needs a signed-in user (and a CSRF header for POST)."""

import math
import secrets
import time

from flask import Blueprint, Response, jsonify, request

from . import config, deploy, jobs, robots, storage
from .auth import api_guard
from .jobs import DeployError

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.before_request
def guard():
    return api_guard()


def json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@bp.get("/robots")
def list_robots():
    busy = jobs.busy_robots()
    rows = robots.robot_rows()
    for r in rows:
        r["job"] = busy.get(r["name"])
    return jsonify(rows)


@bp.post("/robots")
def add_robot():
    data = json_body()
    host = str(data.get("host", "")).strip()
    user = str(data.get("user", "")).strip() or "pi"
    password = str(data.get("password", ""))
    name = str(data.get("name", "")).strip()
    if not config.HOST_RE.fullmatch(host):
        return jsonify(error="Enter the robot's IP address, for example 192.168.149.1."), 400
    if not config.USER_RE.fullmatch(user):
        return jsonify(error="That username doesn't look right."), 400
    if not password:
        return jsonify(error="Enter the robot's password."), 400
    if name and not config.NAME_RE.fullmatch(name):
        return jsonify(error="Names can use letters, digits, - and _ (up to 32)."), 400
    job = jobs.start("add", None, deploy.do_install, host=host, user=user, password=password,
                     wanted_name=name or None, reboot=bool(data.get("reboot", False)))
    return jsonify(job=job["id"])


@bp.get("/jobs/<job_id>")
def get_job(job_id):
    job = jobs.snapshot(job_id)
    if job is None:
        return jsonify(error="no such job"), 404
    return jsonify(job)


@bp.get("/robots/<name>/camera")
def camera(name):
    """Live camera as an MJPEG stream (an <img> tag can show it directly).
    Opening this is what tells the robot to start its camera."""
    rec = robots.get_online(name)
    if rec is None:
        return jsonify(error="robot is offline"), 409

    def frames():
        last_id = None
        idle_since = time.time()
        try:
            while rec["online"]:
                rec["cam_wanted"] = time.time()
                frame, frame_id = rec["frame"], rec["frame_id"]
                if frame is not None and frame_id != last_id:
                    last_id = frame_id
                    idle_since = time.time()
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                           + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n")
                else:
                    time.sleep(0.03)
                    if time.time() - idle_since > 15:      # nothing for a while: let the page retry
                        return
        finally:
            rec["cam_wanted"] = 0.0

    return Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame",
                    headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


# ---- installing: update / remove / terminal (over SSH)

def registry_entry(name):
    with storage.registry_lock:
        return storage.registry.get(name)


@bp.post("/robots/<name>/update")
def update_robot(name):
    data = json_body()
    entry = registry_entry(name)
    if entry is None:
        return jsonify(error="This robot wasn't installed by the hub."), 404
    job = jobs.start("update", name, deploy.do_install, host=entry["host"], user=entry["user"],
                     password=str(data.get("password", "")), existing=entry,
                     reboot=bool(data.get("reboot", False)))
    if job is None:
        return jsonify(error="Something is already running for this robot. Wait for it to finish."), 409
    return jsonify(job=job["id"])


@bp.post("/robots/<name>/remove")
def remove_robot(name):
    data = json_body()
    job = jobs.start("remove", name, deploy.do_remove, password=str(data.get("password", "")),
                     forget=bool(data.get("forget")))
    if job is None:
        return jsonify(error="Something is already running for this robot. Wait for it to finish."), 409
    return jsonify(job=job["id"])


@bp.post("/robots/<name>/exec")
def terminal(name):
    """Terminal: run one command on the robot over SSH (works even if its agent is offline)."""
    data = json_body()
    command, cwd = data.get("command"), data.get("cwd") or ""
    if not isinstance(command, str) or not command.strip():
        return jsonify(error="Type a command."), 400
    if len(command) > 4000 or "\0" in command:
        return jsonify(error="That command is too long."), 400
    if not isinstance(cwd, str) or len(cwd) > 500 or "\0" in cwd:
        cwd = ""
    entry = registry_entry(name)
    if entry is None:
        return jsonify(error="This robot wasn't installed by the hub, so the hub can't log in to it."), 404
    try:
        return jsonify(deploy.run_terminal(entry, command, cwd))
    except DeployError as err:
        return jsonify(error=str(err)), 502


# ---- live commands (over the robot's WebSocket)

def online_or_409(name):
    rec = robots.get_online(name)
    if rec is None:
        return None, (jsonify(error="robot is offline"), 409)
    return rec, None


@bp.post("/robots/<name>/drive")
def drive(name):
    """Manual control: forward, strafe and rotate, each from -1 to 1. The page repeats this
    about 10 times a second while a button is held; the robot stops if it stops arriving."""
    rec, err = online_or_409(name)
    if err:
        return err
    data = json_body()
    try:
        values = [float(data.get(k, 0)) for k in ("forward", "strafe", "rotate")]
    except (TypeError, ValueError):
        return jsonify(error="forward, strafe and rotate must be numbers from -1 to 1"), 400
    if not all(math.isfinite(v) for v in values):
        return jsonify(error="forward, strafe and rotate must be numbers from -1 to 1"), 400
    forward, strafe, rotate = (max(-1.0, min(1.0, v)) for v in values)
    ok = robots.send(rec, {"type": "drive", "forward": forward, "strafe": strafe, "rotate": rotate})
    rec["event"] = "driving" if any((forward, strafe, rotate)) else "drive stopped"
    return jsonify(ok=ok)


@bp.post("/robots/<name>/arm")
def arm(name):
    """Arm: servo pulse widths in microseconds per joint, e.g. {"targets": {"base": 1500}}.
    The robot clips each one to that joint's limits in robot/robot_movement.py."""
    rec, err = online_or_409(name)
    if err:
        return err
    targets = json_body().get("targets")
    if not isinstance(targets, dict) or not targets or len(targets) > 16:
        return jsonify(error="targets must name the joints to move, e.g. {\"base\": 1500}"), 400
    clean = {}
    for joint, value in targets.items():
        try:
            value = float(value)
        except (TypeError, ValueError):
            return jsonify(error="arm values must be numbers (pulse width in microseconds)"), 400
        if not config.JOINT_RE.fullmatch(str(joint)) or not math.isfinite(value) or not 400 <= value <= 2600:
            return jsonify(error="bad joint name or a pulse width outside 400-2600 microseconds"), 400
        clean[joint] = value
    ok = robots.send(rec, {"type": "arm", "targets": clean})
    rec["event"] = "arm moved"
    return jsonify(ok=ok)


@bp.post("/robots/<name>/arm_release")
def arm_release(name):
    rec, err = online_or_409(name)
    if err:
        return err
    ok = robots.send(rec, {"type": "arm_release"})
    rec["event"] = "arm released"
    return jsonify(ok=ok)


@bp.post("/robots/<name>/ping")
def ping(name):
    rec, err = online_or_409(name)
    if err:
        return err
    ping_id = secrets.randbelow(10 ** 9)
    if len(rec["ping_sent"]) > 20:
        rec["ping_sent"].clear()
    rec["ping_sent"][ping_id] = time.time()
    return jsonify(ok=robots.send(rec, {"type": "ping", "id": ping_id}))


@bp.post("/robots/<name>/stop")
def stop(name):
    rec, err = online_or_409(name)
    if err:
        return err
    ok = robots.send(rec, {"type": "stop"})
    rec["event"] = "stop sent"
    return jsonify(ok=ok)

"""The live link to each robot: one WebSocket per robot at /robot, and the list of robots and their status."""

import json
import math
import re
import secrets
import threading
import time

from flask import Blueprint, request
from flask_sock import Sock
from simple_websocket import ConnectionClosed

from . import auth, config, storage

bp = Blueprint("robots", __name__)
sock = Sock()

robots = {}  # name -> live connection record (see robot_socket)
robots_lock = threading.Lock()

ROBOT_TOKEN = storage.get_robot_token()


def send(rec, msg):
    """Send one JSON message to a robot. Returns False if the send failed."""
    try:
        with rec["send_lock"]:
            rec["ws"].send(json.dumps(msg))
        return True
    except Exception:
        return False


def get_online(name):
    """The live record for a connected robot, or None."""
    with robots_lock:
        rec = robots.get(name)
    return rec if rec is not None and rec["online"] else None


def disconnect(name):
    """Forget a robot's live link and close it."""
    with robots_lock:
        rec = robots.pop(name, None)
    if rec is not None and rec["online"]:
        rec["online"] = False
        try:
            rec["ws"].close()
        except Exception:
            pass


def clean_capabilities(raw):
    """What the robot says it can do, from its hello. None means an older agent that didn't say."""
    if not isinstance(raw, dict):
        return None
    arm = {}
    if isinstance(raw.get("arm"), dict):
        for joint, limits in list(raw["arm"].items())[:16]:
            if (config.JOINT_RE.fullmatch(str(joint)) and isinstance(limits, list) and len(limits) == 2
                    and all(isinstance(v, (int, float)) and 400 <= v <= 2600 for v in limits)):
                arm[joint] = [min(limits), max(limits)]
    return {"drive": bool(raw.get("drive")), "camera": bool(raw.get("camera")), "arm": arm,
            "sensors": [str(s)[:32] for s in raw.get("sensors", [])[:16]] if isinstance(raw.get("sensors"), list) else []}


def clean_sensors(raw):
    """Sensor readings from a heartbeat: name -> number (or None when there's no reading)."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k, v in list(raw.items())[:16]:
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
            out[str(k)[:32]] = round(float(v), 2)
        elif v is None:
            out[str(k)[:32]] = None
    return out


@sock.route("/robot", bp=bp)
def robot_socket(ws):
    """One WebSocket per robot. The robot speaks first with a 'hello' message."""
    key = "robot:" + str(request.remote_addr)
    rec = None
    try:
        if auth.blocked(key):
            ws.send(json.dumps({"type": "refused", "reason": "too many attempts"}))
            return
        try:
            hello = json.loads(ws.receive(timeout=5) or "null")
        except ValueError:
            hello = None
        if not isinstance(hello, dict) or hello.get("type") != "hello":
            auth.record_fail(key)
            ws.send(json.dumps({"type": "refused", "reason": "expected hello"}))
            return
        token_ok = secrets.compare_digest(str(hello.get("token", "")).encode(), ROBOT_TOKEN.encode())
        if not token_ok:
            auth.record_fail(key)
            ws.send(json.dumps({"type": "refused", "reason": "bad token"}))
            return
        name = hello.get("name")
        if not isinstance(name, str) or not config.NAME_RE.fullmatch(name):
            ws.send(json.dumps({"type": "refused", "reason": "bad name (use letters, digits, - and _)"}))
            return
        auth.clear_fails(key)

        now = time.time()
        rec = {
            "name": name, "ws": ws, "send_lock": threading.Lock(), "online": True,
            "address": request.remote_addr, "robot_type": str(hello.get("robot_type", ""))[:32],
            "hostname": re.sub(r"[^A-Za-z0-9._-]", "", str(hello.get("hostname", "")))[:64],
            "capabilities": clean_capabilities(hello.get("capabilities")), "sensors": {},
            "connected_at": now, "last_seen": now, "latency_ms": None,
            "ping_sent": {}, "event": "connected",
            "cam_wanted": 0.0, "frame": None, "frame_id": 0, "camera_error": "",
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
        send(rec, {"type": "welcome", "name": name, "seen_as": request.remote_addr})

        while True:
            raw = ws.receive(timeout=config.SILENCE_LIMIT)
            if raw is None:
                rec["event"] = "went silent"
                break
            if isinstance(raw, bytes):            # a binary message is one camera frame (JPEG)
                rec["last_seen"] = time.time()
                if len(raw) <= config.CAMERA_MAX_FRAME:
                    rec["frame"] = raw
                    rec["frame_id"] += 1
                continue
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(msg, dict):
                continue
            rec["last_seen"] = time.time()
            kind = msg.get("type")
            if kind == "heartbeat":
                rec["sensors"] = clean_sensors(msg.get("sensors"))
                # The ack carries the swarm list, which the robot's status screen shows,
                # and tells the robot whether anyone is watching its camera.
                watching = time.time() - rec["cam_wanted"] < config.CAMERA_IDLE
                send(rec, {"type": "heartbeat_ack", "swarm": swarm_for_robots(), "camera": watching})
            elif kind == "camera_status":
                rec["camera_error"] = str(msg.get("error", ""))[:200]
                if rec["camera_error"]:
                    rec["event"] = "camera: " + rec["camera_error"]
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


def robot_rows():
    """Every robot the hub knows (installed here or connected now), with its status."""
    now = time.time()
    with storage.registry_lock:
        reg = dict(storage.registry)
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
            elif ago < config.ONLINE_WITHIN:
                status = "connected"
            else:
                status = "unresponsive"
            ago, latency, event = round(ago, 1), r["latency_ms"], r["event"]
        rows.append({
            "name": name, "status": status, "seen_ago": ago, "latency_ms": latency, "event": event,
            "hostname": (r and r.get("hostname")) or (entry and entry.get("hostname")) or "",
            "address": (r["address"] if r else None) or (entry["host"] if entry else None),
            "installed": entry is not None,
            "robot_type": (r and r.get("robot_type")) or "",
            "capabilities": r and r.get("capabilities"),
            "sensors": (r and r["online"] and r.get("sensors")) or {},
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

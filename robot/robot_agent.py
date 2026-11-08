"""Robot agent: connects this robot to the Swarm Hub.

You normally never run this by hand. The hub's "Add robot" button copies it
onto the robot and installs it as a service called swarm-agent, so it starts
on every boot and restarts by itself if it crashes. Edit this file on your
computer and press "Update" in the hub to push the new version to a robot.

To run it by hand instead (over SSH), stop the service first:
    sudo systemctl stop swarm-agent
    python3 robot_agent.py

It needs only Python 3.7+ and its standard library for the hub link, so nothing
has to be installed for that (handy, because a robot in hotspot mode has no
internet). The hub copies these files next to it:
    ws_client.py        the WebSocket link to the hub (standard library only)
    robot_movement.py   the wheels and the arm
    camera.py           the USB camera
    sensors.py          the ultrasonic sensor
The top of each says what it needs installed. If one isn't set up the agent
still connects, tells the hub that part is missing, and leaves it disabled.

It reads config.json next to this file, connects to the hub, says what it can do,
sends a heartbeat (with sensor readings)
every second, answers ping, stop, drive, arm and arm_release commands, and reconnects by itself if
the link drops. If the hub goes silent, or the service is stopped, it stops the
wheels and the arm holds where it is. While driving, the robot also stops by itself if drive commands stop
arriving for half a second.

Several times a second it also writes status.json (no secrets in it), which the
status window (status_ui.py) shows on the robot's desktop: the robot's name and
user, its IP address, the hub connection, and the last command from the hub.
"""

import asyncio
import getpass
import json
import math
import os
import signal
import socket
import sys
import time
from pathlib import Path

import robot_movement as movement   # wheels and arm: pins, servo channels and limits are set there
import sensors
from camera import MAX_BUFFERED, camera
from ws_client import CONNECT_TIMEOUT, LinkClosed, WebSocket

CONFIG_FILE = Path(__file__).with_name("config.json")
STATUS_FILE = Path(__file__).with_name("status.json")

HEARTBEAT_EVERY = 1.0     # seconds between heartbeats to the hub
HUB_SILENCE_LIMIT = 3.0   # stop the robot if nothing arrives from the hub this long
DRIVE_TIMEOUT = 0.5   # stop if no drive command arrives for this long (seconds)


def handle_arm(msg):
    """Move arm joints: {"type": "arm", "targets": {"base": 1500, ...}}, pulse widths in microseconds."""
    targets = msg.get("targets")
    if not isinstance(targets, dict) or len(targets) > 16:
        return
    movement.arm_move(targets)
    set_control("arm")


def handle_drive(msg, state):
    """Apply a drive command from the hub: forward, strafe and rotate, each from -1 to 1."""
    try:
        values = [float(msg.get(k, 0)) for k in ("forward", "strafe", "rotate")]
    except (TypeError, ValueError):
        return
    if not all(math.isfinite(v) for v in values):
        return
    movement.drive(*values)
    set_control("drive", forward=values[0], strafe=values[1], rotate=values[2])
    # Keep moving only while commands keep arriving; drive_guard stops the robot if they stop.
    state["drive_until"] = (time.monotonic() + DRIVE_TIMEOUT) if any(values) else 0.0


def capabilities():
    """What this robot can do, sent to the hub in the hello (and again if it changes) so its page
    only offers what works."""
    return {
        "drive": movement.wheels_ready(),
        "arm": movement.arm_limits(),             # joint -> [lowest, highest] pulse; empty if no arm
        "camera": camera.available(),
        "sensors": sensors.names(),
    }


def current_user():
    try:
        return getpass.getuser()
    except Exception:
        return ""


# What the status screen shows. Written to status.json several times a second.
STATUS = {
    "hostname": socket.gethostname(),   # the robot's own name
    "user": current_user(),             # the Linux user the agent runs as
    "hub_name": "",                     # its name on the hub
    "ips": [],                          # this robot's IP addresses
    "seen_as": "",                      # the address the hub sees it at
    "hub": "",                          # hub address it is using or trying
    "connected": False,
    "since": time.time(),               # when "connected" last changed
    "error": "",                        # why it isn't connected
    "swarm": [],                        # every robot the hub knows, from the hub
    "control": {},                      # the last command received from the hub (see set_control)
    "sensors": {},                      # latest readings from sensors.py, e.g. the gyro's x/y/z
    "updated": 0,
}


def describe(err):
    """A short, plain reason for the status screen."""
    if isinstance(err, ConnectionRefusedError):
        return "the hub isn't running at that address"
    if isinstance(err, (asyncio.TimeoutError, socket.timeout)):
        return "no answer from the hub"
    if isinstance(err, socket.gaierror):
        return "can't find that address on this network"
    if isinstance(err, OSError) and getattr(err, "errno", None) in (101, 113):
        return "no network path to the hub"
    return str(err) or type(err).__name__


def set_control(kind, **values):
    """Remember the last command received from the hub, for the status window."""
    STATUS["control"] = dict(values, kind=kind, at=time.time())


def set_connected(connected, hub, error=""):
    if STATUS["connected"] != connected:
        STATUS["since"] = time.time()
    STATUS.update(connected=connected, hub=hub, error=error)


class Refused(Exception):
    """The hub answered but would not let this robot in."""


def load_config():
    if not CONFIG_FILE.exists():
        sys.exit("Missing config.json next to robot_agent.py. Add this robot from the hub to create it.")
    try:
        cfg = json.loads(CONFIG_FILE.read_text())
    except ValueError as err:
        sys.exit("config.json is not valid JSON: {}".format(err))
    for key in ("hub", "name", "token"):
        if not cfg.get(key) or str(cfg[key]).startswith("PASTE"):
            sys.exit("config.json: please set '{}'.".format(key))
    hubs = cfg["hub"] if isinstance(cfg["hub"], list) else [cfg["hub"]]
    cfg["hubs"] = []
    for hub in hubs:
        try:
            split_host_port(str(hub))
        except ValueError:
            sys.exit("config.json: '{}' is not a valid hub address (expected host:port).".format(hub))
        cfg["hubs"].append(str(hub))
    return cfg


def split_host_port(addr):
    """'192.168.1.5:8000' -> ('192.168.1.5', 8000). Also accepts '[ipv6]:port'."""
    if addr.startswith("["):
        host, _, rest = addr[1:].partition("]")
        port = rest.lstrip(":")
    else:
        host, _, port = addr.rpartition(":")
    if not host or not port.isdigit():
        raise ValueError(addr)
    return host, int(port)


async def run_session(cfg, hub, status):
    host, port = split_host_port(hub)
    ws = await WebSocket.connect(host, port, "/robot")
    hello_caps = capabilities()
    try:
        await ws.send(json.dumps({
            "type": "hello",
            "name": cfg["name"],
            "token": cfg["token"],
            "robot_type": cfg.get("robot_type", "masterpi"),
            "hostname": STATUS["hostname"],
            "capabilities": hello_caps,
        }))
        try:
            reply = json.loads(await asyncio.wait_for(ws.recv(), CONNECT_TIMEOUT))
        except ValueError:
            reply = None
        if not isinstance(reply, dict) or reply.get("type") != "welcome":
            raise Refused(reply.get("reason", "no reason given") if isinstance(reply, dict) else "unexpected reply")

        status["connected"] = True
        STATUS["hub_name"] = str(reply.get("name") or cfg["name"])
        STATUS["seen_as"] = str(reply.get("seen_as") or "")
        set_connected(True, hub)
        print("[robot] connected to {} as '{}'".format(hub, cfg["name"]), flush=True)
        state = {"last_rx": time.monotonic(), "drive_until": 0.0}

        async def heartbeat():
            sent_caps = hello_caps
            while True:
                await ws.send(json.dumps({"type": "heartbeat", "t": time.time(), "sensors": sensors.read()}))
                # The arm can show up after the hello (robot_movement keeps looking for it),
                # so tell the hub whenever what we can do changes.
                caps = capabilities()
                if caps != sent_caps:
                    await ws.send(json.dumps({"type": "capabilities", "capabilities": caps}))
                    sent_caps = caps
                await asyncio.sleep(HEARTBEAT_EVERY)

        async def reader():
            while True:
                raw = await ws.recv()
                state["last_rx"] = time.monotonic()
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                kind = msg.get("type") if isinstance(msg, dict) else None
                if kind == "heartbeat_ack":
                    camera.set_wanted(msg.get("camera"))
                    swarm = msg.get("swarm")
                    if isinstance(swarm, list):
                        STATUS["swarm"] = [r for r in swarm[:200] if isinstance(r, dict)]
                elif kind == "ping":
                    set_control("ping")
                    await ws.send(json.dumps({"type": "pong", "id": msg.get("id")}))
                elif kind == "stop":
                    state["drive_until"] = 0.0
                    set_control("stop")
                    movement.stop_all("hub command")
                    await ws.send(json.dumps({"type": "stop_ack"}))
                elif kind == "drive":
                    handle_drive(msg, state)
                elif kind == "arm":
                    handle_arm(msg)
                elif kind == "arm_release":
                    set_control("arm_release")
                    movement.arm_release()
                elif kind == "gyro_calibrate":
                    # Zero the gyro's rotation; it measures for 2 s in its own thread, so this
                    # doesn't hold up the link. The robot should stand still meanwhile.
                    set_control("gyro_calibrate")
                    sensors.calibrate_gyro()

        async def watchdog():
            while True:
                await asyncio.sleep(0.5)
                if time.monotonic() - state["last_rx"] > HUB_SILENCE_LIMIT:
                    raise LinkClosed("hub went silent")

        async def drive_guard():
            # Dead-man switch: the hub sends drive commands about 10 times a second while a
            # button is held. If they stop arriving, stop the wheels.
            while True:
                await asyncio.sleep(0.1)
                until = state["drive_until"]
                if until and time.monotonic() > until:
                    state["drive_until"] = 0.0
                    movement.stop_wheels("no drive command received")

        async def camera_sender():
            sent_id = 0
            reported = None
            while True:
                await asyncio.sleep(0.03)
                if camera.error != reported:
                    reported = camera.error
                    await ws.send(json.dumps({"type": "camera_status", "error": reported}))
                frame = camera.frame
                if not camera.want or frame is None or camera.frame_id == sent_id:
                    continue
                if ws.backlog() > MAX_BUFFERED:
                    continue                      # link is behind; drop this frame
                sent_id = camera.frame_id
                await ws.send_bytes(frame)

        tasks = [asyncio.ensure_future(job()) for job in (heartbeat, reader, watchdog, drive_guard, camera_sender)]
        try:
            done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()                     # re-raises the error that ended it
            raise LinkClosed("hub closed the connection")
        except Exception as err:
            # Stop right away, before closing the socket (closing can wait on a dead hub).
            movement.stop_all("link lost: {}".format(err))
            raise
        finally:
            camera.set_wanted(False)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await ws.close()


async def local_ips(cfg):
    """This robot's IPv4 addresses."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "hostname", "-I", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), 3)
        except asyncio.TimeoutError:
            proc.kill()
            raise
        ips = [ip for ip in out.decode(errors="replace").split() if ":" not in ip]
        if proc.returncode == 0 and ips:
            return ips
    except (OSError, asyncio.TimeoutError):
        pass
    # No "hostname -I" (e.g. a Mac): use the address this machine uses to reach the hub.
    try:
        host, port = split_host_port(cfg["hubs"][0])
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect((host, port))           # sends nothing
            return [probe.getsockname()[0]]
        finally:
            probe.close()
    except OSError:
        return []


async def status_writer(cfg):
    """Keep status.json fresh for the status screen, connected or not."""
    next_ip_check = 0
    while True:
        now = time.time()
        if now >= next_ip_check:
            STATUS["ips"] = await local_ips(cfg)
            next_ip_check = now + 10
        STATUS["updated"] = now
        STATUS["sensors"] = sensors.read()     # latest values only; never waits on hardware
        try:
            tmp = STATUS_FILE.with_name("status.json.tmp")
            tmp.write_text(json.dumps(STATUS))
            os.replace(str(tmp), str(STATUS_FILE))
        except OSError:
            pass
        await asyncio.sleep(0.2)


async def main():
    cfg = load_config()
    movement.setup()
    sensors.setup()
    hubs = cfg["hubs"]        # addresses to try in turn, e.g. the hub's IP and its .local name
    STATUS["hub_name"] = cfg["name"]
    STATUS["hub"] = hubs[0]
    writer = asyncio.ensure_future(status_writer(cfg))
    turn = 0
    wait = 1
    while True:
        hub = hubs[turn % len(hubs)]
        status = {"connected": False}
        try:
            await run_session(cfg, hub, status)
        except Refused as err:
            set_connected(False, hub, "hub refused: {}".format(err))
            print("[robot] hub refused the connection: {}. Re-add this robot from the hub.".format(err), flush=True)
            wait = 5
        except (OSError, EOFError, asyncio.TimeoutError) as err:
            set_connected(False, hub, describe(err))
            if status["connected"]:
                wait = 1                          # was working: retry the same address soon
            else:
                turn += 1                         # never got in: try the next address
                wait = min(wait * 2, 5) if turn % len(hubs) == 0 else 0.5
            print("[robot] link to {} down ({}: {}); retrying in {}s".format(
                hub, type(err).__name__, err, wait), flush=True)
        if writer.done():                         # never expected; restart it if it died
            writer = asyncio.ensure_future(status_writer(cfg))
        await asyncio.sleep(wait)


_terminating = False


def _on_sigterm(signum, frame):
    # systemd sends SIGTERM when the service stops (shutdown, update, removal).
    global _terminating
    _terminating = True
    raise SystemExit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _on_sigterm)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit) as exc:
        if isinstance(exc, SystemExit) and not _terminating:
            raise                                 # a config error: show its message
        movement.stop_all("exit")
        print("[robot] stopped", flush=True)

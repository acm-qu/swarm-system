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
internet). The motors also need gpiozero, which comes with Raspberry Pi OS (on a
Pi 5 it uses python3-lgpio). Fill in the motor pin numbers in the MOTORS section
below; until you do, the agent still connects but leaves the motors disabled.

It reads config.json next to this file, connects to the hub, sends a heartbeat
every second, answers ping, stop and drive commands, and reconnects by itself if
the link drops. If the hub goes silent, or the service is stopped, it stops the
robot. While driving, the robot also stops by itself if drive commands stop
arriving for half a second.

Several times a second it also writes status.json (no secrets in it), which the
status window (status_ui.py) shows on the robot's desktop: the robot's name and
user, its IP address, the hub connection, and the last command from the hub.
"""

import asyncio
import base64
import getpass
import hashlib
import json
import math
import os
import signal
import socket
import struct
import sys
import threading
import time
from pathlib import Path

CONFIG_FILE = Path(__file__).with_name("config.json")
STATUS_FILE = Path(__file__).with_name("status.json")

HEARTBEAT_EVERY = 1.0     # seconds between heartbeats to the hub
HUB_SILENCE_LIMIT = 3.0   # stop the robot if nothing arrives from the hub this long
CONNECT_TIMEOUT = 5.0     # seconds allowed for connecting and for the hub's welcome
MAX_MESSAGE = 1 << 20     # refuse messages from the hub bigger than 1 MB
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"   # fixed value from the WebSocket standard


# ---------------------------------------------------------------------------
# MOTORS: four mecanum wheels on two L298N drivers
# ---------------------------------------------------------------------------
#   Driver 1 -> FRONT wheels: channel A = front-left,  channel B = front-right
#   Driver 2 -> REAR wheels:  channel A = rear-left,   channel B = rear-right
#
# PIN SETUP - fill these in yourself (BCM / GPIO numbers, not physical pin
# positions). Each channel has:
#   IN_x1 / IN_x2 = the two direction pins (L298N IN1/IN2 for A, IN3/IN4 for B)
#   EN_x          = the enable pin (L298N ENA / ENB), used for PWM speed control
# Remember to remove the ENA/ENB jumpers on the L298N boards.

# Driver 1 - FRONT wheels
FRONT_IN_A1 = 14
FRONT_IN_A2 = 15
FRONT_EN_A = 9
FRONT_IN_B1 = 18
FRONT_IN_B2 = 23
FRONT_EN_B = 10

# Driver 2 - REAR wheels
REAR_IN_A1 = 25
REAR_IN_A2 = 8
REAR_EN_A = 17
REAR_IN_B1 = 7
REAR_IN_B2 = 12
REAR_EN_B = 27

# If a wheel spins the wrong way, flip its value here.
# Motors on opposite sides are mirrored, so one side usually needs flipping.
INVERT_FRONT_LEFT = False
INVERT_FRONT_RIGHT = False
INVERT_REAR_LEFT = False
INVERT_REAR_RIGHT = False

DRIVE_TIMEOUT = 0.5   # stop if no drive command arrives for this long (seconds)

try:
    from gpiozero import Motor
except ImportError:
    Motor = None

fl = fr = rl = rr = None    # the four Motor objects; created by setup_motors()


def make_motor(in1, in2, enable):
    # pwm=True lets us set speeds between 0 and 1 using the enable pin.
    return Motor(forward=in1, backward=in2, enable=enable, pwm=True)


def setup_motors():
    """Create the four motors. If anything is missing, leave them disabled (the agent still runs)."""
    global fl, fr, rl, rr
    pins = (FRONT_IN_A1, FRONT_IN_A2, FRONT_EN_A, FRONT_IN_B1, FRONT_IN_B2, FRONT_EN_B,
            REAR_IN_A1, REAR_IN_A2, REAR_EN_A, REAR_IN_B1, REAR_IN_B2, REAR_EN_B)
    if any(p is None for p in pins):
        print("[robot] motor pins aren't filled in (see the MOTORS section of robot_agent.py); "
              "motors disabled", flush=True)
        return
    if Motor is None:
        print("[robot] gpiozero isn't installed (sudo apt install python3-gpiozero python3-lgpio); "
              "motors disabled", flush=True)
        return
    try:
        fl = make_motor(FRONT_IN_A1, FRONT_IN_A2, FRONT_EN_A)   # front-left
        fr = make_motor(FRONT_IN_B1, FRONT_IN_B2, FRONT_EN_B)   # front-right
        rl = make_motor(REAR_IN_A1, REAR_IN_A2, REAR_EN_A)      # rear-left
        rr = make_motor(REAR_IN_B1, REAR_IN_B2, REAR_EN_B)      # rear-right
    except Exception as err:
        fl = fr = rl = rr = None
        print("[robot] couldn't set up the motors ({}: {}); motors disabled".format(
            type(err).__name__, err), flush=True)
        return
    print("[robot] motors ready", flush=True)


def set_wheel(motor, speed, invert):
    """Set one wheel. speed goes from -1 (full reverse) to 1 (full forward)."""
    if invert:
        speed = -speed
    motor.value = max(-1.0, min(1.0, speed))


def drive(forward=0.0, strafe=0.0, rotate=0.0):
    """
    Mix the three mecanum movements into the four wheel speeds.
      forward: +1 = forward,        -1 = backward
      strafe:  +1 = slide right,    -1 = slide left
      rotate:  +1 = turn clockwise, -1 = turn counter-clockwise
    Values can be combined (e.g. forward + strafe = diagonal movement).
    """
    if fl is None:
        return                                  # motors disabled
    front_left = forward + strafe + rotate
    front_right = forward - strafe - rotate
    rear_left = forward - strafe + rotate
    rear_right = forward + strafe - rotate

    # If any wheel goes above 1, scale everything down so the direction stays correct.
    biggest = max(abs(front_left), abs(front_right), abs(rear_left), abs(rear_right), 1.0)

    set_wheel(fl, front_left / biggest, INVERT_FRONT_LEFT)
    set_wheel(fr, front_right / biggest, INVERT_FRONT_RIGHT)
    set_wheel(rl, rear_left / biggest, INVERT_REAR_LEFT)
    set_wheel(rr, rear_right / biggest, INVERT_REAR_RIGHT)


def stop_motors(reason):
    """Stop all four wheels. Called on a hub stop command, a lost link, and exit."""
    print("[robot] STOP ({})".format(reason), flush=True)
    for m in (fl, fr, rl, rr):
        if m is not None:
            try:
                m.stop()
            except Exception:
                pass


def handle_drive(msg, state):
    """Apply a drive command from the hub: forward, strafe and rotate, each from -1 to 1."""
    try:
        values = [float(msg.get(k, 0)) for k in ("forward", "strafe", "rotate")]
    except (TypeError, ValueError):
        return
    if not all(math.isfinite(v) for v in values):
        return
    drive(*values)
    set_control("drive", forward=values[0], strafe=values[1], rotate=values[2])
    # Keep moving only while commands keep arriving; drive_guard stops the robot if they stop.
    state["drive_until"] = (time.monotonic() + DRIVE_TIMEOUT) if any(values) else 0.0


# ---------------------------------------------------------------------------
# CAMERA: USB camera streamed to the hub as JPEG frames
# ---------------------------------------------------------------------------
# Needs OpenCV:  sudo apt install python3-opencv
# The camera only runs while someone is watching it in the hub (the hub says so in
# each heartbeat reply), so it costs nothing the rest of the time.

CAMERA_INDEX = 0          # /dev/video0. If it's the wrong one, try 2, 4, ... (see: v4l2-ctl --list-devices)
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 15           # frames per second sent to the hub
JPEG_QUALITY = 70         # 1-100; lower = smaller frames
MAX_BUFFERED = 256 * 1024  # skip a frame if this much is still waiting to be sent (slow Wi-Fi)

try:
    import cv2
except ImportError:
    cv2 = None


class Camera:
    """Grabs frames on a background thread while `want` is True; keeps the latest JPEG."""

    def __init__(self):
        self.want = False
        self.frame = None
        self.frame_id = 0
        self.error = ""
        self.thread = None

    def set_wanted(self, want):
        self.want = bool(want)
        if self.want and (self.thread is None or not self.thread.is_alive()):
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def _run(self):
        if cv2 is None:
            self.error = "OpenCV isn't installed (sudo apt install python3-opencv)"
            return
        while self.want:
            cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
            if not cap.isOpened():
                self.error = "can't open camera {} (is it plugged in?)".format(CAMERA_INDEX)
                cap.release()
                time.sleep(2)
                continue
            # Most USB cameras give JPEG natively, which is far lighter than raw video.
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            last = 0.0
            bad = 0
            while self.want:
                ok, img = cap.read()
                if not ok:
                    bad += 1
                    if bad > 30:
                        self.error = "camera stopped giving frames"
                        break
                    time.sleep(0.05)
                    continue
                bad = 0
                now = time.monotonic()
                if now - last < 1.0 / CAMERA_FPS:
                    continue                      # too soon; drop it
                last = now
                ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                if ok:
                    self.frame = jpg.tobytes()
                    self.frame_id += 1
                    self.error = ""
            cap.release()
            if self.want:
                time.sleep(2)
        self.frame = None


camera = Camera()


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


class LinkClosed(ConnectionError):
    """The connection to the hub ended."""


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


def _mask(data, key):
    """XOR data with the 4-byte key, repeated (WebSocket masking)."""
    if not data:
        return b""
    pad = (key * (len(data) // 4 + 1))[:len(data)]
    return (int.from_bytes(data, "big") ^ int.from_bytes(pad, "big")).to_bytes(len(data), "big")


class WebSocket:
    """Just enough of the WebSocket protocol (RFC 6455) to talk to the hub."""

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.send_lock = asyncio.Lock()

    @classmethod
    async def connect(cls, host, port, path):
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), CONNECT_TIMEOUT)
        ws = cls(reader, writer)
        try:
            await asyncio.wait_for(ws._handshake(host, port, path), CONNECT_TIMEOUT)
        except BaseException:
            writer.close()
            raise
        return ws

    async def _handshake(self, host, port, path):
        key = base64.b64encode(os.urandom(16)).decode()
        host_header = "[{}]:{}".format(host, port) if ":" in host else "{}:{}".format(host, port)
        self.writer.write((
            "GET {} HTTP/1.1\r\n"
            "Host: {}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: {}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n".format(path, host_header, key)).encode())
        await self.writer.drain()
        try:
            head = await self.reader.readuntil(b"\r\n\r\n")
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            raise LinkClosed("hub closed the connection during the handshake")
        lines = head.decode("latin-1").split("\r\n")
        status = lines[0].split(" ")
        if len(status) < 2 or status[1] != "101":
            raise LinkClosed("not a Swarm Hub at this address (it answered: {})".format(lines[0]))
        headers = {}
        for line in lines[1:]:
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()
        expected = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        if headers.get("sec-websocket-accept") != expected:
            raise LinkClosed("bad WebSocket handshake from the hub")

    async def _send_frame(self, opcode, payload):
        n = len(payload)
        if n < 126:
            head = struct.pack("!BB", 0x80 | opcode, 0x80 | n)
        elif n < 65536:
            head = struct.pack("!BBH", 0x80 | opcode, 0x80 | 126, n)
        else:
            head = struct.pack("!BBQ", 0x80 | opcode, 0x80 | 127, n)
        key = os.urandom(4)       # clients must mask what they send
        async with self.send_lock:
            self.writer.write(head + key + _mask(payload, key))
            await self.writer.drain()

    async def send(self, text):
        await self._send_frame(0x1, text.encode())

    async def send_bytes(self, data):
        await self._send_frame(0x2, data)

    def backlog(self):
        """Bytes written but not yet sent (used to skip camera frames on a slow link)."""
        try:
            return self.writer.transport.get_write_buffer_size()
        except Exception:
            return 0

    async def recv(self):
        """Return the next text message. Answers pings; raises LinkClosed when the link ends."""
        parts = []
        size = 0
        try:
            while True:
                b1, b2 = await self.reader.readexactly(2)
                opcode, n = b1 & 0x0F, b2 & 0x7F
                if n == 126:
                    n, = struct.unpack("!H", await self.reader.readexactly(2))
                elif n == 127:
                    n, = struct.unpack("!Q", await self.reader.readexactly(8))
                size += n
                if size > MAX_MESSAGE:
                    raise LinkClosed("message from the hub is too large")
                key = await self.reader.readexactly(4) if b2 & 0x80 else None
                data = await self.reader.readexactly(n) if n else b""
                if key:
                    data = _mask(data, key)
                if opcode == 0x8:                   # close
                    try:
                        await self._send_frame(0x8, data[:2])
                    except Exception:
                        pass
                    raise LinkClosed("hub closed the connection")
                if opcode == 0x9:                   # ping -> pong
                    await self._send_frame(0xA, data)
                    continue
                if opcode == 0xA:                   # pong
                    continue
                parts.append(data)
                if b1 & 0x80:                       # last fragment
                    return b"".join(parts).decode("utf-8", errors="replace")
        except asyncio.IncompleteReadError:
            raise LinkClosed("connection dropped")

    async def close(self):
        try:
            await asyncio.wait_for(self._send_frame(0x8, struct.pack("!H", 1000)), 1)
        except Exception:
            pass
        self.writer.close()
        try:
            await asyncio.wait_for(self.writer.wait_closed(), 1)
        except Exception:
            pass


async def run_session(cfg, hub, status):
    host, port = split_host_port(hub)
    ws = await WebSocket.connect(host, port, "/robot")
    try:
        await ws.send(json.dumps({
            "type": "hello",
            "name": cfg["name"],
            "token": cfg["token"],
            "robot_type": cfg.get("robot_type", "masterpi"),
            "hostname": STATUS["hostname"],
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
            while True:
                await ws.send(json.dumps({"type": "heartbeat", "t": time.time()}))
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
                    stop_motors("hub command")
                    await ws.send(json.dumps({"type": "stop_ack"}))
                elif kind == "drive":
                    handle_drive(msg, state)

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
                    stop_motors("no drive command received")

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
            stop_motors("link lost: {}".format(err))
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
        try:
            tmp = STATUS_FILE.with_name("status.json.tmp")
            tmp.write_text(json.dumps(STATUS))
            os.replace(str(tmp), str(STATUS_FILE))
        except OSError:
            pass
        await asyncio.sleep(0.2)


async def main():
    cfg = load_config()
    setup_motors()
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
        stop_motors("exit")
        print("[robot] stopped", flush=True)

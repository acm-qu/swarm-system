"""Robot agent: connects this robot to the Swarm Hub.

You normally never run this by hand. The hub's "Add robot" button copies it
onto the robot and installs it as a service called swarm-agent, so it starts
on every boot and restarts by itself if it crashes. Edit this file on your
computer and press "Update" in the hub to push the new version to a robot.

To run it by hand instead (over SSH), stop the service first:
    sudo systemctl stop swarm-agent
    python3 robot_agent.py

It needs only Python 3.7+ and its standard library, so nothing has to be
installed on the robot (handy, because a robot in hotspot mode has no internet).

It reads config.json next to this file, connects to the hub, sends a heartbeat
every second, answers ping and stop commands, and reconnects by itself if the
link drops. If the hub goes silent, or the service is stopped, it stops the robot.
"""

import asyncio
import base64
import hashlib
import json
import os
import signal
import struct
import sys
import time
from pathlib import Path

CONFIG_FILE = Path(__file__).with_name("config.json")

HEARTBEAT_EVERY = 1.0     # seconds between heartbeats to the hub
HUB_SILENCE_LIMIT = 3.0   # stop the robot if nothing arrives from the hub this long
CONNECT_TIMEOUT = 5.0     # seconds allowed for connecting and for the hub's welcome
MAX_MESSAGE = 1 << 20     # refuse messages from the hub bigger than 1 MB
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"   # fixed value from the WebSocket standard


def stop_motors(reason):
    # TODO: replace this print with the real motor stop from Hiwonder's code,
    # for example setting all four wheel speeds to zero and holding the arm.
    print("[robot] STOP ({})".format(reason), flush=True)


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
        }))
        try:
            reply = json.loads(await asyncio.wait_for(ws.recv(), CONNECT_TIMEOUT))
        except ValueError:
            reply = None
        if not isinstance(reply, dict) or reply.get("type") != "welcome":
            raise Refused(reply.get("reason", "no reason given") if isinstance(reply, dict) else "unexpected reply")

        status["connected"] = True
        print("[robot] connected to {} as '{}'".format(hub, cfg["name"]), flush=True)
        state = {"last_rx": time.monotonic()}

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
                if kind == "ping":
                    await ws.send(json.dumps({"type": "pong", "id": msg.get("id")}))
                elif kind == "stop":
                    stop_motors("hub command")
                    await ws.send(json.dumps({"type": "stop_ack"}))

        async def watchdog():
            while True:
                await asyncio.sleep(0.5)
                if time.monotonic() - state["last_rx"] > HUB_SILENCE_LIMIT:
                    raise LinkClosed("hub went silent")

        tasks = [asyncio.ensure_future(job()) for job in (heartbeat, reader, watchdog)]
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
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await ws.close()


async def main():
    cfg = load_config()
    hubs = cfg["hubs"]        # addresses to try in turn, e.g. the hub's IP and its .local name
    turn = 0
    wait = 1
    while True:
        hub = hubs[turn % len(hubs)]
        status = {"connected": False}
        try:
            await run_session(cfg, hub, status)
        except Refused as err:
            print("[robot] hub refused the connection: {}. Re-add this robot from the hub.".format(err), flush=True)
            wait = 5
        except (OSError, EOFError, asyncio.TimeoutError) as err:
            if status["connected"]:
                wait = 1                          # was working: retry the same address soon
            else:
                turn += 1                         # never got in: try the next address
                wait = min(wait * 2, 5) if turn % len(hubs) == 0 else 0.5
            print("[robot] link to {} down ({}: {}); retrying in {}s".format(
                hub, type(err).__name__, err, wait), flush=True)
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

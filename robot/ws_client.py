"""Just enough of the WebSocket protocol (RFC 6455) for robot_agent.py to talk to the hub.

Standard library only, so the hub link works on a robot with no internet to install packages.
"""

import asyncio
import base64
import hashlib
import os
import struct

CONNECT_TIMEOUT = 5.0     # seconds allowed for connecting and for the handshake
MAX_MESSAGE = 1 << 20     # refuse messages from the hub bigger than 1 MB
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"   # fixed value from the WebSocket standard


class LinkClosed(ConnectionError):
    """The connection to the hub ended."""


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

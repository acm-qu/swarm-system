"""Who is controlling which robot, and how fast commands may arrive.

One person at a time controls a robot (drive and arm). Anyone signed in can always press Stop.
Control is a lease: it lasts while the holder keeps sending commands, ends when they close the
panel, and lapses CONTROL_LEASE seconds after their last command, so a closed tab never keeps a
robot locked.
"""

import threading
import time

from . import config

_holders = {}      # robot name -> {"user": who controls it, "until": monotonic time the lease ends}
_buckets = {}      # "user:robot" -> [commands left, monotonic time last refilled]
_lock = threading.Lock()


def claim(robot, user):
    """Take or renew control of a robot. Returns None if user now has it, else the name of who does."""
    now = time.monotonic()
    with _lock:
        held = _holders.get(robot)
        if held and held["user"] != user and held["until"] > now:
            return held["user"]
        _holders[robot] = {"user": user, "until": now + config.CONTROL_LEASE}
        return None


def release(robot, user):
    """Give up control of a robot, if user has it."""
    with _lock:
        held = _holders.get(robot)
        if held and held["user"] == user:
            _holders.pop(robot, None)


def holder(robot):
    """Who controls a robot right now, or None."""
    with _lock:
        held = _holders.get(robot)
        return held["user"] if held and held["until"] > time.monotonic() else None


def rate_ok(key):
    """True if another command may go through for key ("user:robot"). Allows COMMAND_RATE a second,
    with short bursts up to COMMAND_BURST, so a stuck key or a script can't flood a robot."""
    now = time.monotonic()
    with _lock:
        if len(_buckets) > 10_000:                # forget idle entries so this can't grow forever
            for k in [k for k, (_, t) in _buckets.items() if now - t > 60]:
                _buckets.pop(k, None)
        left, last = _buckets.get(key, (config.COMMAND_BURST, now))
        left = min(config.COMMAND_BURST, left + (now - last) * config.COMMAND_RATE)
        if left < 1:
            _buckets[key] = [left, now]
            return False
        _buckets[key] = [left - 1, now]
        return True

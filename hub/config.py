"""Paths, limits and names shared by the whole hub."""

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent           # the repository
ROBOT_DIR = ROOT / "robot"                              # code copied onto each robot
DATA_DIR = Path(os.environ.get("SWARM_DATA_DIR") or ROOT / "data")   # private runtime files (gitignored)

USERS_FILE = DATA_DIR / "users.json"        # {"name": "<password hash>"}
SECRET_FILE = DATA_DIR / ".secret_key"      # signs the login cookie
TOKEN_FILE = DATA_DIR / "robot_token.txt"   # shared secret that robots must send
REGISTRY_FILE = DATA_DIR / "robots.json"    # robots this hub has installed (no passwords)
HUB_KEY_FILE = DATA_DIR / "hub_ssh_key"     # the hub's SSH key, added to each robot it installs

# Files copied from robot/ into the robot's folder on Add robot / Update. robot_agent.py is the entry point.
ROBOT_FILES = ("robot_agent.py", "ws_client.py", "camera.py", "robot_movement.py", "sensors.py")
STATUS_UI_FILE = ROBOT_DIR / "status_ui.py"  # the status screen, only copied if the robot has a desktop

PORT = int(os.environ.get("PORT", "8000"))

MAX_FAILS = 5          # wrong attempts allowed ...
LOCK_SECONDS = 60      # ... before that address is blocked for this long

ONLINE_WITHIN = 3.0    # robot counts as connected if heard from this recently (seconds)
SILENCE_LIMIT = 5.0    # hub drops a robot that sends nothing for this long (seconds)
CONNECT_WAIT = 25      # after installing, wait this long for the robot to connect (seconds)
REBOOT_WAIT = 180      # after rebooting a robot, wait this long for it to come back (seconds)
CAMERA_IDLE = 4.0           # robot's camera turns off this long after the last viewer leaves (seconds)
CAMERA_MAX_FRAME = 2_000_000   # ignore camera frames bigger than this (bytes)
TERM_TIMEOUT = 30      # a terminal command is stopped after this many seconds
TERM_MAX_OUTPUT = 100_000   # most output (bytes) returned for one terminal command
TERM_MARK = "__SWARM_CWD__"  # printed after each command so the hub learns the folder it ended in

NAME_RE = re.compile(r"[A-Za-z0-9_-]{1,32}")
JOINT_RE = re.compile(r"[a-z_]{1,16}")   # arm joint names, as in robot/robot_movement.py
HOST_RE = re.compile(r"[A-Za-z0-9.:_-]{1,253}")
USER_RE = re.compile(r"[A-Za-z0-9._-]{1,32}")
PATH_RE = re.compile(r"/[A-Za-z0-9._/-]*")

SERVICE = "swarm-agent"            # systemd service name on the robot
REMOTE_DIR = "swarm-agent"         # folder in the robot user's home
AUTOSTART = ".config/autostart/swarm-status.desktop"   # opens the status screen at desktop login
DEFAULT_PREFIX = "masterpi-"       # robots get named masterpi-01, masterpi-02, ...
KEY_COMMENT = "swarm-hub"          # marks the hub's key in a robot's authorized_keys

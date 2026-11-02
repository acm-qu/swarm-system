"""The hub's private files in data/: logins, keys, the robot token and the robot registry."""

import getpass
import json
import os
import secrets
import subprocess
import threading

from . import config


def write_private(path, data):
    """Write a file that only this user can read."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w" if isinstance(data, str) else "wb") as f:
        f.write(data)
    restrict(tmp)
    os.replace(tmp, path)


def restrict(path):
    """Make a file readable by this user only. chmod does that on macOS/Linux; on Windows it only
    toggles read-only, so drop the inherited permissions with icacls instead."""
    if os.name != "nt":
        os.chmod(path, 0o600)
        return
    try:
        subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{getpass.getuser()}:F"],
                       capture_output=True, timeout=10, check=False)
    except OSError:
        pass                                    # best effort: data/ is still gitignored


# ---- logins

def load_users():
    if config.USERS_FILE.exists():
        return json.loads(config.USERS_FILE.read_text())
    return {}


def save_users(users):
    write_private(config.USERS_FILE, json.dumps(users, indent=2))


# ---- generated secrets

def get_secret_key():
    if not config.SECRET_FILE.exists():
        write_private(config.SECRET_FILE, secrets.token_hex(32))
    return config.SECRET_FILE.read_text().strip()


def get_robot_token():
    if not config.TOKEN_FILE.exists():
        write_private(config.TOKEN_FILE, secrets.token_urlsafe(24))
    return config.TOKEN_FILE.read_text().strip()


def new_hub_key():
    """Write a fresh ed25519 SSH key for the hub."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    private = ed25519.Ed25519PrivateKey.generate()
    write_private(config.HUB_KEY_FILE, private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption()))


def rotate_secrets():
    """Replace the cookie key, robot token and SSH key. The old ones are kept as *.old, not deleted.
    Returns the files that were replaced."""
    replaced = []
    for path in (config.SECRET_FILE, config.TOKEN_FILE, config.HUB_KEY_FILE):
        if path.exists():
            os.replace(path, path.with_name(path.name + ".old"))
            replaced.append(path.name)
    get_secret_key()
    get_robot_token()
    new_hub_key()
    return replaced


# ---- robots this hub has installed

registry_lock = threading.Lock()


def load_registry():
    if config.REGISTRY_FILE.exists():
        try:
            return json.loads(config.REGISTRY_FILE.read_text())
        except ValueError:
            print(f"Warning: {config.REGISTRY_FILE.name} is damaged; starting with an empty robot list.")
    return {}


registry = load_registry()   # name -> {"host", "user", "home", "host_key", "machine_id", ...}


def save_registry():
    """Write the registry to disk. Caller holds registry_lock."""
    write_private(config.REGISTRY_FILE, json.dumps(registry, indent=2))

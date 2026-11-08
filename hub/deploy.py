"""Installing robots over SSH: Add robot, Update, Remove, and the one-command-at-a-time terminal."""

import hashlib
import io
import json
import logging
import re
import shlex
import socket
import subprocess
import sys
import threading
import time

from . import config, robots, storage
from .jobs import DeployError, info, step

logging.getLogger("paramiko").setLevel(logging.CRITICAL)   # errors are reported in the app instead

pending_names = set()        # names picked by installs that are still running
key_lock = threading.Lock()


class HostKeyChanged(Exception):
    pass


def paramiko_module():
    try:
        import paramiko
    except ImportError:
        raise DeployError("The SSH library is missing. In a terminal, in the swarm-system folder, run:  "
                          "pip install -r hub/requirements.txt")
    return paramiko


def hub_key():
    """The hub's own SSH key. Each robot it installs trusts it, so later updates need no password."""
    paramiko = paramiko_module()
    with key_lock:
        if not config.HUB_KEY_FILE.exists():
            storage.new_hub_key()
        key = paramiko.Ed25519Key.from_private_key_file(str(config.HUB_KEY_FILE))
    return key, f"{key.get_name()} {key.get_base64()} {config.KEY_COMMENT}"


def firewall_hint():
    """How to let robots reach this computer, for the OS the hub runs on."""
    if sys.platform == "darwin":
        return ("Make sure macOS allows incoming connections for Python "
                "(System Settings > Network > Firewall), then wait a few seconds.")
    if sys.platform == "win32":
        return (f"Make sure Windows Firewall lets Python accept incoming connections on port {config.PORT} "
                "(Windows Security > Firewall & network protection > Allow an app through firewall) and that "
                "this Wi-Fi network is set to Private, then wait a few seconds.")
    return f"Make sure this computer's firewall allows incoming connections on port {config.PORT}."


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
            f"\n__rc=$?\necho\necho {config.TERM_MARK}$(pwd)\nexit $__rc")
        remote = f"timeout -k 2 {config.TERM_TIMEOUT} bash -c {shlex.quote(script)}"
        code, text, timed_out, truncated = run_capped(client, remote, config.TERM_TIMEOUT + 5,
                                                      config.TERM_MAX_OUTPUT)
    except Exception as err:
        raise DeployError(f"Running the command failed: {err}")
    finally:
        client.close()
    timed_out = timed_out or code in (124, 137)
    new_cwd = cwd
    at = text.rfind(config.TERM_MARK)
    if at != -1:
        lines = text[at + len(config.TERM_MARK):].splitlines()
        if lines:
            new_cwd = lines[0].strip() or cwd
        text = text[:at].rstrip("\n")       # also drops the blank line the marker adds
    return {"output": text, "code": None if timed_out else code, "cwd": new_cwd,
            "timed_out": timed_out, "truncated": truncated, "limit": config.TERM_TIMEOUT}


def run_as_root(client, command, password, timeout=60):
    """Run a command with sudo, typing the password for sudo only if the robot asks for one."""
    script = shlex.quote(command)
    code, _, _ = run(client, "sudo -n true")
    if code == 0:
        return run(client, f"sudo -n sh -c {script}", timeout=timeout)
    if not password:
        raise DeployError("This step needs administrator rights, and the robot wants its password for that. "
                          "Enter the robot's password and try again.")
    code, out, err = run(client, f"sudo -S -p '' sh -c {script}", stdin_data=password + "\n", timeout=timeout)
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
    for k, pattern in (("user", config.USER_RE), ("home", config.PATH_RE), ("python", config.PATH_RE)):
        if not pattern.fullmatch(facts.get(k, "")):
            raise DeployError(f"Unexpected {k} on the robot: {facts.get(k)!r}")
    return facts


def hub_addresses(client):
    """Where the robot should reach this hub: the address this computer used to
    reach the robot, plus (on a Mac) its .local name as a fallback if the IP changes."""
    local_ip = client.get_transport().sock.getsockname()[0]
    addrs = [f"[{local_ip}]:{config.PORT}" if ":" in local_ip else f"{local_ip}:{config.PORT}"]
    if sys.platform == "darwin":
        try:
            name = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True,
                                  text=True, timeout=3).stdout.strip()
            if re.fullmatch(r"[A-Za-z0-9-]{1,63}", name):
                addrs.append(f"{name}.local:{config.PORT}")
        except Exception:
            pass
    return addrs


def service_unit(facts):
    folder = f"{facts['home']}/{config.REMOTE_DIR}"
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
        f"Exec={facts['python']} {facts['home']}/{config.REMOTE_DIR}/status_ui.py\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def authorize_key_script(public_key):
    """Shell that trusts the hub's current key and drops any older hub key (e.g. after `rotate`)."""
    tag = shlex.quote(f" {config.KEY_COMMENT}$")
    return (
        'mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && '
        'chmod 600 ~/.ssh/authorized_keys && f=~/.ssh/authorized_keys && '
        f'{{ grep -v {tag} "$f" > "$f.swarm-tmp"; [ $? -le 1 ]; }} && '
        '{ cat "$f.swarm-tmp"; [ -s "$f.swarm-tmp" ] && [ -n "$(tail -c1 "$f.swarm-tmp")" ] && echo; '
        f'echo {shlex.quote(public_key)}; }} > "$f.swarm-new" && cat "$f.swarm-new" > "$f"; '
        'rc=$?; rm -f "$f.swarm-tmp" "$f.swarm-new"; exit $rc'
    )


def install_packages(job, client, facts, password):
    """Run robot/setup_robot.sh on the robot as root: once per robot, and again only if the script changed.

    A failure doesn't stop the install: the agent runs without the missing packages, and the next
    Update tries again. Returns True if the robot needs a reboot for the changes to take effect."""
    script = config.SETUP_FILE.read_bytes().replace(b"\r\n", b"\n")   # the Pi's sh can't read CRLF
    stamp = hashlib.sha256(script).hexdigest()
    folder = f"{facts['home']}/{config.REMOTE_DIR}"
    _, done, _ = run(client, f"cat {shlex.quote(folder)}/{config.SETUP_STAMP} 2>/dev/null")
    if done.strip() == stamp:
        return False                                      # already set up with this exact script

    step(job, "Installing the robot's packages (the first time takes a few minutes)")
    run(client, f"mkdir -p {shlex.quote(folder)}")
    sftp = client.open_sftp()
    try:
        sftp.putfo(io.BytesIO(script), f"{folder}/{config.SETUP_FILE.name}")
    finally:
        sftp.close()
    try:
        code, out, err = run_as_root(client, f"sh {shlex.quote(folder)}/{config.SETUP_FILE.name} "
                                             f"{shlex.quote(facts['user'])}",
                                     password, timeout=config.SETUP_READ_TIMEOUT)
    except DeployError:
        raise
    except Exception as err:                              # e.g. no output for SETUP_READ_TIMEOUT
        info(job, f"Installing the packages didn't finish ({err}). Parts that need them stay off; "
                  "press Update to try again.")
        return False
    lines = [ln for ln in (out + "\n" + err).splitlines() if ln.strip()]
    if code != 0:
        for line in lines[-8:]:
            info(job, line)
        info(job, "Couldn't install all the robot's packages (see above). The agent still works, but the "
                  "parts that need them stay off. Press Update to try again once the robot has internet.")
        return False
    for line in lines:
        if line.startswith("[setup] "):
            info(job, line[len("[setup] "):])
    run(client, f"echo {stamp} > {shlex.quote(folder)}/{config.SETUP_STAMP}")
    return "SWARM_REBOOT_NEEDED" in out


def agent_log(client, password):
    """Last lines the agent printed on the robot, to explain a failure."""
    cmd = f"journalctl -u {config.SERVICE}.service -n 12 --no-pager -o cat"
    code, out, _ = run(client, cmd + " 2>/dev/null")
    if not out.strip():
        try:
            code, out, _ = run_as_root(client, cmd, password)
        except DeployError:
            out = ""
    return [line for line in out.splitlines() if line.strip()][-12:]


def pick_name(wanted, machine_id):
    """Choose the robot's name: the one it already has, the one asked for, or the next free one."""
    with storage.registry_lock:
        for name, entry in storage.registry.items():
            if machine_id and entry.get("machine_id") == machine_id:
                return name, True
        with robots.robots_lock:
            taken = set(storage.registry) | set(robots.robots) | pending_names
        if wanted:
            if wanted in taken:
                raise DeployError(f"The name '{wanted}' is already used by another robot. Pick another name.")
            name = wanted
        else:
            n = 1
            while f"{config.DEFAULT_PREFIX}{n:02d}" in taken:
                n += 1
            name = f"{config.DEFAULT_PREFIX}{n:02d}"
        pending_names.add(name)
        return name, False


def save_registry_entry(name, entry):
    with storage.registry_lock:
        storage.registry[name] = entry
        storage.save_registry()


def wait_for_robot(name, since, timeout=config.CONNECT_WAIT):
    end = time.time() + timeout
    while time.time() < end:
        with robots.robots_lock:
            rec = robots.robots.get(name)
        if rec and rec["online"] and rec["connected_at"] >= since:
            return True
        time.sleep(0.5)
    return False


def do_install(job, host, user, password, wanted_name=None, existing=None, reboot=False):
    """Install the agent on a robot (Add), or re-install it (Update); optionally reboot it after."""
    for filename in config.ROBOT_FILES + (config.SETUP_FILE.name,):
        if not (config.ROBOT_DIR / filename).exists():
            raise DeployError(f"robot/{filename} is missing from this repository.")
    _, public_key = hub_key()
    step(job, f"Connecting to {user}@{host}")
    client, host_key = ssh_connect(host, user, password, existing and existing.get("host_key"))
    reserved = None
    token_name = None
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
        folder = f"{facts['home']}/{config.REMOTE_DIR}"

        step(job, "Letting the hub log in without a password next time")
        code, _, err = run(client, authorize_key_script(public_key))
        if code != 0:
            info(job, f"Couldn't add the key ({err.strip() or 'unknown error'}); updates will need the password.")

        needs_reboot = install_packages(job, client, facts, password)
        if facts.get("tk") != "yes":
            facts = robot_facts(client)                   # tkinter may have just been installed
        if needs_reboot and not reboot:
            info(job, "Reboot the robot once so the arm's I2C bus turns on (press Update and tick "
                      "'Reboot the robot when done').")

        screen = config.STATUS_UI_FILE.exists() and facts.get("tk") == "yes" and facts.get("desktop") == "yes"
        step(job, f"Copying the agent{' and status screen' if screen else ''} to {folder}")
        addrs = hub_addresses(client)
        with storage.registry_lock:
            token = (storage.registry.get(name) or {}).get("token") or storage.new_robot_token()
            storage.pending_tokens[name] = token      # lets the robot in before this install is saved
        token_name = name
        robot_config = {"hub": addrs, "name": name, "token": token, "robot_type": "masterpi"}
        if screen:
            run(client, "mkdir -p ~/.config/autostart")
        sftp = client.open_sftp()
        try:
            try:
                sftp.mkdir(folder, 0o755)
            except IOError:
                pass                                      # already there
            for filename in config.ROBOT_FILES:
                sftp.put(str(config.ROBOT_DIR / filename), f"{folder}/{filename}")
            with sftp.open(f"{folder}/config.json", "w") as f:
                f.chmod(0o600)                            # private before the token goes in
                f.write(json.dumps(robot_config, indent=2))
            with sftp.open(f"{folder}/{config.SERVICE}.service", "w") as f:
                f.write(service_unit(facts))
            if screen:
                sftp.put(str(config.STATUS_UI_FILE), f"{folder}/status_ui.py")
                with sftp.open(f"{facts['home']}/{config.AUTOSTART}", "w") as f:
                    f.write(autostart_entry(facts))
        finally:
            sftp.close()
        info(job, "Robot will connect to " + " or ".join(addrs))
        if not screen:
            missing = ("robot/status_ui.py is missing" if not config.STATUS_UI_FILE.exists()
                       else "this robot has no desktop" if facts.get("desktop") != "yes"
                       else "this robot's Python has no tkinter")
            info(job, f"Skipped the status screen: {missing}.")

        step(job, "Setting it to start on every boot")
        since = time.time()
        code, out, err = run_as_root(client, (
            f"install -m 644 {shlex.quote(folder)}/{config.SERVICE}.service /etc/systemd/system/{config.SERVICE}.service && "
            f"systemctl daemon-reload && systemctl enable --quiet {config.SERVICE}.service && "
            f"systemctl restart {config.SERVICE}.service"
        ), password)
        if code != 0:
            raise DeployError("Installing the service failed: " + (err.strip() or out.strip() or f"exit code {code}"))
        time.sleep(1.5)
        _, state, _ = run(client, f"systemctl is-active {config.SERVICE}.service")
        if state.strip() != "active":
            for line in agent_log(client, password):
                info(job, line)
            raise DeployError(f"The agent didn't start on the robot (service is {state.strip() or 'unknown'}). "
                              "Its last messages are above.")

        with storage.registry_lock:
            prior = storage.registry.get(name) or {}
        save_registry_entry(name, {
            "host": host, "user": facts["user"], "home": facts["home"], "host_key": host_key,
            "machine_id": facts.get("machine", ""), "hostname": facts.get("hostname", ""),
            "added": prior.get("added", time.time()), "updated": time.time(), "token": token,
        })

        step(job, "Waiting for the robot to connect to the hub")
        if not wait_for_robot(name, since):
            log = agent_log(client, password)
            for line in log:
                info(job, line)
            latest = log[-3:]                     # older lines may be from an earlier run
            if any(re.match(r"(Traceback|\w+(Error|Exception)\b|Missing config|config\.json)", ln) for ln in latest):
                why = ("The agent is crashing on the robot (see its messages above). "
                       "If you edited the robot code, fix it and press Update.")
            elif any("hub refused" in ln for ln in latest):
                why = "The hub refused it (see above). Press Update to send it fresh settings."
            else:
                why = "The robot can't reach this computer. " + firewall_hint()
            if reboot:
                why += " (It wasn't rebooted, since that wouldn't fix this.)"
            job["warning"] = f"{name} is installed and will start on every boot, but it hasn't connected yet. {why}"
            return

        if not reboot:
            job["message"] = f"{name} is installed, connected, and will start by itself whenever the robot boots."
            if screen:
                job["message"] += (" If its status screen is open it updates itself; otherwise it opens "
                                   "the next time the robot starts.")
            if needs_reboot:
                job["message"] += " Reboot it once so the arm's I2C bus turns on."
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
        if not wait_for_robot(name, reboot_at, timeout=config.REBOOT_WAIT):
            job["warning"] = (
                f"{name} rebooted but hasn't reconnected after {config.REBOOT_WAIT // 60} minutes. If this computer "
                "switched Wi-Fi networks while the robot restarted (it happens in hotspot mode), join the "
                "robot's Wi-Fi again and it will reconnect by itself.")
            return
        job["message"] = f"{name} rebooted, started by itself and reconnected."
        if screen:
            job["message"] += " Its status screen is open on the robot's desktop."
    finally:
        client.close()
        if reserved:
            with storage.registry_lock:
                pending_names.discard(reserved)
        if token_name:
            with storage.registry_lock:
                storage.pending_tokens.pop(token_name, None)


def do_remove(job, password, forget=False):
    name = job["robot"]
    with storage.registry_lock:
        entry = storage.registry.get(name)
    if entry and not forget:
        step(job, f"Connecting to {entry['user']}@{entry['host']}")
        client, _ = ssh_connect(entry["host"], entry["user"], password, entry.get("host_key"))
        try:
            step(job, "Stopping the agent and removing the start-on-boot service")
            code, out, err = run_as_root(client, (
                f"systemctl disable --now {config.SERVICE}.service 2>/dev/null; "
                f"rm -f /etc/systemd/system/{config.SERVICE}.service; systemctl daemon-reload"
            ), password)
            if code != 0:
                raise DeployError("Removing the service failed: " + (err.strip() or out.strip() or f"exit code {code}"))
            step(job, "Closing the status screen and deleting the hub's files and key")
            folder = f"{entry['home']}/{config.REMOTE_DIR}"
            run(client, (
                # "[s]tatus" so pkill doesn't match this very shell command
                f"pkill -f {shlex.quote(folder + '/[s]tatus_ui.py')}; rm -f ~/{config.AUTOSTART}; "
                f"rm -rf {shlex.quote(folder)}; f=~/.ssh/authorized_keys; "
                f'if [ -f "$f" ]; then grep -v {shlex.quote(f" {config.KEY_COMMENT}$")} "$f" > "$f.swarm-tmp"; '
                f'cat "$f.swarm-tmp" > "$f"; rm -f "$f.swarm-tmp"; fi'
            ))
        finally:
            client.close()
    step(job, "Taking it off the list")
    with storage.registry_lock:
        storage.registry.pop(name, None)
        storage.save_registry()
    robots.disconnect(name)
    if forget and entry:
        job["message"] = (f"{name} is off the list. If the robot still has the agent, use Add robot then "
                          "Remove to uninstall it properly.")
    else:
        job["message"] = f"{name} has been removed."

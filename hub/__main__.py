"""Swarm Hub: a login-protected app that installs, watches and controls robots.

Run it on your computer, sign in, and press "Add robot". Give it the robot's IP
address, username and password; the hub connects over SSH, copies the code in
robot/ onto the robot and installs it as a service that starts on every boot,
sets status_ui.py to open on the robot's desktop, then reboots the robot and
waits for it to come back and connect.

Usage (from the repository folder):
    python -m hub adduser <name>   # create or change a login (asks for a password)
    python -m hub token            # show the token robots use to connect
    python -m hub rotate           # replace the cookie key, robot token and SSH key
    python -m hub                  # open the app in a window and serve it on port 8000
    python -m hub --headless       # serve only, no window (open the printed URL in a browser)
    python -m hub --port 8001      # use another port if 8000 is taken (also works with --headless)
"""

import getpass
import socket
import sys
import threading
import time

from . import config, storage


def add_user(name):
    if not config.NAME_RE.fullmatch(name):
        sys.exit("Usernames can use letters, digits, - and _ (up to 32).")
    from werkzeug.security import generate_password_hash
    password = getpass.getpass("Password: ")
    if not password:
        sys.exit("The password can't be empty.")
    if getpass.getpass("Repeat password: ") != password:
        sys.exit("Passwords do not match.")
    users = storage.load_users()
    users[name] = generate_password_hash(password)
    storage.save_users(users)
    print(f"Saved user '{name}'.")


def rotate():
    replaced = storage.rotate_secrets()
    print("New cookie key, robot token and SSH key written to " + str(config.DATA_DIR) + ".")
    if replaced:
        print("The old ones were kept as: " + ", ".join(n + ".old" for n in replaced))
    print("Everyone is signed out. Robots will be refused until you press Update on each one and enter\n"
          "its password; that sends the new token and swaps the old hub key for the new one.")


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no traffic is sent
        return s.getsockname()[0]
    except OSError:
        return "your-computer's-address"
    finally:
        s.close()


def wait_for_server(timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", config.PORT), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def port_in_use(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def serve():
    if not storage.load_users():
        sys.exit("No users yet. Create one first:  python -m hub adduser <name>")
    if port_in_use(config.PORT):
        # Otherwise the window would quietly show whatever other app owns the port.
        sys.exit(f"Port {config.PORT} is already used by another program (maybe another project's server, or a "
                 f"second hub). Stop it, or start the hub on another port:  --port 8001\n"
                 f"Robots already installed look for the hub on the port it had when they were added; "
                 f"press Update on each to point them at the new one.")
    for filename in config.ROBOT_FILES:
        if not (config.ROBOT_DIR / filename).exists():
            print(f"Warning: robot/{filename} is missing, so Add robot won't work.")
    from .app import create_app
    app = create_app()

    def run_server():
        app.run(host="0.0.0.0", port=config.PORT, threaded=True)

    print(f"Web page:  http://{lan_ip()}:{config.PORT}  (any device on your network)")
    if "--headless" in sys.argv:
        run_server()          # server only, no window
        return
    try:
        import webview        # native window; needs: pip install pywebview
    except ImportError:
        print("pywebview isn't installed, so there's no window; open the address above in a browser.")
        run_server()
        return
    threading.Thread(target=run_server, daemon=True).start()
    if not wait_for_server():
        sys.exit("The server did not start.")
    webview.create_window("Swarm Hub", f"http://127.0.0.1:{config.PORT}", width=1100, height=720)
    webview.start()           # returns when you close the window; the server stops too


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--port" in argv:
        at = argv.index("--port")
        try:
            config.PORT = int(argv[at + 1])
        except (IndexError, ValueError):
            sys.exit("--port needs a number, e.g. --port 8001")
        del argv[at:at + 2]
    if len(argv) == 2 and argv[0] == "adduser":
        add_user(argv[1])
    elif argv == ["token"]:
        print(storage.get_robot_token())
    elif argv == ["rotate"]:
        rotate()
    elif not argv or argv == ["--headless"]:
        serve()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()

"""Status screen for a Swarm Hub robot.

The hub installs this next to robot_agent.py and sets it to open on the
robot's desktop at startup (on a screen plugged into the robot, or over VNC).
It shows whether this robot is connected to the hub, its names and IP address,
and every robot in the swarm. It reads status.json, which the agent rewrites
every second, so it never touches the robot's connection itself.

Run it by hand on the robot's desktop:  python3 status_ui.py
F11 toggles full screen. It reloads itself when the hub pushes a new version.
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import font as tkfont
    from tkinter import ttk
except ImportError:
    sys.exit("tkinter is not installed, so the status screen can't open. (sudo apt install python3-tk)")

HERE = Path(__file__).resolve().parent
STATUS_FILE = HERE / "status.json"
LOCK_FILE = HERE / ".status_ui.lock"
STALE_AFTER = 5          # seconds without an update before we say the agent isn't running

THEME = {
    "bg": "#f6f7f9", "card": "#ffffff", "text": "#1d2330", "muted": "#667085", "line": "#e4e7ec",
    "ok": ("#157f3b", "#e6f4ea"), "warn": ("#a15c00", "#fdf1dc"), "bad": ("#b42318", "#fde8e7"),
}
STATUS_TEXT = {"connected": "Connected", "unresponsive": "Not responding", "offline": "Offline"}


def single_instance():
    """Return a lock handle, or None if another status screen is already open."""
    try:
        import fcntl
    except ImportError:
        return True
    handle = open(LOCK_FILE, "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    return handle


def read_status():
    try:
        data = json.loads(STATUS_FILE.read_text())
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def ago(seconds):
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "{} s".format(seconds)
    if seconds < 3600:
        return "{} min".format(seconds // 60)
    return "{} h {} min".format(seconds // 3600, seconds % 3600 // 60)


class StatusScreen:
    def __init__(self, root):
        self.root = root
        self.my_mtime = os.stat(__file__).st_mtime
        self.fullscreen = False
        t = THEME
        root.title("Swarm status")
        root.geometry("800x480")
        root.minsize(560, 380)
        root.configure(bg=t["bg"])
        root.bind("<F11>", self.toggle_fullscreen)
        root.bind("<Escape>", lambda e: self.set_fullscreen(False))

        base = tkfont.nametofont("TkDefaultFont").actual()["family"]
        self.f_big = tkfont.Font(family=base, size=20, weight="bold")
        self.f_mid = tkfont.Font(family=base, size=12)
        self.f_label = tkfont.Font(family=base, size=11)
        self.f_value = tkfont.Font(family=base, size=13, weight="bold")
        self.f_head = tkfont.Font(family=base, size=13, weight="bold")
        self.f_me = tkfont.Font(family=base, size=12, weight="bold")   # kept here so Tk doesn't lose it

        # Banner: connected or not
        self.banner = tk.Frame(root, padx=18, pady=12)
        self.banner.pack(fill="x", padx=14, pady=(14, 8))
        self.b_title = tk.Label(self.banner, font=self.f_big, anchor="w")
        self.b_title.pack(fill="x")
        self.b_sub = tk.Label(self.banner, font=self.f_mid, anchor="w", justify="left")
        self.b_sub.pack(fill="x")

        # This robot
        card = tk.Frame(root, bg=t["card"], highlightbackground=t["line"], highlightthickness=1, padx=16, pady=10)
        card.pack(fill="x", padx=14, pady=(0, 8))
        self.values = {}
        fields = [("hostname", "Robot name"), ("hub_name", "Name on the hub"),
                  ("ips", "IP address"), ("hub", "Hub")]
        for i, (key, label) in enumerate(fields):
            row, col = divmod(i, 2)
            tk.Label(card, text=label, font=self.f_label, fg=t["muted"], bg=t["card"], anchor="w").grid(
                row=row * 2, column=col, sticky="w", padx=(0, 24))
            value = tk.Label(card, text="-", font=self.f_value, fg=t["text"], bg=t["card"], anchor="w")
            value.grid(row=row * 2 + 1, column=col, sticky="w", padx=(0, 24), pady=(0, 6))
            self.values[key] = value
        card.columnconfigure(0, weight=1)
        card.columnconfigure(1, weight=1)

        # The swarm
        head = tk.Frame(root, bg=t["bg"])
        head.pack(fill="x", padx=16, pady=(4, 2))
        tk.Label(head, text="Swarm", font=self.f_head, fg=t["text"], bg=t["bg"]).pack(side="left")
        self.swarm_note = tk.Label(head, font=self.f_label, fg=t["muted"], bg=t["bg"])
        self.swarm_note.pack(side="left", padx=10)

        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Swarm.Treeview", font=self.f_mid, rowheight=30, background=t["card"],
                        fieldbackground=t["card"], foreground=t["text"], borderwidth=0)
        style.configure("Swarm.Treeview.Heading", font=self.f_label, foreground=t["muted"],
                        background=t["bg"], relief="flat")
        style.map("Swarm.Treeview", background=[("selected", t["line"])], foreground=[("selected", t["text"])])
        table_frame = tk.Frame(root, bg=t["line"], padx=1, pady=1)
        table_frame.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        columns = ("hub_name", "hostname", "address", "status")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", style="Swarm.Treeview",
                                  selectmode="none")
        for col, title, width in zip(columns, ("Name on the hub", "Robot name", "IP address", "Status"),
                                     (190, 170, 170, 150)):
            self.table.heading(col, text=title, anchor="w")
            self.table.column(col, width=width, anchor="w")
        self.table.tag_configure("connected", foreground=t["ok"][0])
        self.table.tag_configure("unresponsive", foreground=t["warn"][0])
        self.table.tag_configure("offline", foreground=t["muted"])
        self.table.tag_configure("me", font=self.f_me)
        self.table.pack(fill="both", expand=True)

        self.refresh()
        self.check_for_update()

    def toggle_fullscreen(self, _event=None):
        self.set_fullscreen(not self.fullscreen)

    def set_fullscreen(self, on):
        self.fullscreen = on
        self.root.attributes("-fullscreen", on)

    def set_banner(self, kind, title, sub):
        fg, bg = THEME[kind]
        self.banner.configure(bg=bg)
        self.b_title.configure(text=title, fg=fg, bg=bg)
        self.b_sub.configure(text=sub, fg=fg, bg=bg)

    def refresh(self):
        data = read_status()
        age = time.time() - data.get("updated", 0) if data else None
        if data is None:
            self.set_banner("bad", "Agent not running", "The swarm agent hasn't started on this robot yet.")
        elif age > STALE_AFTER:
            self.set_banner("bad", "Agent not running", "No news from the swarm agent for {}.".format(ago(age)))
        elif data.get("connected"):
            self.set_banner("ok", "Connected to the hub",
                            "{}  ·  connected for {}".format(data.get("hub", ""), ago(time.time() - data.get("since", 0))))
        else:
            why = data.get("error") or "starting up"
            self.set_banner("warn", "Not connected to the hub",
                            "Trying {}  ·  {}  ·  for {}".format(data.get("hub") or "the hub", why,
                                                               ago(time.time() - data.get("since", 0))))

        data = data or {}
        self.values["hostname"].configure(text=data.get("hostname") or "-")
        self.values["hub_name"].configure(text=data.get("hub_name") or "-")
        self.values["ips"].configure(text=", ".join(data.get("ips") or []) or "-")
        self.values["hub"].configure(text=data.get("hub") or "-")

        swarm = data.get("swarm") or []
        me = data.get("hub_name")
        live = data.get("connected") and age is not None and age <= STALE_AFTER
        self.table.delete(*self.table.get_children())
        for r in swarm:
            status = str(r.get("status", "offline"))
            if live:
                tags, shown = [status if status in STATUS_TEXT else "offline"], STATUS_TEXT.get(status, status)
            else:
                tags, shown = ["offline"], "Unknown"          # can't know while cut off from the hub
            name = str(r.get("name", "?"))
            if name == me:
                tags.append("me")
                name += "  (this robot)"
            self.table.insert("", "end", tags=tags, values=(
                name, r.get("hostname") or "-", r.get("address") or "-", shown))
        if not swarm:
            self.swarm_note.configure(text="The list appears once this robot connects to the hub.")
        elif live:
            online = sum(1 for r in swarm if r.get("status") == "connected")
            self.swarm_note.configure(text="{} of {} connected".format(online, len(swarm)))
        else:
            self.swarm_note.configure(text="Last known list (this robot isn't connected right now)")
        self.root.after(1000, self.refresh)

    def check_for_update(self):
        """Restart when the hub has copied a new version of this file."""
        try:
            changed = os.stat(__file__).st_mtime != self.my_mtime
        except OSError:
            changed = False
        if changed:
            self.root.destroy()
            os.execv(sys.executable, [sys.executable] + sys.argv)
        self.root.after(3000, self.check_for_update)


def main():
    lock = single_instance()
    if lock is None:
        print("The status screen is already open.")
        return
    try:
        root = tk.Tk()
    except tk.TclError as err:
        sys.exit("Can't open a window ({}). Run this on the robot's desktop.".format(err))
    StatusScreen(root)
    root.mainloop()


if __name__ == "__main__":
    main()

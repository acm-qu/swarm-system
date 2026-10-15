"""Status window shown on the robot's desktop.

Shows the robot's name and user, its IP address, whether it is connected to the
hub, and the last control signal received from the hub. It only reads
status.json, which robot_agent.py keeps up to date, so it can't affect the robot.

The hub starts it at desktop login. To run it by hand:  python3 status_ui.py
"""

import json
import time
import tkinter as tk
from pathlib import Path

STATUS_FILE = Path(__file__).with_name("status.json")
REFRESH_MS = 200       # how often the window redraws
STALE_AFTER = 3.0      # status.json older than this means the agent isn't running (seconds)

BG, FG, MUTED = "#1c2027", "#e7e9ee", "#98a2b3"
GREEN, RED, AMBER = "#6fd391", "#ff8a80", "#f4b860"


def load_status():
    try:
        return json.loads(STATUS_FILE.read_text())
    except (OSError, ValueError):
        return {}


def ago(seconds):
    if seconds < 1:
        return "just now"
    if seconds < 60:
        return "{:.0f} s ago".format(seconds)
    return "{:.0f} min ago".format(seconds / 60)


def describe_control(control, now):
    """What the control signal box shows: a headline, and forward/strafe/rotate for a drive command."""
    if not control:
        return "nothing received yet", None
    kind = control.get("kind", "?")
    when = ago(max(0.0, now - control.get("at", now)))
    if kind == "drive":
        values = ["{:+.2f}".format(control.get(k, 0)) for k in ("forward", "strafe", "rotate")]
        return "DRIVE  ({})".format(when), values
    return "{}  ({})".format(kind.upper(), when), None


class StatusWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Swarm robot")
        self.root.geometry("420x360")
        self.root.configure(bg=BG)
        try:
            self.root.attributes("-topmost", True)
        except tk.TclError:
            pass

        self.state = tk.Label(self.root, text="", bg=BG, font=("Helvetica", 18, "bold"), anchor="w")
        self.state.pack(fill="x", padx=14, pady=(12, 0))
        self.detail = tk.Label(self.root, text="", bg=BG, fg=MUTED, font=("Helvetica", 10),
                               anchor="w", justify="left", wraplength=370)
        self.detail.pack(fill="x", padx=14)

        grid = tk.Frame(self.root, bg=BG)
        grid.pack(fill="x", padx=14, pady=10)
        self.values = {}
        for row, (key, label) in enumerate((("name", "Name"), ("user", "User"),
                                            ("ip", "IP address"), ("hub", "Hub"))):
            tk.Label(grid, text=label, bg=BG, fg=MUTED, font=("Helvetica", 11),
                     anchor="w", width=10).grid(row=row, column=0, sticky="w", pady=1)
            value = tk.Label(grid, text="-", bg=BG, fg=FG, font=("Helvetica", 11),
                             anchor="w", justify="left")
            value.grid(row=row, column=1, sticky="w", pady=1)
            self.values[key] = value

        box = tk.Frame(self.root, bg="#262b33")
        box.pack(fill="x", padx=14, pady=(0, 12))
        tk.Label(box, text="Control signal from hub", bg="#262b33", fg=MUTED,
                 font=("Helvetica", 10), anchor="w").pack(fill="x", padx=10, pady=(8, 0))
        self.control = tk.Label(box, text="", bg="#262b33", fg=FG, font=("Helvetica", 13, "bold"), anchor="w")
        self.control.pack(fill="x", padx=10)
        row = tk.Frame(box, bg="#262b33")
        row.pack(fill="x", padx=10, pady=(2, 8))
        self.control_values = []
        for column, label in enumerate(("Forward", "Strafe", "Rotate")):
            row.columnconfigure(column, weight=1, uniform="v")
            tk.Label(row, text=label, bg="#262b33", fg=MUTED, font=("Helvetica", 9),
                     anchor="w").grid(row=0, column=column, sticky="w")
            value = tk.Label(row, text="", bg="#262b33", fg=FG, font=("Helvetica", 14, "bold"), anchor="w")
            value.grid(row=1, column=column, sticky="w")
            self.control_values.append(value)

        self.tick()

    def tick(self):
        try:
            self.redraw()
        except Exception:
            pass                                  # never let a bad file close the window
        self.root.after(REFRESH_MS, self.tick)

    def redraw(self):
        s = load_status()
        now = time.time()
        running = bool(s) and now - s.get("updated", 0) < STALE_AFTER

        if not running:
            self.state.config(text="● Agent not running", fg=RED)
            self.detail.config(text="The robot agent isn't updating its status. "
                                    "It may be starting up or stopped.")
        elif s.get("connected"):
            self.state.config(text="● Connected", fg=GREEN)
            self.detail.config(text="to the hub for " + ago(now - s.get("since", now)).replace(" ago", ""))
        else:
            self.state.config(text="● Not connected", fg=AMBER)
            self.detail.config(text=s.get("error") or "trying to reach the hub")

        self.values["name"].config(text=s.get("hub_name") or s.get("hostname") or "-")
        self.values["user"].config(text=s.get("user") or "-")
        self.values["ip"].config(text=", ".join(s.get("ips") or []) or "-")
        self.values["hub"].config(text=s.get("hub") or "-")

        headline, values = describe_control(s.get("control") or {}, now)
        self.control.config(text=headline)
        for label, text in zip(self.control_values, values or ("", "", "")):
            label.config(text=text)


if __name__ == "__main__":
    StatusWindow().root.mainloop()

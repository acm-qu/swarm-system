# Swarm Hub app: screens and features (designer brief)

This is everything the app has to show and do, so you can design the layout (Canva, Figma, anything).
It describes **what is on each screen**, not how it should look: the look is yours.
Technical background is in `../ARCHITECTURE.md`, but you don't need it.

---

## 1. Who uses it, and how

- **Users:** our team of students (3 to 6 people). Everyone can use every feature.
- **What they control:** up to 4 robots. Each robot has 4 wheels that can also slide sideways (mecanum),
  a 5-joint arm with a gripper, a camera, and a distance sensor (ultrasonic). Later: battery level and
  heading (gyro).
- **Where:** mostly on a laptop (design for 1280 px wide first), sometimes a tablet. On a phone it must at
  least show the robots and the camera, and the **Stop** buttons must work.
- **Situations:** sitting next to the robots in the lab, or at home watching through the camera. A robot can
  be driven by someone who **can't see it**, so the screen must make what is happening very obvious.
- **Light and dark mode**, both.

### Words you'll see in this brief
- **Hub:** the program in the lab that every robot connects to; the app is its screen.
- **Latency:** how long a message takes to reach the robot and come back, in milliseconds (ms). Under 50 ms
  is good; over 200 ms feels laggy.
- **Servo / µs:** the arm's motors are servos; their position is a pulse length in microseconds (µs),
  about 500 to 2500.
- **Ultrasonic sensor:** measures distance to the nearest object in front by timing a sound echo.
- **Mecanum wheels:** wheels that also let the robot slide sideways.
- **Terminal:** a text window for typing commands that run on the robot.
- **Tailscale:** the private network that lets team laptops open the app from anywhere (only our devices can
  reach it). More in `../ARCHITECTURE.md`, section 13.

## 2. Design principles

1. **Safety first.** *Stop all* is visible on every screen, always red, always works. Each robot also has its
   own Stop. Stop is never greyed out while a robot is online, even when someone else is driving it.
2. **Status at a glance.** From across the room you should see which robots are online, which are moving and
   who is controlling them.
3. **Every feature explains itself.** Each panel has a small **?** that opens a short explanation (texts in
   section 7). The team is still learning the system.
4. **Plain words.** Messages are full sentences a first-year student understands (examples in section 8).
5. **Dangerous actions look different** (Release arm, Remove robot, Terminal) and ask for confirmation.

## 3. Status vocabulary

These words and meanings must be consistent everywhere (colour is your choice, but each needs its own):

| State | Meaning | Today's colour |
|---|---|---|
| **Connected** | Robot is online and answering | green |
| **Unresponsive** | Connected, but not heard from for over 3 s (bad Wi-Fi?) | amber |
| **Offline** | Not connected | grey |
| **Working…** | The hub is installing or updating it (show the current step) | blue |
| **Controlled by *name*** | Someone is driving it or moving its arm; others can watch and Stop | a badge with the person's name |
| **Moving** | Wheels are turning right now | something that draws attention |

## 4. Screens (sitemap)

```
Sign in
└── App frame (top bar + navigation, on every screen)
    ├── Fleet (home)             all robots at a glance
    ├── Robot detail             one robot: drive, camera, arm, sensors, terminal, info, activity
    ├── History                  everything that happened, searchable
    ├── Health                   is the hub machine OK? network quality per robot
    └── Help                     what each feature does, how to set things up
Dialogs: Add robot · Update robot · Remove robot · Confirm · Job progress
Later (leave room in the navigation, mark "coming soon"): Jobs · World map · Planner
```

### 4.0 App frame (every screen)

Top bar:
- App name: **Swarm Hub**
- Hub status: connected or reconnecting to the hub (if the hub is unreachable, everything else is stale:
  show this loudly)
- Summary: "**3 of 4 robots online**"
- **Stop all** button (red, big, always there). Keyboard: `Esc` twice
- Signed-in person: name, *Sign out*

Navigation: Fleet · History · Health · Help (+ greyed "coming soon": Jobs, World, Planner).

A live **notification area** (toast or a strip) for events as they happen: "masterpi-02 went offline",
"sara took control of masterpi-01", "Update of masterpi-03 finished".

### 4.1 Sign in

- Username, password, *Sign in* button
- Errors: "Wrong username or password." · "Too many attempts. Wait a minute." · "Session expired, try again."
- Note under the form: "Only team devices on our Tailscale network can open this page."

### 4.2 Fleet (home)

One **robot card** (or table row; your choice, but cards suit 4 robots) per robot:

| Field | Example |
|---|---|
| Name | masterpi-01 |
| Robot's own name (small) | raspberrypi |
| Status | Connected / Unresponsive / Offline / Working… "Copying the agent" |
| Controlled by | sara (or nothing) |
| Last seen | now / 12 s ago |
| Latency | 18 ms (good) · 250 ms (slow) |
| Sensors | distance 42 cm |
| Camera thumbnail | small live picture, or none (optional, only if cheap) |
| What it can do | icons: wheels, arm, camera, distance sensor (greyed if missing) |
| Last event | "ping ok", "arm moved", "camera: can't open camera 0 (is it plugged in?)" |
| Quick actions | **Stop**, Open (→ Robot detail), Ping |

Other things on this screen:
- **+ Add robot** button
- **Empty state** (no robots yet): "No robots yet. Press **Add robot** to set one up." plus a short what-you-need
  list (robot on the lab Wi-Fi, its IP address, its password)
- Robots that are installed but have never connected: "installed, hasn't connected yet"

### 4.3 Robot detail

The main working screen. Header, then panels (tabs, a grid, or a sidebar; your call). The **Drive** and
**Camera** panels must be usable **at the same time** (people drive by watching the camera).

**Header**
- Name, status, latency, last seen
- **Control badge:** "You are in control" / "sara is in control" / "Nobody is in control"
  - *Take control* (only when free) · *Release control* (when it's you)
  - Note: "Control frees up when the person closes the panel, or 15 seconds after their last command."
- **Stop** (red, always)
- Menu: Update…, Remove… (danger), Ping

**Panel: Drive**
- Direction pad with 6 buttons: forward ▲ (W), back ▼ (S), slide left ◀ (A), slide right ▶ (D),
  turn left ⟲ (Q), turn right ⟳ (E), and a big **Stop** in the middle (Space)
- Show the key letters on the buttons; pressed buttons light up
- **Speed** slider 10% to 100% (default 40%)
- Text: "Hold a button or key to move; let go and the robot stops."
- Live readout of what is being sent: Forward +0.40, Strafe 0.00, Rotate 0.00
- States: disabled when offline / no wheels / someone else in control (show who); error line for messages
  like "Too many commands at once. Slow down a little."

**Panel: Camera**
- Live picture (4:3, 640×480)
- States: "Waiting for the camera…", "No picture yet. Retrying…", camera error text from the robot, offline
- Option: quality Low (5 fps, for home) / High (15 fps, in the lab)
- Fullscreen button

**Panel: Arm**
- 5 sliders: **base, shoulder, elbow, wrist, gripper**. Each shows its value in µs (microseconds, a servo
  pulse, range about 500 to 2500)
- Buttons: **Stop** (arm holds where it is), **Release (go limp)** (danger, confirm: "The arm will sag. Support
  it first."), Close
- Help text: "Nothing is sent until you move a slider. A joint's first move after the robot restarts jumps
  straight to the slider, so start close to where it really is."
- Disabled state: "This robot has no arm board connected."

**Panel: Sensors**
- **Distance:** big number "42 cm" (shows "≥ 200" when nothing is in range)
- Small line chart of the last few minutes
- "Since you opened this: lowest 12 cm, highest 180 cm"
- Coaching note that changes colour: good ("Working: the reading follows what is in front of the sensor."),
  warning ("The reading isn't changing. Move your hand toward the sensor."), bad (wiring hints)
- Later rows (leave space): **Heading** 92°, **Battery** 82%

**Panel: Terminal** (danger styling)
- Black/monospace output area, prompt showing the folder (`~/swarm-agent $`), input line, *Run*, *Clear*
- First use per session: confirm "This runs commands directly on the robot. Everything you run is logged."
- Notes: "One command at a time, stops after 30 seconds. Programs that need typing (nano, top) won't work."
- Meta lines under output: "exit code 1", "stopped: it took longer than 30 seconds", "output cut short"

**Panel: Info**
- Robot type (masterpi), address, robot's own name, installed by this hub (yes/no), what it can do
  (wheels / arm joints and limits / camera / sensors), added on, last updated

**Panel: Activity**
- This robot's history (same list as the History screen, filtered to it)

### 4.4 History

A searchable, scrollable list, newest first:

| Time | Robot | Person | What happened |
|---|---|---|---|
| 14:02:11 | masterpi-01 | sara | took control |
| 14:02:40 | masterpi-01 | najeeb | pressed Stop |
| 14:05:03 | masterpi-02 | | went offline (hub silent 5 s) |
| 14:06:20 | masterpi-03 | ali | ran in Terminal: `journalctl -u swarm-agent -n 30` (exit 0) |
| 14:09:55 | masterpi-03 | ali | Update finished |

Filters: robot, person, type (connections, control, stops, terminal, installs), date range. "Load more" at the
bottom. Empty state: "Nothing happened yet in this range."

### 4.5 Health

- **Hub machine** (the Raspberry Pi in the lab): CPU temperature (warn above 75 °C: "the Pi slows down when
  hot"), load, memory used, disk free, running since, version
- **Per robot:** latency now and over the last hour (small chart), reconnects in the last 24 h, last seen
- A one-line verdict on top: "All good" / "masterpi-02 keeps reconnecting: check its Wi-Fi"

### 4.6 Help

Short articles, also reachable from each panel's **?** (texts in section 7), plus:
- "How the system works" (one simple diagram: app → hub → robots)
- "Adding a robot", "When a robot won't connect", "Keyboard shortcuts", "Safety rules"

### 4.7 Dialogs

**Add robot**
- Fields: IP address (placeholder 192.168.149.1), Username (default `pi`), Password ("Used once to install.
  It is not saved."), Name (optional, "picked for you, e.g. masterpi-01")
- Checkbox: "Reboot the robot when done" + hint "Proves it starts by itself. Takes about a minute."
- Button: *Install*

**Update robot:** password (optional: "Usually not needed. Fill it in only if the robot asks for it."),
reboot checkbox, *Update*.

**Remove robot** (danger): password (optional), checkbox "The robot is gone or can't be reached. Just take it
off this list.", *Remove*.

**Job progress** (shown after Install/Update/Remove; can be hidden and keeps running):
- A list of steps, each with a state: running (spinner) · done ✓ · failed ✕ · info (small grey monospace line)
- Example steps: Connecting to pi@192.168.149.1 → Checking the robot → Installing the robot's packages (the
  first time takes a few minutes) → Copying the agent → Setting it to start on every boot → Waiting for the
  robot to connect to the hub
- Final note: success (green), warning (amber, e.g. "installed but hasn't connected yet. Make sure Windows
  Firewall…"), failure (red) with *Try again*

**Confirm:** title, one sentence of consequence, Cancel + the action in danger style.

## 5. Features list

**Version 1 (design these):**

| Feature | Where |
|---|---|
| Sign in / out | Sign in, top bar |
| Live list of robots with status, latency, sensors, last event | Fleet |
| Stop one robot / Stop all | everywhere |
| Control lock: one person controls a robot, others watch | Robot header, Fleet card |
| Manual drive (buttons + keyboard, speed) | Robot → Drive |
| Live camera (low / high quality, fullscreen) | Robot → Camera |
| Arm sliders, stop, release | Robot → Arm |
| Distance sensor with coaching and chart | Robot → Sensors |
| Terminal on the robot | Robot → Terminal |
| Robot info and capabilities | Robot → Info |
| Add / Update / Remove robot with step-by-step progress | Dialogs |
| History of everything, searchable | History, Robot → Activity |
| Hub and network health | Health |
| Built-in help for every feature | **?** buttons, Help |
| Live notifications | Top bar |

**Later (leave room, show as "coming soon"):**
- **Jobs:** run a fixed recipe ("Scan object", "Lift object", "Carry to zone") and watch its steps, with a
  "ready" check per robot and an abort button
- **World map:** top-down view of the arena: robots, the target object, tags, zones
- **Planner:** type a goal in plain words; an AI proposes steps; you approve before it runs
- Battery and heading sensors; more robot types (e.g. a carrier with a flat bed)

## 6. Keyboard shortcuts

| Key | Action |
|---|---|
| W / S | forward / back |
| A / D | slide left / right |
| Q / E | turn left / right |
| Space | stop this robot |
| Esc Esc | Stop all |
| Esc | close a dialog or panel |
| ↑ / ↓ in Terminal | previous / next command |

## 7. Help texts (for the **?** buttons)

- **Status:** "Connected means the robot is online. Unresponsive means it's connected but hasn't been heard
  from for a few seconds (often weak Wi-Fi). Offline means it isn't connected."
- **Control:** "Only one person can drive a robot or move its arm at a time. Anyone can always press Stop.
  Control frees up when the person closes the panel, or 15 seconds after their last command."
- **Drive:** "Hold a button or key to move; let go and the robot stops. If your connection drops, the robot
  stops by itself within half a second."
- **Camera:** "The robot's camera only runs while someone is watching. Use Low quality from home; it uses less
  of the lab's internet."
- **Arm:** "Each slider is a servo pulse in microseconds. Stop holds the arm where it is. Release makes it go
  limp, so support it first."
- **Distance sensor:** "The ultrasonic sensor measures how far the nearest object in front is, up to 2 m."
- **Terminal:** "Runs one command at a time on the robot, as the robot's user. Commands are logged. Each stops
  after 30 seconds."
- **Update:** "Copies the latest robot code from the hub to the robot and restarts it."
- **Remove:** "Stops the robot program, removes it from the robot, and takes the robot off this list."
- **History:** "Everything that happened: connections, who took control, stops, terminal commands, installs.
  Kept for 90 days."
- **Health:** "How the hub machine in the lab is doing, and how good each robot's connection is."

## 8. Message examples (real text from the system)

- "robot is offline"
- "sara is controlling masterpi-01 right now. You can still press Stop. Control frees up when they close the
  panel, or 15 seconds after their last command."
- "Too many commands at once. Slow down a little."
- "Something is already running for this robot. Wait for it to finish."
- "The robot rejected that username or password."
- "Couldn't reach 192.168.1.20. Check the robot is on and this computer is on the same network as it."
- "The sensor is set up but gave no reading. Check the Echo wire and the 1 kΩ / 2 kΩ divider."

Leave room for long messages: some are two lines.

## 9. What to deliver

Frames (light + dark if possible):
1. Sign in (normal + error)
2. Fleet: 4 robots in mixed states (connected, unresponsive, offline, working, controlled by someone) + empty
   state
3. Robot detail: you in control, driving with camera visible
4. Robot detail: someone else in control (controls disabled, Stop still active)
5. Robot detail: Arm, Sensors, Terminal, Info panels
6. History with filters
7. Health
8. Add robot dialog + job progress (running, success, failure)
9. Confirm dialog (Release arm / Remove)
10. Phone: Fleet + one robot's camera with Stop
11. Components sheet: status pills, control badge, buttons (normal, danger, disabled), toasts, help popover

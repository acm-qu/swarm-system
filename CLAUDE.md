# CLAUDE.md

Guide for AI assistants (and new teammates) working in this repo. Read `README.md` for the project goals
and phases.

## What this is

A swarm of Raspberry Pi robots (rewired Hiwonder MasterPi chassis) controlled by a PC.
- `hub/`: the PC app (Flask). It installs the agent on robots over SSH, shows their status, and sends
  commands. Run with `python -m hub` from the repo root. Planned (ARCHITECTURE.md): one shared hub on a
  Raspberry Pi 5 in the lab with a React front end in `web/`; local hubs stay for development.
- `robot/`: runs on each robot. The hub copies these files into `~/swarm-agent/` on the robot and runs
  `robot_agent.py` as the `swarm-agent` systemd service. Robots never pull code themselves. Edit here,
  then press **Update** in the hub.

## First-time setup

The team uses the launchers in the repo root, not a virtual environment. They find Python 3.9+ even when it
isn't on PATH and install packages with `pip --user`:
```
.\swarm setup            # Windows (swarm.cmd -> scripts/swarm.ps1); Mac/Linux: ./swarm.sh setup
.\swarm                  # start the hub; any other args go to `python -m hub` (adduser, rotate, --headless)
```
Don't create or commit a `.venv`. Add new hub packages to `hub/requirements.txt` so `setup` picks them up.
On Windows, allow Python through Windows Firewall (Private network) or robots can't connect back.
Everything a robot needs (apt packages such as `python3-gpiozero`, `python3-smbus` and `python3-opencv`, the
arm's I2C bus 3 overlay, and GPIO/I2C/camera groups) is in `robot/setup_robot.sh`. The hub runs it as root
once per robot on **Add robot**, and on **Update** only if the script has changed (stamp:
`~/swarm-agent/.setup-done`). A new robot package goes in its `PACKAGES` list.

## Rules

- **Never commit `data/`** or anything holding a key, token, password hash or `config.json`. It is
  gitignored. Don't print or paste these files' contents either.
- Robot code must run on **Python 3.7+ with only the standard library** for the hub link
  (`robot_agent.py`, `ws_client.py`). Hardware libraries are optional imports. If one is missing, that part
  disables itself and the agent still connects.
- Hardware safety: the robot stops its wheels if drive commands stop for 0.5 s or the hub goes silent for 3 s,
  and the arm moves at most `ARM_MAX_SPEED`. Keep these dead-man behaviours when changing movement code.
  Arm limits in `ARM_JOINTS` should be narrow: set each joint's safe range only after mapping it on real
  hardware. (Today they are the full 500-2500 µs; mapping them is on the checklist in `docs/robots.md`.)
- A new robot file must be added to `ROBOT_FILES` in `hub/config.py`, or the hub won't copy it.
- A new capability: report it in `capabilities()` (robot_agent.py). The hub stores it per robot
  (`robots.clean_capabilities`) and the page enables buttons from it (`hub/static/hub.js`).
- A new sensor: add it to `robot/sensors.py` (`setup`, `names`, `read`). Readings travel in each heartbeat
  and appear in the Sensors column.
- Match the existing style: plain-language error messages meant for students, short comments that say why.
- Each robot has its own token (in `data/robots.json`, written to its `config.json` on Add/Update). The
  shared token in `robot_token.txt` still works for robots not updated yet and for test agents.
- One person controls a robot at a time (`hub/control.py`): drive and arm commands claim it, Stop never
  needs it. Keep Stop unblocked by any new check.
- The plan for the new app (shared hub on a Pi 5, React front end, `/ui` WebSocket, SQLite history) is in
  `ARCHITECTURE.md`; its screens are in `docs/UI_SPEC.md`. Follow its build steps (tracks H and S).
- Deleting or removing old code (the old page, the shared-token fallback, `hub/server.py`) waits for the
  last step (S6). Don't remove things earlier unless asked.
- Remote driving only while someone is in the lab with the robots.
- Work on a branch and open a pull request; merge to `main` only when CI is green.
- Robot hardware state, wiring and faults per robot: `docs/robots.md`. Update it when hardware changes.
- The team is learning as it builds: when a doc or change brings in a new tool or term, explain it briefly
  in plain words (what it is, why we use it) in the Glossary of `ARCHITECTURE.md` (hardware terms: the table
  at the top of `docs/robots.md`).

## Protocol (robot <-> hub, JSON over WebSocket at /robot)

Robot → hub: `hello {name, token, robot_type, hostname, capabilities}`, then `heartbeat {sensors}` every
second, `capabilities {capabilities}` when they change after the hello (e.g. the arm board is found
later), `pong`, `stop_ack`, `camera_status`, and binary JPEG frames. The hello's `token` is the robot's
own token (or the shared one for robots not updated yet).
Hub → robot: `welcome`, `refused`, `heartbeat_ack {swarm, camera}`, `ping`, `stop`,
`drive {forward, strafe, rotate}` (each -1..1), `arm {targets: {joint: microseconds}}`, `arm_release`,
`gyro_calibrate` (zero the gyro's rotation; the robot must stand still for 2 s).

## Testing

There's no test suite yet. To check a change without hardware, run the hub with `SWARM_DATA_DIR` pointing
at a temp folder and `PORT=8765`. Then copy `robot/*.py` to a temp folder with a `config.json`
(`{"hub": ["127.0.0.1:8765"], "name": "test-bot", "token": "<python -m hub token>"}`) and run
`python robot_agent.py` there. It connects with all hardware disabled.

## Where the project is

Phase 0/1 (see README): the hub and manual control are built, the ultrasonic sensor is wired (GPIO22/24),
and the hub has per-robot tokens, a control lock and a command rate limit. Two tracks run in parallel
(ARCHITECTURE.md, section 11):
- **Hardware:** finish robot 1 (**Clanker**) against the checklist in `docs/robots.md` (wheel directions,
  arm safe limits, gyro, battery), then build robots 2-4.
- **Software:** rotate the old secrets (S1), then simulated robots + CI (S2), the backend for the app (S3),
  the shared hub Pi (S4) and the React app (S5).
The MPU-6050 gyro is wired on I2C bus 4 (`sensors.py`) and reports rotation `rot_{x,y,z}_deg` and turn
rate `gyro_{x,y,z}_dps`; the hub's Calibrate gyro button zeroes it.
After that: README Phase 2 (scanning with tags).

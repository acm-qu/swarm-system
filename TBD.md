# TBD: design features not built yet

The new page (`hub/templates/app.html`, `hub/static/app.js`, `hub/static/app.css`) follows the mockups in
`design/html/`, but only for what the hub can do today. This file lists what the mockups show and the app
doesn't do yet, with what it needs. Screen numbers are the mockup files (`design/html/NN-*.html`).

**How it was built:** the redesign is plain HTML, CSS and JavaScript served by Flask, on the same REST API as
before. It is not the React app from ARCHITECTURE.md step S5: that needs a Node build and CI, and the lab
hub should stay pip-only until then. The old page still works at `/classic` until S6.

## Pages (sidebar shows them as "Soon")

| Feature | Screens | Needs |
|---|---|---|
| History: every event, with filters for robot, person, type and date, plus Load more | 18 | S3: `history.py` (SQLite), events recorded by the hub, a history endpoint |
| Robot → Activity tab (this robot's history) | 17 | Same as History, filtered to one robot. The tab is left out for now |
| Health: hub machine (CPU temperature, load, memory, disk, uptime, version) and each robot's latency over the last hour and reconnects in 24 h | 19 | S3: health endpoint, latency samples, a reconnect count |
| Help: articles, search, "How the system works" diagram, "Was this clear?" | 20, 21 | Article texts. Each panel's **?** already shows its short help text (UI_SPEC section 7) as a popover |
| Jobs, World, Planner | all | README Phase 2 and later. Shown as "Soon" |

## App frame

| Feature | Screens | Needs |
|---|---|---|
| Notification bell and toasts for events ("Rover went offline", "sara took control of Clanker") | 03, 29, 32 | S3: the `/ui` WebSocket pushing events. Today the only toast is an error about your own action (e.g. a Stop that failed) |
| "Lab hub · Pi 5" under the logo | all | S4: the shared hub on the Pi. It says "Robot lab" until then |
| "Only team devices on our Tailscale network can open this page" on sign-in | 01, 02 | S4: Tailscale. Left out, because it isn't true yet |
| "Hub connected · 18 ms" | all | Built, but it measures the page's request round trip. It is not a ping to the hub |

## Fleet

| Feature | Screens | Needs |
|---|---|---|
| Live camera thumbnail on each card | 03, 05, 30 | Each open stream turns that robot's camera on, and four streams plus polling hit the browser's limit of 6 connections per host. Needs a snapshot endpoint (one JPEG) or `/ui`. The card shows sensors without a picture |
| "Moving" pill with bars | 03, 06, 32, 33 | A reliable "wheels turning" signal from the robot. The hub's last event says "driving" even after the robot's own dead-man stop |
| Time of the last event ("3 min ago") | 03 | The hub to timestamp events (S3) |
| Remove from the Fleet card | 27 | Remove is in Robot → Info |

## Robot view

| Feature | Screens | Needs |
|---|---|---|
| **Take control** button (when nobody has it) | 08 | A claim endpoint. Your first drive or arm command takes control today, and the card says so |
| Camera quality Low 5 fps / High 15 fps | 06, 33 | S3: camera `fps` setting sent to the robot |
| "Live · 15 fps" counter on the camera | 06 | The frame rate from the hub or the robot |
| "Last picture 6 s ago · reconnecting" on a stale camera | 05, 07 | The time of the last frame. Today it shows "No picture yet. Retrying…" |
| Header ⋯ menu (Update…, Remove…) | 06 | Update and Remove are buttons on the Info tab |
| Arm positions while someone else is in control | 07 | The robot to report servo positions. The page shows "— µs" |
| Distance chart before you opened the robot | 12 | Server-side sensor history (S3). The chart starts when you open the robot and covers up to 3 minutes |
| Battery | 12 | A battery sensor (hardware checklist in `docs/robots.md`). Shown as "Coming soon" |
| "Every command is logged" (Terminal) | 14, 15 | History (S3). Left out of the texts, because it isn't true yet |
| Terminal confirmation "until you sign in next time" | 15 | Asked once per browser window (sessionStorage), not per sign-in |
| Info: "Last updated … by asmaa" | 16 | The registry to store who ran the update |

## Install dialog

| Feature | Screens | Needs |
|---|---|---|
| How long each step took ("3 min 12 s") | 23, 24 | Step start and end times in `jobs.py` |
| Steps still to come, shown greyed out | 23 | `deploy.py` to list its steps up front. Today steps appear as they start |
| Reboot ticked by default | 22 | Kept opt-in on purpose: adding a robot from another computer shouldn't restart it |

## Phone

| Feature | Screens | Needs |
|---|---|---|
| Bottom tab bar (Fleet, History, Health, Help) | 32, 33 | The other pages. On a phone, the sidebar becomes a top strip with Fleet and Sign out |
| Compact drive pad in one row | 33 | Layout only. The phone shows the full pad, which works |

## Light mode

Light mode follows the computer's setting (`prefers-color-scheme`). There is no switch in the app yet.

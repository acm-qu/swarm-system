# SWARM HUB — UI/UX DESIGN SPECIFICATION
**Design System v1.0 | November 2026**

## 1. Project Overview

Swarm Hub is a web-based robotics operations console for controlling and monitoring a swarm of up to four modified Hiwonder MasterPi robots.

The system runs through a central hub hosted on a Raspberry Pi 5. Users can monitor robot connectivity, control movement and robotic arms, view camera feeds, inspect sensor readings, and manage robots.

The application is being developed using:
- React + TypeScript + Vite
- Tailwind CSS
- shadcn/ui and Radix UI
- WebSockets for live updates
- MJPEG for camera streams

The design must be suitable for a real university robotics project, not a fictional robotics dashboard.

**Current functionality:** Manual robot control, camera viewing, sensors, terminal access, robot management, history, and system health.

**Future functionality:** Jobs, World Map, and AI Planner. These must be visually marked as Coming Soon and must not be presented as operational.

## 2. Overall Design Direction

### Design philosophy

Create a premium, Apple-inspired dark operations console with a sophisticated, understated appearance.

The visual identity combines:

- Apple macOS: Precise typography, refined surfaces, natural spacing, polished interactions.
- Apple Liquid Glass: Selective translucency, subtle background blur, soft material highlights.
- Professional operations software: Dense but organized information, legible live metrics, and clear operational controls.

The interface should feel like a professionally designed native desktop application.

### Aesthetic keywords

Midnight Slate, warm amber, graphite, frosted glass, minimal, polished, technical, calm, precise, tactile, premium.

### Avoid

- Generic AI-generated dashboard aesthetics
- Purple or cyan gradients
- Neon borders and excessive glowing elements
- Futuristic or science-fiction fonts
- Excessively rounded cards
- Decorative charts without functional meaning
- Large empty hero sections
- Random icons and invented features
- Glass effects that reduce readability
- Using amber on every component indiscriminately

The UI must look intentionally designed rather than assembled from unrelated dashboard components.

---

## 3. Color Palette

### Primary palette — Midnight Slate

| Token | Hex | Usage |
|---|---|---|
| `background` | `#0D1117` | Main application background |
| `surface` | `#161D26` | Standard cards and panels |
| `surface-raised` | `#202A35` | Elevated controls, hover surfaces |
| `surface-deep` | `#111821` | Camera frames, drive surfaces |
| `border` | `#27313D` | Default panel borders |
| `border-strong` | `#36414E` | Active panel outlines and separators |
| `text-primary` | `#E8EDF2` | Main text |
| `text-secondary` | `#9AA9B8` | Supporting information |
| `text-muted` | `#7F95AA` | Tertiary text and metadata |

The background should be predominantly dark charcoal with a subtle cool undertone.

Do not use pure black for the entire interface.

### Primary accent — Warm Amber

**Accent color: `#E8AC65`**

This is the defining brand accent.

Suggested supporting tokens:

| Token | Value | Usage |
|---|---|---|
| `accent` | `#E8AC65` | Primary interactive elements |
| `accent-hover` | `#F0BC80` | Hover states |
| `accent-pressed` | `#D9954E` | Pressed states |
| `accent-soft` | `rgba(232,172,101,0.12)` | Selected navigation backgrounds |
| `accent-border` | `rgba(232,172,101,0.35)` | Selected outlines |
| `accent-text` | `#0D1117` | Text on solid amber buttons |

### Amber distribution

Amber should be visually recognizable throughout the interface, not restricted to a few tiny icons.

Use it for:
- Active navigation
- Primary buttons
- Selected robot cards
- Active tabs
- Focus indicators
- Selected control states
- Selected glass surfaces
- Small progress indicators and relevant highlights

Selected navigation items and primary controls may have larger amber-filled areas.

However, maintain a dark overall interface and preserve sufficient contrast for operational information.

Do not turn every panel orange.

### Semantic colors

These colors communicate operational states and must remain separate from decorative accent usage.

| State | Color |
|---|---|
| Connected | `#22C55E` |
| Unresponsive / Warning | `#F59E0B` |
| Offline | `#94A3B8` |
| Working / Information | `#3B82F6` |
| Emergency Stop | `#EF4444` |

Use semantic colors only when their meaning is relevant.

Every status must include a text label and an icon. Never communicate status through color alone.

**Safety rule:** Red is reserved for Stop, Stop All, and their directly related emergency states. Do not use red for ordinary decorative elements.

---

## 4. Typography

### Primary font

**SF Pro — Apple San Francisco**

Use SF Pro as the visual typography reference.

For implementation, use an appropriately licensed SF Pro installation where permitted. Otherwise use a native system font stack or Helvetica Neue as a fallback.

Recommended CSS stack:

```css
font-family:
  -apple-system,
  BlinkMacSystemFont,
  "Helvetica Neue",
  Arial,
  sans-serif;
```

### Typography scale

| Style | Size | Weight | Usage |
|---|---|---|---|
| Display | 32–34px | 600 | Major screen titles where needed |
| Page title | 26–28px | 600 | Fleet, History, Health |
| Section heading | 18–20px | 600 | Panel headings |
| Subheading | 16–17px | 500 | Robot names and grouped controls |
| Body | 14–15px | 400 | Descriptions, content |
| Button | 14–15px | 500 | Interactive actions |
| Caption | 12–13px | 400 | Supporting metadata |
| Telemetry | 24–32px | 500–600 | Sensor values |

### Typography rules

- Prefer regular and medium weights.
- Use semibold sparingly for hierarchy.
- Avoid excessively bold typography.
- Avoid uppercase text everywhere.
- Do not use oversized dashboard headings.
- Use natural letter spacing.
- Use tabular numbers for live telemetry values.
- Use a restrained monospace font for terminal commands, hostnames, and technical identifiers.

Suitable monospace choices:
- SF Mono, where licensed
- IBM Plex Mono
- A system monospace fallback

Never use Orbitron, futuristic display fonts, or decorative AI-looking typography.

---

## 5. Glassmorphism

### Material philosophy

Use restrained Apple-inspired glassmorphism.

The glass should feel like a real translucent material rather than a colored rectangle with a bright border.

### Where glass should appear

Apply glass effects to:

1. Permanent sidebar
2. Top navigation
3. Selected secondary panels
4. Floating menus and popovers
5. Dropdowns and overlays
6. Selected navigation states

### Where glass should NOT dominate

Use darker, more solid surfaces for:

- Live camera
- Drive controls
- Emergency actions
- Terminal
- Dense sensor readouts
- Critical alerts

### Suggested CSS

```css
.glass-panel {
  background: rgba(22, 29, 38, 0.84);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);

  border: 1px solid rgba(255, 255, 255, 0.07);

  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.glass-selected {
  background: rgba(232, 172, 101, 0.14);
  border: 1px solid rgba(232, 172, 101, 0.35);
}
```

These values are starting design tokens, not rigid requirements.

### Glass rules

- Blur generally 16–24px.
- Keep transparency subtle.
- Use soft highlights and realistic layering.
- Avoid bright glowing borders.
- Do not place decorative orange gradients behind every card.
- Keep the camera unobstructed.
- Ensure readable fallback surfaces when backdrop blur is unsupported.

---

## 6. Spacing, Geometry and Layout

### Spacing system

Use a consistent 4px-based spacing scale.

Recommended values:

- 4px — very small gaps
- 8px — compact internal spacing
- 12px — related controls
- 16px — standard component padding
- 20px — card padding
- 24px — section spacing
- 32px — larger layout separation

### Border radii

| Component | Radius |
|---|---|
| Small controls | 8px |
| Buttons and inputs | 10–12px |
| Standard cards | 12–16px |
| Large panels | 16px |
| Dialogs | 16–20px |
| Status pills | Fully rounded |

Avoid excessive pill-shaped cards.

### Layout

- Desktop-first, targeting 1280px width.
- Responsive tablet layout.
- Mobile must retain robot visibility, camera access, and working Stop controls.
- Permanent desktop sidebar.
- Persistent top bar.
- Stop All must remain visible on every authenticated screen.
- Keep visual hierarchy consistent across all pages.

---

## 7. Component Library

Use Tailwind CSS and shadcn/ui as the foundation.

### Buttons

**Primary**
- Solid amber background
- Dark text
- Medium weight
- 10–12px radius
- Subtle hover and pressed states

**Secondary**
- Dark raised surface
- Thin neutral border
- Light text

**Tertiary**
- Minimal or transparent background
- Neutral icon/text
- Appropriate hover feedback

**Danger**
- Solid red background
- White text
- Clear Stop icon
- Never translucent
- Never visually confused with other actions

### Cards

- Midnight Slate surfaces
- Subtle borders
- Consistent internal padding
- Restrained shadows
- Clear headings and data hierarchy
- Selected cards may use amber outlines or soft amber backgrounds

### Status badges

Use consistent words:

- Connected
- Unresponsive
- Offline
- Working
- Moving
- Controlled by [name]

Working should include the current step when available.

Moving should have a subtle motion indicator.

### Inputs

- Dark surfaces
- Visible labels
- Thin borders
- Amber focus state
- Clear validation messages
- Accessible keyboard focus

### Icons

Use Lucide icons with consistent stroke weights.

Avoid mixing filled, outlined, 3D, and decorative icon systems.

### Motion

- Subtle transitions around 150–250ms
- No bouncing panels
- No unnecessary continuous animations
- Respect reduced-motion preferences
- Moving and Working indicators may animate when useful
- Emergency actions must respond immediately

---

## 8. Navigation Architecture

### Main navigation

- Fleet
- History
- Health
- Help

### Coming Soon

- Jobs
- World
- Planner

These should be clearly labeled and disabled or informational.

Do not invent operational screens for future functionality.

### Persistent top bar

Must include:

- Swarm Hub identity
- Hub connection status
- Online robot count
- Signed-in user
- Stop All

If the hub becomes unreachable, the interface must visibly communicate that live information is stale.

---

## 9. Screens to Design

### A. Sign In

- Minimal, professional authentication interface
- Midnight Slate background
- Restrained amber branding
- Clear form labels
- Username and password
- Sign-in action
- Authentication error handling

Do not invent password recovery or account-registration features without confirmation.

### B. Fleet

- Up to four robots
- Robot name and hostname
- Connectivity status
- Controller ownership
- Last seen
- Latency
- Sensor summary
- Capability indicators
- Optional camera preview
- Last event
- Stop, Open, and Ping actions
- Add Robot
- Empty state

Avoid the original crowded table layout.

### C. Robot Cockpit

**Retain two separate layout options for team review.**

**Option 1 — Dedicated Cockpit**

A full robot-detail page prioritizing the camera and manual controls.

**Option 2 — Split Fleet**

Robot list on the left, selected robot's cockpit on the right.

Both must share the same design system and functional components.

Do not select a winner yet.

Both layouts must support:

- Live camera and drive controls simultaneously
- Control ownership
- Take/Release control
- Individual Stop
- Speed slider
- Keyboard movement
- Six drive directions
- Arm controls
- Sensors
- Terminal
- Robot information
- Robot activity history

The robot cockpit must clearly show when another user holds the control lock.

Do not invent autonomous control modes for the current phase.

### D. History

A professional event-log interface.

Include:

- Timestamp
- Robot
- User
- Event
- Event details
- Filters for relevant event types
- Clear empty states
- Connection and control events
- Stop actions
- Terminal and installation activity

History is retained for 90 days.

### E. Health

Include hub diagnostics:

- CPU temperature
- CPU load
- Memory
- Disk
- Uptime

Robot diagnostics:

- Latency
- Connection status
- Reconnect count in the last 24 hours

Sensor history may support compact charts based on seven-day retention.

Do not fabricate battery values or temperature sensors that are not actually available.

### F. Help

Short, accessible help articles for:

- Getting started
- Connecting a robot
- Manual driving
- Control ownership
- Sensors
- Troubleshooting
- Emergency stopping

Provide contextual help access from relevant panels.

### G. Robot Management Dialogs

Design:

- Add Robot
- Update Robot
- Remove Robot
- Installation progress
- Confirmation dialogs

Show installation progress step by step with clear success/failure states.

Risky operations must require confirmation.

Do not invent unsupported robot configuration fields.

---

## 10. Critical Safety Requirements

These requirements override visual preferences.

1. Stop All must remain accessible on every authenticated screen.
2. Stop All must always be visually distinct and red.
3. Individual Stop controls must remain available.
4. A robot can only have one active controller at a time.
5. Other users may observe but cannot issue drive/arm commands while another user holds control.
6. Anyone may always press Stop.
7. The interface must distinguish connectivity from control ownership.
8. Stale data must visibly appear stale.
9. Hub disconnection must be obvious.
10. Dangerous actions require confirmation where specified.
11. Keyboard controls must be supported.
12. Critical information must never rely on color alone.
13. Camera and drive controls must be usable simultaneously.

The backend handles watchdog timeouts and command limits. The interface must not imply that frontend visuals alone enforce safety.

---

## 11. Screenshot Generation Instructions

Generate high-fidelity desktop UI screenshots suitable for later reconstruction in Figma.

### Requirements

- Use the approved Midnight Slate + Amber design system.
- Follow the original Swarm Hub interface brief.
- Maintain consistent typography, spacing, borders, radii, and glass materials.
- Use realistic but clearly illustrative robot data.
- Prefer functional density over decorative empty space.
- Preserve the actual features and constraints.
- Make every screen feel like part of the same application.

### Deliverables

Create visual designs for:

1. Sign In
2. History
3. Health
4. Help
5. Add Robot dialog
6. Update Robot dialog
7. Remove Robot confirmation
8. Installation progress
9. Dedicated Cockpit — Option 1
10. Split Fleet Cockpit — Option 2

Preserve the previously explored Fleet screen as the reference for further refinement.

### Important

Do not regenerate already-approved screens unless specifically requested.

Do not invent:
- Autonomous missions in Phase 0/1
- Unsupported sensors
- Robot capabilities
- Unspecified user permissions
- New navigation sections
- Additional robot hardware

If the specification is ambiguous, ask before introducing new functionality.

## 12. Final Design Quality Checklist

Before presenting each screenshot, verify:

- Does it look like a real, professionally designed robotics application?
- Does it follow Midnight Slate and Amber consistently?
- Is the typography understated and natural?
- Are glass effects restrained and purposeful?
- Are operational states understandable?
- Is Stop All unmistakable?
- Is the information hierarchy clear?
- Are all displayed features supported by the project brief?
- Is the layout realistic for implementation in React and shadcn/ui?
- Does it remain consistent with previously approved screens?

**Overall goal:** A distinctive, polished, Apple-inspired robotics operations console with functional clarity, carefully distributed amber accents, sophisticated dark materials, and reliable safety-oriented interactions.

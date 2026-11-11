"""Builds the Swarm Hub design mockups as self-contained HTML, one file per screen.

Rebuilt from the approved PNG screenshots (design/swarm-hub-screens-v2.zip), robot view "Set A":
the robot list can be hidden and shown (screens 06 and 09). The older split view is left out.
Every screen also has a phone version (phone-01 to phone-31, 390 px wide); see the phone section.

Each file has its CSS inlined and icons as inline SVG, so it opens on its own and imports into Figma.
Fonts: Inter (stand-in for SF Pro) and IBM Plex Mono. Run from anywhere:

    python design/html/build.py

Icons are Lucide (lucide-static 0.460.0), cached in _icons/.
"""

import html
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ICONS = HERE / "_icons"

# ---------------------------------------------------------------- tokens and styles

CSS = r"""
:root{
  --bg:#0D1117; --sidebar:#10161E; --topbar:#121922; --surface:#161D26; --surface-raised:#202A35;
  --surface-deep:#111821; --border:#27313D; --border-strong:#36414E;
  --text:#E8EDF2; --text-2:#9AA9B8; --text-3:#7F95AA;
  --accent:#E8AC65; --accent-hover:#F0BC80; --accent-text:#0D1117;
  --accent-soft:rgba(232,172,101,.12); --accent-border:rgba(232,172,101,.35);
  --ok:#22C55E; --ok-text:#4ADE80; --ok-bg:rgba(34,197,94,.12); --ok-border:rgba(34,197,94,.35);
  --warn:#F59E0B; --warn-text:#FBBF24; --warn-bg:rgba(245,158,11,.13); --warn-border:rgba(245,158,11,.45);
  --off:#94A3B8; --off-bg:rgba(148,163,184,.10); --off-border:rgba(148,163,184,.28);
  --info:#3B82F6; --info-text:#93C5FD; --info-bg:rgba(59,130,246,.14); --info-border:rgba(59,130,246,.45);
  --stop:#EF4444; --stop-text:#FFFFFF; --stop-deep:#DC2626; --stop-bg:rgba(239,68,68,.12); --stop-border:rgba(239,68,68,.45);
  --you-bg:#E8EDF2; --you-text:#0D1117;
  --overlay:rgba(5,8,12,.62);
}
[data-theme=light]{
  --bg:#F0F2F5; --sidebar:#F7F8FA; --topbar:#FBFBFC; --surface:#FFFFFF; --surface-raised:#F3F5F7;
  --surface-deep:#E9EDF1; --border:#E1E5EA; --border-strong:#CDD3DA;
  --text:#1B2430; --text-2:#5B6876; --text-3:#7A8796;
  --accent:#E8AC65; --accent-hover:#F0BC80; --accent-text:#1B2430;
  --accent-soft:rgba(232,172,101,.20); --accent-border:rgba(217,149,78,.55);
  --ok:#16A34A; --ok-text:#15803D; --ok-bg:rgba(22,163,74,.10); --ok-border:rgba(22,163,74,.35);
  --warn:#D97706; --warn-text:#B45309; --warn-bg:rgba(245,158,11,.14); --warn-border:rgba(217,119,6,.45);
  --off:#64748B; --off-bg:rgba(100,116,139,.08); --off-border:rgba(100,116,139,.30);
  --info:#2563EB; --info-text:#1D4ED8; --info-bg:rgba(37,99,235,.10); --info-border:rgba(37,99,235,.40);
  --stop:#DC2626; --stop-deep:#B91C1C;
  --you-bg:#1B2430; --you-text:#FFFFFF;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:var(--bg)}
body{font-family:-apple-system,BlinkMacSystemFont,"Inter","Helvetica Neue",Arial,sans-serif;color:var(--text);
  font-size:14px;line-height:1.4;-webkit-font-smoothing:antialiased}
.mono{font-family:"IBM Plex Mono","SF Mono",ui-monospace,monospace}
.num{font-variant-numeric:tabular-nums;font-feature-settings:"tnum"}
.muted{color:var(--text-2)} .faint{color:var(--text-3)}
svg.i{display:inline-block;flex:none;vertical-align:middle}
.row{display:flex;align-items:center} .col{display:flex;flex-direction:column}
.gap4{gap:4px}.gap6{gap:6px}.gap8{gap:8px}.gap10{gap:10px}.gap12{gap:12px}.gap16{gap:16px}.gap20{gap:20px}
.grow{flex:1;min-width:0} .between{justify-content:space-between}

/* app frame */
.app{display:flex;width:1440px;min-height:900px;background:var(--bg);position:relative}
.side{width:232px;flex:none;background:var(--sidebar);border-right:1px solid var(--border);display:flex;flex-direction:column;padding:16px 14px}
.brand{display:flex;align-items:center;gap:11px;padding:4px 6px 18px}
.logo{color:var(--text);width:32px;height:32px;border-radius:9px;background:var(--surface-raised);border:1px solid var(--border-strong);display:flex;align-items:center;justify-content:center}
.brand b{font-size:16px;font-weight:600;display:block;line-height:1.2}
.brand span{font-size:12px;color:var(--text-2)}
.nav a{display:flex;align-items:center;gap:12px;height:38px;padding:0 12px;border-radius:9px;color:var(--text-2);font-size:14.5px;text-decoration:none;position:relative;margin-bottom:2px}
.nav a.on{background:var(--accent-soft);color:var(--text)}
.nav a.on svg{color:var(--accent)}
.nav a.on:before{content:"";position:absolute;left:-14px;top:9px;width:3px;height:20px;border-radius:2px;background:var(--accent)}
.nav a.soon{opacity:.55}
.nav .tag{margin-left:auto;font-size:11.5px;border:1px solid var(--border-strong);border-radius:999px;padding:1px 7px;color:var(--text-2)}
.navsep{height:1px;background:var(--border);margin:12px 6px}
.me{margin-top:auto;border:1px solid var(--border);background:var(--surface);border-radius:12px;padding:10px;display:flex;gap:10px;align-items:center}
.me b{font-weight:500;font-size:13.5px;display:block} .me span{font-size:12px;color:var(--text-2)}
.signout{display:flex;align-items:center;gap:10px;color:var(--text-2);padding:16px 10px 4px;font-size:14px}
.main{flex:1;min-width:0;display:flex;flex-direction:column}
.top{height:64px;flex:none;background:var(--topbar);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 12px 0 28px;gap:14px}
.crumb{display:flex;align-items:center;gap:8px;font-size:17px;font-weight:500}
.crumb .up{color:var(--text-3);font-weight:400}
.chip{display:flex;align-items:center;gap:7px;height:30px;padding:0 11px;border:1px solid var(--border);border-radius:999px;font-size:12.5px;color:var(--text-2);white-space:nowrap}
.dot{width:7px;height:7px;border-radius:50%;background:var(--ok);flex:none}
.vsep{width:1px;height:26px;background:var(--border)}
.bell{position:relative;color:var(--text-2);display:flex}
.bell i{position:absolute;top:-6px;right:-7px;font-style:normal;font-size:10px;background:var(--surface-raised);border:1px solid var(--border-strong);color:var(--text);border-radius:999px;min-width:15px;height:15px;display:flex;align-items:center;justify-content:center}
.content{padding:24px 28px 28px;flex:1}

/* avatars, monograms */
.av{width:22px;height:22px;border-radius:50%;background:var(--surface-raised);border:1px solid var(--border-strong);font-size:10px;font-weight:600;display:inline-flex;align-items:center;justify-content:center;flex:none;color:var(--text)}
.av.lg{width:30px;height:30px;font-size:11.5px}
.mg{width:36px;height:36px;border-radius:10px;border:1px solid var(--border-strong);background:var(--surface-deep);font-size:13px;font-weight:600;display:flex;align-items:center;justify-content:center;flex:none;letter-spacing:.02em}
.mg.sm{width:24px;height:24px;border-radius:7px;font-size:10.5px}
.mg.lg{width:46px;height:46px;border-radius:12px;font-size:15px}

/* pills */
.pill{display:inline-flex;align-items:center;gap:6px;height:26px;padding:0 10px;border-radius:999px;border:1px solid;font-size:13px;font-weight:500;white-space:nowrap}
.pill.sm{height:22px;padding:0 8px;font-size:12px;gap:5px}
.p-ok{color:var(--ok-text);background:var(--ok-bg);border-color:var(--ok-border)}
.p-warn{color:var(--warn-text);background:var(--warn-bg);border-color:var(--warn-border)}
.p-off{color:var(--off);background:var(--off-bg);border-color:var(--off-border)}
.p-info{color:var(--info-text);background:var(--info-bg);border-color:var(--info-border)}
.p-move{color:#fff;background:var(--info);border-color:var(--info)}
.p-ctl{color:var(--text);background:transparent;border-color:var(--border-strong);padding-left:3px}
.p-you{color:var(--you-text);background:var(--you-bg);border-color:var(--you-bg);padding-left:3px}
.p-you .av{background:var(--you-text);color:var(--you-bg);border-color:var(--you-text)}
.p-nobody{color:var(--text-2);background:transparent;border-color:var(--border-strong);border-style:dashed}
.p-fail{color:#FCA5A5;background:var(--stop-bg);border-color:var(--stop-border)}
.bars{display:inline-flex;gap:2px;align-items:center;margin-left:2px}
.bars i{width:3px;height:10px;border-radius:1px;background:currentColor;display:block;opacity:.9}
.bars i:nth-child(2){opacity:.7}.bars i:nth-child(3){opacity:.5}

/* buttons */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;height:36px;padding:0 14px;border-radius:10px;font-size:14px;font-weight:500;border:1px solid var(--border-strong);background:var(--surface-raised);color:var(--text);white-space:nowrap}
.btn.sm{height:30px;padding:0 10px;font-size:13px;border-radius:9px}
.btn.icon{width:36px;padding:0}
.btn.sm.icon{width:30px}
.btn.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-text)}
.btn.ghost{background:transparent;border-color:transparent;color:var(--text-2)}
.btn.stop{background:var(--stop);border-color:var(--stop);color:#fff;font-weight:600}
.btn.stop-off{background:transparent;border-color:var(--border);color:var(--text-3)}
.btn.danger-soft{background:var(--stop-bg);border-color:var(--stop-border);color:#FCA5A5}
.btn.danger{background:var(--stop-deep);border-color:var(--stop-deep);color:#fff}
.btn.dis{opacity:.45}
.kbd{font-family:"IBM Plex Mono",monospace;font-size:11px;padding:1px 6px;border-radius:5px;border:1px solid rgba(255,255,255,.35);background:rgba(0,0,0,.18);font-weight:500}
.kbd.n{border-color:var(--border-strong);background:var(--surface-deep);color:var(--text-2)}
.stopall{height:42px;padding:0 14px;font-size:15.5px;box-shadow:0 4px 18px rgba(239,68,68,.35)}

/* cards */
.card{background:var(--surface);border:1px solid var(--border);border-radius:14px}
.card-h{display:flex;align-items:center;gap:10px;padding:16px 18px;border-bottom:1px solid var(--border)}
.card-h h3{font-size:16px;font-weight:600}
.card-b{padding:16px 18px}
.help{width:20px;height:20px;border-radius:50%;border:1px solid var(--border-strong);color:var(--text-2);display:inline-flex;align-items:center;justify-content:center;flex:none}
.note{display:flex;gap:10px;align-items:flex-start;border-radius:10px;padding:11px 13px;font-size:13.5px;border:1px solid var(--border);background:var(--surface-deep);color:var(--text-2)}
.note.good{color:var(--text);background:var(--ok-bg);border-color:var(--ok-border)} .note.good svg{color:var(--ok-text)}
.note.warn{color:var(--text);background:var(--warn-bg);border-color:var(--warn-border)} .note.warn svg{color:var(--warn-text)}
.note.bad{color:var(--text);background:var(--stop-bg);border-color:var(--stop-border)} .note.bad svg{color:#F87171}
.note.info{color:var(--text);background:var(--info-bg);border-color:var(--info-border)} .note.info svg{color:var(--info-text)}
.h1{font-size:19px;font-weight:600} .sub{font-size:13px;color:var(--text-2);margin-top:3px}
.lbl{font-size:12.5px;color:var(--text-2)}

/* robot view */
.rhead{display:flex;align-items:center;gap:12px;margin-bottom:16px}
.rhead .name{font-size:21px;font-weight:600;line-height:1.15}
.rhead .meta{font-size:12.5px;color:var(--text-2);margin-top:3px;white-space:nowrap}
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--border);margin-bottom:18px}
.tab{display:flex;align-items:center;gap:7px;height:42px;padding:0 11px;color:var(--text-2);font-size:14.5px;position:relative}
.tab.on{color:var(--text)} .tab.on svg{color:var(--accent)}
.tab.on:after{content:"";position:absolute;left:6px;right:6px;bottom:-1px;height:2px;background:var(--accent);border-radius:2px}
.cam{position:relative;border-radius:14px;overflow:hidden;border:1px solid var(--border);background:var(--surface-deep)}
.cam svg.scene{display:block;width:100%;height:100%}
.cam .ov{position:absolute;display:flex;align-items:center;gap:6px;background:rgba(10,13,18,.78);border:1px solid rgba(255,255,255,.08);border-radius:9px;color:#E8EDF2;font-size:13px;padding:0 10px;height:30px}
.seg{display:flex;padding:3px;gap:2px;background:rgba(10,13,18,.82);border:1px solid rgba(255,255,255,.08);border-radius:10px}
.seg span{padding:5px 10px;border-radius:7px;font-size:13px;color:#C9D2DB}
.seg span.on{background:var(--accent);color:#0D1117;font-weight:500}
.strip{display:flex;border:1px solid var(--border);border-radius:14px;background:var(--surface);margin-top:14px}
.strip>div{padding:14px 16px;border-right:1px solid var(--border)} .strip>div:last-child{border-right:0}
.big{font-size:24px;font-weight:500} .big small{font-size:13px;color:var(--text-2);font-weight:400;margin-left:2px}
.xyz{display:flex;gap:16px} .xyz>div{display:flex;flex-direction:column} .xyz .lbl{font-size:11.5px}
.pad{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.key{position:relative;height:74px;border-radius:11px;border:1px solid var(--border-strong);background:var(--surface-raised);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;color:var(--text-2);font-size:12.5px}
.key svg{color:var(--text)}
.key .kl{position:absolute;top:7px;left:7px;font-family:"IBM Plex Mono",monospace;font-size:10.5px;border:1px solid var(--border-strong);border-radius:5px;padding:0 5px;color:var(--text-2);background:var(--surface-deep)}
.key.held{background:var(--accent);border-color:var(--accent);color:#0D1117;font-weight:500;box-shadow:0 0 0 4px var(--accent-soft)}
.key.held svg{color:#0D1117} .key.held .kl{background:rgba(0,0,0,.12);border-color:rgba(0,0,0,.25);color:#0D1117}
.key.stopk{background:var(--stop);border-color:var(--stop);color:#fff;font-weight:600}
.key.stopk svg{color:#fff}
.key.ro{background:transparent;border-style:dashed;color:var(--text-3)} .key.ro svg{color:var(--text-3)}
.slider{position:relative;height:16px;display:flex;align-items:center}
.slider .tr{height:4px;border-radius:2px;background:var(--border-strong);width:100%}
.slider .fill{position:absolute;left:0;height:4px;border-radius:2px;background:var(--accent)}
.slider .th{position:absolute;width:18px;height:18px;border-radius:50%;background:#F4F1EC;border:3px solid var(--accent);transform:translateX(-9px)}
.slider.ro .th{background:var(--surface);border:2px solid var(--text-3)} .slider.ro .fill{display:none}
.sending{border:1px solid var(--border);background:var(--surface-deep);border-radius:9px;padding:10px 13px;font-family:"IBM Plex Mono",monospace;font-size:12.5px;color:var(--text-2)}
.sending b{color:var(--text);font-weight:500}
.ctl{padding:14px 16px}
.list{display:flex;flex-direction:column;gap:8px}
.rrow{border:1px solid var(--border);border-radius:12px;background:var(--surface);padding:11px 12px}
.rrow.sel{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}
.tbl{width:100%;border-collapse:collapse}
.tbl th{text-align:left;font-weight:400;color:var(--text-2);font-size:13px;padding:11px 14px;border-bottom:1px solid var(--border)}
.tbl td{padding:12px 14px;border-bottom:1px solid var(--border);font-size:14px;vertical-align:middle}
.tbl tr:last-child td{border-bottom:0}
.code{font-family:"IBM Plex Mono",monospace;font-size:12.5px;background:var(--surface-deep);border:1px solid var(--border);border-radius:6px;padding:1px 6px}
.field{display:flex;flex-direction:column;gap:7px}
.field label{font-size:14px;font-weight:500}
.inp{height:42px;border:1px solid var(--border-strong);border-radius:10px;background:var(--surface-deep);display:flex;align-items:center;padding:0 13px;font-size:14.5px;color:var(--text);gap:10px}
.inp.focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.inp.err{border-color:var(--warn);box-shadow:0 0 0 3px var(--warn-bg)}
.inp .ph{color:var(--text-3)}
.caret{width:2px;height:18px;background:var(--accent);display:inline-block}
.cb{width:20px;height:20px;border-radius:6px;border:1px solid var(--border-strong);background:var(--surface-deep);display:flex;align-items:center;justify-content:center;flex:none}
.cb.on{background:var(--accent);border-color:var(--accent);color:#0D1117}

/* dialogs */
.scrim{position:absolute;inset:0;background:var(--overlay);display:flex;align-items:center;justify-content:center;z-index:5}
.dim{filter:blur(2.5px);opacity:.75}
.dlg{width:520px;background:var(--surface);border:1px solid var(--border-strong);border-radius:18px;box-shadow:0 24px 70px rgba(0,0,0,.55);overflow:hidden}
.dlg.danger{border-top:3px solid var(--stop)}
.dlg-h{display:flex;gap:14px;align-items:flex-start;padding:22px 22px 0}
.dlg-h h2{font-size:18px;font-weight:600}
.dlg-b{padding:16px 22px 20px}
.dlg-f{display:flex;justify-content:flex-end;gap:10px;align-items:center;padding:14px 22px;border-top:1px solid var(--border)}
.dicon{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex:none;background:var(--stop-bg);border:1px solid var(--stop-border);color:#F87171}
.step{display:flex;gap:12px;align-items:flex-start;padding:7px 0}
.sicon{width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex:none;margin-top:1px}
.s-ok{background:var(--ok-bg);border:1px solid var(--ok-border);color:var(--ok-text)}
.s-run{border:2px solid var(--info);border-right-color:transparent}
.s-todo{border:1px dashed var(--border-strong)}
.s-fail{background:var(--stop-bg);border:1px solid var(--stop-border);color:#F87171}
.slog{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--text-2);background:var(--surface-deep);border:1px solid var(--border);border-radius:8px;padding:8px 10px;margin-top:7px}

"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&'
         'family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">')

# ---------------------------------------------------------------- helpers

_icon_cache = {}


def icon(name, size=16, stroke=1.75, color=None, cls=""):
    if name not in _icon_cache:
        raw = (ICONS / f"{name}.svg").read_text(encoding="utf-8")
        _icon_cache[name] = re.search(r"<svg[^>]*>(.*)</svg>", raw, re.S).group(1).strip()
    style = f' style="color:{color}"' if color else ""
    return (f'<svg class="i {cls}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round"{style}>'
            f'{_icon_cache[name]}</svg>')


def esc(s):
    return html.escape(s, quote=False)


LOGO = ('<div class="logo"><svg width="20" height="20" viewBox="0 0 24 24" fill="none">'
        '<path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>'
        '<circle cx="12" cy="12" r="3.2" fill="#E8AC65"/><circle cx="5" cy="5" r="2.2" fill="currentColor"/>'
        '<circle cx="19" cy="5" r="2.2" fill="currentColor"/><circle cx="5" cy="19" r="2.2" fill="currentColor"/>'
        '<circle cx="19" cy="19" r="2.2" fill="currentColor"/></svg></div>')

ROBOTS = {
    "clanker": dict(name="Clanker", mg="CL", host="masterpi-01", ip="192.168.50.11", status="connected",
                    moving=True, ctrl="you", lat="18 ms", seen="seen now", seen_short="Seen now", dist="42",
                    rot=("0.4°", "−1.2°", "87.5°"), spd=("0", "0", "32"), arm=True, gyro=True,
                    event=("driving", "now")),
    "rover": dict(name="Rover", mg="RO", host="masterpi-02", ip="192.168.50.12", status="connected",
                  moving=False, ctrl="sara", lat="24 ms", seen="seen now", seen_short="Seen now", dist="118",
                  rot=("0.1°", "0.3°", "−12.0°"), spd=("0", "0", "0"), arm=True, gyro=True,
                  event=("sara took control", "3 min ago")),
    "scout": dict(name="Scout", mg="SC", host="masterpi-03", ip="192.168.50.13", status="unresponsive",
                  moving=False, ctrl=None, lat="212 ms", seen="seen 6 s ago", seen_short="Seen 6 s ago",
                  dist="76", rot=None, spd=None, arm=False, gyro=False, event=("hub silent 5 s", "6 s ago")),
    "vex": dict(name="Vex", mg="VX", host="masterpi-04", ip="192.168.50.14", status="offline", moving=False,
                ctrl=None, lat="—", seen="seen 3 h ago", seen_short="Seen 3 h ago", dist=None, rot=None,
                spd=None, arm=True, gyro=True, event=("went offline", "3 h ago")),
}


def status_pill(status, sm=False, label=None):
    s = " sm" if sm else ""
    n = 13 if sm else 14
    if status == "connected":
        return f'<span class="pill p-ok{s}">{icon("circle-check", n)}{label or "Connected"}</span>'
    if status == "unresponsive":
        return f'<span class="pill p-warn{s}">{icon("triangle-alert", n)}{label or "Unresponsive"}</span>'
    if status == "offline":
        return f'<span class="pill p-off{s}">{icon("wifi-off", n)}{label or "Offline"}</span>'
    if status == "working":
        return f'<span class="pill p-info{s}">{icon("loader-circle", n)}{label or "Working…"}</span>'
    if status == "done":
        return f'<span class="pill p-ok{s}">{icon("circle-check", n)}Done</span>'
    if status == "failed":
        return f'<span class="pill p-fail{s}">{icon("circle-x", n)}Failed</span>'
    raise ValueError(status)


def moving_pill(sm=False):
    s = " sm" if sm else ""
    return f'<span class="pill p-move{s}">{icon("move", 14)}Moving<span class="bars"><i></i><i></i><i></i></span></span>'


def ctrl_pill(ctrl, sm=False, long=False):
    s = " sm" if sm else ""
    if ctrl == "you":
        return f'<span class="pill p-you{s}"><span class="av">AS</span>{"You are in control" if long else "You"}</span>'
    if ctrl is None:
        return f'<span class="pill p-nobody{s}">{icon("lock-open", 14)}{"Nobody is in control" if long else "Nobody"}</span>'
    txt = f"{ctrl} is in control" if long else f"Controlled by {ctrl}"
    return f'<span class="pill p-ctl{s}"><span class="av">{ctrl[:2].upper()}</span>{txt}{icon("lock", 14)}</span>'


def stopbtn(label="Stop", key=None, cls="", off=False, size=16):
    if off:
        return f'<span class="btn stop-off {cls}">{icon("octagon", size)}{label}</span>'
    k = f'<span class="kbd">{key}</span>' if key else ""
    return f'<span class="btn stop {cls}">{icon("octagon", size)}{label}{k}</span>'


def helpdot():
    return f'<span class="help">{icon("circle-help", 13)}</span>'


# ---------------------------------------------------------------- frame

NAV = [("fleet", "layout-grid", "Fleet"), ("history", "history", "History"), ("health", "activity", "Health"),
       ("help", "circle-help", "Help")]
SOON = [("list-checks", "Jobs"), ("map", "World"), ("workflow", "Planner")]


def sidebar(active):
    items = "".join(f'<a class="{"on" if k == active else ""}">{icon(ic, 18)}{t}</a>' for k, ic, t in NAV)
    soon = "".join(f'<a class="soon">{icon(ic, 18)}{t}<span class="tag">Soon</span></a>' for ic, t in SOON)
    return (f'<aside class="side"><div class="brand">{LOGO}<div><b>Swarm Hub</b><span>Lab hub · Pi 5</span></div></div>'
            f'<nav class="nav">{items}<div class="navsep"></div>{soon}</nav>'
            f'<div class="me"><span class="mg" style="width:34px;height:34px;font-size:12px">AS</span>'
            f'<div><b>asmaa</b><span>Signed in</span></div></div>'
            f'<div class="signout">{icon("log-out", 17)}Sign out</div></aside>')


def topbar(left, online="3 of 4", hub="ok", bell=2):
    if hub == "ok":
        hubchip = '<span class="chip"><span class="dot"></span>Hub connected · <span class="num">18 ms</span></span>'
        rob = (f'<span class="chip" style="border:0;padding:0">{icon("bot", 16)}'
               + (f'<b style="color:var(--text)">{online}</b>&nbsp;robots online' if online != "none" else "No robots yet")
               + "</span>")
    else:
        hubchip = (f'<span class="chip" style="color:var(--warn-text);border-color:var(--warn-border);background:var(--warn-bg)">'
                   f'{icon("triangle-alert", 15)}Can\'t reach the hub · reconnecting…</span>')
        rob = (f'<span class="chip" style="border:0;padding:0;opacity:.75">{icon("bot", 16)}<b>{online}</b>&nbsp;robots online'
               f'<span style="color:var(--warn-text);display:flex;align-items:center;gap:4px;margin-left:6px">'
               f'{icon("clock", 13)}24 s ago</span></span>')
    b = f'<i>{bell}</i>' if bell else ""
    return (f'<header class="top"><div class="crumb">{left}</div><div class="grow"></div>{hubchip}{rob}'
            f'<span class="vsep"></span><span class="bell">{icon("bell", 19)}{b}</span>'
            f'<span class="row gap8" style="font-size:14px"><span class="av lg" style="border:0">AS</span>asmaa</span>'
            f'{stopbtn("Stop all", "Esc Esc", "stopall", size=19)}</header>')


def crumb(*parts):
    out = []
    for p in parts[:-1]:
        out.append(f'<span class="up">{p}</span>{icon("chevron-right", 15, color="var(--text-3)")}')
    out.append(f'<span>{parts[-1]}</span>')
    return "".join(out)


def app(active, top_left, body, online="3 of 4", hub="ok", bell=2, overlay="", height=900):
    inner = f'{sidebar(active)}<div class="main">{topbar(top_left, online, hub, bell)}<div class="content">{body}</div></div>'
    if overlay:
        # Blur only the page body and sidebar; the top bar with Stop all stays sharp.
        inner = (f'<div class="dim" style="display:flex;width:100%">{sidebar(active)}<div style="flex:1"></div></div>'
                 f'<div style="position:absolute;left:232px;right:0;top:0;bottom:0;display:flex;flex-direction:column">'
                 f'{topbar(top_left, online, hub, bell)}<div class="content dim">{body}</div></div>'
                 f'<div class="scrim" style="top:64px;left:0">{overlay}</div>')
    return f'<div class="app" style="min-height:{height}px">{inner}</div>'


# ---------------------------------------------------------------- camera scene

def scene(dark=False, variant=0):
    """A placeholder lab floor with the box to carry and tag stickers. Clearly not a photo."""
    floor_top, floor_bot = ("#3A3F46", "#2A2E33") if dark else ("#5E656E", "#868C94")
    wall = "#2B3036" if dark else "#3E444B"
    box = "#6B7078" if dark else "#B9BDC3"
    side = "#555A61" if dark else "#9DA2A8"
    lines = "".join(f'<line x1="320" y1="150" x2="{x}" y2="480" stroke="#fff" stroke-opacity=".10" stroke-width="1"/>'
                    for x in range(-560, 1220, 70))
    hz = "".join(f'<line x1="0" y1="{y}" x2="640" y2="{y}" stroke="#fff" stroke-opacity=".08"/>'
                 for y in (170, 196, 226, 262, 306, 360, 424))
    bx, by = [(0, 0), (-150, 15), (0, -30)][variant]
    tags = [(250, 345, 26), (430, 300, 22), (330, 405, 30)] if variant != 1 else [(390, 268, 22), (290, 330, 24), (470, 365, 28)]

    def tag(x, y, s):
        q = s / 4
        return (f'<g transform="translate({x},{y})"><rect width="{s}" height="{s*0.62:.1f}" fill="#F2F3F4"/>'
                f'<rect x="{q*0.8:.1f}" y="{q*0.6:.1f}" width="{s-q*1.6:.1f}" height="{s*0.62-q*1.2:.1f}" fill="#1D2126"/>'
                f'<rect x="{q*1.3:.1f}" y="{q*1.0:.1f}" width="{q:.1f}" height="{q*0.7:.1f}" fill="#F2F3F4"/>'
                f'<rect x="{q*2.2:.1f}" y="{q*1.5:.1f}" width="{q*0.9:.1f}" height="{q*0.6:.1f}" fill="#F2F3F4"/></g>')
    return (f'<svg class="scene" viewBox="0 0 640 480" preserveAspectRatio="xMidYMid slice">'
            f'<defs><linearGradient id="fl{variant}{int(dark)}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{floor_top}"/><stop offset="1" stop-color="{floor_bot}"/></linearGradient></defs>'
            f'<rect width="640" height="140" fill="{wall}"/><rect x="80" y="60" width="120" height="80" fill="#fff" fill-opacity=".03"/>'
            f'<rect x="450" y="70" width="190" height="70" fill="#fff" fill-opacity=".03"/>'
            f'<rect y="140" width="640" height="14" fill="#000" fill-opacity=".22"/>'
            f'<rect y="152" width="640" height="328" fill="url(#fl{variant}{int(dark)})"/>{hz}{lines}'
            f'<g transform="translate({bx},{by})"><ellipse cx="370" cy="302" rx="60" ry="10" fill="#000" fill-opacity=".25"/>'
            f'<polygon points="318,232 404,232 420,220 334,220" fill="#D5D8DC" fill-opacity="{.6 if dark else 1}"/>'
            f'<polygon points="404,232 420,220 420,282 404,296" fill="{side}"/>'
            f'<rect x="318" y="232" width="86" height="64" fill="{box}"/>'
            f'<line x1="362" y1="232" x2="356" y2="296" stroke="#000" stroke-opacity=".25"/></g>'
            + "".join(tag(*t) for t in tags) + "</svg>")


def camera(w, quality="high", top=None, dark=False, variant=0, extra=""):
    h = w * 3 // 4
    top = top or '<span style="width:7px;height:7px;border-radius:50%;background:#fff"></span>Live · <span class="num">15 fps</span>'
    q_low, q_high = ("on", "") if quality == "low" else ("", "on")
    return (f'<div class="cam" style="width:{w}px;height:{h}px">{scene(dark, variant)}'
            f'<div class="ov" style="top:12px;left:12px">{top}</div>'
            f'<div class="ov" style="top:12px;right:12px;width:30px;padding:0;justify-content:center">{icon("scan", 16)}</div>'
            f'<div class="seg" style="position:absolute;left:12px;bottom:12px"><span class="{q_low}">Low · 5 fps</span>'
            f'<span class="{q_high}">High · 15 fps</span></div>{extra}</div>')


# ---------------------------------------------------------------- robot view parts

def robot_header(r, robots_button=True, ping_text=True, ctrl_override="keep", moving=None, compact=False):
    rb = (f'<span class="btn sm" style="height:34px">{icon("panel-left", 16)}Robots</span>' if robots_button else "")
    ctrl = r["ctrl"] if ctrl_override == "keep" else ctrl_override
    mv = r["moving"] if moving is None else moving
    pills = status_pill(r["status"], compact) + (moving_pill(compact) if mv else "") + ctrl_pill(ctrl, compact)
    slow = (f' <span style="color:var(--warn-text)">{icon("triangle-alert", 12)} slow</span>'
            if r["status"] == "unresponsive" else "")
    ping = (f'<span class="btn sm" style="height:34px">{icon("radio", 16)}Ping</span>' if ping_text
            else f'<span class="btn sm icon" style="height:34px;width:34px">{icon("radio", 16)}</span>')
    return (f'<div class="rhead">{rb}<span class="mg lg">{r["mg"]}</span>'
            f'<div><div class="name">{r["name"]}</div><div class="meta"><span class="mono">{r["host"]}</span> · '
            f'{r["ip"]} · <span class="num">{r["lat"]}</span>{slow} · {r["seen"]}</div></div>'
            f'<div class="row gap8" style="margin-left:6px">{pills}</div><div class="grow"></div>{ping}'
            f'<span class="btn sm icon" style="height:34px;width:34px">{icon("ellipsis", 16)}</span>'
            f'{stopbtn("Stop" if compact else "Stop " + r["name"], "Space")}</div>')


TABS = [("Drive", "gamepad-2"), ("Arm", "hand"), ("Sensors", "radar"), ("Terminal", "terminal"), ("Info", "info"),
        ("Activity", "history")]


def tabs(active, locked=False):
    out = []
    for t, ic in TABS:
        lock = icon("lock", 13, color="var(--text-3)") if locked and t in ("Drive", "Arm") else ""
        out.append(f'<span class="tab {"on" if t == active else ""}">{icon(ic, 16)}{t}{lock}</span>')
    return f'<div class="tabs">{"".join(out)}</div>'


def strip(r, w):
    fs = 21 if w >= 600 else 17
    if r["rot"] is None:
        stale = f'<span style="color:var(--warn-text);font-size:12px;margin-left:6px">{icon("clock", 12)} 6 s ago</span>'
        return (f'<div class="strip" style="width:{w}px"><div style="width:200px"><div class="lbl row gap6">{icon("radar", 14)}Distance{stale}</div>'
                f'<div class="big num" style="opacity:.6">{r["dist"]}<small>cm</small></div></div>'
                f'<div class="grow"><div class="lbl row gap6">{icon("rotate-3d", 14)}Gyro rotation</div>'
                f'<div style="margin-top:8px;color:var(--text-2)">No gyro on this robot</div></div>'
                f'<div style="width:{w//3}px"><div class="lbl row gap6">{icon("gauge", 14)}Gyro speed</div>'
                f'<div style="margin-top:8px;color:var(--text-2)">—</div></div></div>')
    rx = "".join(f'<div><span class="lbl">{a}</span><span class="big num" style="font-size:{fs}px">{v}</span></div>'
                 for a, v in zip("XYZ", r["rot"]))
    sx = "".join(f'<div><span class="lbl">{a}</span><span class="big num" style="font-size:{fs}px">{v}<small>°/s</small></span></div>'
                 for a, v in zip("XYZ", r["spd"]))
    return (f'<div class="strip" style="width:{w}px"><div style="width:{int(w*.235)}px"><div class="lbl row gap6">{icon("radar", 14)}Distance</div>'
            f'<div class="big num" style="margin-top:6px">{r["dist"]}<small>cm</small></div></div>'
            f'<div class="grow"><div class="lbl row gap6">{icon("rotate-3d", 14)}Gyro rotation</div><div class="xyz" style="margin-top:4px;gap:{12 if fs < 21 else 16}px">{rx}</div></div>'
            f'<div class="grow"><div class="lbl row gap6">{icon("gauge", 14)}Gyro speed</div><div class="xyz" style="margin-top:4px;gap:{12 if fs < 21 else 16}px">{sx}</div></div></div>')


def control_card(state, who="sara"):
    if state == "you":
        return (f'<div class="card ctl"><div class="row gap10">{ctrl_pill("you", long=True)}<div class="grow"></div>'
                f'<span class="btn sm">{icon("lock-open", 15)}Release control</span>{helpdot()}</div>'
                f'<p class="muted" style="margin-top:10px;font-size:13.5px">Others can watch and press Stop. Control frees up 15 seconds after your last command.</p></div>')
    if state == "other":
        return (f'<div class="card ctl"><div class="row gap10">{ctrl_pill(who, long=True)}'
                f'<span class="muted" style="font-size:13.5px;margin-left:6px">You can watch and press Stop.</span><div class="grow"></div>{helpdot()}</div>'
                f'<p class="muted" style="margin-top:10px;font-size:13.5px">Control frees up when the person closes the panel, or 15 seconds after their last command.</p></div>')
    return (f'<div class="card ctl"><div class="row gap10">{ctrl_pill(None, long=True)}<div class="grow"></div>'
            f'<span class="btn sm primary">{icon("gamepad-2", 15)}Take control</span>{helpdot()}</div>'
            f'<p class="muted" style="margin-top:10px;font-size:13.5px">Take control to drive or move the arm. Anyone can always press Stop.</p></div>')


def drive_card(mode="you", lat="18 ms"):
    """mode: you (W held), free (nothing held), ro (someone else in control)."""
    keys = [("Q", "rotate-ccw", "Turn left"), ("W", "arrow-up", "Forward"), ("E", "rotate-cw", "Turn right"),
            ("A", "arrow-left", "Slide left"), (None, None, None), ("D", "arrow-right", "Slide right"),
            ("", "", ""), ("S", "arrow-down", "Back"), ("", "", "")]
    cells = []
    for k, ic, t in keys:
        if k is None:
            cells.append(f'<div class="key stopk"{" style=height:62px" if mode == "ro" else ""}>{icon("octagon", 22)}Stop · Space</div>')
        elif k == "":
            cells.append("<div></div>")
        else:
            cls = "held" if (mode == "you" and k == "W") else ("ro" if mode == "ro" else "")
            hs = ' style="height:62px"' if mode == "ro" else ""   # shorter so the Arm card below fits the screen
            cells.append(f'<div class="key {cls}"{hs}><span class="kl">{k}</span>{icon(ic, 20)}{t}</div>')
    watching = (f'<span class="pill sm p-ctl" style="padding-left:8px">{icon("eye", 13)}Watching</span>' if mode == "ro" else "")
    head = (f'<div class="card-h">{icon("gamepad-2", 18)}<h3>Drive</h3>{helpdot()}<div class="grow"></div>'
            f'<span class="muted row gap6" style="font-size:13px">{icon("radio", 14)}Latency <b class="num" style="color:var(--text);font-weight:500">{lat}</b></span>{watching}</div>')
    pad = f'<div class="pad">{"".join(cells)}</div>'
    if mode == "ro":
        tail = (f'<div class="note" style="margin-top:14px">{icon("lock", 15)}Read-only while sara is in control. The red Stop still works.</div>')
        return f'<div class="card">{head}<div class="card-b">{pad}{tail}</div></div>'
    send = ("Sending: <b>Forward +0.40</b> · Strafe 0.00 · Rotate 0.00" if mode == "you"
            else "Sending: Forward 0.00 · Strafe 0.00 · Rotate 0.00")
    speed = (f'<div class="row between" style="margin-top:18px"><b style="font-weight:500">Speed</b><b class="num" style="font-weight:500">40%</b></div>'
             f'<div class="slider" style="margin-top:10px"><div class="tr"></div><div class="fill" style="width:33%"></div><div class="th" style="left:33%"></div></div>'
             f'<div class="row between faint" style="font-size:12.5px;margin-top:6px"><span>10%</span><span>100%</span></div>'
             f'<div class="sending" style="margin-top:12px">{send}</div>'
             f'<p class="muted" style="font-size:13px;margin-top:12px">Hold a button or key to move; let go and the robot stops.</p>')
    return f'<div class="card">{head}<div class="card-b">{pad}{speed}</div></div>'


ARM = [("Base", 1500), ("Shoulder", 1320), ("Elbow", 1710), ("Wrist", 1450), ("Gripper", 1100)]


def arm_card(mode="you", stack=False):
    head = f'<div class="card-h">{icon("hand", 18)}<h3>Arm</h3>{helpdot()}<div class="grow"></div>'
    if mode == "watch":
        cells = "".join(f'<div class="grow"><div class="lbl" style="font-size:13px;color:var(--text)">{n}</div>'
                        f'<div class="faint num" style="font-size:12.5px;margin:4px 0 8px">— µs</div>'
                        f'<div class="slider ro"><div class="tr"></div><div class="th" style="left:0"></div></div></div>' for n, _ in ARM)
        return (f'<div class="card">{head}<span class="pill sm p-ctl" style="padding-left:8px">{icon("eye", 13)}Watching</span></div>'
                f'<div class="card-b"><div class="row gap12">{cells}</div><p class="muted" style="font-size:13px;margin-top:12px">Read-only. The robot doesn\'t report arm positions.</p></div></div>')
    if mode == "none":
        rows = "".join(f'<div class="row gap16" style="opacity:.35;margin-top:10px"><span style="width:90px" class="muted">{n}</span>'
                       f'<div class="slider ro grow"><div class="tr"></div><div class="th" style="left:50%"></div></div><span class="faint" style="width:40px;text-align:right">—</span></div>' for n, _ in ARM)
        return (f'<div class="card">{head}</div><div class="card-b" style="text-align:center;padding-top:40px">'
                f'<div class="mg lg" style="margin:0 auto 18px">{icon("hand", 20)}</div><div style="font-size:16.5px;font-weight:500">This robot has no arm board connected.</div>'
                f'<p class="muted" style="margin:8px auto 30px;max-width:360px">The arm controls turn on by themselves when the robot reports an arm board.</p>'
                f'<div style="text-align:left">{rows}</div></div></div>')
    rows = []
    for n, v in ARM:
        p = (v - 500) / 2000 * 100
        rows.append(f'<div style="margin-bottom:14px"><div class="row between"><span style="font-size:14px">{n}</span>'
                    f'<span class="row gap16"><span class="faint num" style="font-size:12.5px">500–2500</span>'
                    f'<b class="mono num" style="font-weight:500;width:64px;text-align:right">{v} µs</b></span></div>'
                    f'<div class="slider" style="margin-top:8px"><div class="tr"></div><div class="fill" style="width:{p:.1f}%"></div>'
                    f'<div class="th" style="left:{p:.1f}%"></div></div></div>')
    release = f'<span class="btn danger-soft">{icon("hand", 16)}Release (go limp)</span>'
    if stack:   # phone: full-width buttons, no Close (the tab row switches away)
        btns = f'<div class="col gap8" style="margin-top:6px">{stopbtn("Stop (arm holds)", cls="bigstop")}{release}</div>'
    else:
        btns = (f'<div class="row gap10" style="margin-top:6px">{stopbtn("Stop (arm holds)")}{release}'
                f'<div class="grow"></div><span class="btn ghost">Close</span></div>')
    return (f'<div class="card">{head}<span class="faint" style="font-size:12.5px">Limits 500–2500 µs</span></div>'
            f'<div class="card-b">{"".join(rows)}{btns}'
            f'<div class="note" style="margin-top:14px">{icon("info", 16)}<span>Nothing is sent until you move a slider. A joint\'s first move after the robot restarts jumps straight to the slider, so start close to where it really is.</span></div></div></div>')


def dial(angle, active=True):
    ticks = "".join(f'<line x1="50" y1="{6 if i % 3 == 0 else 8}" x2="50" y2="12" stroke="var(--text-2)" stroke-width="{1.4 if i % 3 == 0 else 1}" '
                    f'transform="rotate({i * 15} 50 50)"/>' for i in range(24))
    needle = (f'<line x1="50" y1="50" x2="50" y2="17" stroke="var(--text)" stroke-width="2.4" stroke-linecap="round" transform="rotate({-angle} 50 50)"/>'
              f'<path d="M50 50 L50 10 A40 40 0 0 0 {50 - 40 * 0.9991:.1f} {50 - 40 * 0.0436:.1f} Z" fill="var(--info)" fill-opacity=".14"/>' if active else "")
    return (f'<svg width="100" height="100" viewBox="0 0 100 100"><circle cx="50" cy="50" r="46" fill="var(--surface-deep)" stroke="var(--border-strong)"/>'
            f'{ticks}<text x="50" y="27" text-anchor="middle" font-size="9" fill="var(--text-2)" font-family="Inter">0°</text>{needle}'
            f'<circle cx="50" cy="50" r="3.5" fill="var(--text)"/></svg>')


def sensors_card(calibrating=False):
    pts = [(0, 38), (40, 40), (70, 38), (100, 46), (140, 58), (175, 64), (200, 62), (240, 52), (280, 40), (320, 24), (350, 12),
           (370, 14), (400, 26), (440, 38), (480, 44), (520, 48), (560, 51), (600, 52)]
    line = " ".join(f"{x},{y}" for x, y in pts)
    chart = (f'<svg width="100%" height="80" viewBox="0 0 600 80" preserveAspectRatio="none"><line x1="0" y1="2" x2="600" y2="2" stroke="var(--border-strong)" stroke-dasharray="3 4"/>'
             f'<polygon points="0,80 {line} 600,80" fill="var(--info)" fill-opacity=".15"/>'
             f'<polyline points="{line}" fill="none" stroke="var(--info)" stroke-width="2"/></svg>')
    if calibrating:
        gyro_head = f'<div class="grow"></div><span class="pill sm p-info">{icon("loader-circle", 13)}Calibrating…</span>'
        turned = '<div class="faint" style="font-size:22px;margin-top:6px">—</div>'
        tilt = f'<div class="faint num" style="font-size:13px">X —<br>Y —</div>'
        speed = 'Speed <span style="margin-left:16px">X —</span><span style="margin-left:14px">Y —</span><span style="margin-left:14px">Z —</span>'
        bottom = (f'<div class="note info" style="margin-top:14px;align-items:center">{icon("loader-circle", 18)}<div class="grow">'
                  f'<b style="font-weight:500">Calibrating… keep the robot still</b><div class="muted" style="font-size:12.5px">Readings come back in about 2 seconds.</div></div>'
                  f'<span class="btn sm dis">{icon("crosshair", 15)}Calibrate gyro</span></div>')
    else:
        gyro_head = ""
        turned = '<div class="num" style="font-size:28px;font-weight:500;margin-top:4px">87.5°</div><div class="muted" style="font-size:13px">left of the start</div>'
        tilt = '<div class="num" style="font-size:13.5px">X 0.4°<br>Y −1.2°</div>'
        speed = ('Speed <span style="margin-left:16px">X <b class="num" style="font-weight:500">0 °/s</b></span>'
                 '<span style="margin-left:14px">Y <b class="num" style="font-weight:500">0 °/s</b></span>'
                 '<span style="margin-left:14px">Z <b class="num" style="font-weight:500">32 °/s</b></span>')
        bottom = (f'<div class="row gap12" style="margin-top:14px"><span class="btn sm">{icon("crosshair", 15)}Calibrate gyro</span>'
                  f'<span class="muted" style="font-size:12.5px">Keep the robot still for 2 seconds. Z drifts about 1° a minute, so calibrate again to zero it.</span></div>')
    tiltsvg = ('<svg width="66" height="66" viewBox="0 0 66 66"><circle cx="33" cy="33" r="31" fill="none" stroke="var(--border-strong)"/>'
               '<circle cx="33" cy="33" r="16" fill="none" stroke="var(--border-strong)" stroke-dasharray="2 3"/>'
               '<line x1="33" y1="4" x2="33" y2="62" stroke="var(--border)"/><line x1="4" y1="33" x2="62" y2="33" stroke="var(--border)"/>'
               + ('' if calibrating else '<circle cx="34" cy="31" r="5" fill="var(--text)"/>') + '</svg>')
    return (f'<div class="card"><div class="card-h">{icon("radar", 18)}<h3>Distance</h3>{helpdot()}<div class="grow"></div>'
            f'<span class="faint" style="font-size:12.5px">Ultrasonic · up to 2 m</span></div>'
            f'<div class="card-b"><div class="row gap16"><div class="num" style="font-size:38px;font-weight:500;line-height:1">42<small style="font-size:16px;color:var(--text-2);font-weight:400"> cm</small></div>'
            f'<span class="muted" style="font-size:13px">Since you opened this: lowest <b style="color:var(--text);font-weight:500">12 cm</b>, highest <b style="color:var(--text);font-weight:500">180 cm</b></span></div>'
            f'<div style="margin-top:10px;position:relative">{chart}<span class="faint" style="position:absolute;right:0;top:4px;font-size:11.5px">200 cm</span></div>'
            f'<div class="row between faint" style="font-size:11.5px"><span>3 min ago</span><span>now</span></div>'
            f'<div class="note good" style="margin-top:12px">{icon("circle-check", 16)}Working: the reading follows what is in front of the sensor.</div></div>'
            f'<div class="card-h" style="border-top:1px solid var(--border)">{icon("rotate-3d", 18)}<h3>Gyro</h3>{helpdot()}{gyro_head}</div>'
            f'<div class="card-b"><div class="row gap16"><div class="col" style="align-items:center;gap:4px">{dial(87.5, not calibrating)}<span class="muted" style="font-size:12.5px">Rotation Z</span></div>'
            f'<div class="grow" style="align-self:flex-start;padding-top:6px"><div class="muted" style="font-size:13px">Turned (Z)</div>{turned}</div>'
            f'<div class="col" style="align-items:center;gap:4px">{tiltsvg}<span class="muted" style="font-size:12px">Tilt X / Y</span></div>{tilt}</div>'
            f'<div class="sending" style="font-family:inherit;margin-top:10px">{speed}</div>{bottom}</div>'
            f'<div class="row gap10" style="padding:12px 18px;border-top:1px solid var(--border);color:var(--text-3)">{icon("battery", 16)}Battery'
            f'<div class="grow"></div><span class="pill sm p-ctl" style="padding-left:8px;color:var(--text-2)">Coming soon</span></div></div>')


def terminal_card(empty=False):
    border = "border-color:var(--stop-border)"
    if empty:
        body = '<div class="mono faint" style="font-size:12.5px;height:120px">Nothing run yet in this session.</div>'
    else:
        body = '<div class="mono" style="font-size:12.5px;line-height:1.75;color:var(--text)">' + TERM_OUT + '</div>'
    return _terminal_tail(body, border)


TERM_OUT = (
                '<span class="faint">~/swarm-agent $</span> journalctl -u swarm-agent -n 30<br>'
                'Nov 10 09:15:41 masterpi-01 robot_agent.py[812]: [robot]<br>&nbsp;&nbsp;gyro calibrated: rotation is 0, 0, 0<br>'
                'Nov 10 09:15:44 masterpi-01 robot_agent.py[812]: [robot]<br>&nbsp;&nbsp;connected to hub 192.168.50.2:8765<br>'
                '<span class="faint">exit code 0 · output cut short (28 more lines)</span><br><br>'
                '<span class="faint">~/swarm-agent $</span> i2cdetect -y 4<br>'
                '&nbsp;&nbsp;&nbsp;&nbsp;0&nbsp;&nbsp;1&nbsp;&nbsp;2&nbsp;&nbsp;3&nbsp;&nbsp;4&nbsp;&nbsp;5&nbsp;&nbsp;6&nbsp;&nbsp;7&nbsp;&nbsp;8&nbsp;&nbsp;9&nbsp;&nbsp;a&nbsp;&nbsp;b&nbsp;&nbsp;c&nbsp;&nbsp;d&nbsp;&nbsp;e&nbsp;&nbsp;f<br>'
                '60: -- -- -- -- -- -- -- -- 68 -- -- -- -- -- -- --<br>70: -- -- -- -- -- -- -- --<br>'
                '<span class="faint">exit code 0</span><br><br>'
                '<span class="faint">~/swarm-agent $</span> cat gyro.log<br>cat: gyro.log: No such file or directory<br>'
                '<span style="color:var(--warn-text)">exit code 1</span>')


def _terminal_tail(body, border):
    return (f'<div class="card" style="{border}"><div class="card-h" style="background:var(--stop-bg);{border};border-radius:14px 14px 0 0">'
            f'{icon("terminal", 17, color="#F87171")}<b style="font-weight:600">Terminal on Clanker</b>'
            f'<span class="muted" style="font-size:13px">runs as pi · every command is logged</span><div class="grow"></div>'
            f'<span class="help" style="color:#F87171;border-color:var(--stop-border)">{icon("circle-help", 13)}</span></div>'
            f'<div class="card-b" style="background:var(--surface-deep)">{body}</div>'
            f'<div class="row gap10" style="padding:12px 16px;border-top:1px solid var(--border)">'
            f'<div class="inp grow mono" style="height:40px;font-size:13px"><span class="faint">~/swarm-agent $</span><span class="caret"></span></div>'
            f'<span class="btn sm primary" style="height:36px">{icon("corner-down-left", 15)}Run</span><span class="btn sm" style="height:36px">Clear</span></div>'
            f'<p class="muted" style="font-size:13px;padding:10px 16px 14px;border-top:1px solid var(--border)">One command at a time, stops after 30 seconds. Programs that need typing (nano, top) won\'t work.</p></div>')


INFO_ROWS = [("Robot type", '<span class="mono">masterpi</span>'), ("Address", "192.168.50.11"),
             ("Robot's own name", '<span class="mono">masterpi-01</span>'), ("Installed by this hub", "CHECK Yes"),
             ("Added on", "14 Oct 2026, 16:20"), ("Last updated", 'Today, 09:15 <span class="muted">by asmaa</span>')]
INFO_CAPS = [("move", "Wheels"), ("camera", "Camera"), ("hand", "Arm · 5 joints"), ("radar", "Distance"), ("rotate-3d", "Gyro")]
INFO_SENSORS = ("distance_cm", "rot_x_deg", "rot_y_deg", "rot_z_deg", "gyro_x_dps", "gyro_y_dps", "gyro_z_dps")


def _info_value(v):
    return v.replace("CHECK", icon("check", 15))


def info_card():
    rows = INFO_ROWS
    tr = "".join(f'<div class="row" style="padding:11px 0;border-bottom:1px solid var(--border)"><span class="muted" style="width:160px">{k}</span><span class="row gap6">{_info_value(v)}</span></div>' for k, v in rows)
    caps = "".join(f'<span class="pill sm p-ctl" style="padding-left:8px">{icon(ic, 13)}{t}</span>' for ic, t in INFO_CAPS)
    joints = "".join(f'<div class="grow" style="padding:9px 11px;border-right:1px solid var(--border)"><div class="mono" style="font-size:12.5px">{j}</div>'
                     f'<div class="muted num" style="font-size:12.5px">500–2500</div></div>' for j in ("base", "shoulder", "elbow", "wrist", "gripper"))
    sens = "".join(f'<span class="code" style="font-size:12px">{s}</span>' for s in INFO_SENSORS)
    return (f'<div class="card"><div class="card-h">{icon("info", 18)}<h3>Info</h3><div class="grow"></div>'
            f'<span class="btn sm">{icon("download", 15)}Update…</span><span class="btn sm danger-soft">{icon("trash-2", 15)}Remove…</span></div>'
            f'<div class="card-b" style="padding-top:4px">{tr}<div class="muted" style="font-size:13px;margin:12px 0 8px">What it can do</div>'
            f'<div class="row gap6" style="flex-wrap:wrap">{caps}</div><div class="muted" style="font-size:13px;margin:14px 0 8px">Arm joints and limits (µs)</div>'
            f'<div class="row" style="border:1px solid var(--border);border-radius:10px;overflow:hidden">{joints}</div>'
            f'<div class="muted" style="font-size:13px;margin:14px 0 8px">Sensors</div><div class="row gap6" style="flex-wrap:wrap">{sens}</div></div></div>')


ACT = [("14:10:02", "asmaa", "lock", "took control"), ("14:09:47", "najeeb", "lock", "released control"),
       ("14:06:12", "najeeb", "octagon", "pressed Stop"), ("14:05:20", "najeeb", "lock", "took control"),
       ("13:58:03", "hafsah", "octagon", "pressed Stop all: stopped Clanker, Rover and Scout"),
       ("10:04:31", "asmaa", "terminal", 'ran in Terminal: <span class="code">cat gyro.log</span> (exit 1)'),
       ("10:03:12", "asmaa", "terminal", 'ran in Terminal: <span class="code">i2cdetect -y 4</span> (exit 0)'),
       ("10:02:40", "asmaa", "terminal", 'ran in Terminal: <span class="code">journalctl -u swarm-agent -n 30</span> (exit 0)'),
       ("09:15:44", None, "wifi", "connected")]


def activity_card():
    rows = "".join(f'<tr><td class="num muted">{t}</td><td>' + (f'<span class="row gap8"><span class="av">{p[:2].upper()}</span>{p}</span>' if p else '<span class="faint">—</span>')
                   + f'</td><td><span class="row gap8" style="align-items:flex-start">{icon(ic, 15, color="var(--text-2)")}<span>{w}</span></span></td></tr>' for t, p, ic, w in ACT)
    return (f'<div class="card"><div class="card-h">{icon("history", 18)}<h3>Activity</h3>{helpdot()}<div class="grow"></div>'
            f'<span class="faint" style="font-size:13px">Clanker only · today</span><span class="row gap6" style="font-size:13.5px;margin-left:12px">Open in History{icon("arrow-right", 14)}</span></div>'
            f'<table class="tbl"><tr><th style="width:100px">Time</th><th style="width:120px">Person</th><th>What happened</th></tr>{rows}</table>'
            f'<div class="row between" style="padding:12px 18px;border-top:1px solid var(--border)"><span class="faint" style="font-size:13px">9 of 11 today</span><span class="btn sm">Load more</span></div></div>')


def robot_list_panel(selected="clanker"):
    rows = []
    for k, r in ROBOTS.items():
        sel = " sel" if k == selected else ""
        dim = ' style="opacity:.8"' if r["status"] != "connected" else ""
        pills = status_pill(r["status"], sm=True)
        line2 = ""
        if r["moving"]:
            line2 = moving_pill(sm=True) + ctrl_pill(r["ctrl"], sm=True)
        elif r["ctrl"] and r["ctrl"] != "you":
            line2 = ctrl_pill(r["ctrl"], sm=True)
        rows.append(f'<div class="rrow{sel}"{dim}><div class="row gap10"><span class="mg" style="width:30px;height:30px;font-size:11.5px">{r["mg"]}</span>'
                    f'<div><div style="font-size:14.5px">{r["name"]}</div><div class="mono faint" style="font-size:11.5px">{r["host"]}</div></div></div>'
                    f'<div class="row gap6" style="margin-top:8px;flex-wrap:wrap">{pills}</div>'
                    + (f'<div class="row gap6" style="margin-top:6px;flex-wrap:wrap">{line2}</div>' if line2 else "") + "</div>")
    return (f'<div class="card" style="width:232px;padding:14px;flex:none;align-self:flex-start"><div class="row gap8" style="margin-bottom:12px">'
            f'<b style="font-size:16px;font-weight:600">Robots</b><span class="muted" style="font-size:12.5px">3 of 4 online</span><div class="grow"></div>'
            f'<span class="btn sm icon">{icon("panel-left-close", 16)}</span></div><div class="list">{"".join(rows)}</div>'
            f'<p class="muted" style="font-size:12.5px;margin-top:12px;padding-top:12px;border-top:1px solid var(--border)">Switching robots closes this one\'s panel: '
            f'your keys stop sending, and your control of it is released. You don\'t get control of the next robot until you take it.</p></div>')


def cockpit(rkey, tab, right, ctrl_state="you", locked=False, cam_note=False, theme_dark=True, list_open=False, header_ctrl="keep",
            moving=None):
    r = ROBOTS[rkey]
    stale = r["status"] == "unresponsive"
    top = (f'<span style="color:var(--warn-text);display:flex;gap:6px;align-items:center">{icon("triangle-alert", 14)}Last picture 6 s ago · reconnecting</span>'
           if stale else None)
    variant = 1 if rkey == "rover" else (2 if rkey == "scout" else 0)
    if list_open:
        cw = 500
        main = (f'<div class="row gap20" style="align-items:flex-start">{robot_list_panel(rkey)}<div class="grow">'
                f'{robot_header(r, robots_button=False, ping_text=False, ctrl_override=header_ctrl, moving=moving, compact=True)}{tabs(tab, locked)}'
                f'<div class="row gap20" style="align-items:flex-start"><div>{camera(cw, top=top, dark=stale, variant=variant)}{strip(r, cw)}</div>'
                f'<div class="grow col gap16">{right}</div></div></div></div>')
        return main
    cw = 640
    note = (f'<p class="muted row gap8" style="font-size:13px;margin-top:12px">{icon("camera", 15)}Camera stays live while you use the other tabs. Keyboard driving works on every tab.</p>'
            if cam_note else "")
    sstrip = "" if cam_note else strip(r, cw)
    return (f'{robot_header(r, ctrl_override=header_ctrl, moving=moving)}{tabs(tab, locked)}<div class="row gap20" style="align-items:flex-start">'
            f'<div>{camera(cw, top=top, dark=stale, variant=variant)}{sstrip}{note}</div><div class="grow col gap16">{right}</div></div>')


# ---------------------------------------------------------------- fleet

CAPS = [("move", True), ("hand", "arm"), ("camera", True), ("radar", True), ("rotate-3d", "gyro")]


def fleet_card(k, stale=False):
    r = ROBOTS[k]
    off = r["status"] == "offline"
    unr = r["status"] == "unresponsive"
    pills = status_pill(r["status"]) + (moving_pill() if r["moving"] else "")
    staleclk = f'<span style="color:var(--warn-text);display:inline-flex;gap:4px;align-items:center">{icon("clock", 13)}24 s ago</span>' if stale else ""
    slow = f'<span style="color:var(--warn-text);display:inline-flex;gap:3px;align-items:center;font-size:12.5px">{icon("triangle-alert", 12)}slow</span>' if unr else ""
    meta = (f'<div class="row gap16" style="margin:10px 0 12px">{ctrl_pill(r["ctrl"])}<span class="muted">Last seen <b style="color:var(--text);font-weight:500">{r["seen_short"].replace("Seen ", "")}</b></span>'
            f'<span class="muted">Latency <b class="num" style="color:var(--text);font-weight:500">{r["lat"]}</b></span>{slow}{staleclk}</div>')
    if off:
        cam = (f'<div class="cam col" style="width:165px;height:124px;align-items:center;justify-content:center;gap:6px;background:#0A0E13;color:var(--text-2);font-size:13px">'
               f'{icon("camera-off", 20)}No picture · offline</div>')
    else:
        lbl = (f'<span style="color:var(--warn-text);display:flex;gap:5px;align-items:center">{icon("triangle-alert", 13)}{"24 s ago" if stale else "6 s ago"}</span>'
               if (unr or stale) else '<span style="width:6px;height:6px;border-radius:50%;background:#fff"></span>Live')
        cam = (f'<div class="cam" style="width:165px;height:124px;{"opacity:.6;" if (unr or stale) else ""}">{scene(unr or stale, 1 if k == "rover" else (2 if k == "scout" else 0))}'
               f'<div class="ov" style="top:8px;left:8px;height:24px;font-size:12px">{lbl}</div></div>')
    dist = "—" if r["dist"] is None else f'{r["dist"]}<small>cm</small>'
    rz = "—" if off else (r["rot"][2] if r["rot"] else '<span class="muted" style="font-size:15px">No gyro</span>')
    dstyle = "opacity:.55" if unr else ""
    dstale = f'<div style="color:var(--warn-text);font-size:12px">{icon("clock", 12)} 6 s ago</div>' if unr else ""
    caps = "".join(f'<span class="mg sm" style="width:28px;height:28px;{"border-style:dashed;opacity:.45" if (v == "arm" and not r["arm"]) or (v == "gyro" and not r["gyro"]) else ""}">'
                   f'{icon(ic, 14)}</span>' for ic, v in CAPS)
    sens = (f'<div class="grow"><div class="row"><div class="grow"><div class="lbl" style="{dstyle}">Distance</div><div class="big num" style="{dstyle}">{dist}</div>{dstale}</div>'
            f'<div class="grow"><div class="lbl">Rotation Z</div><div class="big num">{rz}</div></div></div>'
            f'<div class="lbl" style="margin:10px 0 6px">What it can do</div><div class="row gap6">{caps}</div></div>')
    ev = (f'<div class="row gap10" style="margin-top:12px;border:1px solid var(--border);border-radius:10px;padding:9px 12px;background:var(--surface-deep)">'
          f'{icon("history", 15, color="var(--text-2)")}<span class="muted">Last event</span><span>{r["event"][0]}</span><div class="grow"></div>'
          f'<span class="faint" style="font-size:12.5px">{r["event"][1]}</span></div>')
    acts = (f'<div class="row gap8" style="margin-top:12px">{stopbtn(off=off)}<div class="grow"></div>'
            f'<span class="btn {"dis" if off else ""}">{icon("radio", 15)}Ping</span><span class="btn">Open{icon("arrow-right", 15)}</span></div>')
    return (f'<div class="card" style="padding:16px 18px"><div class="row gap12"><span class="mg lg">{r["mg"]}</span><div class="grow">'
            f'<div style="font-size:17px;font-weight:500">{r["name"]}</div><div class="muted" style="font-size:12.5px"><span class="mono">{r["host"]}</span> · {r["ip"]}</div></div>'
            f'<div class="row gap6" style="{"opacity:.75" if stale else ""}">{pills}</div></div>{meta}<div class="row gap16" style="align-items:flex-start">{cam}{sens}</div>{ev}{acts}</div>')


def fleet_header(sub="4 robots on this hub · up to 4"):
    return (f'<div class="row" style="margin-bottom:16px"><div><div class="row gap8"><span class="h1">Robots</span>{helpdot()}</div>'
            f'<div class="sub">{sub}</div></div><div class="grow"></div><span class="btn primary">{icon("plus", 16)}Add robot</span></div>')


def fleet_grid(stale=False):
    cards = [fleet_card(k, stale) for k in ROBOTS]
    return (f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">{"".join(cards)}</div>')


def empty_fleet():
    need = "".join(f'<div class="row gap12" style="margin-top:12px">{icon(ic, 17, color="var(--text-2)")}<span>{t}</span></div>' for ic, t in
                   [("wifi", "The robot switched on and on the lab Wi-Fi"),
                    ("hash", 'Its IP address, e.g. <span class="mono">192.168.149.1</span>'),
                    ("key-round", "Its password (used once, not saved)")])
    return (fleet_header("No robots on this hub yet · up to 4") +
            f'<div style="border:1px dashed var(--border-strong);border-radius:16px;height:690px;display:flex;flex-direction:column;align-items:center;justify-content:center">'
            f'<div class="mg lg">{icon("bot", 22)}</div><div style="font-size:18px;font-weight:600;margin-top:18px">No robots yet. Press Add robot to set one up.</div>'
            f'<p class="muted" style="text-align:center;max-width:470px;margin-top:8px;font-size:14.5px">The hub installs its program on the robot for you. It takes a few minutes the first time.</p>'
            f'<div class="card" style="width:470px;padding:16px 18px;margin-top:22px;background:var(--surface)"><div class="muted" style="font-size:13px">What you need</div>{need}</div>'
            f'<span class="btn primary" style="margin-top:22px;height:42px;padding:0 20px">{icon("plus", 16)}Add robot</span></div>')


# ---------------------------------------------------------------- other pages

HIST = [("14:12:04", "SC Scout", None, "wifi", "Connection", "went unresponsive: not heard from for over 3 s"),
        ("14:10:02", "CL Clanker", "asmaa", "lock", "Control", "took control"),
        ("14:09:47", "CL Clanker", "najeeb", "lock", "Control", "released control"),
        ("14:08:40", "RO Rover", "sara", "lock", "Control", "took control"),
        ("14:06:12", "CL Clanker", "najeeb", "octagon", "Stop", "pressed Stop"),
        ("14:05:20", "CL Clanker", "najeeb", "lock", "Control", "took control"),
        ("13:58:03", None, "hafsah", "octagon", "Stop", "pressed Stop all: stopped Clanker, Rover and Scout"),
        ("13:41:55", "SC Scout", "rawan", "terminal", "Terminal", 'ran in Terminal: <span class="code">journalctl -u swarm-agent -n 30</span> (exit 0)'),
        ("13:40:10", "SC Scout", None, "wifi", "Connection", "connected"),
        ("13:39:52", "SC Scout", None, "wifi", "Connection", "went offline (hub silent 5 s)"),
        ("13:22:18", "RO Rover", "hafsah", "download", "Install", "Update finished"),
        ("13:20:31", "RO Rover", "hafsah", "download", "Install", "Update started"),
        ("12:47:09", None, "sara", "log-out", "Sign-in", "sign-in failed: wrong username or password"),
        ("11:09:40", "VX Vex", None, "wifi", "Connection", "went offline (hub silent 5 s)"),
        ("10:04:31", "CL Clanker", "asmaa", "terminal", "Terminal", 'ran in Terminal: <span class="code">cat gyro.log</span> (exit 1)'),
        ("10:03:12", "CL Clanker", "asmaa", "terminal", "Terminal", 'ran in Terminal: <span class="code">i2cdetect -y 4</span> (exit 0)'),
        ("10:02:40", "CL Clanker", "asmaa", "terminal", "Terminal", 'ran in Terminal: <span class="code">journalctl -u swarm-agent -n 30</span> (exit 0)'),
        ("09:15:44", "CL Clanker", None, "wifi", "Connection", "connected"),
        ("09:15:02", "CL Clanker", "asmaa", "download", "Install", "Update finished"),
        ("09:13:37", "CL Clanker", "asmaa", "download", "Install", "Update started")]


def history_page():
    def sel(ic, t, w):
        return (f'<div class="inp" style="width:{w}px;height:40px;background:var(--surface-deep)">{icon(ic, 16, color="var(--text-2)")}'
                f'<span class="grow">{t}</span>{icon("chevron-down", 15, color="var(--text-2)")}</div>')
    types = [("All", None), ("Connections", "wifi"), ("Control", "lock"), ("Stops", "octagon"), ("Terminal", "terminal"), ("Installs", "download")]
    chips = "".join((f'<span class="btn sm primary">{t}</span>' if ic is None else f'<span class="btn sm">{icon(ic, 15)}{t}</span>') for t, ic in types)
    rows = []
    for t, rob, who, ic, typ, what in HIST:
        rc = (f'<span class="row gap8"><span class="mg sm">{rob[:2]}</span>{rob[3:]}</span>' if rob else '<span class="muted">All robots</span>')
        pc = (f'<span class="row gap8"><span class="av">{who[:2].upper()}</span>{who}</span>' if who else '<span class="faint">—</span>')
        rows.append(f'<tr><td class="num muted">{t}</td><td>{rc}</td><td>{pc}</td><td><span class="row gap6 muted" style="font-size:13px">{icon(ic, 14)}{typ}</span></td><td>{what}</td></tr>')
    return (f'<div class="row gap8"><span class="h1">Everything that happened</span>{helpdot()}</div>'
            f'<div class="sub">Connections, who took control, stops, terminal commands, installs. Kept for 90 days.</div>'
            f'<div class="card" style="padding:16px 18px;margin-top:18px"><div class="row gap16"><div class="field"><span class="lbl">Robot</span>{sel("bot", "All robots", 170)}</div>'
            f'<div class="field"><span class="lbl">Person</span>{sel("user", "Anyone", 170)}</div><div class="field"><span class="lbl">Date range</span>{sel("calendar", "Today · 10 Nov 2026", 220)}</div></div>'
            f'<div class="lbl" style="margin:14px 0 8px">Type</div><div class="row gap6">{chips}</div></div>'
            f'<div class="card" style="margin-top:16px"><table class="tbl"><tr><th style="width:110px">Time</th><th style="width:140px">Robot</th><th style="width:125px">Person</th><th style="width:130px">Type</th><th>What happened</th></tr>'
            f'{"".join(rows)}</table><div class="row between" style="padding:12px 18px;border-top:1px solid var(--border)">'
            f'<span class="faint" style="font-size:13px">Showing 20 events from today · newest first</span><span class="btn sm">Load more</span></div></div>')


def spark(points, color="var(--text-3)", fill=False):
    line = " ".join(f"{i * 240 / (len(points) - 1):.0f},{30 - p}" for i, p in enumerate(points))
    f = f'<polygon points="0,30 {line} 240,30" fill="{color}" fill-opacity=".18"/>' if fill else ""
    return f'<svg width="240" height="32" viewBox="0 0 240 32">{f}<polyline points="{line}" fill="none" stroke="{color}" stroke-width="1.6"/></svg>'


HEALTH_TILES = [("CPU temperature", "61 °C", "the Pi slows down above 75 °C", True), ("CPU load", "0.42", "1-minute average", False),
             ("Memory used", "38%", "of the Pi's memory", False), ("Disk free", "21 GB", "on the SD card", False),
             ("Running for", "3 days 4 h", "since 7 Nov, 10:08", False), ("Version", "1.0.0", "hub software", False)]


def temp_gauge():
    return ('<div class="slider" style="margin-top:12px;height:10px"><div class="tr" style="height:5px"></div><div class="fill" style="width:68%;height:5px;background:var(--text-2)"></div>'
            '<div style="position:absolute;left:83%;width:2px;height:12px;background:var(--text-2)"></div></div>'
            '<div class="row faint num" style="font-size:11.5px;margin-top:4px"><span>0</span><div class="grow"></div><span style="margin-right:22px">75</span><span>90 °C</span></div>')


def health_robots():
    return [("clanker", "18 ms", spark([2, 2, 3, 2, 2, 3, 2, 2, 2, 3, 2, 2]), "0", "now"),
            ("rover", "24 ms", spark([2, 2, 3, 2, 3, 2, 8, 3, 2, 2, 3, 2]), "1", "now"),
            ("scout", "212 ms", spark([4, 6, 5, 12, 16, 10, 7, 20, 22, 14, 18, 22, 17, 15, 19, 20, 18], "var(--warn)", True), "7", "6 s ago"),
            ("vex", "—", None, "2", "3 h ago")]


def health_page():
    tiles = HEALTH_TILES
    t = []
    for name, val, sub, gauge in tiles:
        g = temp_gauge() if gauge else ""
        t.append(f'<div class="card" style="padding:16px;flex:{1.5 if gauge else 1};background:var(--surface-deep)"><div class="muted" style="font-size:13px">{name}</div>'
                 f'<div class="num" style="font-size:26px;font-weight:500;margin:6px 0 4px">{val}</div><div class="muted" style="font-size:12.5px">{sub}</div>{g}</div>')
    robots = health_robots()
    rows = []
    for k, lat, sp, rec, seen in robots:
        r = ROBOTS[k]
        if sp is None:
            sp = '<div style="width:240px;height:32px;border:1px dashed var(--border-strong);border-radius:8px;display:flex;align-items:center;padding-left:10px;font-size:12.5px" class="muted">No data · offline for 3 h</div>'
        slow = f' <span style="color:var(--warn-text);font-size:12.5px">{icon("triangle-alert", 12)} slow</span>' if k == "scout" else ""
        high = f' <span style="color:var(--warn-text);font-size:12.5px;margin-left:8px">{icon("triangle-alert", 12)} high</span>' if k == "scout" else ""
        rows.append(f'<tr><td><span class="row gap10"><span class="mg" style="width:30px;height:30px;font-size:11.5px">{r["mg"]}</span><span><div>{r["name"]}</div>'
                    f'<div class="mono faint" style="font-size:11.5px">{r["host"]}</div></span></span></td><td>{status_pill(r["status"], sm=True)}</td>'
                    f'<td class="num">{lat}{slow}</td><td>{sp}<div class="row between faint" style="font-size:11px;width:240px"><span>1 h ago</span><span>now</span></div></td>'
                    f'<td class="num">{rec}{high}</td><td class="muted">{seen}</td></tr>')
    return (f'<div class="row gap8"><span class="h1">Health</span>{helpdot()}</div><div class="sub">How the hub machine in the lab is doing, and how good each robot\'s connection is.</div>'
            f'<div class="note warn" style="margin-top:16px;align-items:center;font-size:14px">{icon("triangle-alert", 17)}<span><b style="font-weight:600">Scout keeps reconnecting: check its Wi-Fi</b>'
            f'<span class="muted"> · 7 reconnects in the last 24 h. Everything else is fine.</span></span></div>'
            f'<div class="card" style="margin-top:16px"><div class="card-h">{icon("server", 18)}<h3>Hub machine</h3><span class="muted" style="font-size:13px">Raspberry Pi 5 in the lab</span>'
            f'<div class="grow"></div>{status_pill("connected", sm=True)}</div><div class="row gap12" style="padding:16px 18px;align-items:stretch">{"".join(t)}</div></div>'
            f'<div class="card" style="margin-top:16px"><div class="card-h">{icon("radio", 18)}<h3>Robots</h3><span class="muted" style="font-size:13px">Latency under 50 ms is good; over 200 ms feels laggy.</span></div>'
            f'<table class="tbl"><tr><th>Robot</th><th>Status</th><th>Latency now</th><th>Last hour</th><th>Reconnects (24 h)</th><th>Last seen</th></tr>{"".join(rows)}</table></div>')


HELP_ARTS = [("rocket", "Getting started", "Sign in, find your robot on Fleet, open it and take control.", "2 min read"),
            ("plus", "Adding a robot", "What you need, and what the hub does during Install.", "3 min read"),
            ("wifi-off", "When a robot won't connect", "Unresponsive, Offline and the usual Wi-Fi causes.", "2 min read"),
            ("gamepad-2", "Manual driving", "Hold a button or key to move; let go and the robot stops.", "2 min read"),
            ("lock", "Control (who can drive)", "Only one person can drive a robot or move its arm at a time.", "2 min read"),
            ("rotate-3d", "Sensors and the gyro", "Distance up to 2 m, rotation and turn speed, Calibrate gyro.", "3 min read"),
            ("keyboard", "Keyboard shortcuts", "W A S D to move, Q E to turn, Space to stop, Esc Esc for Stop all.", "1 min read"),
            ("octagon", "Safety rules", "Stop always works. Remote driving only while someone is in the lab.", "2 min read")]


def help_page():
    arts = HELP_ARTS
    cards = "".join(f'<div class="card" style="padding:16px 18px"><span class="mg" style="width:32px;height:32px">{icon(ic, 16)}</span>'
                    f'<div style="font-size:16px;font-weight:600;margin-top:14px">{t}</div><p class="muted" style="margin-top:6px;font-size:14px;min-height:40px">{d}</p>'
                    f'<div class="faint" style="font-size:13px;margin-top:10px">{rt}</div></div>' for ic, t, d, rt in arts)
    rb = "".join(f'<div class="row gap10" style="border:1px solid var(--border-strong);border-radius:10px;padding:8px 12px;background:var(--surface-deep)">'
                 f'<span class="mg sm">{r["mg"]}</span>{r["name"]}<div class="grow"></div><span class="mono faint" style="font-size:12px">{r["host"]}</span></div>' for r in ROBOTS.values())

    def box(ic, t, d):
        return (f'<div style="border:1px solid var(--border-strong);border-radius:12px;padding:14px 16px;width:200px;background:var(--surface-deep)">'
                f'<div class="row gap8" style="font-weight:500">{icon(ic, 16)}{t}</div><div class="muted" style="font-size:12.5px;margin-top:4px">{d}</div></div>')

    def arrow(t):
        return (f'<div class="grow" style="text-align:center;font-size:12.5px" class="muted"><div class="muted">{t}</div>'
                f'<div style="height:1px;background:var(--border-strong);margin-top:8px;position:relative"><span style="position:absolute;right:-4px;top:-7px;color:var(--text-2)">›</span></div></div>')
    diagram = (f'<div class="row gap8" style="padding:30px 24px">{box("laptop", "The app", "In your browser, on a team laptop")}'
               f'{arrow("Tailscale (private network)<br>sign-in · live updates · camera")}'
               f'{box("server", "The hub", "Raspberry Pi 5 in the lab. Keeps history, checks who is in control")}'
               f'{arrow("Lab Wi-Fi<br>commands · heartbeats every second")}<div class="col gap6" style="width:200px">{rb}</div></div>'
               f'<p class="muted" style="padding:0 24px 22px;font-size:14px">Robots only talk to the hub, never to your laptop. If the hub goes silent for 3 seconds, every robot stops by itself. '
               f'If your connection drops while you drive, the robot stops within half a second.</p>')
    return (f'<div class="row"><div><span class="h1">Help</span><div class="sub">Short answers. Every panel\'s <b>?</b> opens the matching article.</div></div><div class="grow"></div>'
            f'<div class="inp" style="width:420px;background:var(--surface)">{icon("search", 16, color="var(--text-2)")}<span class="ph">Search help, e.g. "unresponsive" or "calibrate"</span></div></div>'
            f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:20px">{cards}</div>'
            f'<div class="card" style="margin-top:20px"><div class="card-h">{icon("network", 18)}<h3>How the system works</h3></div>{diagram}</div>')


def help_article():
    art, side = help_article_parts()
    return f'<div class="row gap20" style="align-items:flex-start">{art}{side}</div>'


def help_article_parts():
    def h(t):
        return f'<h3 style="font-size:16.5px;font-weight:600;margin:22px 0 8px">{t}</h3>'
    p = 'style="color:var(--text-2);font-size:15px;line-height:1.6"'
    keys = "".join(f'<div class="row gap8" style="margin-top:10px">{"".join(f"<span class=kbd style=border-color:var(--border-strong)>{k}</span>" for k in ks)}'
                   f'<span class="muted" style="margin-left:8px">{t}</span></div>' for ks, t in
                   [(("W", "A", "S", "D"), "move and slide"), (("Q", "E"), "turn"), (("Space",), "stop this robot"), (("Esc Esc",), "Stop all")])
    rel = "".join(f'<div class="row" style="padding:11px 0;border-top:1px solid var(--border)">{t}<div class="grow"></div>{icon("chevron-right", 15)}</div>'
                  for t in ("Manual driving", "Safety rules", "Keyboard shortcuts", "When a robot won't connect"))
    frees = "".join(f'<div class="row gap10" style="margin-top:8px;color:var(--text-2);font-size:15px">{icon(ic, 16)}<span>{t}</span></div>' for ic, t in
                    [("lock-open", "The person presses <b style='color:var(--text);font-weight:600'>Release control</b> or closes the panel."),
                     ("timer", "15 seconds pass after their last command."),
                     ("wifi-off", "Their app loses its connection. The hub stops the robot at once and frees control.")])
    art = (f'<div class="card" style="padding:28px 34px;flex:1"><div class="row gap6 muted" style="font-size:13px">Help{icon("chevron-right", 13)}Control</div>'
           f'<div class="note" style="margin-top:14px;align-items:center">{icon("circle-help", 16)}<span>Opened from the <b style="color:var(--text)">?</b> on Clanker\'s Drive panel. '
           f'<span style="color:var(--accent)">Back to Clanker</span></span></div>'
           f'<h1 style="font-size:28px;font-weight:600;margin:22px 0 12px">Control: who can drive</h1>'
           f'<p {p}>Only one person can drive a robot or move its arm at a time. Anyone can always press Stop. Control frees up when the person closes the panel, or 15 seconds after their last command.</p>'
           f'{h("Taking control")}<p {p}>When nobody is in control, press <b style="color:var(--text)">Take control</b> on the robot\'s page. Your first drive or arm command also takes control if it\'s free. '
           f'The badge then says {ctrl_pill("you", sm=True, long=True)} for you and your name for everyone else.</p>'
           f'{h("When someone else has it")}<p {p}>You see {ctrl_pill("sara", sm=True, long=True)}. You can watch the camera and sensors, but the drive pad and arm are read-only. If you try to drive, you get: '
           f'"sara is controlling masterpi-01 right now. You can still press Stop. Control frees up when they close the panel, or 15 seconds after their last command."</p>'
           f'{h("Stop always works")}<p {p}>Stop and Stop all never need control and are never blocked. Every stop is logged with who pressed it.</p>'
           f'{h("When control frees up")}{frees}<div class="row gap8" style="margin-top:26px;padding-top:16px;border-top:1px solid var(--border)">'
           f'<span class="muted" style="font-size:13.5px">Was this clear?</span><span class="btn sm">{icon("thumbs-up", 15)}Yes</span><span class="btn sm">{icon("thumbs-down", 15)}Not really</span></div></div>')
    side = (f'<div class="col gap16" style="width:300px"><div class="card" style="padding:14px 16px"><div class="muted" style="font-size:13px;margin-bottom:6px">Related</div>{rel}</div>'
            f'<div class="card" style="padding:14px 16px"><div class="muted" style="font-size:13px">Keys while you have control</div>{keys}</div></div>')
    return art, side


# ---------------------------------------------------------------- dialogs

def dlg(title, sub, body, foot, icon_html="", danger=False, width=520, close=True):
    x = f'<span style="color:var(--text-2);margin-left:auto">{icon("x", 18)}</span>' if close else ""
    s = f'<p class="muted" style="margin-top:4px;font-size:14px">{sub}</p>' if sub else ""
    return (f'<div class="dlg {"danger" if danger else ""}" style="width:{width}px"><div class="dlg-h">{icon_html}<div class="grow"><h2>{title}</h2>{s}</div>{x}</div>'
            f'<div class="dlg-b">{body}</div>' + (f'<div class="dlg-f">{foot}</div>' if foot else "") + "</div>")


def install_dialog(state):
    steps = [("Connecting to pi@192.168.149.1", "2 s"), ("Checking the robot", "1 s"),
             ("Installing the robot's packages", "3 min 12 s"), ("Copying the agent", "4 s"),
             ("Setting it to start on every boot", "2 s"), ("Waiting for the robot to connect to the hub", "9 s")]
    rows = []
    for i, (t, dur) in enumerate(steps):
        sub = '<div class="muted" style="font-size:13px">The first time takes a few minutes</div>' if i == 2 else ""
        if state == "done":
            ic, txt, d = f'<span class="sicon s-ok">{icon("check", 13, 2.4)}</span>', t, dur
        elif state == "running":
            if i < 2:
                ic, txt, d = f'<span class="sicon s-ok">{icon("check", 13, 2.4)}</span>', t, dur
            elif i == 2:
                ic, txt, d = '<span class="sicon s-run"></span>', f'<b style="font-weight:500">{t}…</b>', ""
            else:
                ic, txt, d = '<span class="sicon s-todo"></span>', f'<span class="muted">{t}</span>', ""
            if i == 1:
                sub = '<div class="slog">Raspberry Pi OS 11 (bullseye) · Python 3.9.2 · camera found</div>'
        else:
            if i == 0:
                ic, txt, d = f'<span class="sicon s-fail">{icon("x", 13, 2.4)}</span>', t, ""
                sub = '<div class="slog">ssh pi@192.168.149.1: Permission denied (publickey,password)</div>'
            else:
                ic, txt, d = '<span class="sicon s-todo"></span>', f'<span class="muted">{t}</span>', ""
        rows.append(f'<div class="step">{ic}<div class="grow" style="font-size:14.5px">{txt}{sub}</div><span class="faint num" style="font-size:12.5px">{d}</span></div>')
    pill = {"running": status_pill("working"), "done": status_pill("done"), "failed": status_pill("failed")}[state]
    title = (f'<div class="row gap12" style="align-items:flex-start">{pill}<div><h2>Installing the robot</h2>'
             f'<p class="muted" style="margin-top:4px">Adding <span class="mono">pi@192.168.149.1</span> · name picked for you: <span class="mono">masterpi-01</span></p></div></div>')
    if state == "running":
        tail = '<p class="muted" style="font-size:13.5px;margin-top:12px">You can hide this window. The install keeps running, and the robot\'s card shows its current step.</p>'
        foot = f'<span class="btn">{icon("eye-off", 16)}Hide (keeps running)</span>'
    elif state == "done":
        tail = (f'<div class="note good" style="margin-top:12px">{icon("circle-check", 17)}<div><b style="font-weight:600">masterpi-01 is installed and connected to the hub.</b>'
                f'<div class="muted">It rebooted and started by itself. You\'ll find it on Fleet.</div></div></div>')
        foot = f'<span class="btn">Close</span><span class="btn primary">Open robot{icon("arrow-right", 15)}</span>'
    else:
        tail = (f'<div class="note bad" style="margin-top:12px">{icon("circle-x", 17)}<div><b style="font-weight:600">The robot rejected that username or password.</b>'
                f'<div class="muted">Nothing was changed on the robot. Check the password and try again.</div></div></div>')
        foot = f'<span class="btn">Close</span><span class="btn primary">{icon("refresh-cw", 15)}Try again</span>'
    return (f'<div class="dlg" style="width:520px"><div class="dlg-h"><div class="grow">{title}</div><span style="color:var(--text-2)">{icon("x", 18)}</span></div>'
            f'<div class="dlg-b">{"".join(rows)}{tail}</div><div class="dlg-f">{foot}</div></div>')


def add_robot_dialog():
    body = (f'<div class="field"><label>IP address</label><div class="inp focus"><span class="caret"></span><span class="ph">192.168.149.1</span></div>'
            f'<span class="muted" style="font-size:13px">Shown on the robot\'s screen, or in your router\'s list of devices.</span></div>'
            f'<div class="row gap12" style="margin-top:16px"><div class="field grow"><label>Username</label><div class="inp mono">pi</div></div>'
            f'<div class="field grow"><label>Password</label><div class="inp" style="letter-spacing:3px">••••••••</div></div></div>'
            f'<div class="muted" style="font-size:13px;text-align:right;margin-top:6px">Password: used once to install. It is not saved.</div>'
            f'<div class="field" style="margin-top:14px"><label>Name <span class="muted" style="font-weight:400">(optional)</span></label><div class="inp"><span class="ph">picked for you, e.g. masterpi-01</span></div></div>'
            f'<div class="row gap10" style="margin-top:18px;align-items:flex-start"><span class="cb on">{icon("check", 13, 2.6)}</span><div><div>Reboot the robot when done</div>'
            f'<div class="muted" style="font-size:13px">Proves it starts by itself. Takes about a minute.</div></div></div>')
    foot = f'{helpdot()}<div class="grow"></div><span class="btn">Cancel</span><span class="btn primary">{icon("download", 16)}Install</span>'
    return dlg("Add robot", "The hub connects to the robot over the lab network and installs its program.", body, foot)


def update_dialog():
    body = (f'<div class="field"><label>Password <span class="muted" style="font-weight:400">(optional)</span></label><div class="inp"><span class="ph">Robot password</span></div>'
            f'<span class="muted" style="font-size:13px">Usually not needed. Fill it in only if the robot asks for it.</span></div>'
            f'<div class="row gap10" style="margin-top:18px;align-items:flex-start"><span class="cb"></span><div><div>Reboot the robot when done</div>'
            f'<div class="muted" style="font-size:13px">Proves it starts by itself. Takes about a minute.</div></div></div>'
            f'<div class="note" style="margin-top:16px">{icon("info", 16)}<span>The robot stops and restarts its program during the update, so it can\'t be driven for a few seconds.</span></div>')
    foot = f'<span class="btn">Cancel</span><span class="btn primary">{icon("download", 16)}Update</span>'
    return dlg("Update Clanker", "Copies the latest robot code from the hub to the robot and restarts it.", body, foot)


def remove_dialog():
    r = ROBOTS["vex"]
    body = (f'<div class="row gap12" style="border:1px solid var(--border);border-radius:12px;padding:12px 14px;background:var(--surface-deep)">'
            f'<span class="mg">{r["mg"]}</span><div class="grow"><div>Vex</div><div class="muted" style="font-size:12.5px"><span class="mono">masterpi-04</span> · 192.168.50.14</div></div>{status_pill("offline", sm=True)}</div>'
            f'<div class="field" style="margin-top:16px"><label>Password <span class="muted" style="font-weight:400">(optional)</span></label><div class="inp"><span class="ph">Robot password</span></div>'
            f'<span class="muted" style="font-size:13px">Usually not needed. Fill it in only if the robot asks for it.</span></div>'
            f'<div class="row gap10" style="margin-top:18px;align-items:flex-start"><span class="cb on">{icon("check", 13, 2.6)}</span><div><div>The robot is gone or can\'t be reached. Just take it off this list.</div>'
            f'<div class="muted" style="font-size:13px">Vex has been offline for 3 h, so the hub can\'t clean up the robot itself.</div></div></div>')
    foot = f'<span class="btn">Cancel</span><span class="btn danger">{icon("trash-2", 16)}Remove</span>'
    return dlg("Remove Vex?", "Stops the robot program, removes it from the robot, and takes the robot off this list.", body, foot,
               f'<span class="dicon">{icon("trash-2", 18)}</span>', danger=True)


def release_arm_dialog():
    foot = f'<span class="btn">Cancel</span><span class="btn danger">{icon("hand", 16)}Release</span>'
    return dlg("Release Clanker's arm?", None, '<p style="font-size:15px">The arm will sag. Support it first.</p>', foot,
               f'<span class="dicon">{icon("hand", 18)}</span>', danger=True, width=440)


def terminal_confirm_dialog():
    body = (f'<p style="font-size:15px">This runs commands directly on the robot. Everything you run is logged.</p>'
            f'<div class="note" style="margin-top:14px">{icon("info", 16)}<span>Commands run as the robot\'s user, one at a time, and stop after 30 seconds. '
            f'The log keeps who ran what and the exit code, not the output. You won\'t be asked again until you sign in next time.</span></div>')
    foot = f'<span class="btn">Cancel</span><span class="btn danger">{icon("terminal", 16)}Open terminal</span>'
    return dlg("Open the terminal on Clanker?", None, body, foot, f'<span class="dicon">{icon("terminal", 18)}</span>', danger=True, width=470)


# ---------------------------------------------------------------- sign in

def sign_in(error=False):
    brand, card, note = sign_in_parts(error)
    return (f'<div style="width:1440px;height:900px;background:radial-gradient(ellipse 700px 420px at 50% 22%,rgba(232,172,101,.06),transparent),var(--bg);'
            f'display:flex;flex-direction:column;align-items:center;justify-content:center">{brand}{card}{note}</div>')


def sign_in_parts(error=False):
    err = (f'<div class="note warn" style="margin-bottom:16px;align-items:center">{icon("triangle-alert", 17)}Wrong username or password.</div>' if error else "")
    user = '<div class="inp">asmaa</div>' if error else '<div class="inp focus">asmaa<span class="caret"></span></div>'
    pw = (f'<div class="inp err" style="letter-spacing:3px"><span class="grow">•••••••••</span>{icon("triangle-alert", 16, color="var(--text-2)")}</div>'
          f'<span class="muted" style="font-size:13px">Check your password and try again. After 5 wrong tries, sign-in pauses for a minute.</span>'
          if error else f'<div class="inp"><span class="ph grow">Password</span>{icon("eye", 16, color="var(--text-2)")}</div>')
    return (f'<div class="row gap12" style="margin-bottom:28px">{LOGO}<div><div style="font-size:22px;font-weight:600">Swarm Hub</div>'
            f'<div class="muted" style="font-size:13px">Robot lab · sign in to continue</div></div></div>',
            f'<div class="card" style="width:400px;padding:28px;border-radius:18px"><div style="font-size:19px;font-weight:600">Sign in</div>'
            f'<p class="muted" style="margin:4px 0 22px">Use your hub login.</p>{err}<div class="field"><label>Username</label>{user}</div>'
            f'<div class="field" style="margin-top:16px"><label>Password</label>{pw}</div>'
            f'<span class="btn primary" style="width:100%;height:44px;margin-top:22px;font-size:15px">Sign in</span></div>',
            f'<p class="muted row gap8" style="margin-top:22px;font-size:13.5px">{icon("shield", 15)}Only team devices on our Tailscale network can open this page.</p>')


# ---------------------------------------------------------------- components sheet

def components_page():
    pills1 = (status_pill("connected") + status_pill("unresponsive") + status_pill("offline")
              + f'<span class="pill p-info">{icon("loader-circle", 14)}Working…<span style="opacity:.8">&nbsp;Copying the agent</span></span>'
              + moving_pill() + ctrl_pill("sara") + ctrl_pill("you", long=True) + ctrl_pill(None, long=True))
    pills2 = (status_pill("connected", True) + status_pill("unresponsive", True) + status_pill("offline", True) + moving_pill(True)
              + ctrl_pill("sara", True) + ctrl_pill("you", True) + '<span class="faint" style="font-size:13px">Small size, for lists</span>')
    sel = (f'<div class="nav" style="width:180px"><a class="on" style="margin:0">{icon("layout-grid", 18)}Fleet</a></div>'
           f'<span class="muted" style="font-size:13px">Selected (amber)</span>{status_pill("unresponsive")}'
           f'<span class="muted" style="font-size:13px">Warning: triangle + word on a tinted pill</span>')
    btns1 = (f'<span class="btn primary">{icon("plus", 16)}Primary</span><span class="btn primary" style="background:var(--accent-hover)">Hover</span>'
             f'<span class="btn primary" style="box-shadow:0 0 0 3px var(--bg),0 0 0 5px var(--accent)">Focus</span><span class="btn">Secondary</span>'
             f'<span class="btn ghost">Tertiary</span><span class="btn danger-soft">{icon("hand", 16)}Danger · Release</span>'
             f'<span class="btn danger">{icon("trash-2", 16)}Danger · confirm</span><span class="btn dis">Disabled</span>')
    btns2 = (f'{stopbtn()}{stopbtn("Stop · offline", off=True)}{stopbtn("Stop all", "Esc Esc", "stopall", size=19)}<span class="btn sm">Small</span>'
             f'<span class="btn icon">{icon("ellipsis", 16)}</span>{helpdot()}<span class="muted" style="font-size:13px">Red is only for Stop and destructive actions. Stop always has the octagon.</span>')
    inputs = (f'<div class="field"><label>Normal</label><div class="inp"><span class="ph">192.168.149.1</span></div></div>'
              f'<div class="field" style="margin-top:14px"><label>Focus</label><div class="inp focus">asmaa<span class="caret"></span></div></div>'
              f'<div class="field" style="margin-top:14px"><label>Error</label><div class="inp err">192.168.1.20</div>'
              f'<span style="color:var(--warn-text);font-size:13px" class="row gap6">{icon("triangle-alert", 14)}Couldn\'t reach 192.168.1.20. Check the robot is on and this computer is on the same network as it.</span></div>'
              f'<div class="row gap16" style="margin-top:16px"><span class="row gap8"><span class="cb on">{icon("check", 13, 2.6)}</span>Checkbox</span>'
              f'<span class="row gap8"><span class="cb"></span>Off</span></div>'
              f'<div class="row gap16" style="margin-top:16px"><div class="seg" style="background:var(--surface-deep);border-color:var(--border)"><span>Low · 5 fps</span><span class="on">High · 15 fps</span></div>'
              f'<div class="slider" style="width:220px"><div class="tr"></div><div class="fill" style="width:33%"></div><div class="th" style="left:33%"></div></div></div>')
    toasts = "".join(f'<div class="card row gap12" style="padding:12px 14px;background:var(--surface-raised);margin-bottom:10px"><span class="mg" style="width:32px;height:32px">{icon(ic, 16)}</span>'
                     f'<div class="grow"><div style="font-weight:500">{t}</div><div class="muted" style="font-size:12.5px">{s}</div></div>{icon("x", 16, color="var(--text-2)")}</div>'
                     for ic, t, s in [("wifi-off", "Rover went offline", "just now"), ("lock", "sara took control of Clanker", "You can still press Stop.")])
    popover = (f'<div class="card" style="padding:14px 16px;background:var(--surface-raised);flex:1"><div class="row gap8" style="font-weight:600">{icon("circle-help", 16)}Status</div>'
               f'<p class="muted" style="margin-top:6px;font-size:13.5px">Connected means the robot is online. Unresponsive means it\'s connected but hasn\'t been heard from for a few seconds (often weak Wi-Fi). Offline means it isn\'t connected.</p></div>')
    readout = (f'<div class="card" style="padding:14px 16px;width:200px"><div class="lbl row gap6">{icon("radar", 14)}Distance</div>'
               f'<div class="big num" style="font-size:30px">42<small>cm</small></div><div class="muted" style="font-size:12.5px">≥ 200 when nothing is in range</div></div>')
    types = ('<div style="font-size:32px;font-weight:600">Display 32 / 600</div><div style="font-size:26px;font-weight:600;margin-top:10px">Page title 26 / 600</div>'
             '<div style="font-size:18px;font-weight:600;margin-top:12px">Section heading 18 / 600</div><div style="font-size:16px;font-weight:500;margin-top:10px">Subheading 16 / 500 · Clanker</div>'
             '<div style="font-size:14px;margin-top:10px">Body 14 / 400 · Hold a button or key to move; let go and the robot stops.</div>'
             '<div class="muted" style="font-size:12.5px;margin-top:10px">Caption 12.5 / 400 · Last seen 6 s ago</div>'
             '<div class="num" style="font-size:28px;font-weight:500;margin-top:14px">Telemetry 28 · 87.5° 118 cm</div>'
             '<div class="mono" style="font-size:13px;margin-top:10px">Mono · masterpi-01 · ~/swarm-agent $</div>')
    sw = [("background", "--bg"), ("surface", "--surface"), ("surface-raised", "--surface-raised"), ("surface-deep", "--surface-deep"),
          ("border-strong", "--border-strong"), ("text-muted", "--text-3"), ("accent", "--accent"), ("ok · Connected", "--ok"),
          ("warn · Unresponsive", "--warn"), ("offline", "--off"), ("info · Working", "--info"), ("stop", "--stop")]
    swatches = "".join(f'<div style="width:118px"><div style="height:40px;border-radius:9px;background:var({v});border:1px solid var(--border-strong)"></div>'
                       f'<div style="font-size:13px;margin-top:6px">{n}</div><div class="mono faint" style="font-size:11.5px">{v}</div></div>' for n, v in sw)

    def sec(title, inner, extra=""):
        return f'<div class="card" style="padding:20px 22px;{extra}"><div style="font-size:16.5px;font-weight:600;margin-bottom:14px">{title}</div>{inner}</div>'
    return (sec("Status pills · every status has a word and an icon, never the amber accent",
                f'<div class="row gap8" style="flex-wrap:wrap">{pills1}</div><div class="row gap8" style="flex-wrap:wrap;margin-top:12px">{pills2}</div>'
                f'<div class="row gap16" style="margin-top:16px;padding-top:16px;border-top:1px solid var(--border)">{sel}</div>')
            + f'<div style="height:16px"></div>' + sec("Buttons", f'<div class="row gap10" style="flex-wrap:wrap">{btns1}</div><div class="row gap10" style="margin-top:12px;flex-wrap:wrap">{btns2}</div>')
            + f'<div class="row gap16" style="margin-top:16px;align-items:stretch">{sec("Inputs", inputs, "flex:1")}'
            + sec("Toasts, help popover, sensor readout", f'{toasts}<div class="row gap12" style="align-items:flex-start">{popover}{readout}</div>', "flex:1") + "</div>"
            + f'<div class="row gap16" style="margin-top:16px;align-items:stretch">{sec("Type scale · Inter as SF Pro stand-in, IBM Plex Mono", types, "flex:1")}'
            + sec("Colour tokens", f'<div class="row gap10" style="flex-wrap:wrap">{swatches}</div>', "flex:1.2") + "</div>")


# ---------------------------------------------------------------- phone
# Every desktop screen again at 390 px wide. Same data and parts; what changes on a phone:
# the sidebar becomes a bottom tab bar, Stop all stays in the top bar on every screen,
# the robot's tabs become a sideways-scrolling row, dialogs become bottom sheets,
# the drive pad is for touch (no key letters) and the camera starts on Low · 5 fps.

CSS += r"""
/* phone */
.phone{width:390px;min-height:844px;background:var(--bg);display:flex;flex-direction:column;position:relative}
.ptop{height:66px;flex:none;display:flex;align-items:center;gap:12px;padding:0 14px 0 16px;border-bottom:1px solid var(--border);background:var(--topbar)}
.ptop .t{font-size:17px;font-weight:600;display:flex;align-items:center;gap:4px;line-height:1.25}
.ptop .s{font-size:12px;color:var(--text-2);display:flex;align-items:center;gap:6px;white-space:nowrap;overflow:hidden}
.ptop .stopall{height:38px;padding:0 12px;font-size:14.5px;gap:6px}
.pbody{padding:14px;display:flex;flex-direction:column;gap:12px}
.ptab{margin-top:auto;flex:none;display:flex;border-top:1px solid var(--border);background:var(--topbar);padding:10px 0 22px}
.ptab div{flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;font-size:12px;color:var(--text-2)}
.ptab div.on{color:var(--text)} .ptab div.on svg{color:var(--accent)}
.ptabs{display:flex;gap:6px;overflow:hidden;margin:0 -14px;padding:0 14px}
.ptabs span{flex:none;display:flex;align-items:center;gap:6px;height:36px;padding:0 13px;border-radius:999px;border:1px solid var(--border);background:var(--surface);color:var(--text-2);font-size:13.5px}
.ptabs span.on{background:var(--accent-soft);border-color:var(--accent-border);color:var(--text)}
.ptabs span.on svg{color:var(--accent)}
.bigstop{width:100%;height:50px;font-size:16.5px;border-radius:14px}
.pscrim{position:absolute;left:0;right:0;top:66px;bottom:0;background:var(--overlay);z-index:5}
.sheet{position:absolute;left:0;right:0;bottom:0;z-index:6}
.sheet .grab{position:absolute;top:8px;left:50%;width:40px;height:5px;margin-left:-20px;border-radius:3px;background:var(--border-strong);z-index:1}
.sheet .dlg{width:auto!important;border-radius:22px 22px 0 0;border-bottom:0;box-shadow:0 -14px 40px rgba(0,0,0,.45)}
.sheet .dlg-h{padding:26px 18px 0}
.sheet .dlg-b{padding:14px 18px 16px}
.sheet .dlg-f{flex-direction:column-reverse;align-items:stretch;gap:8px;padding:12px 18px 30px}
.sheet .dlg-f .btn{width:100%;height:46px;font-size:15px}
.sheet .dlg-f>.grow,.sheet .dlg-f>.help{display:none}
.prow{display:flex;align-items:center;gap:10px;padding:11px 0;border-bottom:1px solid var(--border)}
.prow:last-child{border-bottom:0}
.ph2{font-size:20px;font-weight:600}
"""

PHONE_TABS = [("fleet", "layout-grid", "Fleet"), ("history", "history", "History"), ("health", "activity", "Health"),
              ("help", "circle-help", "Help")]


def phone_tabbar(active="fleet"):
    return '<div class="ptab">' + "".join(f'<div class="{"on" if k == active else ""}">{icon(ic, 21)}{t}</div>'
                                          for k, ic, t in PHONE_TABS) + "</div>"


PHONE_SUBS = {
    "ok": '<span class="dot"></span>Hub connected · 3 of 4 online',
    "none": '<span class="dot"></span>Hub connected · no robots yet',
    "one": '<span class="dot"></span>Hub connected · 1 of 1 online',
}


def phone_top(title, back=False, sub="ok", stop_all=True):
    lead = icon("chevron-left", 22, color="var(--text-2)") if back else LOGO
    if sub == "down":
        s = (f'<span style="color:var(--warn-text);display:flex;align-items:center;gap:5px">'
             f'{icon("triangle-alert", 13)}Hub unreachable · reconnecting…</span>')
    else:
        s = PHONE_SUBS.get(sub, sub)
    sa = stopbtn("Stop all", None, "stopall", size=17) if stop_all else ""
    return f'<div class="ptop">{lead}<div class="grow"><div class="t">{title}</div><div class="s">{s}</div></div>{sa}</div>'


def phone(title, body, back=False, sub="ok", active="fleet", overlay="", stop_all=True, tabbar=True):
    """A phone screen. With an overlay (a bottom sheet) the page dims, but the top bar with Stop all stays sharp."""
    top = phone_top(title, back, sub, stop_all)
    tb = phone_tabbar(active) if tabbar else ""
    if not overlay:
        return f'<div class="phone">{top}<div class="pbody">{body}</div>{tb}</div>'
    return (f'<div class="phone" style="height:844px;overflow:hidden">{top}'
            f'<div class="dim col" style="flex:1;overflow:hidden"><div class="pbody">{body}</div>{tb}</div>'
            f'<div class="pscrim"></div><div class="sheet"><div class="grab"></div>{overlay}</div></div>')


def phead(title, sub=None, right=""):
    s = f'<div class="sub">{sub}</div>' if sub else ""
    return f'<div class="row gap8"><div class="grow"><div class="row gap8"><span class="ph2">{title}</span>{helpdot()}</div>{s}</div>{right}</div>'


def pcard(title, ic, inner, right="", pad=True):
    head = (f'<div class="row gap8" style="padding:13px 14px;border-bottom:1px solid var(--border)">{icon(ic, 17)}'
            f'<b style="font-size:15px;font-weight:600">{title}</b>{helpdot()}<div class="grow"></div>{right}</div>')
    return f'<div class="card">{head}<div style="{"padding:12px 14px" if pad else ""}">{inner}</div></div>'


# ---- sign in

def p_sign_in(error=False):
    brand, card, note = sign_in_parts(error)
    card = card.replace("width:400px;padding:28px", "width:100%;padding:22px")
    return (f'<div class="phone" style="height:844px;padding:0 16px;align-items:center;justify-content:center;'
            f'background:radial-gradient(ellipse 340px 300px at 50% 20%,rgba(232,172,101,.07),transparent),var(--bg)">'
            f'{brand}{card}{note.replace("margin-top:22px", "margin-top:22px;text-align:center;justify-content:center")}</div>')


# ---- fleet

def p_fleet_card(k, stale=False):
    r = ROBOTS[k]
    pills = status_pill(r["status"], True) + (moving_pill(True) if r["moving"] else "") + ctrl_pill(r["ctrl"], True)
    info = f'{r["seen_short"]} · {r["lat"]}' + (f' · {r["dist"]} cm' if r["dist"] else "")
    if stale:
        info = f'<span style="color:var(--warn-text);display:inline-flex;gap:4px;align-items:center">{icon("clock", 12)}24 s ago</span> · {info}'
    return (f'<div class="card" style="padding:14px"><div class="row gap12" style="align-items:flex-start"><span class="mg">{r["mg"]}</span>'
            f'<div class="grow"><div class="row gap8"><span style="font-size:15px;font-weight:500">{r["name"]}</span><span class="mono faint" style="font-size:12px">{r["host"]}</span></div>'
            f'<div class="row gap6" style="flex-wrap:wrap;margin-top:7px;{"opacity:.75" if stale else ""}">{pills}</div></div></div>'
            f'<div class="row gap8" style="margin-top:12px"><span class="muted grow" style="font-size:12.5px">{info}</span><span class="btn sm">Open</span>'
            f'{stopbtn(off=r["status"] == "offline", cls="sm")}</div></div>')


def p_fleet(stale=False, toast=True):
    banner = ""
    if stale:
        banner = (f'<div class="note warn" style="align-items:flex-start">{icon("triangle-alert", 18)}<div class="grow">'
                  f'<b style="font-weight:600">Can\'t reach the hub. Reconnecting…</b>'
                  f'<div class="muted" style="font-size:12.5px;margin-top:2px">Everything below may be out of date. Last update 24 s ago. '
                  f'If you were driving, the hub stops that robot when your connection drops.</div>'
                  f'<div class="row gap8" style="margin-top:10px"><span class="muted row gap6" style="font-size:12.5px">{icon("loader-circle", 14)}Trying again in 3 s</span>'
                  f'<div class="grow"></div><span class="btn sm">{icon("refresh-cw", 14)}Retry now</span></div></div></div>')
    t = ""
    if toast and not stale:
        t = (f'<div class="card row gap12" style="padding:12px 14px;background:var(--surface-raised)"><span class="mg" style="width:32px;height:32px">{icon("lock", 15)}</span>'
             f'<div><div style="font-weight:500">sara took control of Rover</div><div class="muted" style="font-size:12.5px">3 min ago · you can still press Stop</div></div></div>')
    head = phead("Robots", "4 robots on this hub · up to 4", f'<span class="btn sm primary">{icon("plus", 15)}Add</span>')
    return banner + head + "".join(p_fleet_card(k, stale) for k in ROBOTS) + t


def p_fleet_empty():
    need = "".join(f'<div class="row gap10" style="margin-top:10px;align-items:flex-start;font-size:13.5px">{icon(ic, 16, color="var(--text-2)")}<span>{t}</span></div>' for ic, t in
                   [("wifi", "The robot switched on and on the lab Wi-Fi"),
                    ("hash", 'Its IP address, e.g. <span class="mono">192.168.149.1</span>'),
                    ("key-round", "Its password (used once, not saved)")])
    return (phead("Robots", "No robots on this hub yet · up to 4") +
            f'<div style="border:1px dashed var(--border-strong);border-radius:16px;padding:34px 18px 22px;display:flex;flex-direction:column;align-items:center;text-align:center">'
            f'<div class="mg lg">{icon("bot", 22)}</div><div style="font-size:17px;font-weight:600;margin-top:16px">No robots yet. Press Add robot to set one up.</div>'
            f'<p class="muted" style="margin-top:8px;font-size:14px">The hub installs its program on the robot for you. It takes a few minutes the first time.</p>'
            f'<div class="card" style="width:100%;padding:14px 16px;margin-top:20px;text-align:left"><div class="muted" style="font-size:13px">What you need</div>{need}</div>'
            f'<span class="btn primary" style="margin-top:20px;height:46px;width:100%;font-size:15px">{icon("plus", 16)}Add robot</span></div>')


# ---- robot view

def p_robot_tabs(active, locked=False):
    out = []
    for t, ic in TABS:
        lock = icon("lock", 12, color="var(--text-3)") if locked and t in ("Drive", "Arm") else ""
        out.append(f'<span class="{"on" if t == active else ""}">{icon(ic, 15)}{t}{lock}</span>')
    return f'<div class="ptabs">{"".join(out)}</div>'


def p_camera(rkey, mini=False):
    r = ROBOTS[rkey]
    stale = r["status"] == "unresponsive"
    variant = 1 if rkey == "rover" else (2 if rkey == "scout" else 0)
    if mini:
        lbl = (f'<span style="color:var(--warn-text);display:flex;gap:4px;align-items:center">{icon("triangle-alert", 12)}6 s ago</span>' if stale
               else '<span style="width:6px;height:6px;border-radius:50%;background:#fff"></span>Live')
        return (f'<div class="cam" style="width:132px;height:99px;flex:none">{scene(stale, variant)}'
                f'<div class="ov" style="top:6px;left:6px;height:22px;font-size:11.5px;padding:0 7px">{lbl}</div></div>')
    top = (f'<span style="color:var(--warn-text);display:flex;gap:6px;align-items:center">{icon("triangle-alert", 14)}Last picture 6 s ago · reconnecting</span>'
           if stale else '<span style="width:6px;height:6px;border-radius:50%;background:#fff"></span>Live · <span class="num">5 fps</span>')
    return camera(362, quality="low", top=top, dark=stale, variant=variant)


def p_robot(rkey, tab, content, mini=False, header_ctrl="keep", moving=None, locked=False, overlay=""):
    """The robot page on a phone, in the layout of the first approved phone screen: camera, status, the
    robot's big Stop, then the controls straight underneath, so the camera stays in view while you drive.
    Take control / Release sit in the Drive and Arm card headers, next to the controls they unlock."""
    r = ROBOTS[rkey]
    ctrl = r["ctrl"] if header_ctrl == "keep" else header_ctrl
    mv = r["moving"] if moving is None else moving
    pills = (f'<div class="row gap6" style="flex-wrap:wrap">{status_pill(r["status"], True)}{moving_pill(True) if mv else ""}'
             f'{ctrl_pill(ctrl, True)}</div>')
    slow = f' <span style="color:var(--warn-text)">slow</span>' if r["status"] == "unresponsive" else ""
    sub = f'<span class="mono">{r["host"]}</span> · <span class="num">{r["lat"]}</span>{slow} · {r["seen"]}'
    title = f'{r["name"]}{icon("chevron-down", 16, color="var(--text-2)")}'
    if mini:   # tabs without the camera keep a small live picture, so you still see the robot
        head = (f'<div class="row gap12" style="align-items:flex-start">{p_camera(rkey, True)}<div class="col gap8">'
                f'<div class="row gap6" style="flex-wrap:wrap">{status_pill(r["status"], True)}{moving_pill(True) if mv else ""}{ctrl_pill(ctrl, True)}</div>'
                f'<span class="muted" style="font-size:12px">The camera stays live on every tab. Tap it to make it bigger.</span></div></div>')
    else:
        head = p_camera(rkey) + pills
    stop = f'<div class="btn stop" style="width:100%;height:52px;font-size:17px;border-radius:14px">{icon("octagon", 20)}Stop {r["name"]}</div>'
    return phone(title, head + p_robot_tabs(tab, locked) + stop + content, back=True, sub=sub, overlay=overlay)


def control_action(mode):
    """The button that goes with who's in control: Release (you), Take control (nobody), or a Watching tag."""
    if mode == "you":
        return f'<span class="btn sm">{icon("lock-open", 14)}Release</span>'
    if mode == "ro":
        return f'<span class="pill sm p-ctl" style="padding-left:8px">{icon("eye", 13)}Watching</span>'
    return f'<span class="btn sm primary">{icon("gamepad-2", 14)}Take control</span>'


def p_drive(mode="you", lat="18 ms"):
    """The first phone design's pad: six touch buttons in one row, right under the big Stop.
    Hold a button to move; let go and the robot stops."""
    keys = [("Q", "rotate-ccw"), ("W", "arrow-up"), ("E", "rotate-cw"), ("A", "arrow-left"), ("S", "arrow-down"), ("D", "arrow-right")]
    pad = "".join(f'<div class="key {"held" if (mode == "you" and k == "W") else ("ro" if mode == "ro" else "")}" style="height:56px;flex:1;font-size:11px">'
                  f'{icon(ic, 18)}<span class="mono">{k}</span></div>' for k, ic in keys)
    head = (f'<div class="row gap10"><b style="font-weight:500;font-size:15px">Drive</b><div class="grow"></div>'
            f'<span class="muted" style="font-size:13px">Speed <b style="color:var(--text);font-weight:500">40%</b></span>{control_action(mode)}</div>')
    if mode == "ro":
        tail = f'<div class="note" style="margin-top:12px;font-size:13px">{icon("lock", 15)}Read-only while sara is in control. The red Stop still works.</div>'
    else:
        send = ("Sending: <b>Forward +0.40</b> · Strafe 0.00 · Rotate 0.00" if mode == "you"
                else "Sending: Forward 0.00 · Strafe 0.00 · Rotate 0.00")
        tail = (f'<div class="sending" style="margin-top:12px;font-size:11.5px">{send}</div>'
                f'<p class="muted" style="font-size:12.5px;margin-top:10px">Hold a button to move; let go and the robot stops.</p>')
    readout = (f'<p class="muted" style="text-align:center;font-size:13px">Distance <b style="color:var(--text);font-weight:500">'
               f'{"118" if mode == "ro" else "42"} cm</b>&nbsp;&nbsp;&nbsp;Turned <b style="color:var(--text);font-weight:500">{"−12.0" if mode == "ro" else "87.5"}°</b></p>')
    return f'<div class="card" style="padding:14px">{head}<div class="row gap6" style="margin-top:12px">{pad}</div>{tail}</div>{readout}'


def p_arm(mode="you"):
    """Five joints, one line each, under the big Stop so you can watch the arm move in the camera."""
    rows = []
    for n, v in ARM:
        p = (v - 500) / 2000 * 100
        rows.append(f'<div class="row gap10" style="height:38px"><span style="width:66px;font-size:13.5px">{n}</span>'
                    f'<div class="slider grow"><div class="tr"></div><div class="fill" style="width:{p:.1f}%"></div><div class="th" style="left:{p:.1f}%"></div></div>'
                    f'<b class="mono num" style="font-weight:500;font-size:12.5px;width:62px;text-align:right">{v} µs</b></div>')
    head = (f'<div class="row gap10" style="margin-bottom:4px"><b style="font-weight:500;font-size:15px">Arm</b><div class="grow"></div>'
            f'<span class="muted" style="font-size:13px">500–2500 µs</span>{control_action(mode)}</div>')
    btns = (f'<div class="row gap8" style="margin-top:8px">{stopbtn("Stop (arm holds)", cls="grow")}'
            f'<span class="btn danger-soft grow">{icon("hand", 16)}Release (go limp)</span></div>')
    note = (f'<p class="muted" style="font-size:12.5px;margin-top:10px">Nothing is sent until you move a slider. '
            f'A joint\'s first move after the robot restarts jumps straight to the slider, so start close to where it really is.</p>')
    return f'<div class="card" style="padding:14px">{head}{"".join(rows)}{btns}{note}</div>'


def p_sensors(calibrating=False):
    pts = [(0, 38), (40, 40), (70, 38), (100, 46), (140, 58), (175, 64), (200, 62), (240, 52), (280, 40), (320, 24), (350, 12),
           (370, 14), (400, 26), (440, 38), (480, 44), (520, 48), (560, 51), (600, 52)]
    line = " ".join(f"{x},{y}" for x, y in pts)
    chart = (f'<svg width="100%" height="70" viewBox="0 0 600 80" preserveAspectRatio="none"><line x1="0" y1="2" x2="600" y2="2" stroke="var(--border-strong)" stroke-dasharray="3 4"/>'
             f'<polygon points="0,80 {line} 600,80" fill="var(--info)" fill-opacity=".15"/>'
             f'<polyline points="{line}" fill="none" stroke="var(--info)" stroke-width="2"/></svg>')
    dist = (f'<div class="row gap12"><div class="num" style="font-size:36px;font-weight:500;line-height:1;white-space:nowrap">42<small style="font-size:15px;color:var(--text-2);font-weight:400"> cm</small></div>'
            f'<span class="muted" style="font-size:12.5px">Since you opened this: lowest <b style="color:var(--text);font-weight:500">12 cm</b>, highest <b style="color:var(--text);font-weight:500">180 cm</b></span></div>'
            f'<div style="margin-top:10px;position:relative">{chart}<span class="faint" style="position:absolute;right:0;top:4px;font-size:11px">200 cm</span></div>'
            f'<div class="row between faint" style="font-size:11px"><span>3 min ago</span><span>now</span></div>'
            f'<div class="note good" style="margin-top:10px;font-size:13px">{icon("circle-check", 16)}Working: the reading follows what is in front of the sensor.</div>')
    tiltsvg = ('<svg width="56" height="56" viewBox="0 0 66 66"><circle cx="33" cy="33" r="31" fill="none" stroke="var(--border-strong)"/>'
               '<circle cx="33" cy="33" r="16" fill="none" stroke="var(--border-strong)" stroke-dasharray="2 3"/>'
               '<line x1="33" y1="4" x2="33" y2="62" stroke="var(--border)"/><line x1="4" y1="33" x2="62" y2="33" stroke="var(--border)"/>'
               + ('' if calibrating else '<circle cx="34" cy="31" r="5" fill="var(--text)"/>') + '</svg>')
    if calibrating:
        right = f'<span class="pill sm p-info">{icon("loader-circle", 13)}Calibrating…</span>'
        turned = '<div class="faint" style="font-size:22px;margin-top:6px">—</div>'
        tilt = '<div class="faint num" style="font-size:13px">X —<br>Y —</div>'
        speed = 'Speed <span style="margin-left:12px">X —</span><span style="margin-left:12px">Y —</span><span style="margin-left:12px">Z —</span>'
        bottom = (f'<div class="note info" style="margin-top:12px;align-items:flex-start">{icon("loader-circle", 18)}<div class="grow">'
                  f'<b style="font-weight:500">Calibrating… keep the robot still</b><div class="muted" style="font-size:12.5px">Readings come back in about 2 seconds.</div></div></div>'
                  f'<span class="btn dis" style="width:100%;margin-top:10px">{icon("crosshair", 15)}Calibrate gyro</span>')
    else:
        right = ""
        turned = '<div class="num" style="font-size:28px;font-weight:500;margin-top:4px">87.5°</div><div class="muted" style="font-size:13px">left of the start</div>'
        tilt = '<div class="num" style="font-size:13px">X 0.4°<br>Y −1.2°</div>'
        speed = ('Speed <span style="margin-left:12px">X <b class="num" style="font-weight:500">0 °/s</b></span>'
                 '<span style="margin-left:12px">Y <b class="num" style="font-weight:500">0 °/s</b></span>'
                 '<span style="margin-left:12px">Z <b class="num" style="font-weight:500">32 °/s</b></span>')
        bottom = (f'<span class="btn" style="width:100%;margin-top:12px">{icon("crosshair", 15)}Calibrate gyro</span>'
                  f'<p class="muted" style="font-size:12.5px;margin-top:8px">Keep the robot still for 2 seconds. Z drifts about 1° a minute, so calibrate again to zero it.</p>')
    gyro = (f'<div class="row gap16"><div class="col" style="align-items:center;gap:4px">{dial(87.5, not calibrating)}<span class="muted" style="font-size:12px">Rotation Z</span></div>'
            f'<div class="grow"><div class="muted" style="font-size:13px">Turned (Z)</div>{turned}</div></div>'
            f'<div class="row gap12" style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border)">{tiltsvg}<div class="grow"><div class="muted" style="font-size:12.5px">Tilt X / Y</div>{tilt}</div></div>'
            f'<div class="sending" style="font-family:inherit;margin-top:12px;font-size:12.5px">{speed}</div>{bottom}')
    battery = (f'<div class="card row gap10" style="padding:12px 14px;color:var(--text-3)">{icon("battery", 16)}Battery<div class="grow"></div>'
               f'<span class="pill sm p-ctl" style="padding-left:8px;color:var(--text-2)">Coming soon</span></div>')
    return (pcard("Distance", "radar", dist, '<span class="faint" style="font-size:12px">Ultrasonic · up to 2 m</span>')
            + pcard("Gyro", "rotate-3d", gyro, right) + battery)


def p_terminal(empty=False):
    border = "border-color:var(--stop-border)"
    if empty:
        body = '<div class="mono faint" style="font-size:12px;height:90px">Nothing run yet in this session.</div>'
    else:
        body = f'<div class="mono" style="font-size:10.5px;line-height:1.7;color:var(--text);overflow-wrap:anywhere">{TERM_OUT}</div>'
    return (f'<div class="card" style="{border}"><div style="padding:12px 14px;background:var(--stop-bg);border-bottom:1px solid var(--stop-border);border-radius:14px 14px 0 0">'
            f'<div class="row gap8">{icon("terminal", 17, color="#F87171")}<b style="font-weight:600">Terminal on Clanker</b><div class="grow"></div>'
            f'<span class="help" style="color:#F87171;border-color:var(--stop-border)">{icon("circle-help", 13)}</span></div>'
            f'<div class="muted" style="font-size:12.5px;margin-top:3px">Runs as pi · every command is logged</div></div>'
            f'<div style="padding:12px;background:var(--surface-deep)">{body}</div>'
            f'<div class="row gap8" style="padding:10px 12px;border-top:1px solid var(--border)">'
            f'<div class="inp grow mono" style="height:42px;font-size:12.5px;padding:0 10px"><span class="faint">~/swarm-agent $</span><span class="caret"></span></div>'
            f'<span class="btn primary" style="height:42px">{icon("corner-down-left", 15)}Run</span></div>'
            f'<p class="muted" style="font-size:12.5px;padding:10px 14px 12px;border-top:1px solid var(--border)">One command at a time, stops after 30 seconds. '
            f'Programs that need typing (nano, top) won\'t work. <span style="color:var(--text)">Clear</span></p></div>')


def p_info():
    rows = "".join(f'<div class="prow" style="font-size:13.5px"><span class="muted" style="width:128px;flex:none">{k}</span><span class="row gap6">{_info_value(v)}</span></div>'
                   for k, v in INFO_ROWS)
    caps = "".join(f'<span class="pill sm p-ctl" style="padding-left:8px">{icon(ic, 13)}{t}</span>' for ic, t in INFO_CAPS)
    joints = "".join(f'<div style="padding:9px 11px;border:1px solid var(--border);border-radius:10px"><div class="mono" style="font-size:12.5px">{j}</div>'
                     f'<div class="muted num" style="font-size:12px">500–2500</div></div>' for j in ("base", "shoulder", "elbow", "wrist", "gripper"))
    sens = "".join(f'<span class="code" style="font-size:11.5px">{s}</span>' for s in INFO_SENSORS)
    inner = (f'{rows}<div class="muted" style="font-size:13px;margin:12px 0 8px">What it can do</div><div class="row gap6" style="flex-wrap:wrap">{caps}</div>'
             f'<div class="muted" style="font-size:13px;margin:14px 0 8px">Arm joints and limits (µs)</div>'
             f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px">{joints}</div>'
             f'<div class="muted" style="font-size:13px;margin:14px 0 8px">Sensors</div><div class="row gap6" style="flex-wrap:wrap">{sens}</div>'
             f'<div class="row gap8" style="margin-top:16px"><span class="btn grow">{icon("download", 15)}Update…</span>'
             f'<span class="btn danger-soft grow">{icon("trash-2", 15)}Remove…</span></div>')
    return pcard("Info", "info", inner)


def p_activity():
    rows = "".join(f'<div class="prow" style="align-items:flex-start;padding:11px 14px"><span class="num muted" style="width:64px;flex:none;font-size:12.5px;padding-top:1px">{t}</span>'
                   f'<div class="grow"><div class="row gap6" style="font-size:12.5px;color:var(--text-2)">'
                   + (f'<span class="av" style="width:18px;height:18px;font-size:8.5px">{p[:2].upper()}</span>{p}' if p else '<span class="faint">the robot</span>')
                   + f'</div><div class="row gap6" style="margin-top:4px;align-items:flex-start;font-size:13.5px">{icon(ic, 15, color="var(--text-2)")}<span>{w}</span></div></div></div>'
                   for t, p, ic, w in ACT)
    foot = (f'<div class="row between" style="padding:12px 14px;border-top:1px solid var(--border)"><span class="faint" style="font-size:12.5px">9 of 11 today</span>'
            f'<span class="row gap6" style="font-size:13px">Open in History{icon("arrow-right", 14)}</span><span class="btn sm">Load more</span></div>')
    return pcard("Activity", "history", rows + foot, '<span class="faint" style="font-size:12.5px">Clanker · today</span>', pad=False)


def p_switcher():
    """The phone's version of the hideable robot list: a sheet opened from the robot's name."""
    rows = []
    for k, r in ROBOTS.items():
        sel = " sel" if k == "clanker" else ""
        dim = ' style="opacity:.8"' if r["status"] != "connected" else ""
        extra = (moving_pill(sm=True) if r["moving"] else "") + (ctrl_pill(r["ctrl"], sm=True) if r["ctrl"] else "")
        rows.append(f'<div class="rrow{sel}"{dim}><div class="row gap10"><span class="mg" style="width:32px;height:32px;font-size:11.5px">{r["mg"]}</span>'
                    f'<div class="grow"><div style="font-size:14.5px">{r["name"]}</div><div class="mono faint" style="font-size:11.5px">{r["host"]}</div></div>'
                    f'{stopbtn(off=r["status"] == "offline", cls="sm")}</div>'
                    f'<div class="row gap6" style="margin-top:8px;flex-wrap:wrap">{status_pill(r["status"], sm=True)}{extra}</div></div>')
    return (f'<div class="dlg"><div class="dlg-h"><div class="grow"><h2>Switch robot</h2><p class="muted" style="margin-top:4px;font-size:13.5px">3 of 4 online</p></div>'
            f'<span style="color:var(--text-2)">{icon("x", 18)}</span></div><div class="dlg-b"><div class="list">{"".join(rows)}</div>'
            f'<p class="muted" style="font-size:12.5px;margin-top:12px">Switching robots closes this one\'s panel: your buttons stop sending, and your control of it is released. '
            f'You don\'t get control of the next robot until you take it.</p></div></div>')


# ---- other pages

def p_history():
    def sel(ic, t):
        return (f'<div class="inp grow" style="height:42px;font-size:14px;background:var(--surface-deep)">{icon(ic, 15, color="var(--text-2)")}'
                f'<span class="grow">{t}</span>{icon("chevron-down", 15, color="var(--text-2)")}</div>')
    types = [("All", None), ("Connections", "wifi"), ("Control", "lock"), ("Stops", "octagon"), ("Terminal", "terminal"), ("Installs", "download")]
    chips = "".join((f'<span class="btn sm primary" style="flex:none">{t}</span>' if ic is None else f'<span class="btn sm" style="flex:none">{icon(ic, 14)}{t}</span>')
                    for t, ic in types)
    filters = (f'<div class="card" style="padding:12px 14px"><div class="row gap8">{sel("bot", "All robots")}{sel("user", "Anyone")}</div>'
               f'<div class="row" style="margin-top:8px">{sel("calendar", "Today · 10 Nov 2026")}</div>'
               f'<div class="row gap6" style="margin:12px -14px 0;padding:0 14px;overflow:hidden">{chips}</div></div>')
    rows = []
    for t, rob, who, ic, typ, what in HIST[:14]:
        rc = (f'<span class="mg sm" style="width:18px;height:18px;font-size:8.5px;border-radius:5px">{rob[:2]}</span>{rob[3:]}' if rob else 'All robots')
        pc = f' · {who}' if who else ""
        rows.append(f'<div class="prow" style="align-items:flex-start;padding:11px 14px"><span class="num muted" style="width:64px;flex:none;font-size:12.5px;padding-top:1px">{t}</span>'
                    f'<div class="grow"><div class="row gap6" style="font-size:12.5px;color:var(--text-2)">{rc}{pc}<div class="grow"></div>{icon(ic, 13)}{typ}</div>'
                    f'<div style="margin-top:4px;font-size:13.5px">{what}</div></div></div>')
    foot = (f'<div class="row between" style="padding:12px 14px;border-top:1px solid var(--border)"><span class="faint" style="font-size:12.5px">14 of 20 today · newest first</span>'
            f'<span class="btn sm">Load more</span></div>')
    return (phead("Everything that happened", "Connections, who took control, stops, terminal commands, installs. Kept for 90 days.")
            + filters + f'<div class="card">{"".join(rows)}{foot}</div>')


def p_health():
    tiles = []
    for name, val, sub, gauge in HEALTH_TILES:
        span = "grid-column:span 2;" if gauge else ""
        tiles.append(f'<div class="card" style="{span}padding:12px 13px;background:var(--surface-deep)"><div class="muted" style="font-size:12.5px">{name}</div>'
                     f'<div class="num" style="font-size:22px;font-weight:500;margin:4px 0 2px">{val}</div><div class="muted" style="font-size:12px">{sub}</div>'
                     f'{temp_gauge() if gauge else ""}</div>')
    hub = (f'<div class="card"><div class="row gap8" style="padding:13px 14px;border-bottom:1px solid var(--border)">{icon("server", 17)}<div class="grow">'
           f'<b style="font-size:15px;font-weight:600">Hub machine</b><div class="muted" style="font-size:12.5px">Raspberry Pi 5 in the lab</div></div>{status_pill("connected", sm=True)}</div>'
           f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:12px 14px">{"".join(tiles)}</div></div>')
    robots = []
    for k, lat, sp, rec, seen in health_robots():
        r = ROBOTS[k]
        if sp is None:
            sp = '<div style="height:32px;border:1px dashed var(--border-strong);border-radius:8px;display:flex;align-items:center;padding-left:10px;font-size:12.5px" class="muted">No data · offline for 3 h</div>'
        warn = k == "scout"
        w = f' <span style="color:var(--warn-text);font-size:12px">{icon("triangle-alert", 12)}</span>' if warn else ""

        def stat(lbl, v):
            return f'<div class="grow"><div class="muted" style="font-size:12px">{lbl}</div><div class="num" style="font-size:14.5px">{v}</div></div>'
        robots.append(f'<div style="padding:12px 14px;border-bottom:1px solid var(--border)"><div class="row gap10"><span class="mg" style="width:30px;height:30px;font-size:11.5px">{r["mg"]}</span>'
                      f'<div class="grow"><div>{r["name"]}</div><div class="mono faint" style="font-size:11.5px">{r["host"]}</div></div>{status_pill(r["status"], sm=True)}</div>'
                      f'<div class="row gap8" style="margin-top:10px">{stat("Latency now", lat + w)}{stat("Reconnects (24 h)", rec + w)}{stat("Last seen", seen)}</div>'
                      f'<div style="margin-top:8px">{sp}</div><div class="row between faint" style="font-size:11px;width:240px"><span>1 h ago</span><span>now</span></div></div>')
    rcard = (f'<div class="card"><div style="padding:13px 14px;border-bottom:1px solid var(--border)"><div class="row gap8">{icon("radio", 17)}<b style="font-size:15px;font-weight:600">Robots</b></div>'
             f'<div class="muted" style="font-size:12.5px;margin-top:3px">Latency under 50 ms is good; over 200 ms feels laggy.</div></div>{"".join(robots)}</div>')
    note = (f'<div class="note warn" style="align-items:flex-start">{icon("triangle-alert", 17)}<span><b style="font-weight:600">Scout keeps reconnecting: check its Wi-Fi</b>'
            f'<span class="muted"> · 7 reconnects in the last 24 h. Everything else is fine.</span></span></div>')
    return phead("Health", "How the hub machine in the lab is doing, and how good each robot's connection is.") + note + hub + rcard


def p_help():
    search = (f'<div class="inp" style="background:var(--surface)">{icon("search", 16, color="var(--text-2)")}'
              f'<span class="ph">Search help, e.g. "calibrate"</span></div>')
    arts = "".join(f'<div class="prow" style="padding:12px 14px;align-items:flex-start"><span class="mg" style="width:32px;height:32px">{icon(ic, 16)}</span>'
                   f'<div class="grow"><div style="font-size:15px;font-weight:600">{t}</div><div class="muted" style="font-size:13px;margin-top:2px">{d}</div>'
                   f'<div class="faint" style="font-size:12px;margin-top:4px">{rt}</div></div>{icon("chevron-right", 16, color="var(--text-3)")}</div>'
                   for ic, t, d, rt in HELP_ARTS)

    def box(ic, t, d):
        return (f'<div style="border:1px solid var(--border-strong);border-radius:12px;padding:11px 14px;background:var(--surface-deep)">'
                f'<div class="row gap8" style="font-weight:500">{icon(ic, 16)}{t}</div><div class="muted" style="font-size:12.5px;margin-top:2px">{d}</div></div>')

    def link(t):
        return (f'<div class="row gap10" style="padding:6px 0 6px 20px;font-size:12.5px"><div style="width:1px;height:30px;background:var(--border-strong)"></div>'
                f'<span class="muted">{t}</span></div>')
    rb = "".join(f'<span class="row gap6" style="border:1px solid var(--border-strong);border-radius:9px;padding:6px 9px;background:var(--surface-deep);font-size:13px">'
                 f'<span class="mg sm" style="width:20px;height:20px;font-size:9px">{r["mg"]}</span>{r["name"]}</span>' for r in ROBOTS.values())
    diagram = (f'<div style="padding:14px">{box("laptop", "The app", "In your browser, on a team laptop or phone")}'
               f'{link("Tailscale (private network): sign-in · live updates · camera")}'
               f'{box("server", "The hub", "Raspberry Pi 5 in the lab. Keeps history, checks who is in control")}'
               f'{link("Lab Wi-Fi: commands · heartbeats every second")}'
               f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">{rb}</div>'
               f'<p class="muted" style="margin-top:12px;font-size:13px">Robots only talk to the hub, never to your phone. If the hub goes silent for 3 seconds, every robot stops by itself. '
               f'If your connection drops while you drive, the robot stops within half a second.</p></div>')
    me = (f'<div class="card row gap10" style="padding:12px 14px"><span class="mg" style="width:34px;height:34px;font-size:12px">AS</span>'
          f'<div class="grow"><b style="font-weight:500">asmaa</b><div class="muted" style="font-size:12.5px">Signed in</div></div>'
          f'<span class="btn sm">{icon("log-out", 15)}Sign out</span></div>')
    return (phead("Help", "Short answers. Every panel's <b>?</b> opens the matching article.") + search
            + f'<div class="card">{arts}</div>'
            + f'<div class="card"><div class="row gap8" style="padding:13px 14px;border-bottom:1px solid var(--border)">{icon("network", 17)}'
              f'<b style="font-size:15px;font-weight:600">How the system works</b></div>{diagram}</div>' + me)


def p_help_article():
    art, side = help_article_parts()
    art = (art.replace("padding:28px 34px;flex:1", "padding:18px 16px")
              .replace("font-size:28px;font-weight:600;margin:22px 0 12px", "font-size:23px;font-weight:600;margin:18px 0 10px")
              .replace("font-size:15px;line-height:1.6", "font-size:14.5px;line-height:1.55"))
    side = side.replace("width:300px", "width:auto")
    return art + side


# ---- components

def p_components():
    def sec(t, inner, note=""):
        n = f'<p class="muted" style="font-size:12.5px;margin-top:10px">{note}</p>' if note else ""
        return f'<div class="card" style="padding:14px"><div style="font-size:15px;font-weight:600;margin-bottom:12px">{t}</div>{inner}{n}</div>'

    def framed(x):
        return f'<div style="border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:8px">{x}</div>'
    tops = (framed(phone_top("Fleet")) + framed(phone_top(f'Clanker{icon("chevron-down", 16, color="var(--text-2)")}', True,
            '<span class="mono">masterpi-01</span> · 18 ms · seen now')) + framed(phone_top("Fleet", sub="down")))
    keys = (f'<div class="pad" style="gap:8px"><div class="key" style="height:66px;font-size:12px">{icon("arrow-up", 20)}Normal</div>'
            f'<div class="key held" style="height:66px;font-size:12px">{icon("arrow-up", 20)}Held</div>'
            f'<div class="key stopk" style="height:66px">{icon("octagon", 20)}Stop</div>'
            f'<div class="key ro" style="height:58px;font-size:12px">{icon("arrow-up", 20)}Read-only</div></div>')
    stops = (f'<div class="btn stop bigstop">{icon("octagon", 20)}Stop Clanker</div>'
             f'<div class="row gap8" style="margin-top:10px">{stopbtn(cls="sm")}{stopbtn("Stop", off=True, cls="sm")}'
             f'<div class="grow"></div>{stopbtn("Stop all", None, "stopall", size=17).replace("stopall", "stopall sm")}</div>')
    sheet = (f'<div style="position:relative;border:1px solid var(--border-strong);border-radius:22px 22px 0 0;background:var(--surface);padding:24px 16px 16px">'
             f'<div style="position:absolute;top:8px;left:50%;width:40px;height:5px;margin-left:-20px;border-radius:3px;background:var(--border-strong)"></div>'
             f'<b style="font-size:17px;font-weight:600">Sheet title</b><p class="muted" style="font-size:13px;margin-top:4px">What happens if you go ahead.</p>'
             f'<span class="btn primary" style="width:100%;height:46px;margin-top:14px">Main action</span><span class="btn" style="width:100%;height:46px;margin-top:8px">Cancel</span></div>')
    rules = "".join(f'<div class="row gap10" style="margin-top:8px;align-items:flex-start;font-size:13.5px">{icon(ic, 16, color="var(--text-2)")}<span>{t}</span></div>' for ic, t in
                    [("octagon", "Stop all is in the top bar on every signed-in screen, even under a sheet."),
                     ("hand", "Touch targets are at least 44 px. The drive keys are 66 px."),
                     ("camera", "The camera starts on Low · 5 fps on phones to save data."),
                     ("gamepad-2", "Hold a drive button to move; let go and the robot stops. No key letters on phones."),
                     ("camera", "On Drive and Arm, the controls sit right under the big Stop, so the camera stays in view while you drive."),
                     ("panel-left", "Dialogs open as bottom sheets. Buttons stack full width, main action on top.")])
    return (phead("Phone components", "The parts that change on a narrow screen. Everything else is the desktop set.")
            + sec("Top bar", tops, "Shows where you are and the hub's state. On a robot, tap the name to switch robots.")
            + sec("Tab bar", f'<div style="border:1px solid var(--border);border-radius:12px;overflow:hidden">{phone_tabbar("fleet")}</div>')
            + sec("Robot tabs", p_robot_tabs("Drive") + f'<div style="height:8px"></div>' + p_robot_tabs("Drive", locked=True),
                  "Scroll sideways for the rest. A lock means someone else is in control.")
            + sec("Stop buttons", stops, "The robot's own Stop is full width under the camera.")
            + sec("Drive keys", keys)
            + sec("Robot card (Fleet)", p_fleet_card("rover"))
            + sec("Bottom sheet", sheet)
            + sec("Rules", rules))


# ---------------------------------------------------------------- phone screens

def build_phone():
    cl = "clanker"
    you = p_drive("you")
    S = {}
    S["phone-01-sign-in"] = ("Phone · Sign in", p_sign_in(False))
    S["phone-02-sign-in-error"] = ("Phone · Sign in · error", p_sign_in(True))
    S["phone-03-fleet"] = ("Phone · Fleet", phone("Fleet", p_fleet()))
    S["phone-04-fleet-empty"] = ("Phone · Fleet · empty", phone("Fleet", p_fleet_empty(), sub="none"))
    S["phone-05-fleet-hub-disconnected"] = ("Phone · Fleet · hub unreachable", phone("Fleet", p_fleet(stale=True), sub="down"))
    S["phone-06-robot-you-driving"] = ("Phone · Robot · you driving", p_robot(cl, "Drive", you))
    S["phone-07-robot-someone-else-in-control"] = ("Phone · Robot · sara in control",
                                                   p_robot("rover", "Drive", p_drive("ro", "24 ms"), locked=True))
    S["phone-08-robot-nobody-in-control"] = ("Phone · Robot · nobody in control",
                                             p_robot(cl, "Drive", p_drive("free"), header_ctrl=None, moving=False))
    S["phone-09-switch-robot"] = ("Phone · Switch robot", p_robot(cl, "Drive", you, overlay=p_switcher()))
    S["phone-10-tab-arm"] = ("Phone · Tab · Arm", p_robot(cl, "Arm", p_arm()))
    S["phone-11-tab-arm-disabled"] = ("Phone · Tab · Arm · no arm board", p_robot("scout", "Arm", arm_card("none")))
    S["phone-12-tab-sensors"] = ("Phone · Tab · Sensors", p_robot(cl, "Sensors", p_sensors(), mini=True))
    S["phone-13-tab-sensors-calibrating"] = ("Phone · Tab · Sensors · calibrating", p_robot(cl, "Sensors", p_sensors(True), mini=True, moving=False))
    S["phone-14-tab-terminal"] = ("Phone · Tab · Terminal", p_robot(cl, "Terminal", p_terminal(), mini=True))
    S["phone-15-terminal-first-use-confirm"] = ("Phone · Terminal · first-use confirm",
                                                p_robot(cl, "Terminal", p_terminal(empty=True), mini=True, overlay=terminal_confirm_dialog()))
    S["phone-16-tab-info"] = ("Phone · Tab · Info", p_robot(cl, "Info", p_info(), mini=True))
    S["phone-17-tab-activity"] = ("Phone · Tab · Activity", p_robot(cl, "Activity", p_activity(), mini=True))
    S["phone-18-history"] = ("Phone · History", phone("History", p_history(), active="history"))
    S["phone-19-health"] = ("Phone · Health", phone("Health", p_health(), active="health"))
    S["phone-20-help"] = ("Phone · Help", phone("Help", p_help(), active="help"))
    S["phone-21-help-article"] = ("Phone · Help · article", phone("Control", p_help_article(), back=True, active="help"))
    empty = p_fleet_empty()
    S["phone-22-add-robot"] = ("Phone · Sheet · Add robot", phone("Fleet", empty, sub="none", overlay=add_robot_dialog()))
    S["phone-23-install-progress-running"] = ("Phone · Sheet · Installing", phone("Fleet", empty, sub="none", overlay=install_dialog("running")))
    S["phone-24-install-success"] = ("Phone · Sheet · Install done", phone("Fleet", empty, sub="one", overlay=install_dialog("done")))
    S["phone-25-install-failure"] = ("Phone · Sheet · Install failed", phone("Fleet", empty, sub="none", overlay=install_dialog("failed")))
    S["phone-26-update-robot"] = ("Phone · Sheet · Update robot", p_robot(cl, "Info", p_info(), mini=True, overlay=update_dialog()))
    S["phone-27-remove-robot"] = ("Phone · Sheet · Remove robot", phone("Fleet", p_fleet(toast=False), overlay=remove_dialog()))
    S["phone-28-confirm-release-arm"] = ("Phone · Sheet · Release arm",
                                         p_robot(cl, "Arm", p_arm(), overlay=release_arm_dialog()))
    S["phone-29-components"] = ("Phone · Components", phone("Components", p_components(), active=None))
    S["phone-30-fleet-light"] = ("Phone · Fleet · light", phone("Fleet", p_fleet()), "light")
    S["phone-31-robot-light"] = ("Phone · Robot · light", p_robot(cl, "Drive", you), "light")
    return S


# ---------------------------------------------------------------- screens

def build():
    cl = "Fleet", "Clanker"
    S = {}
    S["01-sign-in"] = ("Sign in", sign_in(False), 1440, 900)
    S["02-sign-in-error"] = ("Sign in · error", sign_in(True), 1440, 900)
    S["03-fleet"] = ("Fleet", app("fleet", crumb("Fleet"), fleet_header() + fleet_grid()), 1440, 900)
    S["04-fleet-empty"] = ("Fleet · empty", app("fleet", crumb("Fleet"), empty_fleet(), online="none", bell=0), 1440, 900)
    banner = (f'<div class="note warn" style="margin-bottom:22px;align-items:center;padding:14px 16px">{icon("triangle-alert", 22)}<div class="grow">'
              f'<b style="font-weight:600;font-size:15px">Can\'t reach the hub. Reconnecting… Everything below may be out of date.</b>'
              f'<div class="muted" style="font-size:13.5px">Last update 24 s ago. If you were driving, the hub stops that robot when your connection drops.</div></div>'
              f'<span class="muted row gap6" style="font-size:13px">{icon("loader-circle", 15)}Trying again in 3 s</span><span class="btn sm">{icon("refresh-cw", 15)}Retry now</span></div>')
    S["05-fleet-hub-disconnected"] = ("Fleet · hub unreachable", app("fleet", crumb("Fleet"), banner + fleet_header() + fleet_grid(stale=True), hub="down", height=990), 1440, 990)
    S["06-robot-list-hidden-you-driving"] = ("Robot · list hidden · you driving", app("fleet", crumb(*cl), cockpit("clanker", "Drive", control_card("you") + drive_card("you"))), 1440, 900)
    S["07-robot-someone-else-in-control"] = ("Robot · sara in control", app("fleet", crumb("Fleet", "Rover"), cockpit("rover", "Drive", control_card("other") + drive_card("ro", "24 ms") + arm_card("watch"), locked=True)), 1440, 900)
    S["08-robot-nobody-in-control"] = ("Robot · nobody in control", app("fleet", crumb(*cl), cockpit("clanker", "Drive", control_card("nobody") + drive_card("free"), header_ctrl=None, moving=False)), 1440, 900)
    S["09-robot-list-open"] = ("Robot · list open", app("fleet", crumb(*cl), cockpit("clanker", "Drive", control_card("you") + drive_card("you"), list_open=True)), 1440, 900)
    S["10-tab-arm"] = ("Tab · Arm", app("fleet", crumb(*cl), cockpit("clanker", "Arm", control_card("you") + arm_card("you"))), 1440, 900)
    S["11-tab-arm-disabled"] = ("Tab · Arm · no arm board", app("fleet", crumb("Fleet", "Scout"), cockpit("scout", "Arm", control_card("nobody") + arm_card("none"))), 1440, 900)
    S["12-tab-sensors"] = ("Tab · Sensors", app("fleet", crumb(*cl), cockpit("clanker", "Sensors", sensors_card(), cam_note=True)), 1440, 900)
    S["13-tab-sensors-calibrating"] = ("Tab · Sensors · calibrating", app("fleet", crumb(*cl), cockpit("clanker", "Sensors", sensors_card(True), cam_note=True, moving=False)), 1440, 900)
    S["14-tab-terminal"] = ("Tab · Terminal", app("fleet", crumb(*cl), cockpit("clanker", "Terminal", terminal_card())), 1440, 900)
    S["15-terminal-first-use-confirm"] = ("Terminal · first-use confirm", app("fleet", crumb(*cl), cockpit("clanker", "Terminal", terminal_card(empty=True)), overlay=terminal_confirm_dialog()), 1440, 900)
    S["16-tab-info"] = ("Tab · Info", app("fleet", crumb(*cl), cockpit("clanker", "Info", info_card())), 1440, 900)
    S["17-tab-activity"] = ("Tab · Activity", app("fleet", crumb(*cl), cockpit("clanker", "Activity", activity_card())), 1440, 900)
    S["18-history"] = ("History", app("history", crumb("History"), history_page(), height=1390), 1440, 1390)
    S["19-health"] = ("Health", app("health", crumb("Health"), health_page()), 1440, 900)
    S["20-help"] = ("Help", app("help", crumb("Help"), help_page()), 1440, 900)
    S["21-help-article"] = ("Help · article", app("help", crumb("Help", "Control"), help_article()), 1440, 900)
    empty = empty_fleet()
    S["22-add-robot"] = ("Dialog · Add robot", app("fleet", crumb("Fleet"), empty, online="none", bell=0, overlay=add_robot_dialog()), 1440, 900)
    S["23-install-progress-running"] = ("Dialog · Installing", app("fleet", crumb("Fleet"), empty, online="none", bell=0, overlay=install_dialog("running")), 1440, 900)
    S["24-install-success"] = ("Dialog · Install done", app("fleet", crumb("Fleet"), empty, online="1 of 1", bell=1, overlay=install_dialog("done")), 1440, 900)
    S["25-install-failure"] = ("Dialog · Install failed", app("fleet", crumb("Fleet"), empty, online="none", bell=1, overlay=install_dialog("failed")), 1440, 900)
    S["26-update-robot"] = ("Dialog · Update robot", app("fleet", crumb(*cl), cockpit("clanker", "Info", info_card()), overlay=update_dialog()), 1440, 900)
    S["27-remove-robot"] = ("Dialog · Remove robot", app("fleet", crumb("Fleet"), fleet_header() + fleet_grid(), overlay=remove_dialog()), 1440, 900)
    S["28-confirm-release-arm"] = ("Dialog · Release arm", app("fleet", crumb(*cl), cockpit("clanker", "Arm", control_card("you") + arm_card("you")), overlay=release_arm_dialog()), 1440, 900)
    S["29-components"] = ("Components", app("fleet", crumb("Components"), components_page(), height=1560).replace('class="on"', 'class=""', 1), 1440, 1560)
    S["30-fleet-light"] = ("Fleet · light", app("fleet", crumb("Fleet"), fleet_header() + fleet_grid()), 1440, 900, "light")
    S["31-robot-light"] = ("Robot · light", app("fleet", crumb(*cl), cockpit("clanker", "Drive", control_card("you") + drive_card("you"))), 1440, 900, "light")
    for name, spec in build_phone().items():
        S[name] = (spec[0], spec[1], 390, 844) + tuple(spec[2:])
    return S


def page(title, body, w, h, theme="dark"):
    return (f'<!doctype html><html lang="en" data-theme="{theme}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width={w}"><title>Swarm Hub · {esc(title)}</title>{FONTS}'
            f'<style>{CSS}html,body{{width:{w}px;min-height:{h}px}}</style></head><body>{body}</body></html>')


def main():
    screens = build()
    for old in list(HERE.glob("[0-9][0-9]-*.html")) + list(HERE.glob("phone-[0-9][0-9]-*.html")):
        old.unlink()
    for name, spec in screens.items():
        title, body, w, h = spec[:4]
        theme = spec[4] if len(spec) > 4 else "dark"
        (HERE / f"{name}.html").write_text(page(title, body, w, h, theme), encoding="utf-8")
    links = "".join(f'<a href="{n}.html" style="display:block;padding:8px 0;color:#E8AC65">{n} · {esc(s[0])}</a>' for n, s in screens.items())
    (HERE / "index.html").write_text(
        f'<!doctype html><meta charset="utf-8"><title>Swarm Hub screens</title><body style="background:#0D1117;color:#E8EDF2;'
        f'font-family:Inter,system-ui;padding:32px"><h1 style="font-size:22px">Swarm Hub · {len(screens)} screens</h1>{links}</body>',
        encoding="utf-8")
    print(f"wrote {len(screens)} screens to {HERE}")


if __name__ == "__main__":
    main()

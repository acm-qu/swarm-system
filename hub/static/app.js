'use strict';
// Swarm Hub app: one page with two views, Fleet and one robot, picked by the address (#/robot/<name>/<tab>).
// It asks the hub for the robot list once a second and redraws only the parts that changed, so buttons
// don't get swapped out under your mouse. Text that comes from robots is always set as text, never as HTML.

const csrf = document.querySelector('meta[name=csrf]').content;
const ME = document.body.dataset.user;
const SVG_NS = 'http://www.w3.org/2000/svg';
const $ = id => document.getElementById(id);
const enc = encodeURIComponent;

const ULTRASONIC_MAX_CM = 200;   // the robot reports this when nothing is in range (ULTRASONIC_MAX_M in robot/sensors.py)
const SLOW_MS = 200;             // latency above this feels laggy
const CHART_SECONDS = 180;       // the distance chart shows this much of the past
// Only used for older agents that don't report their joints (ARM_JOINTS in robot/robot_movement.py).
const DEFAULT_JOINTS = { base: [500, 2500], shoulder: [500, 2500], elbow: [500, 2500], wrist: [500, 2500], gripper: [500, 2500] };

const HELP = {
  status: "Connected means the robot is online. Unresponsive means it's connected but hasn't been heard from for a few " +
          "seconds (often weak Wi-Fi). Offline means it isn't connected.",
  control: 'Only one person can drive a robot or move its arm at a time. Anyone can always press Stop. Control frees up ' +
           'when the person leaves the robot, or 15 seconds after their last command.',
  drive: 'Hold a button or key to move; let go and the robot stops. If your connection drops, the robot stops by itself ' +
         'within half a second. Keys: W A S D to move, Q and E to turn, Space to stop.',
  arm: 'Each slider is a servo pulse in microseconds. Stop holds the arm where it is. Release makes it go limp, so support it first.',
  distance: 'The ultrasonic sensor measures how far the nearest object in front is, up to 2 m.',
  gyro: 'Rotation is how far the robot has turned or tipped since the gyro was last calibrated; speed is how fast it turns now. ' +
        'Z drifts about a degree a minute, so calibrate again to zero it.',
  terminal: "Runs one command at a time on the robot, as the robot's user. Each stops after 30 seconds.",
};

// ---- small helpers

// h('div', {class: 'x', text: 'hi', onclick: fn}, child, ...): builds an element. Strings become text nodes.
function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'text') el.textContent = v;
    else if (k.startsWith('on')) el[k] = v;
    else if (k in el && typeof v !== 'string') el[k] = v;   // disabled, checked, value, min, ...
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) el.append(kid);
  return el;
}

function icon(name, cls) {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('class', 'i' + (cls ? ' ' + cls : ''));
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS(SVG_NS, 'use');
  use.setAttribute('href', '#' + name);         // the sprite is inlined in app.html
  svg.append(use);
  return svg;
}

function svgFrom(markup) {         // fixed markup only (numbers, no robot text)
  const t = document.createElement('template');
  t.innerHTML = markup.trim();
  return t.content.firstChild;
}

// Rebuild el's contents only when sig changed since last time.
function patch(el, sig, build) {
  if (el._sig === sig) return;
  el._sig = sig;
  el.replaceChildren(...[].concat(build()).filter(x => x !== null && x !== undefined && x !== false));
}

function help(text) {
  return h('button', { type: 'button', class: 'help', 'aria-label': text }, icon('circle-help'), h('span', { class: 'tip', text }));
}

function note(kind, ...body) {
  const ic = { good: 'circle-check', warn: 'triangle-alert', bad: 'circle-x', info: 'info' }[kind] || 'info';
  return h('div', { class: 'note ' + (kind || '') }, icon(ic), h('span', {}, ...body));
}

function setNote(el, kind, text) {
  el.hidden = !text;
  if (text) el.replaceWith(Object.assign(note(kind, text), { id: el.id }));
}

function cardHead(ic, title, helpText, ...extra) {
  return h('div', { class: 'card-h' }, icon(ic), h('h3', { text: title }), helpText ? help(helpText) : null,
           h('div', { class: 'grow' }), ...extra);
}

const initials = s => String(s).slice(0, 2).toUpperCase();
const ms = v => (v === null || v === undefined ? '—' : v + ' ms');
const num = (v, d) => (v === null || v === undefined ? '—' : Number(v).toFixed(d).replace('-', '−'));
const signed = v => (v === 0 ? '0.00' : (v > 0 ? '+' : '−') + Math.abs(v).toFixed(2));
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);

function ago(s) {
  if (s === null || s === undefined) return '—';
  if (s < 1) return 'now';
  if (s < 60) return Math.round(s) + ' s ago';
  if (s < 3600) return Math.round(s / 60) + ' min ago';
  if (s < 86400) return Math.round(s / 3600) + ' h ago';
  return Math.round(s / 86400) + ' days ago';
}

function when(epoch) {
  if (!epoch) return '—';
  return new Date(epoch * 1000).toLocaleString([], { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function post(url, data) {
  return fetch(url, {
    method: 'POST',
    headers: { 'X-CSRF': csrf, 'Content-Type': 'application/json' },
    body: JSON.stringify(data || {}),
  }).then(async res => {
    if (res.status === 401) { location.reload(); throw new Error('signed out'); }
    const out = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(out.error || ('HTTP ' + res.status));
    return out;
  });
}

const api = (name, action, data) => post('/api/robots/' + enc(name) + '/' + action, data);

let toastTimer = null;
function toast(text, bad) {
  const t = $('toast');
  t.textContent = text;
  t.className = 'toast' + (bad ? ' bad' : '');
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 6000);
}

// ---- what a robot is and can do

const live = r => r.status !== 'offline';
const holder = r => r.controlled_by || null;
const other = r => !!r.controlled_by && r.controlled_by !== ME;

// What the robot said it can do when it connected. Older agents don't say, so allow everything.
function can(r, what) {
  const c = r.capabilities;
  const sensors = c ? (c.sensors || []) : Object.keys(r.sensors || {});
  if (what === 'gyro') return sensors.includes('rot_z_deg');
  if (what === 'distance') return !c || sensors.includes('distance_cm');
  if (!c) return true;
  if (what === 'arm') return Object.keys(c.arm || {}).length > 0;
  return !!c[what];
}

// Joints in arm order (the hub's JSON comes back sorted by name).
const JOINT_ORDER = ['base', 'shoulder', 'elbow', 'wrist', 'gripper'];
function joints(r) {
  const c = r.capabilities;
  const js = c && Object.keys(c.arm || {}).length ? c.arm : DEFAULT_JOINTS;
  const rank = j => (JOINT_ORDER.includes(j) ? JOINT_ORDER.indexOf(j) : JOINT_ORDER.length);
  return Object.fromEntries(Object.entries(js).sort((x, y) => rank(x[0]) - rank(y[0])));
}

function statusPill(r, sm) {
  const c = sm ? ' sm' : '';
  if (r.job) {
    return h('span', { class: 'pill p-info' + c, title: r.job }, icon('loader-circle', 'spin'), 'Working…',
             sm ? null : h('span', { style: 'opacity:.8', text: r.job }));
  }
  const [cls, ic, word] = {
    connected: ['p-ok', 'circle-check', 'Connected'],
    unresponsive: ['p-warn', 'triangle-alert', 'Unresponsive'],
    offline: ['p-off', 'wifi-off', 'Offline'],
  }[r.status];
  return h('span', { class: `pill ${cls}${c}` }, icon(ic), word);
}

function ctrlPill(who, sm, long) {
  const c = sm ? ' sm' : '';
  if (who === ME) return h('span', { class: 'pill p-you' + c }, h('span', { class: 'av', text: initials(ME) }), long ? 'You are in control' : 'You');
  if (!who) return h('span', { class: 'pill p-nobody' + c }, icon('lock-open'), long ? 'Nobody is in control' : 'Nobody');
  return h('span', { class: 'pill p-ctl' + c }, h('span', { class: 'av', text: initials(who) }),
           long ? who + ' is in control' : 'Controlled by ' + who, icon('lock'));
}

function slowTag(r) {
  return r.latency_ms > SLOW_MS ? h('span', { class: 'slow' }, icon('triangle-alert'), 'slow') : null;
}

function distText(d) {
  if (d === null || d === undefined) return '—';
  return d >= ULTRASONIC_MAX_CM ? '≥ ' + ULTRASONIC_MAX_CM : String(Math.round(d));
}

function stopButton(r, label, extra) {
  return h('button', { type: 'button', class: 'btn stop' + (extra ? ' ' + extra : ''), disabled: !live(r),
                       title: 'Stop never needs control', onclick: () => stopRobot(r.name) },
           icon('octagon'), label || 'Stop');
}

// ---- state, polling and routing

const S = { robots: [], byName: {}, loaded: false, ok: true, lastOk: Date.now(), hubMs: null, listOpen: false };
let view = { page: 'fleet' };
const content = $('content');
const bannerSlot = h('div');
const pageEl = h('div');
content.append(bannerSlot, pageEl);

function refresh() {
  const started = performance.now();
  return fetch('/api/robots').then(res => {
    if (res.status === 401) { location.reload(); return null; }
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }).then(list => {
    if (!list) return;
    Object.assign(S, { robots: list, loaded: true, ok: true, lastOk: Date.now(), hubMs: Math.round(performance.now() - started) });
    S.byName = Object.fromEntries(list.map(r => [r.name, r]));
    if (rv.name && S.byName[rv.name]) sensTrack(S.byName[rv.name]);   // once per reading, not per redraw
    render();
  }).catch(() => { S.ok = false; render(); });
}

const TABS = {
  drive: { label: 'Drive', icon: 'gamepad-2', locks: true },
  arm: { label: 'Arm', icon: 'hand', locks: true },
  sensors: { label: 'Sensors', icon: 'radar' },
  terminal: { label: 'Terminal', icon: 'terminal' },
  info: { label: 'Info', icon: 'info' },
};

const robotUrl = (name, tab) => '#/robot/' + enc(name) + '/' + (tab || 'drive');

function route() {
  const m = location.hash.match(/^#\/robot\/([^/]+)(?:\/(\w+))?/);
  let next = { page: 'fleet' };
  if (m) {
    let name = null;
    try { name = decodeURIComponent(m[1]); } catch (e) { /* bad address: show Fleet */ }
    if (name) next = { page: 'robot', name, tab: TABS[m[2]] ? m[2] : 'drive' };
  }
  const sameRobot = view.page === 'robot' && next.page === 'robot' && next.name === view.name;
  if (view.page === 'robot' && !sameRobot) leaveRobot();
  view = next;
  if (view.page === 'robot' && !sameRobot) enterRobot(view.name);
  if (view.page === 'fleet') { pageEl._sig = null; pageEl.replaceChildren(fleet.root); }
  render();
}

function render() {
  renderFrame();
  patch(bannerSlot, S.ok ? '' : Math.round((Date.now() - S.lastOk) / 1000), banner);
  if (view.page === 'fleet') renderFleet();
  else renderRobot();
}

function renderFrame() {
  patch($('crumb'), view.page + '|' + view.name, () => view.page === 'robot'
    ? [h('a', { href: '#/', text: 'Fleet' }), icon('chevron-right'), h('span', { text: view.name })]
    : h('span', { text: 'Fleet' }));
  const chip = $('hub-chip');
  chip.className = 'chip' + (S.ok ? '' : ' down');
  patch(chip, S.ok + '|' + S.hubMs, () => S.ok
    ? [h('span', { class: 'dot' }), 'Hub connected' + (S.hubMs !== null ? ' · ' + S.hubMs + ' ms' : '')]
    : [icon('triangle-alert'), "Can't reach the hub · reconnecting…"]);
  const online = S.robots.filter(r => r.status === 'connected').length;
  patch($('online-chip'), online + '/' + S.robots.length + S.loaded, () => [icon('bot'),
    ...(S.robots.length ? [h('b', { text: online + ' of ' + S.robots.length }), ' robots online']
                        : [S.loaded ? 'No robots yet' : 'Loading…'])]);
}

function banner() {
  if (S.ok) return null;
  const s = Math.round((Date.now() - S.lastOk) / 1000);
  return h('div', { class: 'note warn banner', role: 'alert' }, icon('triangle-alert'),
    h('div', { class: 'grow' },
      h('b', { text: "Can't reach the hub. Reconnecting… Everything below may be out of date." }),
      h('div', { class: 'muted', text: 'Last update ' + s + ' s ago. If you were driving, the robot stops by itself within half a second.' })),
    h('button', { type: 'button', class: 'btn sm', onclick: refresh }, icon('refresh-cw'), 'Retry now'));
}

// ---- Stop and Stop all: never need control, never blocked

function stopRobot(name) {
  if (rv.name === name) release();
  return api(name, 'stop').then(refresh, err => toast("Couldn't stop " + name + ': ' + err.message, true));
}

let stopAllTimer = null;
function stopAll() {
  release();
  const targets = S.robots.filter(live);
  const label = $('stop-all-label');
  Promise.allSettled(targets.map(r => api(r.name, 'stop'))).then(results => {
    const failed = targets.filter((r, i) => results[i].status === 'rejected').map(r => r.name);
    label.textContent = !targets.length ? 'None online' : failed.length ? 'Stop failed' : 'Stop sent';
    if (failed.length) toast("Couldn't stop " + failed.join(', ') + ". Is the hub reachable?", true);
    clearTimeout(stopAllTimer);
    stopAllTimer = setTimeout(() => { label.textContent = 'Stop all'; }, 1500);
    refresh();
  });
}

$('stop-all').onclick = stopAll;

function ping(name) {
  api(name, 'ping').then(refresh, err => toast(err.message, true));
}

// ---- Fleet

const fleet = { root: null, head: h('div', { class: 'page-head' }), body: h('div'), grid: h('div', { class: 'fleet' }), cards: new Map() };
fleet.root = h('div', {}, fleet.head, fleet.body);

function renderFleet() {
  const list = S.robots;
  patch(fleet.head, list.length, () => [
    h('div', {}, h('div', { class: 'row gap8' }, h('span', { class: 'h1', text: 'Robots' }), help(HELP.status)),
      h('div', { class: 'sub', text: list.length ? list.length + (list.length === 1 ? ' robot' : ' robots') + ' on this hub'
                                                 : 'No robots on this hub yet' })),
    h('div', { class: 'grow' }),
    h('button', { type: 'button', class: 'btn primary', onclick: () => openForm('add') }, icon('plus'), 'Add robot')]);
  patch(fleet.body, S.loaded + '|' + (list.length > 0), () => (!S.loaded ? h('p', { class: 'muted', text: 'Loading robots…' })
                                                             : list.length ? fleet.grid : emptyFleet()));
  const els = list.map(r => {
    let c = fleet.cards.get(r.name);
    if (!c) { c = newFleetCard(r.name); fleet.cards.set(r.name, c); }
    updateFleetCard(c, r);
    return c.el;
  });
  for (const name of fleet.cards.keys()) if (!S.byName[name]) fleet.cards.delete(name);
  if (els.length !== fleet.grid.children.length || els.some((el, i) => fleet.grid.children[i] !== el)) fleet.grid.replaceChildren(...els);
}

function newFleetCard() {
  const c = { top: h('div', { class: 'row gap12' }), meta: h('div', { class: 'row gap16 meta' }),
              sens: h('div', { class: 'row gap16 top-align' }), event: h('div', { class: 'row gap10 event' }),
              acts: h('div', { class: 'row gap8', style: 'margin-top:12px' }) };
  c.el = h('div', { class: 'card rcard' }, c.top, c.meta, c.sens, c.event, c.acts);
  return c;
}

const CAPS = [['move', 'drive', 'Wheels'], ['hand', 'arm', 'Arm'], ['camera', 'camera', 'Camera'],
              ['radar', 'distance', 'Distance sensor'], ['rotate-3d', 'gyro', 'Gyro']];

function capIcons(r) {
  if (!r.capabilities && !live(r)) return h('div', { class: 'faint small', text: 'Shows up once it connects' });
  return h('div', { class: 'row gap6' }, CAPS.map(([ic, what, word]) => {
    const has = can(r, what);
    return h('span', { class: 'mg sm' + (has ? '' : ' missing'), title: word + (has ? '' : ': not on this robot'),
                       'aria-label': word + (has ? '' : ': not on this robot'), role: 'img' }, icon(ic));
  }));
}

function updateFleetCard(c, r) {
  const s = r.sensors || {};
  const unr = r.status === 'unresponsive';
  patch(c.top, [r.name, r.hostname, r.address, r.status, r.job].join('|'), () => [
    h('span', { class: 'mg lg', text: initials(r.name) }),
    h('div', { class: 'grow' }, h('div', { class: 'name', text: r.name }),
      h('div', { class: 'muted small' }, h('span', { class: 'mono', text: r.hostname || '—' }), ' · ' + (r.address || '—'))),
    h('div', { class: 'row gap6' }, statusPill(r))]);
  patch(c.meta, [holder(r), ago(r.seen_ago), r.latency_ms].join('|'), () => [
    ctrlPill(holder(r)),
    h('span', { class: 'muted' }, 'Last seen ', h('b', { text: ago(r.seen_ago) })),
    h('span', { class: 'muted' }, 'Latency ', h('b', { class: 'num', text: ms(r.latency_ms) })),
    slowTag(r)]);
  patch(c.sens, JSON.stringify([s.distance_cm, s.rot_z_deg, r.status, r.capabilities]), () => {
    const dist = s.distance_cm;
    const rz = !live(r) ? '—' : can(r, 'gyro') ? num(s.rot_z_deg, 1) + (s.rot_z_deg === null || s.rot_z_deg === undefined ? '' : '°') : null;
    return [
      h('div', { class: 'grow', style: unr ? 'opacity:.55' : null }, h('div', { class: 'lbl', text: 'Distance' }),
        h('div', { class: 'big num' }, live(r) ? distText(dist) : '—', live(r) && dist !== null && dist !== undefined ? h('small', { text: 'cm' }) : null)),
      h('div', { class: 'grow' }, h('div', { class: 'lbl', text: 'Rotation Z' }),
        rz === null ? h('div', { class: 'muted', style: 'margin-top:6px', text: 'No gyro' }) : h('div', { class: 'big num', text: rz })),
      h('div', {}, h('div', { class: 'lbl', style: 'margin-bottom:6px', text: 'What it can do' }), capIcons(r))];
  });
  patch(c.event, r.job || r.event || '', () => [icon('history'), h('span', { class: 'muted', text: 'Last event' }),
                                                h('span', { class: 'grow', title: r.job || r.event || '', text: r.job || r.event || '—' })]);
  patch(c.acts, r.name + live(r), () => [
    stopButton(r), h('div', { class: 'grow' }),
    h('button', { type: 'button', class: 'btn', disabled: !live(r), onclick: () => ping(r.name) }, icon('radio'), 'Ping'),
    h('a', { class: 'btn', href: robotUrl(r.name) }, 'Open', icon('arrow-right'))]);
}

function emptyFleet() {
  const need = [['wifi', 'The robot switched on and on the lab Wi-Fi'], ['hash', 'Its IP address, e.g. 192.168.149.1'],
                ['key-round', 'Its password (used once, not saved)']];
  return h('div', { class: 'empty-box' },
    h('div', { class: 'mg lg' }, icon('bot')),
    h('div', { style: 'font-size:18px;font-weight:600;margin-top:18px', text: 'No robots yet. Press Add robot to set one up.' }),
    h('p', { class: 'muted', style: 'max-width:470px;margin-top:8px;font-size:14.5px',
             text: 'The hub installs its program on the robot for you. It takes a few minutes the first time.' }),
    h('div', { class: 'card' }, h('div', { class: 'muted small', text: 'What you need' }),
      need.map(([ic, t]) => h('div', { class: 'row gap12', style: 'margin-top:12px' }, icon(ic), h('span', { text: t })))),
    h('button', { type: 'button', class: 'btn primary', style: 'margin-top:22px;height:42px;padding:0 20px', onclick: () => openForm('add') },
      icon('plus'), 'Add robot'));
}

// ---- one robot's view: header, tabs, camera on the left, the tab's panel on the right

const rv = { name: null };

function enterRobot(name) {
  rv.name = name;
  rv.list = h('div');
  rv.toggle = h('button', { type: 'button', class: 'btn sm list-toggle', style: 'height:34px', onclick: () => { S.listOpen = !S.listOpen; render(); } },
                icon('panel-left'), 'Robots');
  rv.info = h('div', { class: 'row gap12 grow', style: 'min-width:0' });
  rv.actions = h('div', { class: 'row gap8' });
  rv.tabs = h('div', { class: 'tabs', role: 'tablist' });
  rv.below = h('div');
  rv.ctl = h('div');
  rv.card = h('div');
  rv.img = h('img', { alt: 'Live camera picture' });
  rv.camMsg = h('div', { class: 'msg' });
  rv.camTop = h('div', { class: 'ov live', style: 'top:12px;left:12px', text: 'Live', hidden: true });
  rv.cam = h('div', { class: 'cam' }, rv.img, rv.camMsg, rv.camTop,
    h('button', { type: 'button', class: 'ov', style: 'top:12px;right:12px', title: 'Full screen', 'aria-label': 'Full screen',
                  onclick: () => { const el = rv.cam; (el.requestFullscreen || el.webkitRequestFullscreen || (() => {})).call(el); } },
      icon('scan')));
  rv.el = h('div', { class: 'rview' }, rv.list,
    h('div', { class: 'grow' },
      h('div', { class: 'rhead' }, rv.toggle, rv.info, rv.actions),
      rv.tabs,
      h('div', { class: 'cockpit' }, h('div', { class: 'left' }, rv.cam, rv.below), h('div', { class: 'right' }, rv.ctl, rv.card))));
  Object.assign(sens, { low: null, high: null, count: 0, hist: [], calUntil: 0 });
  term = newTerm();
  arm.pending = {};
  drv.moving = false;
  clearInterval(drv.timer);
  drv.timer = setInterval(driveTick, 100);
  pageEl._sig = null;
  pageEl.replaceChildren(rv.el);
}

function leaveRobot() {
  const name = rv.name;
  release();
  if (drv.moving) sendStop();                // we were driving it: don't leave it rolling
  clearInterval(drv.timer);
  drv.timer = null;
  clearTimeout(arm.timer);
  arm.timer = null;
  arm.pending = {};
  camStop();
  if (name) api(name, 'release_control').catch(() => {});   // let a teammate take over right away
  if (dlg && dlg.robotView) closeDlg(true);
  rv.name = null;
}

function renderRobot() {
  const r = S.byName[view.name];
  if (!r) {
    if (!S.loaded) return;
    camStop();
    patch(pageEl, 'missing:' + view.name, () => h('div', { class: 'empty-box' },
      h('div', { class: 'mg lg' }, icon('bot')),
      h('div', { style: 'font-size:18px;font-weight:600;margin-top:18px', text: view.name + " isn't on this hub." }),
      h('p', { class: 'muted', style: 'margin-top:8px', text: 'It may have been removed.' }),
      h('a', { class: 'btn', style: 'margin-top:18px', href: '#/' }, icon('arrow-left'), 'Back to Fleet')));
    return;
  }
  if (pageEl.firstChild !== rv.el) { pageEl._sig = null; pageEl.replaceChildren(rv.el); }

  patch(rv.list, S.listOpen + '|' + view.name + '|' + view.tab + '|' +
        JSON.stringify(S.robots.map(x => [x.name, x.hostname, x.status, x.job, x.controlled_by])), () => (S.listOpen ? robotList() : null));
  rv.toggle.hidden = S.listOpen;
  patch(rv.info, [r.name, r.hostname, r.address, r.latency_ms, ago(r.seen_ago), r.status, r.job, holder(r)].join('|'), () => [
    h('span', { class: 'mg lg', text: initials(r.name) }),
    h('div', { style: 'min-width:0' }, h('div', { class: 'name', text: r.name }),
      h('div', { class: 'meta' }, h('span', { class: 'mono', text: r.hostname || '—' }), ' · ' + (r.address || '—') + ' · ',
        h('span', { class: 'num', text: ms(r.latency_ms) }), r.latency_ms > SLOW_MS ? ' ' : null, slowTag(r), ' · seen ' + ago(r.seen_ago))),
    h('div', { class: 'row gap8 wrap', style: 'margin-left:6px' }, statusPill(r, true), ctrlPill(holder(r), true))]);
  patch(rv.actions, r.name + live(r), () => [
    h('button', { type: 'button', class: 'btn sm', style: 'height:34px', disabled: !live(r), onclick: () => ping(r.name) }, icon('radio'), 'Ping'),
    h('button', { type: 'button', class: 'btn stop', disabled: !live(r), title: 'Stop never needs control. Keyboard: Space',
                  onclick: () => stopRobot(r.name) }, icon('octagon'), 'Stop ' + r.name, h('span', { class: 'kbd', text: 'Space' }))]);
  patch(rv.tabs, view.tab + '|' + other(r), () => Object.entries(TABS).map(([key, t]) =>
    h('a', { class: 'tab' + (key === view.tab ? ' on' : ''), href: robotUrl(r.name, key), role: 'tab', 'aria-selected': String(key === view.tab) },
      icon(t.icon), t.label, t.locks && other(r) ? icon('lock', 'lock') : null)));

  updateCamera(r);
  if (view.tab === 'sensors') {
    patch(rv.below, 'note', () => h('p', { class: 'muted row gap8 small', style: 'margin-top:12px' }, icon('camera'),
      'The camera stays live while you use the other tabs. Keyboard driving works on every tab.'));
  } else {
    patch(rv.below, JSON.stringify([r.sensors, r.status, r.capabilities]), () => strip(r));
  }

  const tab = view.tab;
  patch(rv.ctl, (TABS[tab].locks ? holder(r) : '-') + '|' + live(r), () => (TABS[tab].locks ? controlCard(r) : null));
  if (tab === 'drive') {
    patch(rv.card, 'drive|' + driveMode(r), () => driveCard(r));
    if (rv.driveLat) rv.driveLat.textContent = ms(r.latency_ms);
  } else if (tab === 'arm') {
    patch(rv.card, 'arm|' + armMode(r) + JSON.stringify(joints(r)), () => armCard(r));
  } else if (tab === 'sensors') {
    patch(rv.card, 'sensors|' + can(r, 'gyro') + live(r), () => sensorsCard(r));
    sensUpdate(r);
  } else if (tab === 'terminal') {
    patch(rv.card, 'terminal|' + r.installed, () => (r.installed ? termCard(r)
      : note('info', "This robot wasn't installed by this hub, so the hub can't log in to it.")));
    if (r.installed && !termAllowed() && !dlg) askTerminal(r);
  } else {
    patch(rv.card, 'info|' + JSON.stringify([r.robot_type, r.address, r.hostname, r.installed, r.added, r.updated, r.capabilities, !!r.job]),
          () => infoCard(r));
  }
}

function robotList() {
  const online = S.robots.filter(x => x.status === 'connected').length;
  return h('div', { class: 'card rlist' },
    h('div', { class: 'row gap8', style: 'margin-bottom:12px' }, h('b', { style: 'font-size:16px;font-weight:600', text: 'Robots' }),
      h('span', { class: 'muted', style: 'font-size:12.5px', text: online + ' of ' + S.robots.length + ' online' }), h('div', { class: 'grow' }),
      h('button', { type: 'button', class: 'btn sm icon', title: 'Hide the list', 'aria-label': 'Hide the list',
                    onclick: () => { S.listOpen = false; render(); } }, icon('panel-left-close'))),
    h('div', { class: 'list' }, S.robots.map(x => h('a', { class: 'rrow' + (x.name === view.name ? ' sel' : ''), href: robotUrl(x.name, view.tab),
                                                     style: 'display:block;text-decoration:none' + (x.status !== 'connected' ? ';opacity:.8' : '') },
      h('span', { class: 'row gap10' }, h('span', { class: 'mg md', text: initials(x.name) }),
        h('span', { style: 'min-width:0' }, h('span', { style: 'font-size:14.5px;display:block', text: x.name }),
          h('span', { class: 'mono faint', style: 'font-size:11.5px;display:block', text: x.hostname || '—' }))),
      h('span', { class: 'row gap6 wrap', style: 'margin-top:8px' }, statusPill(x, true), x.controlled_by ? ctrlPill(x.controlled_by, true) : null)))),
    h('p', { class: 'muted', style: 'font-size:12.5px;margin-top:12px;padding-top:12px;border-top:1px solid var(--border)',
             text: "Switching robots closes this one's panel: your keys stop sending, and your control of it is released. " +
                   "You don't get control of the next robot until you drive it or move its arm." }));
}

function strip(r) {
  const s = r.sensors || {};
  const stale = r.status === 'unresponsive' ? 'opacity:.6' : null;
  const gyro = can(r, 'gyro');
  const xyz = (prefix, unit) => h('div', { class: 'xyz', style: stale }, ['x', 'y', 'z'].map(a =>
    h('div', {}, h('span', { class: 'lbl', text: a.toUpperCase() }),
      h('span', { class: 'big num' }, num(s[prefix + a + (unit === '°' ? '_deg' : '_dps')], unit === '°' ? 1 : 0),
        h('small', { text: unit })))));
  return h('div', { class: 'strip' },
    h('div', { style: 'width:24%' }, h('div', { class: 'lbl row gap6' }, icon('radar'), 'Distance'),
      h('div', { class: 'big num', style: 'margin-top:6px' + (stale ? ';' + stale : '') }, live(r) ? distText(s.distance_cm) : '—',
        live(r) && s.distance_cm !== null && s.distance_cm !== undefined ? h('small', { text: 'cm' }) : null)),
    h('div', { class: 'grow' }, h('div', { class: 'lbl row gap6' }, icon('rotate-3d'), 'Gyro rotation'),
      gyro ? xyz('rot_', '°') : h('div', { class: 'muted', style: 'margin-top:8px', text: 'No gyro on this robot' })),
    h('div', { class: 'grow' }, h('div', { class: 'lbl row gap6' }, icon('gauge'), 'Gyro speed'),
      gyro ? xyz('gyro_', '°/s') : h('div', { class: 'muted', style: 'margin-top:8px', text: '—' })));
}

function controlCard(r) {
  const who = holder(r);
  if (who === ME) {
    return h('div', { class: 'card ctl' },
      h('div', { class: 'row gap10' }, ctrlPill(ME, false, true), h('div', { class: 'grow' }),
        h('button', { type: 'button', class: 'btn sm', onclick: () => { release(); api(r.name, 'release_control').then(refresh, () => {}); } },
          icon('lock-open'), 'Release control'), help(HELP.control)),
      h('p', { text: 'Others can watch and press Stop. Control frees up 15 seconds after your last command.' }));
  }
  if (who) {
    return h('div', { class: 'card ctl' },
      h('div', { class: 'row gap10' }, ctrlPill(who, false, true), h('span', { class: 'muted small', text: 'You can watch and press Stop.' }),
        h('div', { class: 'grow' }), help(HELP.control)),
      h('p', { text: 'Control frees up when they leave the robot, or 15 seconds after their last command.' }));
  }
  return h('div', { class: 'card ctl' },
    h('div', { class: 'row gap10' }, ctrlPill(null, false, true), h('div', { class: 'grow' }), help(HELP.control)),
    h('p', { text: live(r) ? 'Your first drive or arm command takes control. Anyone can always press Stop.' : 'The robot is offline.' }));
}

// ---- camera: the hub serves the robot's frames as an MJPEG stream the <img> shows directly.
// Having the stream open is what keeps the robot's camera on; leaving the robot lets the camera turn off.

const cam = { name: null, timer: null };

function camMessage(ic, text) {
  rv.camMsg.hidden = false;
  rv.camMsg.replaceChildren(icon(ic, ic === 'loader-circle' ? 'spin' : null), h('span', { text }));
}

function updateCamera(r) {
  const want = live(r) && can(r, 'camera');
  if (want && cam.name !== r.name) camStart(r.name);
  if (!want) {
    camStop();
    camMessage('camera-off', live(r) ? "This robot didn't report a camera." : 'No picture · offline');
  }
}

function camStart(name) {
  clearTimeout(cam.timer);
  cam.name = name;
  camMessage('loader-circle', 'Waiting for the camera…');
  rv.camTop.hidden = true;
  rv.img.onload = () => { rv.camMsg.hidden = true; rv.camTop.hidden = false; };
  rv.img.onerror = () => {                  // robot offline or the stream ended: try again shortly
    if (cam.name !== name) return;
    const r = S.byName[name];
    const why = r && r.event && r.event.startsWith('camera:') ? ' (' + r.event + ')' : '';
    camMessage('camera-off', 'No picture yet. Retrying…' + why);
    rv.camTop.hidden = true;
    clearTimeout(cam.timer);
    cam.timer = setTimeout(() => { if (cam.name === name) camStart(name); }, 2000);
  };
  rv.img.src = '/api/robots/' + enc(name) + '/camera?t=' + Date.now();
}

function camStop() {
  clearTimeout(cam.timer);
  cam.name = null;
  if (rv.img) {
    rv.img.onerror = null;
    rv.img.onload = null;
    rv.img.removeAttribute('src');          // drops the connection, so the robot's camera can stop
    rv.camTop.hidden = true;
  }
}

// ---- drive
// While a button or key is held, the page sends a drive command about 10 times a second.
// The robot stops by itself if they stop arriving, so a closed tab or dropped link is safe.

// [forward, strafe, rotate] for each key; strafe + is right, rotate + is clockwise
const DIRS = { w: [1, 0, 0], s: [-1, 0, 0], a: [0, -1, 0], d: [0, 1, 0], q: [0, 0, -1], e: [0, 0, 1] };
const drv = { held: new Set(), byPointer: new Set(), moving: false, timer: null, speed: 40 };

function driveMode(r) {
  if (!live(r)) return 'offline';
  if (!can(r, 'drive')) return 'nodrive';
  return other(r) ? 'ro:' + holder(r) : 'ok';
}

function driveVector() {
  const sum = [0, 0, 0];
  for (const k of drv.held) DIRS[k].forEach((x, i) => { sum[i] += x; });
  return sum.map(x => Math.max(-1, Math.min(1, x)) * drv.speed / 100);
}

function paintPad() {
  document.querySelectorAll('.key[data-key]').forEach(b => b.classList.toggle('held', drv.held.has(b.dataset.key)));
  paintSending(driveVector());
}

function paintSending(v) {
  if (!rv.sending || !rv.sending.isConnected) return;
  const part = (word, x) => (x ? h('b', { text: word + ' ' + signed(x) }) : word + ' ' + signed(x));
  rv.sending.replaceChildren('Sending: ', part('Forward', v[0]), ' · ', part('Strafe', v[1]), ' · ', part('Rotate', v[2]));
}

function release() {
  drv.held.clear();
  drv.byPointer.clear();
  paintPad();
}

function sendStop() {
  drv.moving = false;
  if (rv.name) api(rv.name, 'stop').catch(() => {});
}

function setDriveErr(text) {
  if (rv.driveErr) rv.driveErr.textContent = text;
}

function driveTick() {
  const r = S.byName[rv.name];
  if (!r || driveMode(r) !== 'ok') {
    if (drv.held.size) release();
    if (drv.moving) sendStop();
    return;
  }
  const v = driveVector();
  if (v.every(x => x === 0)) {
    if (drv.moving) sendStop();
    return;
  }
  drv.moving = true;
  api(rv.name, 'drive', { forward: v[0], strafe: v[1], rotate: v[2] })
    .then(() => setDriveErr(''))
    .catch(err => setDriveErr(err.message));
}

function driveCard(r) {
  const mode = driveMode(r);
  const ro = mode !== 'ok';
  const keys = [['q', 'rotate-ccw', 'Turn left'], ['w', 'arrow-up', 'Forward'], ['e', 'rotate-cw', 'Turn right'],
                ['a', 'arrow-left', 'Slide left'], 'stop', ['d', 'arrow-right', 'Slide right'], '', ['s', 'arrow-down', 'Back'], ''];
  const pad = h('div', { class: 'pad', oncontextmenu: e => e.preventDefault() }, keys.map(k => {
    if (k === 'stop') {
      return h('button', { type: 'button', class: 'key stopk', disabled: !live(r), onclick: () => stopRobot(r.name) },
               icon('octagon'), 'Stop · Space');
    }
    if (!k) return h('div');
    const [key, ic, word] = k;
    const b = h('button', { type: 'button', class: 'key', 'data-key': key, disabled: ro, 'aria-label': word + ' (' + key.toUpperCase() + ')' },
                h('span', { class: 'kl', text: key.toUpperCase() }), icon(ic), word);
    b.onpointerdown = e => {
      if (e.button !== 0) return;          // only a plain press drives; a right-click could lose its pointerup
      e.preventDefault();
      drv.held.add(key); drv.byPointer.add(key); paintPad();
    };
    b.onpointerleave = () => { if (drv.byPointer.delete(key)) { drv.held.delete(key); paintPad(); } };
    return b;
  }));
  rv.driveLat = h('b', { class: 'num', style: 'color:var(--text);font-weight:500', text: ms(r.latency_ms) });
  const head = cardHead('gamepad-2', 'Drive', HELP.drive,
    h('span', { class: 'muted row gap6 small' }, icon('radio'), 'Latency ', rv.driveLat),
    mode.startsWith('ro:') ? h('span', { class: 'pill sm p-ctl plain' }, icon('eye'), 'Watching') : null);
  if (ro) {
    const why = { offline: 'The robot is offline.', nodrive: "This robot didn't report any wheels." }[mode] ||
                'Read-only while ' + holder(r) + ' is in control. The red Stop still works.';
    rv.sending = null;
    rv.driveErr = null;
    return h('div', { class: 'card' }, head, h('div', { class: 'card-b' }, pad, h('div', { style: 'margin-top:14px' }, note('', why))));
  }
  const speedLabel = h('b', { class: 'num', style: 'font-weight:500', text: drv.speed + '%' });
  const speed = h('input', { type: 'range', min: 10, max: 100, value: drv.speed, 'aria-label': 'Speed' });
  speed.oninput = () => { drv.speed = Number(speed.value); speedLabel.textContent = drv.speed + '%'; paintSending(driveVector()); };
  rv.sending = h('div', { class: 'sending', style: 'margin-top:12px' });
  rv.driveErr = h('p', { class: 'err-line', style: 'margin-top:10px', role: 'alert' });
  const card = h('div', { class: 'card' }, head, h('div', { class: 'card-b' }, pad,
    h('div', { class: 'row between', style: 'margin-top:18px' }, h('b', { style: 'font-weight:500', text: 'Speed' }), speedLabel),
    h('div', { style: 'margin-top:8px' }, speed),
    h('div', { class: 'row between faint', style: 'font-size:12.5px;margin-top:2px' }, h('span', { text: '10%' }), h('span', { text: '100%' })),
    rv.sending, rv.driveErr,
    h('p', { class: 'muted', style: 'font-size:13px;margin-top:12px', text: 'Hold a button or key to move; let go and the robot stops.' })));
  setTimeout(paintPad);                     // after the card is on the page
  return card;
}

// A pointer let go anywhere ends what it was holding, even if the button moved under it.
for (const ev of ['pointerup', 'pointercancel']) {
  window.addEventListener(ev, () => {
    if (!drv.byPointer.size) return;
    for (const k of drv.byPointer) drv.held.delete(k);
    drv.byPointer.clear();
    paintPad();
  });
}

function typing(el) {
  if (!el || !el.tagName) return false;
  if (el.isContentEditable || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') return true;
  return el.tagName === 'INPUT' && !['range', 'checkbox', 'radio', 'button', 'submit'].includes(el.type);
}

let lastEsc = 0;
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {                  // Esc closes a dialog; Esc twice is Stop all
    const now = Date.now();
    if (now - lastEsc < 600) { lastEsc = 0; stopAll(); return; }
    lastEsc = now;
    if (dlg) closeDlg();
    return;
  }
  if (e.metaKey && drv.held.size) release();   // macOS drops the key-up of W while Cmd is held
  if (view.page !== 'robot' || dlg || typing(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
  const r = S.byName[rv.name];
  if (!r) return;
  const k = e.key.toLowerCase();
  if (k === ' ') {
    e.preventDefault();
    if (live(r)) stopRobot(r.name);
    return;
  }
  if (DIRS[k] && driveMode(r) === 'ok') {
    e.preventDefault();
    if (!e.repeat) { drv.held.add(k); paintPad(); }
  }
});
document.addEventListener('keyup', e => {
  const k = e.key.toLowerCase();
  if (drv.held.has(k) && !drv.byPointer.has(k)) { drv.held.delete(k); paintPad(); }
});
window.addEventListener('blur', release);
document.addEventListener('visibilitychange', () => { if (document.hidden) release(); });

// ---- arm: one slider per joint; each value is a servo pulse width in microseconds.

const arm = { timer: null, pending: {} };
const armLast = {};          // robot name -> {joint: pulse} last sent, so the sliders reopen where the arm is

function armMode(r) {
  if (!live(r)) return 'offline';
  if (!can(r, 'arm')) return 'none';
  return other(r) ? 'ro:' + holder(r) : 'ok';
}

function armRemembered(name) {
  if (!armLast[name]) {
    try { armLast[name] = JSON.parse(localStorage.getItem('arm:' + name)) || {}; } catch (e) { armLast[name] = {}; }
  }
  return armLast[name];
}

function armRemember(name, joint, value) {
  armRemembered(name)[joint] = value;
  try { localStorage.setItem('arm:' + name, JSON.stringify(armLast[name])); } catch (e) { /* private window: just don't remember */ }
}

function armSend() {
  arm.timer = null;
  const targets = arm.pending;
  arm.pending = {};
  if (!rv.name || !Object.keys(targets).length) return;
  api(rv.name, 'arm', { targets })
    .then(() => { if (rv.armErr) rv.armErr.textContent = ''; })
    .catch(err => { if (rv.armErr) rv.armErr.textContent = err.message; });
}

function armQueue(joint, value) {            // at most ~12 messages a second while a slider is dragged
  arm.pending[joint] = value;
  if (!arm.timer) arm.timer = setTimeout(armSend, 80);
}

function armCard(r) {
  const mode = armMode(r);
  const js = joints(r);
  if (mode === 'none') {
    return h('div', { class: 'card' }, cardHead('hand', 'Arm', HELP.arm),
      h('div', { class: 'card-b', style: 'text-align:center;padding:40px 18px' },
        h('div', { class: 'mg lg', style: 'margin:0 auto 18px' }, icon('hand')),
        h('div', { style: 'font-size:16.5px;font-weight:500', text: 'This robot has no arm board connected.' }),
        h('p', { class: 'muted', style: 'margin:8px auto 0;max-width:360px', text: 'The arm controls turn on by themselves when the robot reports an arm board.' })));
  }
  const ok = mode === 'ok';
  const lows = Object.values(js).map(v => v[0]), highs = Object.values(js).map(v => v[1]);
  const last = armRemembered(r.name);
  rv.armErr = h('p', { class: 'err-line', role: 'alert' });
  const rows = Object.entries(js).map(([joint, [low, high]]) => {
    const saved = Number(last[joint]);       // start where we left it; mid-range if never moved
    const start = Number.isFinite(saved) ? Math.min(high, Math.max(low, saved)) : Math.round((low + high) / 20) * 10;
    const shown = h('b', { class: 'mono num', text: ok ? start + ' µs' : '— µs' });   // only we know where we left it
    const input = h('input', { type: 'range', min: low, max: high, step: 10, value: start, disabled: !ok, 'aria-label': joint });
    input.oninput = () => {
      shown.textContent = input.value + ' µs';
      armRemember(r.name, joint, Number(input.value));
      armQueue(joint, Number(input.value));
    };
    return h('div', { class: 'joint' },
      h('div', { class: 'row between' }, h('span', { text: cap(joint) }),
        h('span', { class: 'row gap16' }, h('span', { class: 'faint num', style: 'font-size:12.5px', text: low + '–' + high }), shown)),
      h('div', { style: 'margin-top:6px' }, input));
  });
  const why = mode === 'offline' ? 'The robot is offline.'
    : !ok ? 'Read-only while ' + holder(r) + " is in control. The red Stop still works. The robot doesn't report arm positions."
    : "Nothing is sent until you move a slider. The sliders open where you last left them, in this browser. A joint's first " +
      'move after the robot restarts jumps straight to the slider, so start close to where it really is.';
  return h('div', { class: 'card' },
    cardHead('hand', 'Arm', HELP.arm, h('span', { class: 'faint', style: 'font-size:12.5px', text: 'Limits ' + Math.min(...lows) + '–' + Math.max(...highs) + ' µs' }),
      ok ? null : mode !== 'offline' ? h('span', { class: 'pill sm p-ctl plain' }, icon('eye'), 'Watching') : null),
    h('div', { class: 'card-b' }, rows,
      h('div', { class: 'row gap10 wrap' },
        h('button', { type: 'button', class: 'btn stop', disabled: !live(r), onclick: () => stopRobot(r.name) }, icon('octagon'), 'Stop (arm holds)'),
        h('button', { type: 'button', class: 'btn danger-soft', disabled: !ok, onclick: () => askReleaseArm(r.name) }, icon('hand'), 'Release (go limp)')),
      rv.armErr,
      h('div', { style: 'margin-top:14px' }, note('info', why))));
}

function askReleaseArm(name) {
  openDlg({
    title: 'Release ' + name + "'s arm?", ic: 'hand', danger: true, narrow: true,
    body: h('p', { style: 'font-size:15px', text: 'The arm will sag. Support it first.' }),
    foot: [h('button', { type: 'button', class: 'btn', onclick: () => closeDlg() }, 'Cancel'),
           h('button', { type: 'button', class: 'btn danger', onclick: () => {
             closeDlg();
             api(name, 'arm_release').catch(err => toast(err.message, true));
           } }, icon('hand'), 'Release')],
  });
}

// ---- sensors: readings come in each heartbeat. The page keeps the last few minutes of distance for the
// chart and says what to check when something looks wrong.

const sens = { low: null, high: null, count: 0, hist: [], calUntil: 0 };
const KNOWN_SENSORS = ['distance_cm', 'rot_x_deg', 'rot_y_deg', 'rot_z_deg', 'gyro_x_dps', 'gyro_y_dps', 'gyro_z_dps'];

function sensTrack(r) {
  const d = (r.sensors || {}).distance_cm;
  if (r.status !== 'connected' || typeof d !== 'number') return;
  const now = Date.now();
  sens.count++;
  sens.low = sens.low === null ? d : Math.min(sens.low, d);
  sens.high = sens.high === null ? d : Math.max(sens.high, d);
  sens.hist.push([now, Math.min(d, ULTRASONIC_MAX_CM)]);
  while (sens.hist.length && sens.hist[0][0] < now - CHART_SECONDS * 1000) sens.hist.shift();
}

function sensorsCard(r) {
  const R = rv.s = {};
  R.dist = h('span', { class: 'num', style: 'font-size:38px;font-weight:500;line-height:1' });
  R.range = h('span', { class: 'muted', style: 'font-size:13px' });
  R.chart = svgFrom('<svg width="100%" height="80" viewBox="0 0 600 80" preserveAspectRatio="none" aria-hidden="true">' +
    '<line x1="0" y1="4" x2="600" y2="4" style="stroke:var(--border-strong)" stroke-dasharray="3 4"/>' +
    '<polygon style="fill:var(--info)" fill-opacity=".15" points=""/>' +
    '<polyline fill="none" style="stroke:var(--info)" stroke-width="2" vector-effect="non-scaling-stroke" points=""/></svg>');
  R.note = h('div', { id: 'sens-note' });
  const parts = [
    cardHead('radar', 'Distance', HELP.distance, h('span', { class: 'faint', style: 'font-size:12.5px', text: 'Ultrasonic · up to 2 m' })),
    h('div', { class: 'card-b' },
      h('div', { class: 'row gap16 wrap' }, h('span', {}, R.dist, h('small', { class: 'muted', style: 'font-size:16px', text: ' cm' })), R.range),
      h('div', { style: 'margin-top:10px;position:relative' }, R.chart,
        h('span', { class: 'faint', style: 'position:absolute;right:0;top:8px;font-size:11.5px', text: ULTRASONIC_MAX_CM + ' cm' })),
      h('div', { class: 'row between faint', style: 'font-size:11.5px' }, h('span', { text: CHART_SECONDS / 60 + ' min ago' }), h('span', { text: 'now' })),
      h('div', { style: 'margin-top:12px' }, R.note)),
  ];
  if (can(r, 'gyro')) {
    R.needle = null;
    const dial = svgFrom('<svg width="100" height="100" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="46" style="fill:var(--surface-deep);stroke:var(--border-strong)"/>' +
      Array.from({ length: 24 }, (_, i) => `<line x1="50" y1="${i % 3 ? 8 : 6}" x2="50" y2="12" style="stroke:var(--text-2)" stroke-width="${i % 3 ? 1 : 1.4}" transform="rotate(${i * 15} 50 50)"/>`).join('') +
      '<text x="50" y="27" text-anchor="middle" font-size="9" style="fill:var(--text-2)">0°</text>' +
      '<line class="needle" x1="50" y1="50" x2="50" y2="17" style="stroke:var(--text)" stroke-width="2.4" stroke-linecap="round"/>' +
      '<circle cx="50" cy="50" r="3.5" style="fill:var(--text)"/></svg>');
    R.needle = dial.querySelector('.needle');
    const tilt = svgFrom('<svg width="66" height="66" viewBox="0 0 66 66" aria-hidden="true"><circle cx="33" cy="33" r="31" fill="none" style="stroke:var(--border-strong)"/>' +
      '<circle cx="33" cy="33" r="16" fill="none" style="stroke:var(--border-strong)" stroke-dasharray="2 3"/>' +
      '<line x1="33" y1="4" x2="33" y2="62" style="stroke:var(--border)"/><line x1="4" y1="33" x2="62" y2="33" style="stroke:var(--border)"/>' +
      '<circle class="dot" cx="33" cy="33" r="5" style="fill:var(--text)"/></svg>');
    R.tiltDot = tilt.querySelector('.dot');
    R.turn = h('div', { class: 'num', style: 'font-size:28px;font-weight:500;margin-top:4px' });
    R.turnDir = h('div', { class: 'muted', style: 'font-size:13px' });
    R.tilt = h('div', { class: 'num', style: 'font-size:13.5px' });
    R.speed = h('div', { class: 'sending', style: 'font-family:inherit;margin-top:10px' });
    R.calPill = h('span', { class: 'pill sm p-info', hidden: true }, icon('loader-circle', 'spin'), 'Calibrating…');
    R.calBtn = h('button', { type: 'button', class: 'btn sm', disabled: !live(r), onclick: () => {
      sens.calUntil = Date.now() + 2500;      // the robot measures for 2 s; give the reading a moment to come back
      R.calBtn.disabled = true;
      api(r.name, 'gyro_calibrate').then(refresh, err => { sens.calUntil = 0; toast(err.message, true); });
      sensUpdate(r);
    } }, icon('crosshair'), 'Calibrate gyro');
    R.calHint = h('span', { class: 'muted', style: 'font-size:12.5px', text: 'Keep the robot still for 2 seconds. Z drifts about a degree a minute, so calibrate again to zero it.' });
    R.calNote = note('info', h('b', { style: 'font-weight:500', text: 'Calibrating… keep the robot still' }),
                     h('div', { class: 'muted', style: 'font-size:12.5px', text: 'Readings come back in about 2 seconds.' }));
    parts.push(
      h('div', { style: 'border-top:1px solid var(--border)' }, cardHead('rotate-3d', 'Gyro', HELP.gyro, R.calPill)),
      h('div', { class: 'card-b' },
        h('div', { class: 'dial-row' },
          h('div', { class: 'col', style: 'align-items:center;gap:4px' }, dial, h('span', { class: 'muted', style: 'font-size:12.5px', text: 'Rotation Z' })),
          h('div', { class: 'grow', style: 'align-self:flex-start;padding-top:6px' }, h('div', { class: 'muted', style: 'font-size:13px', text: 'Turned (Z)' }), R.turn, R.turnDir),
          h('div', { class: 'col', style: 'align-items:center;gap:4px' }, tilt, h('span', { class: 'muted', style: 'font-size:12px', text: 'Tilt X / Y' })), R.tilt),
        R.speed,
        h('div', { class: 'row gap12', style: 'margin-top:14px' }, R.calBtn, R.calHint),
        h('div', { style: 'margin-top:14px' }, R.calNote)));
  } else {
    parts.push(h('div', { style: 'border-top:1px solid var(--border)' }, cardHead('rotate-3d', 'Gyro', HELP.gyro)),
               h('div', { class: 'card-b muted', text: "This robot didn't report a gyro." }));
  }
  // Any sensor the page has no panel for yet still shows up here (add it in robot/sensors.py).
  R.other = h('div', { class: 'row gap16 wrap' });
  R.otherBox = h('div', { class: 'card-b', style: 'border-top:1px solid var(--border)' },
    h('div', { class: 'muted', style: 'font-size:13px;margin-bottom:8px', text: 'Other readings' }), R.other);
  parts.push(R.otherBox);
  parts.push(h('div', { class: 'row gap10 faint', style: 'padding:12px 18px;border-top:1px solid var(--border)' }, icon('battery'), 'Battery',
               h('div', { class: 'grow' }), h('span', { class: 'pill sm p-ctl plain', text: 'Coming soon' })));
  return h('div', { class: 'card' }, parts);
}

function sensUpdate(r) {
  const R = rv.s;
  if (!R || !R.dist.isConnected) return;
  const s = r.sensors || {};
  const d = s.distance_cm;
  const noteEl = () => document.getElementById('sens-note');
  R.range.textContent = sens.low === null ? '' : 'Since you opened this robot: lowest ' + Math.round(sens.low) + ' cm, highest ' + Math.round(sens.high) + ' cm';
  if (sens.hist.length > 1) {
    const now = Date.now();
    const pts = sens.hist.map(([t, v]) => `${(600 - (now - t) / (CHART_SECONDS * 1000) * 600).toFixed(1)},${(78 - v / ULTRASONIC_MAX_CM * 72).toFixed(1)}`);
    R.chart.querySelector('polyline').setAttribute('points', pts.join(' '));
    R.chart.querySelector('polygon').setAttribute('points', pts[0].split(',')[0] + ',80 ' + pts.join(' ') + ' 600,80');
  }
  // What to check when there's no good reading (moved here from the old Sensors dialog).
  if (r.status !== 'connected') {
    R.dist.textContent = '—';
    setNote(noteEl(), 'warn', 'The robot is not connected right now.');
  } else if (d === undefined) {
    R.dist.textContent = '—';
    setNote(noteEl(), can(r, 'distance') ? '' : 'bad', can(r, 'distance') ? 'Waiting for a reading…'
      : "This robot didn't report an ultrasonic sensor. Check the pins in robot/sensors.py and press Update. If it is still " +
        'missing, run "journalctl -u swarm-agent -n 30" in the Terminal: the robot prints why it turned the sensor off.');
  } else if (d === null) {
    R.dist.textContent = '—';
    setNote(noteEl(), 'bad', 'The sensor is set up but gave no reading. Check the Echo wire and the 1 kΩ / 2 kΩ divider, and that VCC is on 5V (pin 2).');
  } else if (d >= ULTRASONIC_MAX_CM) {
    R.dist.textContent = distText(d);
    setNote(noteEl(), 'warn', 'Nothing within ' + ULTRASONIC_MAX_CM / 100 + ' m. If it stays like this with your hand right in front of the sensor, check the Echo wire and the divider.');
  } else {
    R.dist.textContent = distText(d);
    if (sens.high - sens.low >= 2) setNote(noteEl(), 'good', 'Working: the reading follows what is in front of the sensor.');
    else if (sens.count >= 5) setNote(noteEl(), 'warn', "The reading isn't changing. Move your hand toward the sensor. If it still doesn't change, check the wiring.");
    else setNote(noteEl(), '', 'Getting readings. Move your hand in front of the sensor to check that it responds.');
  }
  const others = Object.entries(s).filter(([k]) => !KNOWN_SENSORS.includes(k));
  R.otherBox.hidden = !others.length;
  R.other.replaceChildren(...others.map(([k, v]) => h('span', {}, h('span', { class: 'code', text: k }), ' ',
                                                       h('b', { class: 'num', style: 'font-weight:500', text: v === null ? '—' : String(v) }))));
  if (!R.turn) return;
  const calibrating = Date.now() < sens.calUntil;
  R.calPill.hidden = !calibrating;
  R.calNote.hidden = !calibrating;
  R.calBtn.parentNode.hidden = calibrating;
  R.calBtn.disabled = calibrating || !live(r);
  const rz = calibrating || !live(r) ? null : s.rot_z_deg;
  const has = v => typeof v === 'number';
  R.needle.style.display = has(rz) ? '' : 'none';
  if (has(rz)) R.needle.setAttribute('transform', `rotate(${-rz} 50 50)`);   // positive = turned left (anticlockwise)
  R.turn.textContent = has(rz) ? num(Math.abs(rz), 1) + '°' : '—';
  R.turnDir.textContent = !has(rz) ? '' : Math.abs(rz) < 0.5 ? 'facing the start' : (rz > 0 ? 'left' : 'right') + ' of the start';
  const rx = calibrating ? null : s.rot_x_deg, ry = calibrating ? null : s.rot_y_deg;
  R.tiltDot.style.display = has(rx) && has(ry) ? '' : 'none';
  if (has(rx) && has(ry)) {
    const clamp = v => Math.max(-30, Math.min(30, v)) / 30 * 24;
    R.tiltDot.setAttribute('cx', (33 + clamp(ry)).toFixed(1));
    R.tiltDot.setAttribute('cy', (33 - clamp(rx)).toFixed(1));
  }
  R.tilt.replaceChildren('X ' + (has(rx) ? num(rx, 1) + '°' : '—'), h('br'), 'Y ' + (has(ry) ? num(ry, 1) + '°' : '—'));
  R.speed.replaceChildren('Speed', ...['x', 'y', 'z'].map(a => {
    const v = calibrating ? null : s['gyro_' + a + '_dps'];
    return h('span', { style: 'margin-left:14px' }, a.toUpperCase() + ' ', h('b', { class: 'num', style: 'font-weight:500', text: has(v) ? num(v, 0) + ' °/s' : '—' }));
  }));
}

// ---- terminal: one command at a time over SSH; the server tells us which folder it ended in

let term = newTerm();
let termOk = false;

function newTerm() {
  return { name: null, cwd: '', busy: false, history: [], pos: 0, card: null };
}

function termAllowed() {
  try { return termOk || sessionStorage.getItem('terminal-ok') === '1'; } catch (e) { return termOk; }
}

function askTerminal(r) {
  openDlg({
    title: 'Open the terminal on ' + r.name + '?', ic: 'terminal', danger: true, narrow: true, robotView: true,
    body: [h('p', { style: 'font-size:15px', text: 'This runs commands directly on the robot.' }),
           note('info', "Commands run as the robot's user, one at a time, and stop after 30 seconds. You won't be asked again in this window.")],
    foot: [h('button', { type: 'button', class: 'btn', onclick: () => closeDlg() }, 'Cancel'),
           h('button', { type: 'button', class: 'btn danger', onclick: () => {
             termOk = true;
             try { sessionStorage.setItem('terminal-ok', '1'); } catch (e) { /* remembered for this page only */ }
             closeDlg(true);
             if (term.input) term.input.focus();
           } }, icon('terminal'), 'Open terminal')],
    onclose: () => { view.tab = 'drive'; location.hash = robotUrl(r.name, 'drive'); },
  });
}

function termCard(r) {
  if (term.card && term.name === r.name) return term.card;
  term = newTerm();
  term.name = r.name;
  term.out = h('div', { class: 'term-out', 'aria-live': 'polite' }, h('div', { class: 'faint', text: 'Nothing run yet.' }));
  term.empty = true;
  term.prompt = h('span', { text: '~ $' });
  term.input = h('input', { spellcheck: 'false', autocapitalize: 'off', autocomplete: 'off', 'aria-label': 'Command' });
  term.run = h('button', { type: 'submit', class: 'btn sm primary', style: 'height:36px' }, icon('corner-down-left'), 'Run');
  term.input.onkeydown = e => {             // Up / Down walk through earlier commands
    if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
    if (!term.history.length) return;
    e.preventDefault();
    term.pos = e.key === 'ArrowUp' ? Math.max(0, term.pos - 1) : Math.min(term.history.length, term.pos + 1);
    e.target.value = term.history[term.pos] || '';
  };
  const form = h('form', { class: 'term-line', autocomplete: 'off', onsubmit: termRun },
    h('label', { class: 'inp grow mono' }, term.prompt, term.input), term.run,
    h('button', { type: 'button', class: 'btn sm', style: 'height:36px', onclick: () => { term.out.replaceChildren(); } }, 'Clear'));
  term.card = h('div', { class: 'card term' },
    cardHead('terminal', 'Terminal on ' + r.name, HELP.terminal, h('span', { class: 'muted small', text: "runs as the robot's user" })),
    term.out, form,
    h('p', { class: 'muted small', style: 'padding:10px 16px 14px;border-top:1px solid var(--border)',
             text: "One command at a time, stops after 30 seconds. A folder change (cd) is remembered. Programs that need typing " +
                   "(nano, top, sudo asking for a password) won't work. Works even when the robot's program is offline." }));
  return term.card;
}

function termAdd(prompt, command, output, meta, bad) {
  if (term.empty) { term.out.replaceChildren(); term.empty = false; }
  term.out.append(h('div', { class: 'cmd' }, h('span', { text: prompt }), ' ' + command));
  if (output) term.out.append(h('pre', { text: output }));   // text only, so robot output can't inject markup
  if (meta) term.out.append(h('div', { class: 'meta' + (bad ? ' bad' : ''), text: meta }));
  term.out.scrollTop = term.out.scrollHeight;
}

function termRun(event) {
  event.preventDefault();
  const command = term.input.value.trim();
  if (!command || term.busy || !term.name) return;
  const t = term;
  const prompt = t.prompt.textContent;
  t.history.push(command);
  if (t.history.length > 200) t.history.shift();
  t.pos = t.history.length;
  t.busy = true;
  t.run.disabled = true;
  t.input.value = '';
  api(t.name, 'exec', { command, cwd: t.cwd }).then(out => {
    if (out.cwd) t.cwd = out.cwd;
    t.prompt.textContent = (t.cwd || '~') + ' $';
    let meta = '';
    if (out.timed_out) meta = 'stopped: it took longer than ' + out.limit + ' seconds';
    else if (out.code) meta = 'exit code ' + out.code;
    if (out.truncated) meta += (meta ? ' · ' : '') + 'output cut short';
    if (term === t) termAdd(prompt, command, out.output, meta, !!out.code || !!out.timed_out);
  }, err => {
    if (term === t) termAdd(prompt, command, '', err.message, true);
  }).finally(() => {
    t.busy = false;
    t.run.disabled = false;
    if (term === t && t.input.isConnected) t.input.focus();
  });
}

// ---- info

function infoCard(r) {
  const c = r.capabilities;
  const row = (k, ...v) => h('tr', {}, h('td', { text: k }), h('td', {}, h('span', { class: 'row gap6' }, ...v)));
  const js = c && Object.keys(c.arm || {}).length ? joints(r) : null;
  const capPills = c ? CAPS.filter(([, what]) => can(r, what)).map(([ic, what, word]) =>
    h('span', { class: 'pill sm p-ctl plain' }, icon(ic), what === 'arm' ? 'Arm · ' + Object.keys(js).length + ' joints' : word)) : [];
  return h('div', { class: 'card' },
    cardHead('info', 'Info', null, ...(r.installed ? [
      h('button', { type: 'button', class: 'btn sm', disabled: !!r.job, onclick: () => openForm('update', r.name) }, icon('download'), 'Update…'),
      h('button', { type: 'button', class: 'btn sm danger-soft', disabled: !!r.job, onclick: () => openForm('remove', r.name) }, icon('trash-2'), 'Remove…')] : [])),
    h('div', { class: 'card-b', style: 'padding-top:4px' },
      h('table', { class: 'tbl' }, h('tbody', {},
        row('Robot type', h('span', { class: 'mono', text: r.robot_type || '—' })),
        row('Address', r.address || '—'),
        row("Robot's own name", h('span', { class: 'mono', text: r.hostname || '—' })),
        row('Installed by this hub', ...(r.installed ? [icon('check'), 'Yes'] : ['No'])),
        row('Added on', when(r.added)),
        row('Last updated', when(r.updated)))),
      h('div', { class: 'muted', style: 'font-size:13px;margin:12px 0 8px', text: 'What it can do' }),
      c ? h('div', { class: 'row gap6 wrap' }, capPills.length ? capPills : h('span', { class: 'muted', text: 'Nothing reported.' }))
        : h('div', { class: 'muted', text: 'It tells the hub when it connects.' }),
      js ? [h('div', { class: 'muted', style: 'font-size:13px;margin:14px 0 8px', text: 'Arm joints and limits (µs)' }),
            h('div', { class: 'joints' }, Object.entries(js).map(([j, [lo, hi]]) =>
              h('div', {}, h('div', { class: 'mono', style: 'font-size:12.5px', text: j }), h('div', { class: 'muted num', style: 'font-size:12.5px', text: lo + '–' + hi }))))] : null,
      c && (c.sensors || []).length ? [h('div', { class: 'muted', style: 'font-size:13px;margin:14px 0 8px', text: 'Sensors' }),
        h('div', { class: 'row gap6 wrap' }, c.sensors.map(s => h('span', { class: 'code', text: s })))] : null,
      r.installed ? null : h('div', { style: 'margin-top:14px' },
        note('info', "This robot wasn't installed by this hub, so Update, Remove and the Terminal aren't available here."))));
}

// ---- dialogs. The scrim starts under the top bar, so Stop all is always reachable.

let dlg = null;              // {onclose, timer, robotView, job, ...}
const dlgBox = $('dlg');

function fillDlg(o) {
  dlgBox.className = 'dlg' + (o.danger ? ' danger' : '') + (o.narrow ? ' narrow' : '');
  dlgBox.replaceChildren(
    h('div', { class: 'dlg-h' }, o.ic ? h('span', { class: 'dicon' }, icon(o.ic)) : null,
      h('div', { class: 'grow' }, o.lead || null, h('h2', { id: 'dlg-title', text: o.title }),
        o.sub ? h('p', { class: 'muted', style: 'margin-top:4px;font-size:14px' }, o.sub) : null),
      h('button', { type: 'button', class: 'x', 'aria-label': 'Close', onclick: () => closeDlg() }, icon('x'))),
    h('div', { class: 'dlg-b' }, o.body),
    o.foot ? h('div', { class: 'dlg-f' }, o.foot) : '');
}

function openDlg(o) {
  closeDlg(true);
  dlg = { onclose: o.onclose, timer: null, robotView: !!o.robotView };
  fillDlg(o);
  $('scrim').hidden = false;
  // A form starts in its first field; a confirm starts on Cancel, so Enter never confirms by accident.
  const first = dlgBox.querySelector('input:not([type=hidden]):not([type=checkbox])') || dlgBox.querySelector('.dlg-f .btn');
  if (first) first.focus();
}

function closeDlg(quiet) {
  if (!dlg) return;
  const d = dlg;
  dlg = null;
  clearTimeout(d.timer);
  $('scrim').hidden = true;
  dlgBox.replaceChildren();
  if (!quiet && d.onclose) d.onclose();
}

// Add / Update / Remove: a form, then the job's steps as the hub works through them.

function field(label, input, hintText) {
  return h('label', { class: 'field grow' }, label, input, hintText ? h('span', { class: 'hint', text: hintText }) : null);
}

function openForm(mode, name, prev) {
  const v = prev || {};
  const r = name ? S.byName[name] : null;
  const f = {};
  const err = h('p', { class: 'err-line', role: 'alert' });
  const body = [];
  if (mode === 'remove' && r) {
    body.push(h('div', { class: 'row gap12', style: 'border:1px solid var(--border);border-radius:12px;padding:12px 14px;background:var(--surface-deep)' },
      h('span', { class: 'mg', text: initials(r.name) }),
      h('div', { class: 'grow' }, h('div', { text: r.name }),
        h('div', { class: 'muted', style: 'font-size:12.5px' }, h('span', { class: 'mono', text: r.hostname || '—' }), ' · ' + (r.address || '—'))),
      statusPill(r, true)));
  }
  if (mode === 'add') {
    f.host = h('input', { class: 'inp', name: 'host', placeholder: '192.168.149.1', spellcheck: 'false', required: true, value: v.host || '' });
    f.user = h('input', { class: 'inp mono', name: 'user', spellcheck: 'false', value: v.user || 'pi' });
    f.password = h('input', { class: 'inp', name: 'password', type: 'password', autocomplete: 'new-password', required: true, value: v.password || '' });
    f.name = h('input', { class: 'inp', name: 'name', placeholder: 'picked for you, e.g. masterpi-01', spellcheck: 'false', value: v.name || '' });
    body.push(field('IP address', f.host, "Shown on the robot's screen, or in your router's list of devices."),
      h('div', { class: 'row gap12 top-align' }, field('Username', f.user), field('Password', f.password)),
      h('div', { class: 'muted', style: 'font-size:13px;text-align:right;margin-top:-8px', text: 'Password: used once to install. It is not saved.' }),
      field(h('span', {}, 'Name ', h('span', { class: 'muted', style: 'font-weight:400', text: '(optional)' })), f.name));
  } else {
    f.password = h('input', { class: 'inp', name: 'password', type: 'password', autocomplete: 'new-password', placeholder: 'Robot password', value: v.password || '' });
    body.push(field(h('span', {}, 'Password ', h('span', { class: 'muted', style: 'font-weight:400', text: '(optional)' })), f.password,
                    'Usually not needed. Fill it in only if the robot asks for it.'));
  }
  if (mode === 'remove') {
    f.forget = h('input', { type: 'checkbox', checked: !!v.forget });
    body.push(h('label', { class: 'check' }, f.forget, h('span', {}, "The robot is gone or can't be reached. Just take it off this list.",
      r && !live(r) ? h('span', { class: 'muted', style: 'display:block;font-size:13px',
                                  text: r.name + " is offline, so the hub can't clean up the robot itself." }) : null)));
  } else {
    // Opt-in: adding a robot from another computer shouldn't restart it.
    f.reboot = h('input', { type: 'checkbox', checked: !!v.reboot });
    body.push(h('label', { class: 'check' }, f.reboot, h('span', {}, 'Reboot the robot when done',
      h('span', { class: 'muted', style: 'display:block;font-size:13px', text: 'Proves it starts by itself and opens the status screen on its desktop. Takes about a minute.' }))));
  }
  if (mode === 'update') {
    body.push(note('info', "The robot stops and restarts its program during the update, so it can't be driven for a few seconds."));
  }
  body.push(err);
  const go = h('button', { type: 'submit', form: 'dlg-form', class: mode === 'remove' ? 'btn danger' : 'btn primary' },
               icon(mode === 'remove' ? 'trash-2' : 'download'), { add: 'Install', update: 'Update', remove: 'Remove' }[mode]);
  const form = h('form', { id: 'dlg-form', class: 'col gap16', autocomplete: 'off' }, body);
  form.onsubmit = e => {
    e.preventDefault();
    const values = { password: f.password.value, reboot: f.reboot ? f.reboot.checked : false, forget: f.forget ? f.forget.checked : false };
    let url = '/api/robots/' + enc(name) + '/' + mode;
    if (mode === 'add') {
      Object.assign(values, { host: f.host.value.trim(), user: f.user.value.trim(), name: f.name.value.trim() });
      url = '/api/robots';
    }
    go.disabled = true;
    err.textContent = '';
    post(url, values).then(out => {
      if (!dlg) return;
      Object.assign(dlg, { job: out.job, mode, name, values });
      pollJob();
    }, e2 => {
      go.disabled = false;
      err.textContent = e2.message;
    });
  };
  const text = {
    add: ['Add robot', 'The hub connects to the robot over the lab network and installs its program.'],
    update: ['Update ' + name, 'Copies the latest robot code from the hub to the robot and restarts it.'],
    remove: ['Remove ' + name + '?', 'Stops the robot program, removes it from the robot, and takes the robot off this list.'],
  }[mode];
  openDlg({
    title: text[0], sub: text[1], danger: mode === 'remove', ic: mode === 'remove' ? 'trash-2' : null,
    body: form, foot: [h('button', { type: 'button', class: 'btn', onclick: () => closeDlg() }, 'Cancel'), go],
  });
}

function pollJob() {
  const d = dlg;
  if (!d || !d.job) return;
  fetch('/api/jobs/' + d.job).then(res => res.json()).then(job => {
    if (dlg !== d) return;
    renderJob(d, job);
    if (job.state === 'running') d.timer = setTimeout(pollJob, 600);
    else refresh();
  }).catch(() => { if (dlg === d) d.timer = setTimeout(pollJob, 1500); });
}

function renderJob(d, job) {
  const pill = {
    running: h('span', { class: 'pill p-info' }, icon('loader-circle', 'spin'), 'Working…'),
    done: h('span', { class: 'pill p-ok' }, icon('circle-check'), 'Done'),
    warning: h('span', { class: 'pill p-warn' }, icon('triangle-alert'), 'Check this'),
    failed: h('span', { class: 'pill p-fail' }, icon('circle-x'), 'Failed'),
  }[job.state];
  const steps = job.steps.map(s => {
    if (s.state === 'info') return h('div', { class: 'slog', text: s.text });
    const ic = { ok: h('span', { class: 'sicon s-ok' }, icon('check')), fail: h('span', { class: 'sicon s-fail' }, icon('x')),
                 run: h('span', { class: 'sicon s-run' }) }[s.state];
    return h('div', { class: 'step' }, ic, h('div', { class: 'grow' }, s.state === 'run' ? h('b', { style: 'font-weight:500', text: s.text + '…' }) : s.text));
  });
  let tail, foot;
  const close = h('button', { type: 'button', class: 'btn', onclick: () => closeDlg() }, 'Close');
  if (job.state === 'running') {
    tail = h('p', { class: 'muted', style: 'font-size:13.5px', text: "You can hide this window. The job keeps running, and the robot's card shows its current step." });
    foot = [h('button', { type: 'button', class: 'btn', onclick: () => closeDlg() }, icon('eye-off'), 'Hide (keeps running)')];
  } else {
    tail = note({ done: 'good', warning: 'warn', failed: 'bad' }[job.state], job.message);
    foot = [close];
    if (job.state === 'failed') {
      foot.push(h('button', { type: 'button', class: 'btn primary', onclick: () => openForm(d.mode, d.name, d.values) }, icon('refresh-cw'), 'Try again'));
    } else if (d.mode === 'add' && job.robot) {
      foot.push(h('button', { type: 'button', class: 'btn primary', onclick: () => { closeDlg(); location.hash = robotUrl(job.robot); } },
                  'Open robot', icon('arrow-right')));
    }
  }
  const v = d.values || {};
  fillDlg({
    lead: h('div', { style: 'margin-bottom:8px' }, pill),
    title: { add: 'Installing the robot', update: 'Updating ' + d.name, remove: 'Removing ' + d.name }[d.mode],
    sub: d.mode === 'add' ? ['Adding ', h('span', { class: 'mono', text: v.user + '@' + v.host })] : null,
    body: [h('div', { class: 'steps' }, steps), tail], foot,
  });
}

// ---- start

window.addEventListener('hashchange', route);
route();
refresh();
setInterval(refresh, 1000);

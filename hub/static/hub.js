const csrf = document.querySelector('meta[name=csrf]').content;
const $ = id => document.getElementById(id);
const body = document.querySelector('#robots tbody');
const form = $('dlg-form');
let dlg = null;          // {mode, name, job, timer}

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

function cell(row, text, cls) {
  const td = document.createElement('td');
  if (cls) {
    const span = document.createElement('span');
    span.className = 'pill ' + cls;
    span.textContent = text;
    td.appendChild(span);
  } else {
    td.textContent = text;
  }
  row.appendChild(td);
  return td;
}

function button(parent, label, onclick, opts) {
  const b = document.createElement('button');
  b.textContent = label;
  b.className = 'small' + (opts && opts.danger ? ' danger' : '');
  b.disabled = !!(opts && opts.disabled);
  b.onclick = onclick;
  parent.appendChild(b);
}

function render(list) {
  $('none').hidden = list.length > 0;
  $('robots').hidden = list.length === 0;
  const online = list.filter(r => r.status === 'connected').length;
  $('summary').textContent = list.length ? online + ' of ' + list.length + ' connected' : '';
  body.replaceChildren();
  for (const r of list) {
    const tr = document.createElement('tr');
    const nameTd = cell(tr, r.name);
    if (r.hostname) {
      const sub = document.createElement('div');
      sub.className = 'sub';
      sub.textContent = r.hostname;
      sub.title = "The robot's own name";
      nameTd.appendChild(sub);
    }
    if (r.job) cell(tr, 'working…', 'busy');
    else cell(tr, r.status, r.status);
    cell(tr, r.address || '-');
    cell(tr, r.seen_ago === null ? '-' : (r.seen_ago < 1 ? 'now' : Math.round(r.seen_ago) + ' s ago'));
    cell(tr, r.latency_ms === null ? '-' : r.latency_ms + ' ms');
    cell(tr, sensorText(r.sensors));
    cell(tr, r.job || r.event || '-');
    const cellTd = document.createElement('td');
    const td = document.createElement('div');
    td.className = 'actions';
    cellTd.appendChild(td);
    const live = r.status !== 'offline';
    // What the robot said it can do when it connected. Older agents don't say, so allow everything.
    const caps = r.capabilities;
    const can = what => !caps || (what === 'arm' ? Object.keys(caps.arm || {}).length > 0 : !!caps[what]);
    armLimits[r.name] = caps && caps.arm;
    button(td, 'Ping', () => post('/api/robots/' + encodeURIComponent(r.name) + '/ping').then(refresh, () => {}), { disabled: !live });
    button(td, 'Sensors', () => openSens(r.name), { disabled: !live });
    button(td, 'Camera', () => openCam(r.name), { disabled: !live || !can('camera') });
    button(td, 'Drive', () => openDrive(r.name), { disabled: !live || !can('drive') });
    button(td, 'Arm', () => openArm(r.name), { disabled: !live || !can('arm') });
    button(td, 'Stop', () => post('/api/robots/' + encodeURIComponent(r.name) + '/stop').then(refresh, () => {}), { disabled: !live });
    if (r.installed) {
      button(td, 'Terminal', () => openTerm(r.name), { disabled: !!r.job });
      button(td, 'Update', () => openDialog('update', r.name), { disabled: !!r.job });
      button(td, 'Remove', () => openDialog('remove', r.name), { disabled: !!r.job, danger: true });
    }
    tr.appendChild(cellTd);
    body.appendChild(tr);
  }
  sensUpdate(list);
}

const SENSOR_UNITS = { distance_cm: ' cm' };

// ---- sensors dialog: shows the readings the robot sends in each heartbeat and says what to check
// when there are none. It updates whenever the page refreshes the robot list (once a second).

const ULTRASONIC_MAX_CM = 200;   // the robot reports this when nothing is in range (ULTRASONIC_MAX_M in robot/sensors.py)
const sens = { name: null, low: null, high: null, count: 0 };

function sensNote(text, kind) {
  const note = $('sens-note');
  note.hidden = !text;
  note.className = 'note ' + (kind || '');
  note.textContent = text || '';
}

function sensUpdate(list) {
  if (!sens.name) return;
  const r = list.find(x => x.name === sens.name);
  const value = $('sens-value');
  if (!r || r.status !== 'connected') {
    value.textContent = '-';
    sensNote('The robot is not connected right now.', 'warn');
    return;
  }
  const d = (r.sensors || {}).distance_cm;
  if (d === undefined) {
    value.textContent = '-';
    const caps = r.capabilities;
    if (caps && !(caps.sensors || []).includes('distance_cm')) {
      sensNote("This robot didn't report an ultrasonic sensor. Check the pins in robot/sensors.py and press Update. " +
               'If it is still missing, run "journalctl -u swarm-agent -n 30" in the Terminal: the robot prints why it turned the sensor off.', 'bad');
    } else {
      sensNote('Waiting for a reading…');
    }
    return;
  }
  if (d === null) {
    value.textContent = '-';
    sensNote('The sensor is set up but gave no reading. Check the Echo wire and the 1 kΩ / 2 kΩ divider, and that VCC is on 5V (pin 2).', 'bad');
    return;
  }
  sens.count++;
  sens.low = sens.low === null ? d : Math.min(sens.low, d);
  sens.high = sens.high === null ? d : Math.max(sens.high, d);
  $('sens-range').textContent = 'Since you opened this: lowest ' + sens.low + ' cm, highest ' + sens.high + ' cm';
  if (d >= ULTRASONIC_MAX_CM) {
    value.textContent = '≥ ' + ULTRASONIC_MAX_CM;
    sensNote('Nothing within ' + ULTRASONIC_MAX_CM / 100 + ' m. If it stays like this with your hand right in front of the sensor, check the Echo wire and the divider.', 'warn');
  } else {
    value.textContent = d;
    if (sens.high - sens.low >= 2) sensNote('Working: the reading follows what is in front of the sensor.', 'good');
    else if (sens.count >= 5) sensNote("The reading isn't changing. Move your hand toward the sensor. If it still doesn't change, check the wiring.", 'warn');
    else sensNote('Getting readings. Move your hand in front of the sensor to check that it responds.');
  }
}

function openSens(name) {
  Object.assign(sens, { name, low: null, high: null, count: 0 });
  $('sens-title').textContent = 'Sensors: ' + name;
  $('sens-value').textContent = '-';
  $('sens-range').textContent = '';
  sensNote('Waiting for a reading…');
  $('sens-overlay').hidden = false;
  refresh();
}

function closeSens() {
  sens.name = null;
  $('sens-overlay').hidden = true;
}

$('sens-close').onclick = closeSens;
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('sens-overlay').hidden) closeSens(); });

function sensorText(sensors) {
  const parts = Object.entries(sensors || {}).map(([k, v]) =>
    k.replace(/_cm$/, '') + ' ' + (v === null ? '-' : v + (SENSOR_UNITS[k] || '')));
  return parts.length ? parts.join(' · ') : '-';
}

function refresh() {
  fetch('/api/robots').then(res => {
    if (res.status === 401) { location.reload(); return null; }
    return res.json();
  }).then(list => { if (list) render(list); }).catch(() => {});
}

// ---- dialog for Add / Update / Remove

const TEXT = {
  add: {
    title: 'Add robot',
    intro: 'The hub will log in to the robot over SSH, copy the agent onto it, and set it to start on every boot.',
    hint: 'Used once to install. It is not saved.',
    go: 'Install',
  },
  update: {
    title: 'Update ',
    intro: 'Copies the current code in robot/ and the connection settings to the robot and restarts it.',
    hint: 'Usually not needed. Fill it in only if the robot asks for it.',
    go: 'Update',
  },
  remove: {
    title: 'Remove ',
    intro: 'Stops the agent, removes the start-on-boot service and the hub\'s files from the robot, and takes it off this list.',
    hint: 'Usually not needed. Fill it in only if the robot asks for it.',
    go: 'Remove',
  },
};

function openDialog(mode, name) {
  if (dlg && dlg.timer) clearTimeout(dlg.timer);
  dlg = { mode, name, job: null, timer: null };
  $('dlg-go').onclick = null;
  const t = TEXT[mode];
  $('dlg-title').textContent = t.title + (name || '');
  $('dlg-intro').textContent = t.intro;
  $('pass-hint').textContent = t.hint;
  $('f-add').hidden = mode !== 'add';
  $('f-name').hidden = mode !== 'add';
  $('f-forget').hidden = mode !== 'remove';
  $('f-reboot').hidden = mode === 'remove';
  form.password.required = mode === 'add';
  form.host.required = mode === 'add';
  form.password.value = '';
  form.forget.checked = false;
  form.reboot.checked = mode === 'add';
  if (mode === 'add') { form.host.value = ''; form.user.value = 'pi'; form.name.value = ''; }
  showForm(true);
  $('dlg-go').textContent = t.go;
  $('dlg-go').className = mode === 'remove' ? 'danger' : 'primary';
  $('overlay').hidden = false;
  (mode === 'add' ? form.host : form.password).focus();
}

function showForm(show) {
  form.hidden = !show;
  $('dlg-error').textContent = '';
  $('dlg-steps').replaceChildren();
  $('dlg-note').hidden = true;
  $('dlg-go').hidden = !show;
  $('dlg-go').disabled = false;
  $('dlg-close').textContent = show ? 'Cancel' : 'Close';
}

function closeDialog() {
  if (dlg && dlg.timer) clearTimeout(dlg.timer);
  dlg = null;
  $('overlay').hidden = true;
  refresh();
}

form.onsubmit = event => {
  event.preventDefault();
  if (!dlg) return;
  const data = { password: form.password.value, reboot: form.reboot.checked };
  let url;
  if (dlg.mode === 'add') {
    Object.assign(data, { host: form.host.value.trim(), user: form.user.value.trim(), name: form.name.value.trim() });
    url = '/api/robots';
  } else {
    data.forget = form.forget.checked;
    url = '/api/robots/' + encodeURIComponent(dlg.name) + '/' + dlg.mode;
  }
  $('dlg-go').disabled = true;
  $('dlg-error').textContent = '';
  post(url, data).then(out => {
    dlg.job = out.job;
    showForm(false);
    $('dlg-close').textContent = 'Hide';
    pollJob();
  }, err => {
    $('dlg-go').disabled = false;
    $('dlg-error').textContent = err.message;
  });
};

function pollJob() {
  if (!dlg || !dlg.job) return;
  const current = dlg;
  fetch('/api/jobs/' + current.job).then(res => res.json()).then(job => {
    if (dlg !== current) return;
    const list = $('dlg-steps');
    list.replaceChildren();
    for (const s of job.steps) {
      const li = document.createElement('li');
      li.className = s.state;
      const icon = document.createElement('span');
      icon.className = 'icon';
      icon.textContent = { ok: '✓', fail: '✕', run: '…', info: '' }[s.state];
      const text = document.createElement('span');
      text.textContent = s.text;
      if (s.state !== 'info') li.appendChild(icon);
      li.appendChild(text);
      list.appendChild(li);
    }
    if (job.state === 'running') {
      current.timer = setTimeout(pollJob, 600);
      return;
    }
    const note = $('dlg-note');
    note.hidden = false;
    if (job.state === 'done') {
      note.className = 'note good';
      note.textContent = job.message;
    } else {
      note.className = 'note ' + (job.state === 'warning' ? 'warn' : 'bad');
      note.textContent = job.message;
      if (job.state === 'failed') {          // let them fix the form and try again
        $('dlg-go').hidden = false;
        $('dlg-go').disabled = false;
        $('dlg-go').textContent = 'Try again';
        $('dlg-go').onclick = () => { $('dlg-go').onclick = null; showForm(true); $('dlg-go').textContent = TEXT[current.mode].go; return false; };
      }
    }
    $('dlg-close').textContent = 'Close';
    refresh();
  }).catch(() => { current.timer = setTimeout(pollJob, 1500); });
}

// ---- manual drive panel
// While a button or key is held, the page sends a drive command about 10 times a second.
// The robot stops by itself if they stop arriving, so a closed tab or dropped link is safe.

// [forward, strafe, rotate] for each key; strafe + is right, rotate + is clockwise
const DIRS = { w: [1, 0, 0], s: [-1, 0, 0], a: [0, -1, 0], d: [0, 1, 0], q: [0, 0, -1], e: [0, 0, 1] };
const drv = { name: null, held: new Set(), moving: false, timer: null };

function driveVector() {
  const speed = $('drive-speed').value / 100;
  const sum = [0, 0, 0];
  for (const k of drv.held) DIRS[k].forEach((x, i) => { sum[i] += x; });
  return sum.map(x => Math.max(-1, Math.min(1, x)) * speed);
}

function sendStop() {
  drv.moving = false;
  if (drv.name) post('/api/robots/' + encodeURIComponent(drv.name) + '/stop').catch(() => {});
}

function driveTick() {
  if (!drv.name) return;
  const v = driveVector();
  if (v.every(x => x === 0)) {
    if (drv.moving) sendStop();
    return;
  }
  drv.moving = true;
  post('/api/robots/' + encodeURIComponent(drv.name) + '/drive', { forward: v[0], strafe: v[1], rotate: v[2] })
    .then(() => { $('drive-error').textContent = ''; })
    .catch(err => { $('drive-error').textContent = err.message; });
}

function paintPad() {
  document.querySelectorAll('#drive-pad [data-key]').forEach(b => b.classList.toggle('on', drv.held.has(b.dataset.key)));
}

function release() { drv.held.clear(); paintPad(); }

function openDrive(name) {
  drv.name = name;
  drv.moving = false;
  release();
  $('drive-title').textContent = 'Drive ' + name;
  $('drive-error').textContent = '';
  $('drive-overlay').hidden = false;
  clearInterval(drv.timer);
  drv.timer = setInterval(driveTick, 100);
}

function closeDrive() {
  release();
  sendStop();
  clearInterval(drv.timer);
  drv.timer = null;
  drv.name = null;
  $('drive-overlay').hidden = true;
}

document.querySelectorAll('#drive-pad [data-key]').forEach(b => {
  const key = b.dataset.key;
  b.onpointerdown = e => { e.preventDefault(); drv.held.add(key); paintPad(); };
  for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) {
    b['on' + ev] = () => { drv.held.delete(key); paintPad(); };
  }
});
$('drive-stop').onclick = () => { release(); sendStop(); };
$('drive-close').onclick = closeDrive;
$('drive-speed').oninput = () => { $('drive-speed-label').textContent = $('drive-speed').value + '%'; };
document.addEventListener('keydown', e => {
  if ($('drive-overlay').hidden) return;
  const k = e.key.toLowerCase();
  if (e.key === 'Escape') { closeDrive(); return; }
  if (k === ' ') { e.preventDefault(); release(); sendStop(); return; }
  if (DIRS[k]) { e.preventDefault(); if (!e.repeat) { drv.held.add(k); paintPad(); } }
});
document.addEventListener('keyup', e => { drv.held.delete(e.key.toLowerCase()); paintPad(); });
window.addEventListener('blur', () => { if (drv.name) release(); });
document.addEventListener('visibilitychange', () => { if (document.hidden && drv.name) release(); });

// ---- arm panel: one slider per joint; each value is a servo pulse width in microseconds.
// The robot reports its joints and their limits (ARM_JOINTS in robot/robot_movement.py) when it
// connects; DEFAULT_JOINTS is only used for older agents that don't.

const DEFAULT_JOINTS = { base: [500, 2500], shoulder: [500, 2500], elbow: [500, 2500], wrist: [500, 2500], gripper: [500, 2500] };
const armLimits = {};        // robot name -> {joint: [low, high]}, filled in by render()
const arm = { name: null, timer: null, pending: {} };
const armLast = {};          // robot name -> {joint: pulse} last sent, so the sliders reopen where the arm is

function armRemembered(name) {
  if (!armLast[name]) {
    try { armLast[name] = JSON.parse(localStorage.getItem('arm:' + name)) || {}; } catch (e) { armLast[name] = {}; }
  }
  return armLast[name];
}

function armRemember(name, joint, value) {
  armRemembered(name)[joint] = value;
  try { localStorage.setItem('arm:' + name, JSON.stringify(armLast[name])); } catch (e) {}
}

function armSend() {
  arm.timer = null;
  const targets = arm.pending;
  arm.pending = {};
  if (!arm.name || !Object.keys(targets).length) return;
  post('/api/robots/' + encodeURIComponent(arm.name) + '/arm', { targets: targets })
    .then(() => { $('arm-error').textContent = ''; })
    .catch(err => { $('arm-error').textContent = err.message; });
}

function armQueue(joint, value) {            // at most ~12 messages a second while a slider is dragged
  arm.pending[joint] = value;
  if (!arm.timer) arm.timer = setTimeout(armSend, 80);
}

function buildArm() {
  const box = $('arm-sliders');
  box.replaceChildren();
  const joints = (arm.name && armLimits[arm.name]) || DEFAULT_JOINTS;
  const last = armRemembered(arm.name);
  for (const [joint, [low, high]] of Object.entries(joints)) {
    const saved = Number(last[joint]);         // start where we left it; mid-range if never moved
    const start = Number.isFinite(saved) ? Math.min(high, Math.max(low, saved)) : Math.round((low + high) / 20) * 10;
    const label = document.createElement('label');
    const name = document.createElement('span');
    name.textContent = joint + ' ';
    const shown = document.createElement('span');
    shown.className = 'muted';
    shown.textContent = start + ' \u00b5s';
    const input = document.createElement('input');
    input.type = 'range';
    input.min = low; input.max = high; input.step = 10; input.value = start;
    input.oninput = () => {
      shown.textContent = input.value + ' \u00b5s';
      armRemember(arm.name, joint, Number(input.value));
      armQueue(joint, Number(input.value));
    };
    label.append(name, shown, input);
    box.appendChild(label);
  }
}

function openArm(name) {
  arm.name = name;
  arm.pending = {};
  $('arm-title').textContent = 'Arm: ' + name;
  $('arm-error').textContent = '';
  buildArm();                                 // sliders start where they were left, but nothing is sent yet
  $('arm-overlay').hidden = false;
}

function closeArm() {
  clearTimeout(arm.timer);
  arm.timer = null;
  arm.pending = {};
  arm.name = null;
  $('arm-overlay').hidden = true;
}

$('arm-stop').onclick = () => { if (arm.name) post('/api/robots/' + encodeURIComponent(arm.name) + '/stop').catch(() => {}); };
$('arm-release').onclick = () => {
  if (arm.name) post('/api/robots/' + encodeURIComponent(arm.name) + '/arm_release').catch(err => { $('arm-error').textContent = err.message; });
};
$('arm-close').onclick = closeArm;
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('arm-overlay').hidden) closeArm(); });

// ---- camera: the hub serves the robot's frames as an MJPEG stream the <img> shows directly.
// Having the stream open is what keeps the robot's camera on; closing it lets the camera turn off.

const cam = { name: null, timer: null };

function camStart() {
  const img = $('cam-img');
  $('cam-msg').hidden = false;
  $('cam-msg').textContent = 'Waiting for the camera…';
  img.onload = () => { $('cam-msg').hidden = true; };
  img.onerror = () => {                    // robot offline or the stream ended: try again shortly
    $('cam-msg').hidden = false;
    $('cam-msg').textContent = 'No picture yet. Retrying…';
    clearTimeout(cam.timer);
    if (cam.name) cam.timer = setTimeout(camStart, 2000);
  };
  img.src = '/api/robots/' + encodeURIComponent(cam.name) + '/camera?t=' + Date.now();
}

function openCam(name) {
  cam.name = name;
  $('cam-title').textContent = 'Camera: ' + name;
  $('cam-overlay').hidden = false;
  camStart();
}

function closeCam() {
  clearTimeout(cam.timer);
  cam.name = null;
  $('cam-img').removeAttribute('src');     // drops the connection, so the robot's camera can stop
  $('cam-overlay').hidden = true;
}

$('cam-close').onclick = closeCam;
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('cam-overlay').hidden) closeCam(); });

// ---- terminal: one command at a time over SSH; the server tells us which folder it ended in

const term = { name: null, cwd: '', busy: false, history: [], pos: 0 };

function termAdd(command, output, meta, bad) {
  const out = $('term-out');
  const line = document.createElement('div');
  line.className = 'cmd';
  line.textContent = command;
  out.appendChild(line);
  if (output) {
    const pre = document.createElement('pre');
    pre.textContent = output;             // text only, so robot output can't inject markup
    out.appendChild(pre);
  }
  if (meta) {
    const m = document.createElement('div');
    m.className = 'meta' + (bad ? ' bad' : '');
    m.textContent = meta;
    out.appendChild(m);
  }
  out.scrollTop = out.scrollHeight;
}

function setPrompt() { $('term-prompt').textContent = (term.cwd || '~') + ' $'; }

function openTerm(name) {
  if (drv.name) closeDrive();
  term.name = name;
  term.cwd = '';
  term.busy = false;
  setPrompt();
  $('term-title').textContent = 'Terminal: ' + name;
  $('term-out').replaceChildren();
  $('term-input').value = '';
  $('term-overlay').hidden = false;
  $('term-input').focus();
}

function closeTerm() {
  term.name = null;
  $('term-overlay').hidden = true;
}

$('term-form').onsubmit = event => {
  event.preventDefault();
  const command = $('term-input').value.trim();
  if (!command || term.busy || !term.name) return;
  const name = term.name;
  const prompt = $('term-prompt').textContent;
  term.history.push(command);
  if (term.history.length > 200) term.history.shift();
  term.pos = term.history.length;
  term.busy = true;
  $('term-run').disabled = true;
  $('term-run').textContent = 'Running…';
  $('term-input').value = '';
  post('/api/robots/' + encodeURIComponent(name) + '/exec', { command: command, cwd: term.cwd }).then(out => {
    if (term.name !== name) return;       // the panel was closed or switched meanwhile
    if (out.cwd) term.cwd = out.cwd;
    setPrompt();
    let meta = '';
    if (out.timed_out) meta = 'stopped: it took longer than ' + out.limit + ' seconds';
    else if (out.code) meta = 'exit code ' + out.code;
    if (out.truncated) meta += (meta ? ' · ' : '') + 'output cut short';
    termAdd(prompt + ' ' + command, out.output, meta, !!out.code || !!out.timed_out);
  }, err => {
    if (term.name === name) termAdd(prompt + ' ' + command, '', err.message, true);
  }).finally(() => {
    term.busy = false;
    $('term-run').disabled = false;
    $('term-run').textContent = 'Run';
    if (term.name) $('term-input').focus();
  });
};

$('term-input').onkeydown = e => {         // Up / Down walk through earlier commands
  if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
  if (!term.history.length) return;
  e.preventDefault();
  term.pos = e.key === 'ArrowUp' ? Math.max(0, term.pos - 1) : Math.min(term.history.length, term.pos + 1);
  e.target.value = term.history[term.pos] || '';
};
$('term-clear').onclick = () => $('term-out').replaceChildren();
$('term-close').onclick = closeTerm;
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('term-overlay').hidden) closeTerm(); });

$('add').onclick = () => openDialog('add');
$('dlg-close').onclick = closeDialog;
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('overlay').hidden) closeDialog(); });

refresh();
setInterval(refresh, 1000);
  

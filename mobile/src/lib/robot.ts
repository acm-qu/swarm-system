// What the hub says about a robot (GET /api/robots), and the small rules the screens share.
// Same rules as the web page (hub/static/app.js), so both show a robot the same way.

export type Capabilities = {
  drive?: boolean;
  camera?: boolean;
  arm?: Record<string, [number, number]>; // joint -> [lowest, highest] pulse in microseconds
  sensors?: string[];
};

export type Robot = {
  name: string;
  status: 'connected' | 'unresponsive' | 'offline';
  seen_ago: number | null;
  latency_ms: number | null;
  event: string;
  hostname: string;
  address: string | null;
  installed: boolean;
  added: number | null;
  updated: number | null;
  robot_type: string;
  capabilities: Capabilities | null;
  sensors: Record<string, number | null>;
  job: string | null;
  controlled_by: string | null;
};

export type Feature = 'drive' | 'arm' | 'camera' | 'distance' | 'gyro';

export const ULTRASONIC_MAX_CM = 200; // the robot reports this when nothing is in range (robot/sensors.py)
export const SLOW_MS = 200; // latency above this feels laggy
export const CHART_SECONDS = 180; // the distance chart shows this much of the past

// Only used for older agents that don't report their joints (ARM_JOINTS in robot/robot_movement.py).
const DEFAULT_JOINTS: Record<string, [number, number]> = {
  base: [500, 2500],
  shoulder: [500, 2500],
  elbow: [500, 2500],
  wrist: [500, 2500],
  gripper: [500, 2500],
};
const JOINT_ORDER = ['base', 'shoulder', 'elbow', 'wrist', 'gripper'];

export const live = (r: Robot) => r.status !== 'offline';

/** What the robot said it can do when it connected. Older agents don't say, so allow everything. */
export function can(r: Robot, what: Feature): boolean {
  const c = r.capabilities;
  const sensors = c ? c.sensors || [] : Object.keys(r.sensors || {});
  if (what === 'gyro') return sensors.includes('rot_z_deg');
  if (what === 'distance') return !c || sensors.includes('distance_cm');
  if (!c) return true;
  if (what === 'arm') return Object.keys(c.arm || {}).length > 0;
  return !!c[what];
}

/** Joints in arm order (the hub's JSON comes back sorted by name). */
export function joints(r: Robot): [string, [number, number]][] {
  const c = r.capabilities;
  const js = c && Object.keys(c.arm || {}).length ? c.arm! : DEFAULT_JOINTS;
  const rank = (j: string) => (JOINT_ORDER.includes(j) ? JOINT_ORDER.indexOf(j) : JOINT_ORDER.length);
  return Object.entries(js).sort((x, y) => rank(x[0]) - rank(y[0]));
}

/** Why the Drive or Arm controls are off, or 'ok'. `ro` = someone else is in control. */
export function controlMode(r: Robot, me: string, what: 'drive' | 'arm'): 'ok' | 'offline' | 'missing' | 'ro' {
  if (!live(r)) return 'offline';
  if (!can(r, what)) return 'missing';
  return r.controlled_by && r.controlled_by !== me ? 'ro' : 'ok';
}

// ---- text

const missing = (v: unknown): v is null | undefined => v === null || v === undefined;

export const initials = (s: string) => String(s).slice(0, 2).toUpperCase();
export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
export const ms = (v: number | null | undefined) => (missing(v) ? '—' : v + ' ms');
export const num = (v: number | null | undefined, digits: number) =>
  missing(v) ? '—' : Number(v).toFixed(digits).replace('-', '−');
export const signed = (v: number) => (v === 0 ? '0.00' : (v > 0 ? '+' : '−') + Math.abs(v).toFixed(2));

export function ago(seconds: number | null | undefined): string {
  if (missing(seconds)) return '—';
  if (seconds < 1) return 'now';
  if (seconds < 60) return Math.round(seconds) + ' s ago';
  if (seconds < 3600) return Math.round(seconds / 60) + ' min ago';
  if (seconds < 86400) return Math.round(seconds / 3600) + ' h ago';
  return Math.round(seconds / 86400) + ' days ago';
}

export function when(epoch: number | null | undefined): string {
  if (!epoch) return '—';
  return new Date(epoch * 1000).toLocaleString([], {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function distText(d: number | null | undefined): string {
  if (missing(d)) return '—';
  return d >= ULTRASONIC_MAX_CM ? '≥ ' + ULTRASONIC_MAX_CM : String(Math.round(d));
}

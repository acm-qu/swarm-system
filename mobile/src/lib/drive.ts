// Turning the two thumb sticks into the drive command the hub expects:
// forward, strafe and rotate, each from -1 to 1 (strafe + is right, rotate + is clockwise).

export type Stick = { x: number; y: number }; // -1..1 each; x + is right, y + is up

export const CENTER: Stick = { x: 0, y: 0 };
const DEAD_ZONE = 0.15; // a thumb resting near the middle must not creep the robot

/**
 * Where the thumb is on a stick. (x, y) is the touch inside a square of `size` points, y down
 * as on a screen. The result stays inside the unit circle, and is zero inside the dead zone.
 */
export function stickFromTouch(x: number, y: number, size: number): Stick {
  const r = size / 2;
  let sx = (x - r) / r;
  let sy = (r - y) / r;
  const length = Math.hypot(sx, sy);
  if (!Number.isFinite(length) || length < DEAD_ZONE) return CENTER;
  if (length > 1) {
    sx /= length;
    sy /= length;
  }
  return { x: sx, y: sy };
}

const round2 = (v: number) => Math.round(v * 100) / 100 || 0; // "|| 0" turns -0 into 0

/** [forward, strafe, rotate] to send: the move stick and the turn stick, scaled by the speed (10-100 %). */
export function driveCommand(move: Stick, turn: Stick, speedPercent: number): [number, number, number] {
  const k = Math.max(0, Math.min(100, speedPercent)) / 100;
  return [round2(move.y * k), round2(move.x * k), round2(turn.x * k)];
}

export const isStopped = (v: readonly number[]) => v.every((x) => x === 0);

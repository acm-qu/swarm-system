import { CENTER, driveCommand, isStopped, stickFromTouch } from '../drive';

describe('stickFromTouch', () => {
  it('is centred in the middle and inside the dead zone', () => {
    expect(stickFromTouch(50, 50, 100)).toEqual(CENTER);
    expect(stickFromTouch(55, 47, 100)).toEqual(CENTER);
  });

  it('points up when the thumb is at the top', () => {
    const s = stickFromTouch(50, 0, 100);
    expect(s.x).toBeCloseTo(0);
    expect(s.y).toBeCloseTo(1);
  });

  it('never leaves the unit circle, even when the thumb slides off the stick', () => {
    const s = stickFromTouch(400, -300, 100);
    expect(Math.hypot(s.x, s.y)).toBeCloseTo(1);
    expect(s.x).toBeGreaterThan(0);
    expect(s.y).toBeGreaterThan(0);
  });

  it('is centred for a stick that has no size yet', () => {
    expect(stickFromTouch(10, 10, 0)).toEqual(CENTER);
  });
});

describe('driveCommand', () => {
  it('sends nothing but zeros when both sticks are centred', () => {
    const v = driveCommand(CENTER, CENTER, 100);
    expect(v).toEqual([0, 0, 0]);
    expect(isStopped(v)).toBe(true);
  });

  it('maps up to forward, right to strafe and the turn stick to rotate, scaled by speed', () => {
    expect(driveCommand({ x: 0, y: 1 }, CENTER, 40)).toEqual([0.4, 0, 0]);
    expect(driveCommand({ x: -1, y: 0 }, { x: 1, y: 0.7 }, 50)).toEqual([0, -0.5, 0.5]);
  });

  it('stays within -1..1 whatever the speed setting', () => {
    expect(driveCommand({ x: 0, y: -1 }, { x: -1, y: 0 }, 500)).toEqual([-1, 0, -1]);
    expect(isStopped(driveCommand({ x: 1, y: 1 }, { x: 1, y: 0 }, -20))).toBe(true);
  });
});

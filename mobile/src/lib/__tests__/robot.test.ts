import { ago, can, controlMode, distText, joints, num, signed, type Robot } from '../robot';

const robot = (over: Partial<Robot> = {}): Robot => ({
  name: 'Clanker', status: 'connected', seen_ago: 0.4, latency_ms: 18, event: 'connected',
  hostname: 'masterpi-01', address: '192.168.149.1', installed: true, added: null, updated: null,
  robot_type: 'masterpi', capabilities: null, sensors: {}, job: null, controlled_by: null,
  ...over,
});

describe('can', () => {
  it('allows everything for an older agent that reports no capabilities', () => {
    const r = robot({ sensors: { rot_z_deg: 3 } });
    expect(can(r, 'drive')).toBe(true);
    expect(can(r, 'arm')).toBe(true);
    expect(can(r, 'gyro')).toBe(true);
  });

  it('follows what the robot reported', () => {
    const r = robot({ capabilities: { drive: true, camera: false, arm: {}, sensors: ['distance_cm'] } });
    expect(can(r, 'drive')).toBe(true);
    expect(can(r, 'camera')).toBe(false);
    expect(can(r, 'arm')).toBe(false);
    expect(can(r, 'distance')).toBe(true);
    expect(can(r, 'gyro')).toBe(false);
  });
});

describe('controlMode', () => {
  const caps = { drive: true, arm: { base: [500, 2500] as [number, number] } };

  it('is ok when nobody or you have control', () => {
    expect(controlMode(robot({ capabilities: caps }), 'asmaa', 'drive')).toBe('ok');
    expect(controlMode(robot({ capabilities: caps, controlled_by: 'asmaa' }), 'asmaa', 'arm')).toBe('ok');
  });

  it('is read-only while someone else has control', () => {
    expect(controlMode(robot({ capabilities: caps, controlled_by: 'sara' }), 'asmaa', 'drive')).toBe('ro');
  });

  it('puts offline before everything else', () => {
    expect(controlMode(robot({ status: 'offline', controlled_by: 'sara' }), 'asmaa', 'drive')).toBe('offline');
    expect(controlMode(robot({ capabilities: { drive: false } }), 'asmaa', 'drive')).toBe('missing');
  });
});

describe('joints', () => {
  it('puts the joints in arm order, unknown ones last', () => {
    const r = robot({ capabilities: { arm: { wrist: [600, 2400], extra: [500, 2500], base: [500, 2500] } } });
    expect(joints(r).map(([j]) => j)).toEqual(['base', 'wrist', 'extra']);
  });

  it('falls back to the five standard joints', () => {
    expect(joints(robot()).map(([j]) => j)).toEqual(['base', 'shoulder', 'elbow', 'wrist', 'gripper']);
  });
});

describe('text', () => {
  it('says how long ago', () => {
    expect(ago(null)).toBe('—');
    expect(ago(0.4)).toBe('now');
    expect(ago(24)).toBe('24 s ago');
    expect(ago(180)).toBe('3 min ago');
    expect(ago(3 * 3600)).toBe('3 h ago');
  });

  it('shows a distance, and the sensor limit as "at least"', () => {
    expect(distText(undefined)).toBe('—');
    expect(distText(41.6)).toBe('42');
    expect(distText(200)).toBe('≥ 200');
  });

  it('formats numbers with a real minus sign', () => {
    expect(num(-1.24, 1)).toBe('−1.2');
    expect(num(null, 1)).toBe('—');
    expect(signed(0.4)).toBe('+0.40');
    expect(signed(-0.4)).toBe('−0.40');
    expect(signed(0)).toBe('0.00');
  });
});

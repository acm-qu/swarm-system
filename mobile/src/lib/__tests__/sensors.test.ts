import type { Robot } from '../robot';
import { addReading, chartPoints, NO_TRACK } from '../sensors';

const robot = (distance_cm: number | null, status: Robot['status'] = 'connected') =>
  ({ status, sensors: { distance_cm } }) as unknown as Robot;

describe('addReading', () => {
  it('keeps the lowest and highest reading and counts them', () => {
    let track = addReading(NO_TRACK, robot(42), 1000);
    track = addReading(track, robot(12), 2000);
    track = addReading(track, robot(180), 3000);
    expect(track).toMatchObject({ low: 12, high: 180, count: 3 });
    expect(track.hist).toEqual([[1000, 42], [2000, 12], [3000, 180]]);
  });

  it('ignores a robot that is not connected or has no reading', () => {
    expect(addReading(NO_TRACK, robot(42, 'unresponsive'), 1000)).toBe(NO_TRACK);
    expect(addReading(NO_TRACK, robot(null), 1000)).toBe(NO_TRACK);
    expect(addReading(NO_TRACK, undefined, 1000)).toBe(NO_TRACK);
  });

  it('drops readings older than the chart and caps the chart at the sensor limit', () => {
    let track = addReading(NO_TRACK, robot(50), 0);
    track = addReading(track, robot(900), 181_000);
    expect(track.hist).toEqual([[181_000, 200]]);
    expect(track.high).toBe(900);
  });
});

describe('chartPoints', () => {
  it('puts the newest reading at the right edge and far readings near the top', () => {
    expect(chartPoints([[0, 0], [90_000, 200]], 180_000, 600, 80)).toEqual(['0.0,78.0', '300.0,6.0']);
  });
});

// The distance readings kept while a robot is open: lowest, highest, and the last few minutes
// for the chart (the hub doesn't keep sensor history yet).
import { CHART_SECONDS, ULTRASONIC_MAX_CM, type Robot } from './robot';

export type Track = { low: number | null; high: number | null; count: number; hist: [number, number][] }; // hist: [time ms, cm]

export const NO_TRACK: Track = { low: null, high: null, count: 0, hist: [] };

/** Adds the robot's current distance reading, taken at `now` (ms). Returns the same track if there is none. */
export function addReading(track: Track, robot: Robot | undefined, now: number): Track {
  const d = robot?.sensors?.distance_cm;
  if (!robot || robot.status !== 'connected' || typeof d !== 'number') return track;
  const hist = track.hist.filter(([t]) => t >= now - CHART_SECONDS * 1000);
  hist.push([now, Math.min(d, ULTRASONIC_MAX_CM)]);
  return {
    low: track.low === null ? d : Math.min(track.low, d),
    high: track.high === null ? d : Math.max(track.high, d),
    count: track.count + 1,
    hist,
  };
}

/** The chart's line as SVG points in a width x height box: newest reading on the right, 0 cm at the bottom. */
export function chartPoints(hist: [number, number][], now: number, width: number, height: number): string[] {
  return hist.map(([t, cm]) => {
    const x = width - ((now - t) / (CHART_SECONDS * 1000)) * width;
    const y = height - 2 - (cm / ULTRASONIC_MAX_CM) * (height - 8);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
}

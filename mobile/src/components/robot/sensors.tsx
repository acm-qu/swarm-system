// Sensors: the distance reading with its last three minutes, the gyro, and anything else the
// robot reports (mockups phone-12, phone-13). Says what to check when a reading looks wrong.
import { useState } from 'react';
import { View } from 'react-native';
import Svg, { Circle, Line, Polygon, Polyline, Text as SvgText } from 'react-native-svg';

import { robotPost } from '@/lib/api';
import { useHub } from '@/lib/hub';
import { can, CHART_SECONDS, distText, live, num, ULTRASONIC_MAX_CM, type Robot } from '@/lib/robot';
import { chartPoints, type Track } from '@/lib/sensors';
import { useTheme } from '@/theme';
import { Battery, Crosshair, Radar, Rotate3d } from '../icons';
import { Btn, Card, Code, Grow, Note, Pill, Row, TitledCard, Txt } from '../ui';

const KNOWN = ['distance_cm', 'rot_x_deg', 'rot_y_deg', 'rot_z_deg', 'gyro_x_dps', 'gyro_y_dps', 'gyro_z_dps'];
const isNumber = (v: unknown): v is number => typeof v === 'number';

/** What to check when there's no good reading. */
function distanceAdvice(robot: Robot, track: Track): { kind: 'plain' | 'good' | 'warn' | 'bad'; text: string } {
  const d = robot.sensors.distance_cm;
  if (robot.status !== 'connected') return { kind: 'warn', text: 'The robot is not connected right now.' };
  if (d === undefined) {
    return can(robot, 'distance') ? { kind: 'plain', text: 'Waiting for a reading…' } : {
      kind: 'bad',
      text: "This robot didn't report an ultrasonic sensor. Check the pins in robot/sensors.py and press Update. If it is still " +
        'missing, run "journalctl -u swarm-agent -n 30" in the Terminal: the robot prints why it turned the sensor off.',
    };
  }
  if (d === null) {
    return { kind: 'bad', text: 'The sensor is set up but gave no reading. Check the Echo wire and the 1 kΩ / 2 kΩ divider, and that VCC is on 5V (pin 2).' };
  }
  if (d >= ULTRASONIC_MAX_CM) {
    return { kind: 'warn', text: `Nothing within ${ULTRASONIC_MAX_CM / 100} m. If it stays like this with your hand right in front of the sensor, check the Echo wire and the divider.` };
  }
  if ((track.high ?? 0) - (track.low ?? 0) >= 2) return { kind: 'good', text: 'Working: the reading follows what is in front of the sensor.' };
  if (track.count >= 5) return { kind: 'warn', text: "The reading isn't changing. Move your hand toward the sensor. If it still doesn't change, check the wiring." };
  return { kind: 'plain', text: 'Getting readings. Move your hand in front of the sensor to check that it responds.' };
}

function DistanceCard({ robot, track, now }: { robot: Robot; track: Track; now: number }) {
  const t = useTheme();
  const d = robot.sensors.distance_cm;
  const points = chartPoints(track.hist, now, 600, 80);
  const advice = distanceAdvice(robot, track);
  return (
    <TitledCard icon={Radar} title="Distance" right={<Txt size={12} tone="text3">Ultrasonic · up to 2 m</Txt>}>
      <Row gap={12}>
        <Txt size={36} weight="500" style={{ lineHeight: 40 }}>
          {robot.status === 'connected' ? distText(d) : '—'}
          <Txt size={15} tone="text2"> cm</Txt>
        </Txt>
        {track.low !== null && track.high !== null ? (
          <Txt size={12.5} tone="text2" style={{ flex: 1 }}>
            Since you opened this robot: lowest <Txt size={12.5} weight="500">{Math.round(track.low)} cm</Txt>, highest{' '}
            <Txt size={12.5} weight="500">{Math.round(track.high)} cm</Txt>
          </Txt>
        ) : null}
      </Row>
      <View style={{ marginTop: 10 }} accessible accessibilityLabel={`Chart of the distance over the last ${CHART_SECONDS / 60} minutes`}>
        <Svg width="100%" height={70} viewBox="0 0 600 80" preserveAspectRatio="none">
          <Line x1={0} y1={6} x2={600} y2={6} stroke={t.borderStrong} strokeDasharray="3 4" />
          {points.length > 1 ? (
            <>
              <Polygon points={`${points[0].split(',')[0]},80 ${points.join(' ')} 600,80`} fill={t.info} fillOpacity={0.15} />
              <Polyline points={points.join(' ')} fill="none" stroke={t.info} strokeWidth={2} vectorEffect="non-scaling-stroke" />
            </>
          ) : null}
        </Svg>
        <Txt size={11} tone="text3" style={{ position: 'absolute', right: 0, top: 8 }}>{ULTRASONIC_MAX_CM} cm</Txt>
      </View>
      <Row>
        <Txt size={11} tone="text3">{CHART_SECONDS / 60} min ago</Txt>
        <Grow />
        <Txt size={11} tone="text3">now</Txt>
      </Row>
      <View style={{ marginTop: 10 }}><Note kind={advice.kind}>{advice.text}</Note></View>
    </TitledCard>
  );
}

/** A compass-style dial: the needle shows how far the robot has turned since the gyro was zeroed. */
function Dial({ degrees }: { degrees: number | null }) {
  const t = useTheme();
  return (
    <Svg width={96} height={96} viewBox="0 0 100 100">
      <Circle cx={50} cy={50} r={46} fill={t.surfaceDeep} stroke={t.borderStrong} />
      {Array.from({ length: 24 }, (_, i) => (
        <Line key={i} x1={50} y1={i % 3 ? 8 : 6} x2={50} y2={12} stroke={t.text2} strokeWidth={i % 3 ? 1 : 1.4} transform={`rotate(${i * 15} 50 50)`} />
      ))}
      <SvgText x={50} y={27} textAnchor="middle" fontSize={9} fill={t.text2}>0°</SvgText>
      {degrees !== null ? (
        // positive = turned left (anticlockwise)
        <Line x1={50} y1={50} x2={50} y2={17} stroke={t.text} strokeWidth={2.4} strokeLinecap="round" transform={`rotate(${-degrees} 50 50)`} />
      ) : null}
      <Circle cx={50} cy={50} r={3.5} fill={t.text} />
    </Svg>
  );
}

/** A bubble level: the dot moves away from the middle as the robot tips (up to 30°). */
function Tilt({ x, y }: { x: number | null; y: number | null }) {
  const t = useTheme();
  const clamp = (v: number) => (Math.max(-30, Math.min(30, v)) / 30) * 24;
  return (
    <Svg width={56} height={56} viewBox="0 0 66 66">
      <Circle cx={33} cy={33} r={31} fill="none" stroke={t.borderStrong} />
      <Circle cx={33} cy={33} r={16} fill="none" stroke={t.borderStrong} strokeDasharray="2 3" />
      <Line x1={33} y1={4} x2={33} y2={62} stroke={t.border} />
      <Line x1={4} y1={33} x2={62} y2={33} stroke={t.border} />
      {x !== null && y !== null ? <Circle cx={33 + clamp(y)} cy={33 - clamp(x)} r={5} fill={t.text} /> : null}
    </Svg>
  );
}

function GyroCard({ robot, now }: { robot: Robot; now: number }) {
  const hub = useHub();
  const t = useTheme();
  const [calUntil, setCalUntil] = useState(0);
  const calibrating = now < calUntil;
  const s = robot.sensors;
  const read = (key: string) => (!calibrating && live(robot) && isNumber(s[key]) ? (s[key] as number) : null);
  const rz = read('rot_z_deg');
  const rx = read('rot_x_deg');
  const ry = read('rot_y_deg');

  function calibrate() {
    setCalUntil(Date.now() + 2500); // the robot measures for 2 s; give the reading a moment to come back
    robotPost(robot.name, 'gyro_calibrate').then(hub.refresh, (err) => {
      setCalUntil(0);
      hub.showToast(err.message, true);
    });
  }

  if (!can(robot, 'gyro')) {
    return <TitledCard icon={Rotate3d} title="Gyro"><Txt tone="text2">This robot didn&apos;t report a gyro.</Txt></TitledCard>;
  }
  return (
    <TitledCard icon={Rotate3d} title="Gyro" right={calibrating ? <Pill kind="info" busy label="Calibrating…" /> : null}>
      <Row gap={16}>
        <View style={{ alignItems: 'center', gap: 4 }}>
          <Dial degrees={rz} />
          <Txt size={12} tone="text2">Rotation Z</Txt>
        </View>
        <View style={{ flex: 1 }}>
          <Txt size={13} tone="text2">Turned (Z)</Txt>
          <Txt size={28} weight="500" tone={rz === null ? 'text3' : 'text'} style={{ marginTop: 4 }}>
            {rz === null ? '—' : num(Math.abs(rz), 1) + '°'}
          </Txt>
          <Txt size={13} tone="text2">
            {rz === null ? ' ' : Math.abs(rz) < 0.5 ? 'facing the start' : (rz > 0 ? 'left' : 'right') + ' of the start'}
          </Txt>
        </View>
      </Row>
      <Row gap={12} style={{ marginTop: 12, paddingTop: 12, borderTopWidth: 1, borderTopColor: t.border }}>
        <Tilt x={rx} y={ry} />
        <View style={{ flex: 1 }}>
          <Txt size={12.5} tone="text2">Tilt X / Y</Txt>
          <Txt size={13}>X {rx === null ? '—' : num(rx, 1) + '°'}</Txt>
          <Txt size={13}>Y {ry === null ? '—' : num(ry, 1) + '°'}</Txt>
        </View>
      </Row>
      <Row gap={14} style={{ marginTop: 12, borderWidth: 1, borderColor: t.border, backgroundColor: t.surfaceDeep, borderRadius: 9, paddingVertical: 10, paddingHorizontal: 13 }}>
        <Txt size={12.5} tone="text2">Speed</Txt>
        {(['x', 'y', 'z'] as const).map((axis) => {
          const v = read(`gyro_${axis}_dps`);
          return (
            <Txt key={axis} size={12.5} tone="text2">
              {axis.toUpperCase()} <Txt size={12.5} weight="500">{v === null ? '—' : num(v, 0) + ' °/s'}</Txt>
            </Txt>
          );
        })}
      </Row>
      {calibrating ? (
        <View style={{ marginTop: 12 }}>
          <Note kind="info">
            <Txt size={13.5} weight="500">Calibrating… keep the robot still</Txt>
            <Txt size={12.5} tone="text2">Readings come back in about 2 seconds.</Txt>
          </Note>
        </View>
      ) : null}
      <Btn label="Calibrate gyro" icon={Crosshair} disabled={calibrating || !live(robot)} onPress={calibrate} style={{ marginTop: 12 }} />
      {calibrating ? null : (
        <Txt size={12.5} tone="text2" style={{ marginTop: 8 }}>
          Keep the robot still for 2 seconds. Z drifts about 1° a minute, so calibrate again to zero it.
        </Txt>
      )}
    </TitledCard>
  );
}

export function SensorsPanel({ robot, track, now }: { robot: Robot; track: Track; now: number }) {
  const t = useTheme();
  // Any sensor the app has no panel for yet still shows up here (add it in robot/sensors.py).
  const others = Object.entries(robot.sensors).filter(([key]) => !KNOWN.includes(key));
  return (
    <>
      <DistanceCard robot={robot} track={track} now={now} />
      <GyroCard robot={robot} now={now} />
      {others.length ? (
        <Card style={{ padding: 14, gap: 8 }}>
          <Txt size={13} tone="text2">Other readings</Txt>
          <Row gap={12} wrap>
            {others.map(([key, value]) => (
              <Row key={key} gap={6}>
                <Code>{key}</Code>
                <Txt size={13} weight="500">{value === null ? '—' : String(value)}</Txt>
              </Row>
            ))}
          </Row>
        </Card>
      ) : null}
      <Card style={{ paddingVertical: 12, paddingHorizontal: 14 }}>
        <Row gap={10}>
          <Battery size={16} color={t.text3} />
          <Txt tone="text3">Battery</Txt>
          <Grow />
          <Pill kind="ctl" label="Coming soon" />
        </Row>
      </Card>
    </>
  );
}

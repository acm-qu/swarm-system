// Drive: two thumb sticks. The left one moves the robot (forward/back and sliding sideways), the
// right one turns it. While a stick is off-centre the app sends a drive command about 10 times a
// second; the robot stops by itself if they stop arriving, so a dropped link or a closed app is safe.
import Slider from '@react-native-community/slider';
import { useEffect, useMemo, useRef, useState } from 'react';
import { AppState, View } from 'react-native';
import { GestureDetector, usePanGesture } from 'react-native-gesture-handler';

import { robotPost } from '@/lib/api';
import { CENTER, driveCommand, isStopped, stickFromTouch, type Stick } from '@/lib/drive';
import { useHub } from '@/lib/hub';
import { controlMode, distText, live, num, signed, type Robot } from '@/lib/robot';
import { MONO, useTheme } from '@/theme';
import { Eye, LockOpen, Move, RotateCcw, RotateCw } from '../icons';
import { Btn, Card, ErrorLine, Grow, Note, Pill, Row, Txt } from '../ui';

const SEND_MS = 100;
const STICK = 132; // points across
const KNOB = 54;

// `locked`: a Stop was pressed while this thumb was down. The stick then counts as centred until
// the thumb is lifted and put down again, so the robot can't start moving again by itself.
type Held = Stick & { touching: boolean; locked: boolean };
type Phase = 'down' | 'drag' | 'up';
const LET_GO: Held = { ...CENTER, touching: false, locked: false };
const lockIfHeld = (held: Held): Held => (held.touching ? { ...held, locked: true } : held);
const afterTouch = (stick: Stick, phase: Phase) => (held: Held): Held =>
  ({ ...stick, touching: phase !== 'up', locked: phase === 'down' ? false : held.locked });

function ThumbStick({
  kind, label, value, active, disabled, onChange,
}: {
  kind: 'move' | 'turn'; label: string; value: Stick; active: boolean; disabled: boolean;
  onChange: (stick: Stick, phase: Phase) => void;
}) {
  const t = useTheme();
  const turn = kind === 'turn';
  const height = turn ? KNOB + 14 : STICK;
  // The gesture is set up once (a new set-up on every redraw would be re-sent to the phone's touch
  // system while a thumb is down), so it reaches the newest onChange through this ref.
  const latest = useRef(onChange);
  useEffect(() => {
    latest.current = onChange;
  });
  const config = useMemo(() => {
    // The turn stick only reads left/right, so its touch is always taken as vertically centred.
    const read = (x: number, y: number) => stickFromTouch(x, turn ? STICK / 2 : y, STICK);
    return {
      enabled: !disabled,
      minDistance: 0,
      runOnJS: true,
      onBegin: (e: { x: number; y: number }) => latest.current(read(e.x, e.y), 'down'),
      onUpdate: (e: { x: number; y: number }) => latest.current(read(e.x, e.y), 'drag'),
      onFinalize: () => latest.current(CENTER, 'up'),
    };
  }, [disabled, turn]);
  const pan = usePanGesture(config);
  const reach = (STICK - KNOB) / 2;
  const line = { position: 'absolute', backgroundColor: t.border } as const;
  return (
    <View style={{ alignItems: 'center', gap: 6 }}>
      <GestureDetector gesture={pan}>
        <View
          accessible
          accessibilityLabel={`${label} stick`}
          accessibilityHint={turn ? 'Drag left or right to turn the robot. Let go to stop.' : 'Drag to move the robot. Let go to stop.'}
          accessibilityState={{ disabled }}
          style={{
            width: STICK, height, borderRadius: height / 2, borderWidth: 1, alignItems: 'center', justifyContent: 'center',
            borderColor: t.borderStrong, borderStyle: disabled ? 'dashed' : 'solid',
            backgroundColor: disabled ? 'transparent' : t.surfaceDeep,
          }}>
          {turn ? (
            <>
              <RotateCcw size={16} color={t.text3} style={{ position: 'absolute', left: 12 }} />
              <RotateCw size={16} color={t.text3} style={{ position: 'absolute', right: 12 }} />
            </>
          ) : (
            <>
              <View style={[line, { width: 1, top: 10, bottom: 10 }]} />
              <View style={[line, { height: 1, left: 10, right: 10 }]} />
            </>
          )}
          <View style={{
            width: KNOB, height: KNOB, borderRadius: KNOB / 2, borderWidth: 1, alignItems: 'center', justifyContent: 'center',
            transform: [{ translateX: value.x * reach }, { translateY: turn ? 0 : -value.y * reach }],
            backgroundColor: active ? t.accent : disabled ? 'transparent' : t.surfaceRaised,
            borderColor: active ? t.accent : t.borderStrong,
          }}>
            {turn ? <RotateCw size={18} color={active ? t.accentText : disabled ? t.text3 : t.text} />
              : <Move size={18} color={active ? t.accentText : disabled ? t.text3 : t.text} />}
          </View>
        </View>
      </GestureDetector>
      <Txt size={12.5} tone={disabled ? 'text3' : 'text2'}>{label}</Txt>
    </View>
  );
}

export function DriveCard({ robot, onSteering }: { robot: Robot; onSteering: (steering: boolean) => void }) {
  const hub = useHub();
  const t = useTheme();
  const { name } = robot;
  const me = hub.user || '';
  const mode = controlMode(robot, me, 'drive');
  const ok = mode === 'ok';
  const [move, setMove] = useState<Held>(LET_GO);
  const [turn, setTurn] = useState<Held>(LET_GO);
  const [speed, setSpeed] = useState(40);
  const [error, setError] = useState('');

  // Any Stop (this robot's, Stop all, the switcher's) locks the sticks that are being held right now.
  const [stopsSeen, setStopsSeen] = useState(hub.stopCount);
  if (hub.stopCount !== stopsSeen) {
    setStopsSeen(hub.stopCount);
    setMove(lockIfHeld);
    setTurn(lockIfHeld);
  }

  const current = (held: Held): Stick => (ok && !held.locked ? held : CENTER);
  const command = driveCommand(current(move), current(turn), speed);

  // The page must not scroll under a thumb that is steering.
  const steering = move.touching || turn.touching;
  useEffect(() => {
    onSteering(steering);
  }, [steering, onSteering]);

  // The newest command, for the sender below (which must not restart every time a stick moves).
  const latest = useRef(command);
  useEffect(() => {
    latest.current = command;
  });

  useEffect(() => {
    let moving = false;
    const sendStop = () => {
      moving = false;
      robotPost(name, 'stop').catch(() => {});
    };
    const timer = setInterval(() => {
      const v = latest.current;
      if (isStopped(v)) {
        if (moving) sendStop(); // sticks let go: stop now rather than wait for the robot's own timeout
        return;
      }
      moving = true;
      robotPost(name, 'drive', { forward: v[0], strafe: v[1], rotate: v[2] }).then(() => setError(''), (err) => setError(err.message));
    }, SEND_MS);
    return () => {
      clearInterval(timer);
      if (moving) sendStop(); // leaving the Drive tab or the robot: don't leave it rolling
      onSteering(false);
    };
  }, [name, onSteering]);

  // The app going to the background lets go of both sticks.
  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state !== 'active') {
        setMove(LET_GO);
        setTurn(LET_GO);
      }
    });
    return () => sub.remove();
  }, []);

  const why = {
    ok: '',
    offline: 'The robot is offline.',
    missing: "This robot didn't report any wheels.",
    ro: `Read-only while ${robot.controlled_by} is in control. The red Stop still works.`,
  }[mode];
  const part = (word: string, x: number) => (
    <Txt size={11.5} mono weight={x ? '500' : '400'} tone={x ? 'text' : 'text2'}>{word} {signed(x)}</Txt>
  );
  const s = robot.sensors;

  return (
    <>
      <Card style={{ padding: 14 }}>
        <Row gap={10}>
          <Txt size={15} weight="500" accessibilityRole="header">Drive</Txt>
          <Grow />
          <Txt size={13} tone="text2">Speed <Txt size={13} weight="500">{speed}%</Txt></Txt>
          {mode === 'ro' ? <Pill kind="ctl" icon={Eye} label="Watching" /> : null}
          {ok && robot.controlled_by === me ? (
            <Btn label="Release" icon={LockOpen} size="sm" hint="Lets a teammate take control right away"
              onPress={() => robotPost(name, 'release_control').then(hub.refresh, () => {})} />
          ) : null}
        </Row>
        <Row style={{ justifyContent: 'space-around', marginTop: 14 }}>
          <ThumbStick kind="move" label="Move" value={current(move)} active={ok && move.touching && !move.locked}
            disabled={!ok} onChange={(stick, phase) => setMove(afterTouch(stick, phase))} />
          <ThumbStick kind="turn" label="Turn" value={current(turn)} active={ok && turn.touching && !turn.locked}
            disabled={!ok} onChange={(stick, phase) => setTurn(afterTouch(stick, phase))} />
        </Row>
        {ok ? (
          <>
            <Slider
              accessibilityLabel="Speed" minimumValue={10} maximumValue={100} step={5} value={40} onValueChange={setSpeed}
              minimumTrackTintColor={t.accent} maximumTrackTintColor={t.borderStrong} thumbTintColor={t.accent}
              style={{ marginTop: 8, height: 36 }}
            />
            <View style={{ borderWidth: 1, borderColor: t.border, backgroundColor: t.surfaceDeep, borderRadius: 9, paddingVertical: 10, paddingHorizontal: 12 }}>
              <Txt size={11.5} tone="text2" style={{ fontFamily: MONO }} numberOfLines={1} adjustsFontSizeToFit>
                Sending: {part('Forward', command[0])} · {part('Strafe', command[1])} · {part('Rotate', command[2])}
              </Txt>
            </View>
            <ErrorLine text={error} />
            <Txt size={12.5} tone="text2" style={{ marginTop: 10 }}>
              {robot.controlled_by === me ? 'Drag a stick to move; let go and the robot stops.'
                : 'Drag a stick to move; let go and the robot stops. Your first move takes control.'}
            </Txt>
          </>
        ) : (
          <View style={{ marginTop: 12 }}><Note>{why}</Note></View>
        )}
      </Card>
      <Txt size={13} tone="text2" style={{ textAlign: 'center' }}>
        Distance <Txt size={13} weight="500">{live(robot) ? distText(s.distance_cm) : '—'} cm</Txt>
        {'     '}Turned <Txt size={13} weight="500">{live(robot) ? num(s.rot_z_deg, 1) : '—'}°</Txt>
      </Txt>
    </>
  );
}

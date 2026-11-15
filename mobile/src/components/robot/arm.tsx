// Arm: one slider per joint, as a servo pulse in microseconds (mockups phone-10, phone-11, phone-28).
// Nothing is sent until a slider moves, and the robot clips every value to the joint's limits.
import AsyncStorage from '@react-native-async-storage/async-storage';
import Slider from '@react-native-community/slider';
import { useEffect, useRef, useState } from 'react';
import { View } from 'react-native';

import { robotPost } from '@/lib/api';
import { useHub } from '@/lib/hub';
import { cap, controlMode, joints, live, type Robot } from '@/lib/robot';
import { useTheme } from '@/theme';
import { Eye, Hand, LockOpen } from '../icons';
import { ConfirmSheet } from '../sheet';
import { Btn, Card, ErrorLine, Grow, Monogram, Pill, Row, StopBtn, Txt } from '../ui';

const SEND_MS = 80; // at most ~12 messages a second while a slider is dragged

type Positions = Record<string, number>;

export function ArmCard({ robot }: { robot: Robot }) {
  const hub = useHub();
  const t = useTheme();
  const { name } = robot;
  const me = hub.user || '';
  const mode = controlMode(robot, me, 'arm');
  const ok = mode === 'ok';
  const js = joints(robot);
  // Where the sliders start: where you last left them on this phone (the robot doesn't report positions).
  const [start, setStart] = useState<Positions | null>(null);
  const [shown, setShown] = useState<Positions>({});
  const [error, setError] = useState('');
  const pending = useRef<Positions>({});
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const moved = useRef<Positions>({});

  useEffect(() => {
    let gone = false;
    AsyncStorage.getItem('arm:' + name)
      .then((text) => (text ? JSON.parse(text) : {}))
      .catch(() => ({}))
      .then((saved) => {
        if (gone) return;
        moved.current = saved;
        setStart(saved);
      });
    return () => {
      gone = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [name]);

  function move(joint: string, value: number) {
    setShown((s) => ({ ...s, [joint]: value }));
    moved.current = { ...moved.current, [joint]: value };
    pending.current[joint] = value;
    if (timer.current) return;
    timer.current = setTimeout(() => {
      timer.current = null;
      const targets = pending.current;
      pending.current = {};
      robotPost(name, 'arm', { targets }).then(() => setError(''), (err) => setError(err.message));
      AsyncStorage.setItem('arm:' + name, JSON.stringify(moved.current)).catch(() => {}); // not remembered: sliders reopen mid-range
    }, SEND_MS);
  }

  function askRelease() {
    hub.openSheet(
      <ConfirmSheet
        title={`Release ${name}'s arm?`} icon={Hand} text="The arm will sag. Support it first." confirmLabel="Release"
        onConfirm={() => {
          hub.closeSheet();
          robotPost(name, 'arm_release').catch((err) => hub.showToast(err.message, true));
        }}
      />,
    );
  }

  if (mode === 'missing') {
    return (
      <Card style={{ paddingVertical: 34, paddingHorizontal: 18, alignItems: 'center' }}>
        <Monogram icon={Hand} size={46} />
        <Txt size={16.5} weight="500" style={{ marginTop: 18, textAlign: 'center' }}>This robot has no arm board connected.</Txt>
        <Txt tone="text2" style={{ marginTop: 8, textAlign: 'center' }}>
          The arm controls turn on by themselves when the robot reports an arm board.
        </Txt>
      </Card>
    );
  }

  const lows = js.map(([, limits]) => limits[0]);
  const highs = js.map(([, limits]) => limits[1]);
  const why = mode === 'offline' ? 'The robot is offline.'
    : !ok ? `Read-only while ${robot.controlled_by} is in control. The red Stop still works. The robot doesn't report arm positions.`
    : "Nothing is sent until you move a slider. The sliders open where you last left them, on this phone. A joint's first move " +
      'after the robot restarts jumps straight to the slider, so start close to where it really is.';

  return (
    <Card style={{ padding: 14 }}>
      <Row gap={10} style={{ marginBottom: 4 }}>
        <Txt size={15} weight="500" accessibilityRole="header">Arm</Txt>
        <Grow />
        <Txt size={13} tone="text2">{Math.min(...lows)}–{Math.max(...highs)} µs</Txt>
        {mode === 'ro' ? <Pill kind="ctl" icon={Eye} label="Watching" /> : null}
        {ok && robot.controlled_by === me ? (
          <Btn label="Release" icon={LockOpen} size="sm" hint="Lets a teammate take control right away"
            onPress={() => robotPost(name, 'release_control').then(hub.refresh, () => {})} />
        ) : null}
      </Row>
      {start ? js.map(([joint, [low, high]]) => {
        const saved = Number(start[joint]); // mid-range if this joint was never moved from this phone
        const first = Number.isFinite(saved) ? Math.min(high, Math.max(low, saved)) : Math.round((low + high) / 20) * 10;
        return (
          <Row key={joint} gap={10} style={{ height: 40 }}>
            <Txt size={13.5} style={{ width: 66 }}>{cap(joint)}</Txt>
            <Slider
              accessibilityLabel={`${cap(joint)}, pulse in microseconds`} disabled={!ok}
              minimumValue={low} maximumValue={high} step={10} value={first} onValueChange={(v) => move(joint, v)}
              minimumTrackTintColor={ok ? t.accent : t.borderStrong} maximumTrackTintColor={t.borderStrong}
              thumbTintColor={ok ? t.accent : t.text3} style={{ flex: 1, height: 40 }}
            />
            <Txt size={12.5} mono weight="500" style={{ width: 62, textAlign: 'right' }}>
              {ok ? (shown[joint] ?? first) + ' µs' : '— µs'}
            </Txt>
          </Row>
        );
      }) : <View style={{ height: 40 * js.length }} />}
      <Row gap={8} style={{ marginTop: 8 }}>
        <StopBtn label="Stop (arm holds)" size="md" grow off={!live(robot)} onPress={() => hub.stop(name)} />
        <Btn label="Release (go limp)" icon={Hand} kind="dangerSoft" grow disabled={!ok} onPress={askRelease} style={{ height: 38 }} />
      </Row>
      <ErrorLine text={error} />
      <Txt size={12.5} tone="text2" style={{ marginTop: 10 }}>{why}</Txt>
    </Card>
  );
}

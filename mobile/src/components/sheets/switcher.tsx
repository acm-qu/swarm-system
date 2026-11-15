// The list of robots, opened from the robot's name in the top bar (mockup phone-09).
import { router } from 'expo-router';
import { Pressable, View } from 'react-native';

import { useHub } from '@/lib/hub';
import { live } from '@/lib/robot';
import { useTheme } from '@/theme';
import { Sheet } from '../sheet';
import { CtrlPill, Monogram, Row, StatusPill, StopBtn, Txt } from '../ui';

export function SwitcherSheet({ current, tab }: { current: string; tab?: string }) {
  const hub = useHub();
  const t = useTheme();
  const online = hub.robots.filter((r) => r.status === 'connected').length;

  function open(name: string) {
    hub.closeSheet();
    router.navigate({ pathname: '/robot/[name]', params: tab ? { name, tab } : { name } }); // stay on the same tab
  }

  return (
    <Sheet title="Switch robot" sub={`${online} of ${hub.robots.length} online`}>
      <View style={{ gap: 8 }}>
        {hub.robots.map((r) => (
          <Pressable
            key={r.name}
            accessibilityRole="button"
            accessibilityLabel={`Open ${r.name}`}
            accessibilityState={{ selected: r.name === current }}
            onPress={() => open(r.name)}
            style={{
              borderWidth: r.name === current ? 2 : 1, borderColor: r.name === current ? t.accent : t.border,
              borderRadius: 12, backgroundColor: t.surface, padding: r.name === current ? 10 : 11,
              opacity: r.status === 'connected' ? 1 : 0.8,
            }}>
            <Row gap={10}>
              <Monogram text={r.name} size={32} />
              <View style={{ flex: 1 }}>
                <Txt size={14.5}>{r.name}</Txt>
                <Txt size={11.5} tone="text3" mono>{r.hostname || '—'}</Txt>
              </View>
              <StopBtn off={!live(r)} onPress={() => hub.stop(r.name)} />
            </Row>
            <Row gap={6} wrap style={{ marginTop: 8 }}>
              <StatusPill robot={r} />
              {r.controlled_by ? <CtrlPill who={r.controlled_by} me={hub.user || ''} /> : null}
            </Row>
          </Pressable>
        ))}
      </View>
      <Txt size={12.5} tone="text2">
        Switching robots closes this one&apos;s panel: your sticks stop sending, and your control of it is released.
        You don&apos;t get control of the next robot until you drive it or move its arm.
      </Txt>
    </Sheet>
  );
}

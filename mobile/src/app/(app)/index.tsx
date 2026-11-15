// Fleet: every robot on this hub, with its Stop (mockups phone-03, phone-04, phone-05).
import { router } from 'expo-router';
import { ScrollView, View } from 'react-native';

import { Bot, Clock, Hash, KeyRound, Plus, Radio, RefreshCw, Wifi } from '@/components/icons';
import { RobotFormSheet } from '@/components/sheets/robot-form';
import { Btn, Card, CtrlPill, Grow, Monogram, Note, Row, StatusPill, StopBtn, Txt } from '@/components/ui';
import { useHub } from '@/lib/hub';
import { ago, distText, live, ms, type Robot } from '@/lib/robot';
import { useTheme } from '@/theme';

function FleetCard({ robot: r, staleSeconds }: { robot: Robot; staleSeconds: number | null }) {
  const hub = useHub();
  const t = useTheme();
  const dist = live(r) && typeof r.sensors.distance_cm === 'number' ? ` · ${distText(r.sensors.distance_cm)} cm` : '';
  const seen = r.seen_ago === null ? 'not seen yet' : 'seen ' + ago(r.seen_ago);
  return (
    <Card style={{ padding: 14 }}>
      <Row gap={12} align="flex-start">
        <Monogram text={r.name} />
        <View style={{ flex: 1 }}>
          <Row gap={8}>
            <Txt size={15} weight="500" numberOfLines={1} style={{ flexShrink: 1 }}>{r.name}</Txt>
            <Txt size={12} tone="text3" mono numberOfLines={1} style={{ flexShrink: 1 }}>{r.hostname}</Txt>
          </Row>
          <Row gap={6} wrap style={{ marginTop: 7, opacity: staleSeconds === null ? 1 : 0.75 }}>
            <StatusPill robot={r} />
            <CtrlPill who={r.controlled_by} me={hub.user || ''} />
          </Row>
        </View>
      </Row>
      <Row gap={5} style={{ marginTop: 12 }}>
        {staleSeconds !== null ? (
          <>
            <Clock size={12} color={t.warnText} />
            <Txt size={12.5} color={t.warnText}>{staleSeconds} s ago ·</Txt>
          </>
        ) : null}
        <Txt size={12.5} tone="text2" numberOfLines={1} style={{ flex: 1 }}>
          {r.job || `${seen} · ${ms(r.latency_ms)}${dist}`}
        </Txt>
      </Row>
      <Row gap={8} style={{ marginTop: 10 }}>
        <Btn label="Ping" icon={Radio} size="sm" disabled={!live(r)} onPress={() => hub.ping(r.name)} hint="Measures how fast the robot answers" />
        <Grow />
        <Btn label="Open" size="sm" onPress={() => router.navigate({ pathname: '/robot/[name]', params: { name: r.name } })} />
        <StopBtn off={!live(r)} onPress={() => hub.stop(r.name)} />
      </Row>
    </Card>
  );
}

function EmptyFleet({ onAdd }: { onAdd: () => void }) {
  const t = useTheme();
  const need = [
    { icon: Wifi, text: 'The robot switched on and on the lab Wi-Fi' },
    { icon: Hash, text: 'Its IP address, e.g. 192.168.149.1' },
    { icon: KeyRound, text: 'Its password (used once, not saved)' },
  ];
  return (
    <View style={{
      borderWidth: 1, borderStyle: 'dashed', borderColor: t.borderStrong, borderRadius: 16,
      paddingTop: 34, paddingHorizontal: 18, paddingBottom: 22, alignItems: 'center',
    }}>
      <Monogram icon={Bot} size={46} />
      <Txt size={17} weight="600" style={{ marginTop: 16, textAlign: 'center' }}>No robots yet. Press Add robot to set one up.</Txt>
      <Txt tone="text2" style={{ marginTop: 8, textAlign: 'center' }}>
        The hub installs its program on the robot for you. It takes a few minutes the first time.
      </Txt>
      <Card style={{ alignSelf: 'stretch', paddingVertical: 14, paddingHorizontal: 16, marginTop: 20, gap: 10 }}>
        <Txt size={13} tone="text2">What you need</Txt>
        {need.map(({ icon: Icon, text }) => (
          <Row key={text} gap={10} align="flex-start">
            <Icon size={16} color={t.text2} style={{ marginTop: 2 }} />
            <Txt size={13.5} style={{ flex: 1 }}>{text}</Txt>
          </Row>
        ))}
      </Card>
      <Btn label="Add robot" icon={Plus} kind="primary" size="lg" onPress={onAdd} style={{ alignSelf: 'stretch', marginTop: 20 }} />
    </View>
  );
}

export default function Fleet() {
  const hub = useHub();
  const count = hub.robots.length;
  // How old the list is while the hub can't be reached. Counted from the list's own clock, so it
  // only moves when the hub is asked again.
  const staleSeconds = hub.ok ? null : Math.round((hub.checkedAt - hub.lastOk) / 1000);
  const add = () => hub.openSheet(<RobotFormSheet mode="add" />);

  return (
    <ScrollView contentContainerStyle={{ padding: 14, gap: 12 }}>
      {staleSeconds !== null ? (
        <Note kind="warn">
          <Txt size={13.5} weight="600">Can&apos;t reach the hub. Reconnecting…</Txt>
          <Txt size={12.5} tone="text2" style={{ marginTop: 2 }}>
            Everything below may be out of date. Last update {staleSeconds} s ago. If you were driving, the robot stops
            by itself within half a second.
          </Txt>
          <Btn label="Retry now" icon={RefreshCw} size="sm" onPress={hub.refresh} style={{ alignSelf: 'flex-end', marginTop: 10 }} />
        </Note>
      ) : null}

      <Row>
        <View style={{ flex: 1 }}>
          <Txt size={20} weight="600" accessibilityRole="header">Robots</Txt>
          <Txt size={13} tone="text2">
            {count ? `${count} ${count === 1 ? 'robot' : 'robots'} on this hub` : 'No robots on this hub yet'}
          </Txt>
        </View>
        {count ? <Btn label="Add" icon={Plus} kind="primary" size="sm" onPress={add} hint="Add a robot" /> : null}
      </Row>

      {!hub.loaded ? <Txt tone="text2">{hub.ok ? 'Loading robots…' : 'Waiting for the hub…'}</Txt>
        : count ? hub.robots.map((r) => <FleetCard key={r.name} robot={r} staleSeconds={staleSeconds} />)
        : <EmptyFleet onAdd={add} />}
    </ScrollView>
  );
}

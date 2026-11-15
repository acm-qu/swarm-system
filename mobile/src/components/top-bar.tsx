// The bar at the top of every screen: where you are, how the hub is doing, and Stop all.
// It is drawn above the bottom sheets, so Stop all can always be pressed.
import { router, useGlobalSearchParams, usePathname } from 'expo-router';
import { useRef, useState } from 'react';
import { Pressable, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useHub } from '@/lib/hub';
import { ago, ms, SLOW_MS } from '@/lib/robot';
import { useTheme } from '@/theme';
import { ChevronDown, ChevronLeft, TriangleAlert } from './icons';
import { SwitcherSheet } from './sheets/switcher';
import { Logo, Row, StopBtn, Txt } from './ui';

const TITLES: Record<string, string> = { '/': 'Fleet', '/history': 'History', '/health': 'Health', '/help': 'Help' };

function HubLine() {
  const hub = useHub();
  const t = useTheme();
  if (!hub.ok) {
    return (
      <Row gap={5}>
        <TriangleAlert size={13} color={t.warnText} />
        <Txt size={12} color={t.warnText} numberOfLines={1}>Hub unreachable · reconnecting…</Txt>
      </Row>
    );
  }
  const online = hub.robots.filter((r) => r.status === 'connected').length;
  const count = !hub.loaded ? 'loading…' : hub.robots.length ? `${online} of ${hub.robots.length} online` : 'no robots yet';
  return (
    <Row gap={6}>
      <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: t.ok }} />
      <Txt size={12} tone="text2" numberOfLines={1}>Hub connected · {count}</Txt>
    </Row>
  );
}

export function TopBar() {
  const hub = useHub();
  const t = useTheme();
  const insets = useSafeAreaInsets();
  const pathname = usePathname();
  const { name, tab } = useGlobalSearchParams<{ name?: string; tab?: string }>();
  const [stopLabel, setStopLabel] = useState('Stop all');
  const labelTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const onRobot = pathname.startsWith('/robot/') && !!name;
  const robot = onRobot ? hub.byName[name] : undefined;

  async function stopAll() {
    setStopLabel(await hub.stopAll());
    if (labelTimer.current) clearTimeout(labelTimer.current);
    labelTimer.current = setTimeout(() => setStopLabel('Stop all'), 1500);
  }

  return (
    <View style={{ backgroundColor: t.topbar, borderBottomWidth: 1, borderBottomColor: t.border, paddingTop: insets.top }}>
      <Row gap={12} style={{ height: 66, paddingLeft: 16, paddingRight: 14 }}>
        {onRobot ? (
          <Pressable accessibilityRole="button" accessibilityLabel="Back to Fleet" hitSlop={12} onPress={() => router.navigate('/')}>
            <ChevronLeft size={24} color={t.text2} />
          </Pressable>
        ) : (
          <Logo />
        )}
        <View style={{ flex: 1 }}>
          {onRobot ? (
            <Pressable
              accessibilityRole="button" accessibilityLabel={`${name}. Switch robot`} hitSlop={6}
              onPress={() => hub.openSheet(<SwitcherSheet current={name} tab={tab} />)}
              style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
              <Txt size={17} weight="600" numberOfLines={1} style={{ flexShrink: 1 }}>{name}</Txt>
              <ChevronDown size={16} color={t.text2} />
            </Pressable>
          ) : (
            <Txt size={17} weight="600" accessibilityRole="header">{TITLES[pathname] || 'Swarm Hub'}</Txt>
          )}
          {robot ? (
            <Txt size={12} tone="text2" numberOfLines={1}>
              <Txt size={12} tone="text2" mono>{robot.hostname || '—'}</Txt>
              {' · ' + ms(robot.latency_ms)}
              {(robot.latency_ms ?? 0) > SLOW_MS ? <Txt size={12} color={t.warnText}> slow</Txt> : null}
              {' · seen ' + ago(robot.seen_ago)}
            </Txt>
          ) : (
            <HubLine />
          )}
        </View>
        <StopBtn label={stopLabel} size="md" onPress={stopAll} />
      </Row>
    </View>
  );
}

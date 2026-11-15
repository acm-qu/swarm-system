// One robot's page (mockups phone-06 to phone-17): camera, status, the robot's big Stop, then the
// open tab straight underneath, so the camera stays in view while you drive.
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, View } from 'react-native';

import { robotPost } from '@/lib/api';
import { useHub } from '@/lib/hub';
import { live } from '@/lib/robot';
import { addReading, NO_TRACK } from '@/lib/sensors';
import { useTheme } from '@/theme';
import { Bot, ChevronLeft, Gamepad2, Hand, Info, Lock, Radar, Terminal, type LucideIcon } from '../icons';
import { ConfirmSheet } from '../sheet';
import { Btn, CtrlPill, Monogram, Note, Row, StatusPill, StopBtn, Txt } from '../ui';
import { ArmCard } from './arm';
import { Camera } from './camera';
import { DriveCard } from './drive';
import { InfoCard } from './info';
import { SensorsPanel } from './sensors';
import { NEW_TERM, TerminalCard, type Term } from './terminal';

export type TabKey = 'drive' | 'arm' | 'sensors' | 'terminal' | 'info';

// `locks`: needs control, so it shows a lock while a teammate has the robot.
// `camera`: the tab keeps the full-size camera on top (the others get a small one).
const TABS: { key: TabKey; label: string; icon: LucideIcon; locks?: boolean; camera?: boolean }[] = [
  { key: 'drive', label: 'Drive', icon: Gamepad2, locks: true, camera: true },
  { key: 'arm', label: 'Arm', icon: Hand, locks: true, camera: true },
  { key: 'sensors', label: 'Sensors', icon: Radar },
  { key: 'terminal', label: 'Terminal', icon: Terminal },
  { key: 'info', label: 'Info', icon: Info },
];

export function RobotView({ name, tab, onTab }: { name: string; tab: TabKey; onTab: (tab: TabKey) => void }) {
  const hub = useHub();
  const t = useTheme();
  const robot = hub.byName[name];
  const me = hub.user || '';
  const [steering, setSteering] = useState(false);
  const [bigCamera, setBigCamera] = useState(false);
  const [term, setTerm] = useState<Term>(NEW_TERM);

  // One distance reading per answer from the hub, kept for the Sensors tab's chart.
  const [track, setTrack] = useState(NO_TRACK);
  const [tracked, setTracked] = useState(0);
  if (hub.lastOk !== tracked) {
    setTracked(hub.lastOk);
    setTrack(addReading(track, robot, hub.lastOk));
  }

  const known = !!robot;
  useEffect(() => {
    if (!known) return;
    robotPost(name, 'ping').catch(() => {}); // a fresh latency for the top bar
    return () => {
      robotPost(name, 'release_control').catch(() => {}); // leaving: let a teammate take over right away
    };
  }, [name, known]);

  if (!robot) {
    if (!hub.loaded) return null;
    return (
      <View style={{ margin: 14, borderWidth: 1, borderStyle: 'dashed', borderColor: t.borderStrong, borderRadius: 16, padding: 28, alignItems: 'center' }}>
        <Monogram icon={Bot} size={46} />
        <Txt size={17} weight="600" style={{ marginTop: 16, textAlign: 'center' }}>{name} isn&apos;t on this hub.</Txt>
        <Txt tone="text2" style={{ marginTop: 8 }}>It may have been removed.</Txt>
        <Btn label="Back to Fleet" icon={ChevronLeft} onPress={() => router.navigate('/')} style={{ marginTop: 18 }} />
      </View>
    );
  }

  function select(next: TabKey) {
    setBigCamera(false);
    onTab(next);
    if (next === 'terminal' && robot.installed && !hub.terminalOk) {
      hub.openSheet(
        <ConfirmSheet
          title={`Open the terminal on ${name}?`} icon={Terminal} confirmLabel="Open terminal"
          text="This runs commands directly on the robot."
          note={<Note kind="info">Commands run as the robot&apos;s user, one at a time, and stop after 30 seconds. You won&apos;t be asked again until you sign in next time.</Note>}
          onConfirm={() => { hub.allowTerminal(); hub.closeSheet(); }}
        />,
        () => onTab('drive'), // closed without agreeing: back to Drive
      );
    }
  }

  const locked = !!robot.controlled_by && robot.controlled_by !== me;
  const mini = !TABS.find((x) => x.key === tab)?.camera && !bigCamera;
  const pills = (
    <Row gap={6} wrap>
      <StatusPill robot={robot} />
      <CtrlPill who={robot.controlled_by} me={me} />
    </Row>
  );

  return (
    <ScrollView scrollEnabled={!steering} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 14, gap: 12 }}>
      {mini ? (
        <Row gap={12} align="flex-start">
          <Camera robot={robot} mini onPress={() => setBigCamera(true)} />
          <View style={{ flex: 1, gap: 8 }}>
            {pills}
            <Txt size={12} tone="text2">The camera stays live on every tab. Tap it to make it bigger.</Txt>
          </View>
        </Row>
      ) : (
        <>
          <Camera robot={robot} onPress={bigCamera ? () => setBigCamera(false) : undefined} />
          {pills}
        </>
      )}

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -14 }} contentContainerStyle={{ gap: 6, paddingHorizontal: 14 }}>
        {TABS.map(({ key, label, icon: Icon, locks }) => {
          const on = key === tab;
          return (
            <Pressable
              key={key}
              accessibilityRole="tab"
              accessibilityState={{ selected: on }}
              accessibilityLabel={label + (locks && locked ? ', read-only' : '')}
              onPress={() => select(key)}
              style={{
                flexDirection: 'row', alignItems: 'center', gap: 6, height: 36, paddingHorizontal: 13, borderRadius: 18, borderWidth: 1,
                backgroundColor: on ? t.accentSoft : t.surface, borderColor: on ? t.accentBorder : t.border,
              }}>
              <Icon size={15} color={on ? t.accent : t.text2} />
              <Txt size={13.5} tone={on ? 'text' : 'text2'}>{label}</Txt>
              {locks && locked ? <Lock size={12} color={t.text3} /> : null}
            </Pressable>
          );
        })}
      </ScrollView>

      <StopBtn label={`Stop ${name}`} size="big" off={!live(robot)} onPress={() => hub.stop(name)} />

      {tab === 'drive' ? <DriveCard robot={robot} onSteering={setSteering} /> : null}
      {tab === 'arm' ? <ArmCard robot={robot} /> : null}
      {tab === 'sensors' ? <SensorsPanel robot={robot} track={track} now={hub.lastOk} /> : null}
      {tab === 'terminal' ? <TerminalCard robot={robot} term={term} onTerm={setTerm} /> : null}
      {tab === 'info' ? <InfoCard robot={robot} /> : null}
    </ScrollView>
  );
}

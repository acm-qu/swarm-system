// Info: what the hub knows about the robot, and Update / Remove (mockups phone-16, phone-26, phone-27).
import type { ReactNode } from 'react';
import { View } from 'react-native';

import { useHub } from '@/lib/hub';
import { can, joints, when, type Feature, type Robot } from '@/lib/robot';
import { useTheme } from '@/theme';
import { Camera, Check, Download, Hand, Info, Move, Radar, Rotate3d, Trash2, type LucideIcon } from '../icons';
import { RobotFormSheet } from '../sheets/robot-form';
import { Btn, Code, Note, Pill, Row, TitledCard, Txt } from '../ui';

const CAPS: { icon: LucideIcon; what: Feature; word: string }[] = [
  { icon: Move, what: 'drive', word: 'Wheels' },
  { icon: Hand, what: 'arm', word: 'Arm' },
  { icon: Camera, what: 'camera', word: 'Camera' },
  { icon: Radar, what: 'distance', word: 'Distance sensor' },
  { icon: Rotate3d, what: 'gyro', word: 'Gyro' },
];

function InfoRow({ label, last, children }: { label: string; last?: boolean; children: ReactNode }) {
  const t = useTheme();
  return (
    <Row gap={10} style={{ paddingVertical: 11, borderBottomWidth: last ? 0 : 1, borderBottomColor: t.border }}>
      <Txt size={13.5} tone="text2" style={{ width: 128 }}>{label}</Txt>
      <Row gap={6} style={{ flex: 1 }}>{children}</Row>
    </Row>
  );
}

const Heading = ({ children }: { children: string }) => <Txt size={13} tone="text2" style={{ marginTop: 14, marginBottom: 8 }}>{children}</Txt>;

export function InfoCard({ robot: r }: { robot: Robot }) {
  const hub = useHub();
  const t = useTheme();
  const c = r.capabilities;
  const js = c && Object.keys(c.arm || {}).length ? joints(r) : null;
  const caps = c ? CAPS.filter(({ what }) => can(r, what)) : [];
  const value = (text: string) => <Txt size={13.5} style={{ flexShrink: 1 }}>{text}</Txt>;
  return (
    <TitledCard icon={Info} title="Info">
      <InfoRow label="Robot type"><Txt size={13.5} mono>{r.robot_type || '—'}</Txt></InfoRow>
      <InfoRow label="Address">{value(r.address || '—')}</InfoRow>
      <InfoRow label="Robot's own name"><Txt size={13.5} mono style={{ flexShrink: 1 }}>{r.hostname || '—'}</Txt></InfoRow>
      <InfoRow label="Installed by this hub">
        {r.installed ? <Check size={15} color={t.okText} /> : null}
        {value(r.installed ? 'Yes' : 'No')}
      </InfoRow>
      <InfoRow label="Added on">{value(when(r.added))}</InfoRow>
      <InfoRow label="Last updated" last>{value(when(r.updated))}</InfoRow>

      <Heading>What it can do</Heading>
      {c ? (
        <Row gap={6} wrap>
          {caps.length ? caps.map(({ icon, what, word }) => (
            <Pill key={what} kind="ctl" icon={icon} label={what === 'arm' && js ? `Arm · ${js.length} joints` : word} />
          )) : <Txt tone="text2">Nothing reported.</Txt>}
        </Row>
      ) : <Txt tone="text2">It tells the hub when it connects.</Txt>}

      {js ? (
        <>
          <Heading>Arm joints and limits (µs)</Heading>
          <Row gap={6} wrap>
            {js.map(([joint, [low, high]]) => (
              <View key={joint} style={{ width: '31.5%', paddingVertical: 9, paddingHorizontal: 11, borderWidth: 1, borderColor: t.border, borderRadius: 10 }}>
                <Txt size={12.5} mono>{joint}</Txt>
                <Txt size={12} tone="text2">{low}–{high}</Txt>
              </View>
            ))}
          </Row>
        </>
      ) : null}

      {c?.sensors?.length ? (
        <>
          <Heading>Sensors</Heading>
          <Row gap={6} wrap>{c.sensors.map((s) => <Code key={s}>{s}</Code>)}</Row>
        </>
      ) : null}

      {r.installed ? (
        <Row gap={8} style={{ marginTop: 16 }}>
          <Btn label="Update…" icon={Download} grow disabled={!!r.job} onPress={() => hub.openSheet(<RobotFormSheet mode="update" name={r.name} />)} />
          <Btn label="Remove…" icon={Trash2} kind="dangerSoft" grow disabled={!!r.job} onPress={() => hub.openSheet(<RobotFormSheet mode="remove" name={r.name} />)} />
        </Row>
      ) : (
        <View style={{ marginTop: 14 }}>
          <Note kind="info">This robot wasn&apos;t installed by this hub, so Update, Remove and the Terminal aren&apos;t available here.</Note>
        </View>
      )}
    </TitledCard>
  );
}

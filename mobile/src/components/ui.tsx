// The small parts every screen is built from: text, cards, buttons, pills, notes and form fields.
// Sizes and colours follow the phone mockups (design/html/phone-29-components.html).
import type { ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  Text,
  TextInput,
  View,
  type StyleProp,
  type TextInputProps,
  type TextProps,
  type TextStyle,
  type ViewStyle,
} from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';

import { initials, type Robot } from '@/lib/robot';
import { MONO, MONO_MEDIUM, useTheme, type Theme } from '@/theme';
import { Check as CheckIcon, CircleCheck, CircleX, Info, Lock, LockOpen, Octagon, TriangleAlert, WifiOff, type LucideIcon } from './icons';

type Tone = 'text' | 'text2' | 'text3';

// ---- text and layout

export function Txt({
  size = 14, weight, tone = 'text', color, mono, style, ...rest
}: TextProps & { size?: number; weight?: '400' | '500' | '600'; tone?: Tone; color?: string; mono?: boolean }) {
  const t = useTheme();
  const font: TextStyle = mono
    ? { fontFamily: weight && weight !== '400' ? MONO_MEDIUM : MONO }
    : { fontWeight: weight || '400' };
  return <Text {...rest} style={[{ fontSize: size, color: color || t[tone] }, font, style]} />;
}

export function Row({
  gap = 8, wrap, align = 'center', style, children,
}: { gap?: number; wrap?: boolean; align?: ViewStyle['alignItems']; style?: StyleProp<ViewStyle>; children?: ReactNode }) {
  return (
    <View style={[{ flexDirection: 'row', alignItems: align, gap, flexWrap: wrap ? 'wrap' : 'nowrap' }, style]}>
      {children}
    </View>
  );
}

export const Grow = () => <View style={{ flex: 1 }} />;

export function Card({ style, children }: { style?: StyleProp<ViewStyle>; children?: ReactNode }) {
  const t = useTheme();
  return (
    <View style={[{ backgroundColor: t.surface, borderColor: t.border, borderWidth: 1, borderRadius: 14 }, style]}>
      {children}
    </View>
  );
}

/** A card with a title bar: icon, title, and something on the right. */
export function TitledCard({
  icon: Icon, title, right, pad = true, children,
}: { icon: LucideIcon; title: string; right?: ReactNode; pad?: boolean; children?: ReactNode }) {
  const t = useTheme();
  return (
    <Card>
      <Row style={{ paddingVertical: 13, paddingHorizontal: 14, borderBottomWidth: 1, borderBottomColor: t.border }}>
        <Icon size={17} color={t.text} />
        <Txt size={15} weight="600">{title}</Txt>
        <Grow />
        {right}
      </Row>
      <View style={pad ? { paddingVertical: 12, paddingHorizontal: 14 } : null}>{children}</View>
    </Card>
  );
}

// ---- buttons

type BtnKind = 'default' | 'primary' | 'stop' | 'danger' | 'dangerSoft';

function btnColors(t: Theme, kind: BtnKind): { bg: string; border: string; fg: string } {
  if (kind === 'primary') return { bg: t.accent, border: t.accent, fg: t.accentText };
  if (kind === 'stop') return { bg: t.stop, border: t.stop, fg: '#FFFFFF' };
  if (kind === 'danger') return { bg: t.stopDeep, border: t.stopDeep, fg: '#FFFFFF' };
  if (kind === 'dangerSoft') return { bg: t.stopBg, border: t.stopBorder, fg: t.stopSoftText };
  return { bg: t.surfaceRaised, border: t.borderStrong, fg: t.text };
}

const BTN_SIZES = {
  sm: { height: 30, pad: 10, font: 13, radius: 9, icon: 14 },
  md: { height: 36, pad: 14, font: 14, radius: 10, icon: 15 },
  lg: { height: 46, pad: 16, font: 15, radius: 10, icon: 16 },
};

export function Btn({
  label, icon: Icon, iconRight: IconRight, kind = 'default', size = 'md', disabled, busy, grow, onPress, style, hint,
}: {
  label: string; icon?: LucideIcon; iconRight?: LucideIcon; kind?: BtnKind; size?: keyof typeof BTN_SIZES;
  disabled?: boolean; busy?: boolean; grow?: boolean; onPress?: () => void; style?: StyleProp<ViewStyle>; hint?: string;
}) {
  const t = useTheme();
  const c = btnColors(t, kind);
  const s = BTN_SIZES[size];
  const off = disabled || busy;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint={hint}
      accessibilityState={{ disabled: !!off, busy: !!busy }}
      disabled={off}
      onPress={onPress}
      hitSlop={size === 'sm' ? 8 : 4}
      style={({ pressed }) => [
        {
          height: s.height, paddingHorizontal: s.pad, borderRadius: s.radius, borderWidth: 1,
          backgroundColor: c.bg, borderColor: c.border, flexDirection: 'row', alignItems: 'center',
          justifyContent: 'center', gap: 7, opacity: off ? 0.45 : pressed ? 0.75 : 1,
        },
        grow ? { flex: 1 } : null,
        style,
      ]}>
      {busy ? <ActivityIndicator size="small" color={c.fg} /> : Icon ? <Icon size={s.icon} color={c.fg} /> : null}
      <Txt size={s.font} weight={kind === 'stop' ? '600' : '500'} color={c.fg} numberOfLines={1}>{label}</Txt>
      {IconRight ? <IconRight size={s.icon} color={c.fg} /> : null}
    </Pressable>
  );
}

/**
 * The red Stop. It never needs control and nothing may cover or disable it while the robot is
 * reachable; `off` (robot offline) only greys it out because there is nothing to stop.
 */
export function StopBtn({
  label = 'Stop', off, onPress, size = 'sm', grow, style,
}: { label?: string; off?: boolean; onPress: () => void; size?: 'sm' | 'md' | 'big'; grow?: boolean; style?: StyleProp<ViewStyle> }) {
  const t = useTheme();
  const s = size === 'big'
    ? { height: 52, pad: 16, font: 17, radius: 14, icon: 20 }
    : size === 'md' ? { height: 38, pad: 12, font: 14.5, radius: 10, icon: 17 } : BTN_SIZES.sm;
  const fg = off ? t.text3 : '#FFFFFF';
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!off }}
      disabled={off}
      onPress={onPress}
      hitSlop={8}
      style={({ pressed }) => [
        {
          height: s.height, paddingHorizontal: s.pad, borderRadius: s.radius, borderWidth: 1,
          flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7,
          backgroundColor: off ? 'transparent' : pressed ? t.stopDeep : t.stop, borderColor: off ? t.border : t.stop,
        },
        grow ? { flex: 1 } : null,
        style,
      ]}>
      <Octagon size={s.icon} color={fg} />
      <Txt size={s.font} weight="600" color={fg} numberOfLines={1}>{label}</Txt>
    </Pressable>
  );
}

// ---- avatars and pills

export function Avatar({ name, size = 18, invert }: { name: string; size?: number; invert?: boolean }) {
  const t = useTheme();
  return (
    <View style={{
      width: size, height: size, borderRadius: size / 2, alignItems: 'center', justifyContent: 'center',
      backgroundColor: invert ? t.youText : t.surfaceRaised, borderWidth: 1, borderColor: invert ? t.youText : t.borderStrong,
    }}>
      <Txt size={size * 0.46} weight="600" color={invert ? t.youBg : t.text}>{initials(name)}</Txt>
    </View>
  );
}

/** The rounded square with a robot's initials (or an icon). */
export function Monogram({ text, icon: Icon, size = 36 }: { text?: string; icon?: LucideIcon; size?: number }) {
  const t = useTheme();
  return (
    <View style={{
      width: size, height: size, borderRadius: size * 0.28, borderWidth: 1, borderColor: t.borderStrong,
      backgroundColor: t.surfaceDeep, alignItems: 'center', justifyContent: 'center',
    }}>
      {Icon ? <Icon size={size * 0.48} color={t.text} /> : <Txt size={size * 0.36} weight="600">{initials(text || '')}</Txt>}
    </View>
  );
}

type PillKind = 'ok' | 'warn' | 'off' | 'info' | 'fail' | 'ctl' | 'you' | 'nobody';

function pillColors(t: Theme, kind: PillKind): { fg: string; bg: string; border: string } {
  switch (kind) {
    case 'ok': return { fg: t.okText, bg: t.okBg, border: t.okBorder };
    case 'warn': return { fg: t.warnText, bg: t.warnBg, border: t.warnBorder };
    case 'off': return { fg: t.off, bg: t.offBg, border: t.offBorder };
    case 'info': return { fg: t.infoText, bg: t.infoBg, border: t.infoBorder };
    case 'fail': return { fg: t.stopSoftText, bg: t.stopBg, border: t.stopBorder };
    case 'you': return { fg: t.youText, bg: t.youBg, border: t.youBg };
    case 'nobody': return { fg: t.text2, bg: 'transparent', border: t.borderStrong };
    default: return { fg: t.text, bg: 'transparent', border: t.borderStrong };
  }
}

export function Pill({
  kind, icon: Icon, busy, lead, label, trail: Trail,
}: { kind: PillKind; icon?: LucideIcon; busy?: boolean; lead?: ReactNode; label: string; trail?: LucideIcon }) {
  const t = useTheme();
  const c = pillColors(t, kind);
  return (
    <View style={{
      height: 22, paddingLeft: lead ? 3 : 8, paddingRight: 8, borderRadius: 11, borderWidth: 1, gap: 5,
      flexDirection: 'row', alignItems: 'center', backgroundColor: c.bg, borderColor: c.border,
      borderStyle: kind === 'nobody' ? 'dashed' : 'solid',
    }}>
      {lead}
      {busy ? <ActivityIndicator size={12} color={c.fg} style={{ transform: [{ scale: 0.7 }] }} /> : Icon ? <Icon size={13} color={c.fg} /> : null}
      <Txt size={12} weight="500" color={c.fg} numberOfLines={1}>{label}</Txt>
      {Trail ? <Trail size={12} color={c.fg} /> : null}
    </View>
  );
}

/** Connected / Unresponsive / Offline, or "Working…" while the hub installs or updates the robot. */
export function StatusPill({ robot }: { robot: Robot }) {
  if (robot.job) return <Pill kind="info" busy label="Working…" />;
  if (robot.status === 'connected') return <Pill kind="ok" icon={CircleCheck} label="Connected" />;
  if (robot.status === 'unresponsive') return <Pill kind="warn" icon={TriangleAlert} label="Unresponsive" />;
  return <Pill kind="off" icon={WifiOff} label="Offline" />;
}

/** Who is in control: You, nobody, or a teammate (with a lock). */
export function CtrlPill({ who, me }: { who: string | null; me: string }) {
  if (who === me) return <Pill kind="you" lead={<Avatar name={me} size={16} invert />} label="You" />;
  if (!who) return <Pill kind="nobody" icon={LockOpen} label="Nobody" />;
  return <Pill kind="ctl" lead={<Avatar name={who} size={16} />} label={'Controlled by ' + who} trail={Lock} />;
}

// ---- notes

type NoteKind = 'plain' | 'good' | 'warn' | 'bad' | 'info';

export function Note({ kind = 'plain', icon, children }: { kind?: NoteKind; icon?: LucideIcon; children: ReactNode }) {
  const t = useTheme();
  const look = {
    plain: { bg: t.surfaceDeep, border: t.border, ic: t.text2, Icon: Info },
    good: { bg: t.okBg, border: t.okBorder, ic: t.okText, Icon: CircleCheck },
    warn: { bg: t.warnBg, border: t.warnBorder, ic: t.warnText, Icon: TriangleAlert },
    bad: { bg: t.stopBg, border: t.stopBorder, ic: t.badIcon, Icon: CircleX },
    info: { bg: t.infoBg, border: t.infoBorder, ic: t.infoText, Icon: Info },
  }[kind];
  const Icon = icon || look.Icon;
  return (
    <View
      accessibilityRole={kind === 'bad' || kind === 'warn' ? 'alert' : undefined}
      style={{
        flexDirection: 'row', gap: 10, alignItems: 'flex-start', borderRadius: 10, borderWidth: 1,
        paddingVertical: 11, paddingHorizontal: 13, backgroundColor: look.bg, borderColor: look.border,
      }}>
      <Icon size={16} color={look.ic} style={{ marginTop: 1 }} />
      <View style={{ flex: 1 }}>
        {typeof children === 'string' ? <Txt size={13} tone={kind === 'plain' ? 'text2' : 'text'}>{children}</Txt> : children}
      </View>
    </View>
  );
}

/** A red line of text under a control when its last command failed. Takes no room when empty. */
export function ErrorLine({ text }: { text: string }) {
  const t = useTheme();
  if (!text) return null;
  return <Txt size={13} color={t.stopSoftText} accessibilityRole="alert" style={{ marginTop: 10 }}>{text}</Txt>;
}

// ---- form fields

export function Field({
  label, optional, hint, error, mono, style, ...input
}: TextInputProps & { label: string; optional?: boolean; hint?: string; error?: boolean; mono?: boolean }) {
  const t = useTheme();
  return (
    <View style={[{ gap: 7 }, style]}>
      <Txt size={14} weight="500">
        {label}
        {optional ? <Txt size={14} tone="text2"> (optional)</Txt> : null}
      </Txt>
      <TextInput
        accessibilityLabel={label}
        autoCapitalize="none"
        autoCorrect={false}
        placeholderTextColor={t.text3}
        {...input}
        style={{
          height: 44, borderWidth: 1, borderColor: error ? t.warn : t.borderStrong, borderRadius: 10,
          backgroundColor: t.surfaceDeep, paddingHorizontal: 13, fontSize: 15, color: t.text,
          fontFamily: mono ? MONO : undefined,
        }}
      />
      {hint ? <Txt size={12.5} tone="text2">{hint}</Txt> : null}
    </View>
  );
}

export function Checkbox({
  checked, onChange, label, hint,
}: { checked: boolean; onChange: (next: boolean) => void; label: string; hint?: string }) {
  const t = useTheme();
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
      accessibilityLabel={label}
      onPress={() => onChange(!checked)}
      style={{ flexDirection: 'row', gap: 11, alignItems: 'flex-start', paddingVertical: 4 }}>
      <View style={{
        width: 22, height: 22, borderRadius: 6, borderWidth: 1, marginTop: 1, alignItems: 'center', justifyContent: 'center',
        borderColor: checked ? t.accent : t.borderStrong, backgroundColor: checked ? t.accent : t.surfaceDeep,
      }}>
        {checked ? <CheckIcon size={15} color={t.accentText} /> : null}
      </View>
      <View style={{ flex: 1 }}>
        <Txt size={14}>{label}</Txt>
        {hint ? <Txt size={13} tone="text2">{hint}</Txt> : null}
      </View>
    </Pressable>
  );
}

/** A value shown in the monospace "code" chip (sensor names, joint names). */
export function Code({ children }: { children: string }) {
  const t = useTheme();
  return (
    <View style={{ backgroundColor: t.surfaceDeep, borderColor: t.border, borderWidth: 1, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 1 }}>
      <Txt size={11.5} mono>{children}</Txt>
    </View>
  );
}

/** The Swarm Hub mark: four robots joined to the hub in the middle. */
export function Logo({ size = 32 }: { size?: number }) {
  const t = useTheme();
  return (
    <View style={{
      width: size, height: size, borderRadius: size * 0.28, backgroundColor: t.surfaceRaised, borderWidth: 1,
      borderColor: t.borderStrong, alignItems: 'center', justifyContent: 'center',
    }}>
      <Svg width={size * 0.62} height={size * 0.62} viewBox="0 0 24 24" fill="none">
        <Path d="M6 6l12 12M18 6L6 18" stroke={t.text} strokeWidth={2.2} strokeLinecap="round" />
        <Circle cx={12} cy={12} r={3.2} fill="#E8AC65" />
        <Circle cx={5} cy={5} r={2.2} fill={t.text} />
        <Circle cx={19} cy={5} r={2.2} fill={t.text} />
        <Circle cx={5} cy={19} r={2.2} fill={t.text} />
        <Circle cx={19} cy={19} r={2.2} fill={t.text} />
      </Svg>
    </View>
  );
}

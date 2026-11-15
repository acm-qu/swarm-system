// Colours from the design mockups (the CSS variables at the top of design/html/build.py).
// The app follows the phone's light or dark setting; dark is the default look.
import { useColorScheme } from 'react-native';

const dark = {
  dark: true,
  bg: '#0D1117', topbar: '#121922', surface: '#161D26', surfaceRaised: '#202A35', surfaceDeep: '#111821',
  border: '#27313D', borderStrong: '#36414E',
  text: '#E8EDF2', text2: '#9AA9B8', text3: '#7F95AA',
  accent: '#E8AC65', accentText: '#0D1117', accentSoft: 'rgba(232,172,101,0.12)', accentBorder: 'rgba(232,172,101,0.35)',
  ok: '#22C55E', okText: '#4ADE80', okBg: 'rgba(34,197,94,0.12)', okBorder: 'rgba(34,197,94,0.35)',
  warn: '#F59E0B', warnText: '#FBBF24', warnBg: 'rgba(245,158,11,0.13)', warnBorder: 'rgba(245,158,11,0.45)',
  off: '#94A3B8', offBg: 'rgba(148,163,184,0.10)', offBorder: 'rgba(148,163,184,0.28)',
  info: '#3B82F6', infoText: '#93C5FD', infoBg: 'rgba(59,130,246,0.14)', infoBorder: 'rgba(59,130,246,0.45)',
  stop: '#EF4444', stopDeep: '#DC2626', stopBg: 'rgba(239,68,68,0.12)', stopBorder: 'rgba(239,68,68,0.45)',
  stopSoftText: '#FCA5A5', badIcon: '#F87171',
  youBg: '#E8EDF2', youText: '#0D1117',
  overlay: 'rgba(5,8,12,0.62)',
};

const light: Theme = {
  dark: false,
  bg: '#F0F2F5', topbar: '#FBFBFC', surface: '#FFFFFF', surfaceRaised: '#F3F5F7', surfaceDeep: '#E9EDF1',
  border: '#E1E5EA', borderStrong: '#CDD3DA',
  text: '#1B2430', text2: '#5B6876', text3: '#7A8796',
  accent: '#E8AC65', accentText: '#1B2430', accentSoft: 'rgba(232,172,101,0.20)', accentBorder: 'rgba(217,149,78,0.55)',
  ok: '#16A34A', okText: '#15803D', okBg: 'rgba(22,163,74,0.10)', okBorder: 'rgba(22,163,74,0.35)',
  warn: '#D97706', warnText: '#B45309', warnBg: 'rgba(245,158,11,0.14)', warnBorder: 'rgba(217,119,6,0.45)',
  off: '#64748B', offBg: 'rgba(100,116,139,0.08)', offBorder: 'rgba(100,116,139,0.30)',
  info: '#2563EB', infoText: '#1D4ED8', infoBg: 'rgba(37,99,235,0.10)', infoBorder: 'rgba(37,99,235,0.40)',
  stop: '#DC2626', stopDeep: '#B91C1C', stopBg: 'rgba(239,68,68,0.12)', stopBorder: 'rgba(239,68,68,0.45)',
  stopSoftText: '#B91C1C', badIcon: '#DC2626',
  youBg: '#1B2430', youText: '#FFFFFF',
  overlay: 'rgba(5,8,12,0.45)',
};

export type Theme = typeof dark;

export function useTheme(): Theme {
  return useColorScheme() === 'light' ? light : dark;
}

// IBM Plex Mono, loaded in src/app/_layout.tsx (hostnames, the terminal, numbers that are sent).
export const MONO = 'IBMPlexMono_400Regular';
export const MONO_MEDIUM = 'IBMPlexMono_500Medium';

// The four pages along the bottom. A robot's page belongs to Fleet.
import { router, usePathname } from 'expo-router';
import { Pressable, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useTheme } from '@/theme';
import { Activity, CircleHelp, History, LayoutGrid, type LucideIcon } from './icons';
import { Txt } from './ui';

const TABS: { href: '/' | '/history' | '/health' | '/help'; label: string; icon: LucideIcon }[] = [
  { href: '/', label: 'Fleet', icon: LayoutGrid },
  { href: '/history', label: 'History', icon: History },
  { href: '/health', label: 'Health', icon: Activity },
  { href: '/help', label: 'Help', icon: CircleHelp },
];

export function TabBar() {
  const t = useTheme();
  const insets = useSafeAreaInsets();
  const pathname = usePathname();
  const active = TABS.some((tab) => tab.href === pathname) ? pathname : '/';
  return (
    <View
      accessibilityRole="tablist"
      style={{
        flexDirection: 'row', backgroundColor: t.topbar, borderTopWidth: 1, borderTopColor: t.border,
        paddingTop: 10, paddingBottom: Math.max(insets.bottom, 12),
      }}>
      {TABS.map(({ href, label, icon: Icon }) => {
        const on = href === active;
        return (
          <Pressable
            key={href}
            accessibilityRole="tab"
            accessibilityState={{ selected: on }}
            accessibilityLabel={label}
            onPress={() => router.navigate(href)}
            style={{ flex: 1, alignItems: 'center', gap: 4 }}>
            <Icon size={21} color={on ? t.accent : t.text2} />
            <Txt size={12} tone={on ? 'text' : 'text2'}>{label}</Txt>
          </Pressable>
        );
      })}
    </View>
  );
}

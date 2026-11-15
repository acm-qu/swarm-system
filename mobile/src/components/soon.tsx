// A page the designs show but the hub can't fill yet. What each one needs is listed in TBD.md.
import { ScrollView, View } from 'react-native';

import { useTheme } from '@/theme';
import type { LucideIcon } from './icons';
import { Monogram, Pill, Txt } from './ui';

export function SoonPage({ title, icon, about, needs }: { title: string; icon: LucideIcon; about: string; needs: string }) {
  const t = useTheme();
  return (
    <ScrollView contentContainerStyle={{ padding: 14, gap: 12 }}>
      <View>
        <Txt size={20} weight="600" accessibilityRole="header">{title}</Txt>
        <Txt size={13} tone="text2">{about}</Txt>
      </View>
      <View style={{
        borderWidth: 1, borderStyle: 'dashed', borderColor: t.borderStrong, borderRadius: 16,
        paddingVertical: 34, paddingHorizontal: 18, alignItems: 'center', gap: 12,
      }}>
        <Monogram icon={icon} size={46} />
        <Pill kind="ctl" label="Soon" />
        <Txt tone="text2" style={{ textAlign: 'center' }}>{needs}</Txt>
      </View>
    </ScrollView>
  );
}

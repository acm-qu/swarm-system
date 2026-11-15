// Settings: who is signed in, which hub this phone talks to, and Sign out.
import { ScrollView, View } from 'react-native';

import { LogOut, Server, TriangleAlert } from '@/components/icons';
import { Avatar, Btn, Card, Row, Txt } from '@/components/ui';
import { hubBase } from '@/lib/api';
import { useHub } from '@/lib/hub';
import { useTheme } from '@/theme';

export default function Settings() {
  const hub = useHub();
  const t = useTheme();
  return (
    <ScrollView contentContainerStyle={{ padding: 14, gap: 12 }}>
      <View>
        <Txt size={20} weight="600" accessibilityRole="header">Settings</Txt>
        <Txt size={13} tone="text2">Your login and the hub this phone is connected to.</Txt>
      </View>

      <Card style={{ padding: 14, gap: 14 }}>
        <Row gap={12}>
          <Avatar name={hub.user || ''} size={40} />
          <View style={{ flex: 1 }}>
            <Txt size={12.5} tone="text2">Signed in as</Txt>
            <Txt size={16} weight="600" numberOfLines={1}>{hub.user}</Txt>
          </View>
        </Row>
        <Btn label="Sign out" icon={LogOut} size="lg" onPress={hub.signOut} hint="Goes back to the sign-in screen. The hub address stays filled in." />
      </Card>

      <Card style={{ padding: 14, gap: 10 }}>
        <Row gap={8}>
          <Server size={17} color={t.text} />
          <Txt size={15} weight="600">Hub</Txt>
        </Row>
        <View>
          <Txt size={12.5} tone="text2">Address</Txt>
          <Txt size={15} mono selectable>{hubBase()}</Txt>
        </View>
        {hub.ok ? (
          <Row gap={6}>
            <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: t.ok }} />
            <Txt size={13} tone="text2">Connected</Txt>
          </Row>
        ) : (
          <Row gap={6}>
            <TriangleAlert size={13} color={t.warnText} />
            <Txt size={13} color={t.warnText}>Can&apos;t reach the hub · reconnecting…</Txt>
          </Row>
        )}
        <Txt size={12.5} tone="text2">To use another hub, sign out and type its address on the sign-in screen.</Txt>
      </Card>
    </ScrollView>
  );
}

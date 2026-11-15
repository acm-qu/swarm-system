import { Tabs } from 'expo-router';
import { View } from 'react-native';

import { SheetHost, ToastView } from '@/components/sheet';
import { TabBar } from '@/components/tab-bar';
import { TopBar } from '@/components/top-bar';
import { useTheme } from '@/theme';

/** The frame around every signed-in screen: top bar, the page, the tab bar, and any open sheet. */
export default function AppLayout() {
  const t = useTheme();
  return (
    <View style={{ flex: 1, backgroundColor: t.bg }}>
      <TopBar />
      {/* Sheets and the toast cover this part only, never the top bar with Stop all. */}
      <View style={{ flex: 1 }}>
        <Tabs tabBar={() => <TabBar />} screenOptions={{ headerShown: false, sceneStyle: { backgroundColor: t.bg } }}>
          <Tabs.Screen name="index" />
          <Tabs.Screen name="history" />
          <Tabs.Screen name="health" />
          <Tabs.Screen name="help" />
          <Tabs.Screen name="robot/[name]" />
        </Tabs>
        <SheetHost />
        <ToastView />
      </View>
    </View>
  );
}

import { Tabs } from 'expo-router';
import { KeyboardAvoidingView, View } from 'react-native';

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
      {/* When the keyboard opens, everything under the top bar is squeezed into the space above it,
          so the field you are typing in (on a page or in a sheet) stays in view. */}
      <KeyboardAvoidingView behavior="padding" style={{ flex: 1 }}>
        {/* Sheets and the toast cover this part only, never the top bar with Stop all. */}
        <View style={{ flex: 1 }}>
          <Tabs tabBar={() => <TabBar />} screenOptions={{ headerShown: false, sceneStyle: { backgroundColor: t.bg } }}>
            <Tabs.Screen name="index" />
            <Tabs.Screen name="history" />
            <Tabs.Screen name="health" />
            <Tabs.Screen name="settings" />
            <Tabs.Screen name="robot/[name]" />
          </Tabs>
          <SheetHost />
          <ToastView />
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

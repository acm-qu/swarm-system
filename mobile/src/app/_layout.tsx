import { IBMPlexMono_400Regular, IBMPlexMono_500Medium } from '@expo-google-fonts/ibm-plex-mono';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { GestureHandlerRootView } from 'react-native-gesture-handler';

import { HubProvider, useHub } from '@/lib/hub';
import { useTheme } from '@/theme';

SplashScreen.preventAutoHideAsync();

function Screens() {
  const hub = useHub();
  const t = useTheme();
  const [fontsLoaded, fontError] = useFonts({ IBMPlexMono_400Regular, IBMPlexMono_500Medium });
  // If the font can't load the app still opens, with the phone's own monospace font.
  const ready = hub.ready && (fontsLoaded || !!fontError);

  useEffect(() => {
    if (ready) SplashScreen.hideAsync();
  }, [ready]);

  if (!ready) return null;
  return (
    <>
      <StatusBar style={t.dark ? 'light' : 'dark'} />
      <Stack screenOptions={{ headerShown: false, animation: 'fade', contentStyle: { backgroundColor: t.bg } }}>
        <Stack.Protected guard={!!hub.user}>
          <Stack.Screen name="(app)" />
        </Stack.Protected>
        <Stack.Protected guard={!hub.user}>
          <Stack.Screen name="sign-in" />
        </Stack.Protected>
      </Stack>
    </>
  );
}

export default function RootLayout() {
  return (
    // Needed by the drive sticks (react-native-gesture-handler).
    <GestureHandlerRootView style={{ flex: 1 }}>
      <HubProvider>
        <Screens />
      </HubProvider>
    </GestureHandlerRootView>
  );
}

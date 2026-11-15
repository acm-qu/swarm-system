import { router, useIsFocused, useLocalSearchParams } from 'expo-router';

import { isTab, RobotView } from '@/components/robot/robot-view';

export default function RobotScreen() {
  // The open tab is part of the address (as on the web page), so it survives switching robots.
  const { name, tab } = useLocalSearchParams<{ name: string; tab?: string }>();
  const focused = useIsFocused();
  // Tab screens stay alive in the background. Not drawing this one when you leave it is what stops
  // its camera and drive commands and gives up control of the robot.
  if (!focused || !name) return null;
  return <RobotView key={name} name={name} tab={isTab(tab) ? tab : 'drive'} onTab={(next) => router.setParams({ tab: next })} />;
}

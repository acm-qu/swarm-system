import { useIsFocused, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

import { RobotView, type TabKey } from '@/components/robot/robot-view';

export default function RobotScreen() {
  const { name } = useLocalSearchParams<{ name: string }>();
  const focused = useIsFocused();
  const [tab, setTab] = useState<TabKey>('drive'); // kept when you switch to another robot
  // Tab screens stay alive in the background. Not drawing this one when you leave it is what stops
  // its camera and drive commands and gives up control of the robot.
  if (!focused || !name) return null;
  return <RobotView key={name} name={name} tab={tab} onTab={setTab} />;
}

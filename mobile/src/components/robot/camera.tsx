// The robot's camera. The hub gives one JPEG per request (/snapshot), so the app asks about five
// times a second: the mockups' "Low · 5 fps on phones". Asking is what keeps the robot's camera on,
// so it turns off by itself a few seconds after you leave the robot.
import { useEffect, useState } from 'react';
import { ActivityIndicator, Image, Pressable, View } from 'react-native';

import { snapshot } from '@/lib/api';
import { can, live, type Robot } from '@/lib/robot';
import { useTheme } from '@/theme';
import { CameraOff, Maximize2, TriangleAlert } from '../icons';
import { Row, Txt } from '../ui';

const FRAME_MS = 200; // 5 pictures a second
const RETRY_MS = 2000;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

type Feed = { uri: string | null; problem: string };

export function Camera({ robot, mini, onPress }: { robot: Robot; mini?: boolean; onPress?: () => void }) {
  const t = useTheme();
  const { name } = robot;
  const want = live(robot) && can(robot, 'camera');
  const [feed, setFeed] = useState<Feed>({ uri: null, problem: '' });

  useEffect(() => {
    if (!want) return;
    let gone = false;
    let lastId: string | undefined;
    (async () => {
      while (!gone) {
        const started = Date.now();
        let wait = FRAME_MS;
        try {
          const shot = await snapshot(name, lastId);
          if (gone) return;
          if (shot?.state === 'frame') {
            lastId = shot.id;
            setFeed({ uri: shot.uri, problem: '' });
          } else if (shot?.state === 'offline') {
            wait = RETRY_MS;
          }
        } catch {
          if (gone) return;
          setFeed((f) => ({ ...f, problem: 'No picture yet. Retrying…' }));
          wait = RETRY_MS;
        }
        await sleep(Math.max(0, wait - (Date.now() - started)));
      }
    })();
    return () => {
      gone = true;
    };
  }, [name, want]);

  const uri = want ? feed.uri : null;
  const stale = robot.status === 'unresponsive';
  let message = '';
  if (!live(robot)) message = 'No picture · offline';
  else if (!want) message = "This robot didn't report a camera.";
  else if (!uri) message = feed.problem || 'Waiting for the camera…';

  const badge = { position: 'absolute', backgroundColor: 'rgba(10,13,18,0.78)', borderRadius: 9, borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)' } as const;
  return (
    <Pressable
      disabled={!onPress}
      onPress={onPress}
      accessibilityRole={onPress ? 'button' : 'image'}
      accessibilityLabel={`${name}'s camera${message ? '. ' + message : ''}${onPress ? '. Tap to change its size' : ''}`}
      style={[
        { borderRadius: 14, overflow: 'hidden', borderWidth: 1, borderColor: t.border, backgroundColor: t.surfaceDeep, aspectRatio: 4 / 3 },
        mini ? { width: 132 } : { alignSelf: 'stretch' },
      ]}>
      {uri ? <Image source={{ uri }} fadeDuration={0} resizeMode="cover" style={{ flex: 1, opacity: stale ? 0.55 : 1 }} /> : null}
      {message ? (
        <View style={{ position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, alignItems: 'center', justifyContent: 'center', gap: 8, padding: 10 }}>
          {want ? <ActivityIndicator color={t.text2} /> : <CameraOff size={mini ? 18 : 24} color={t.text3} />}
          <Txt size={mini ? 11.5 : 13} tone="text2" style={{ textAlign: 'center' }}>{message}</Txt>
        </View>
      ) : null}
      {uri ? (
        <Row gap={6} style={[badge, { top: mini ? 6 : 12, left: mini ? 6 : 12, height: mini ? 22 : 30, paddingHorizontal: mini ? 7 : 10 }]}>
          {stale ? <TriangleAlert size={mini ? 12 : 14} color="#FBBF24" /> : <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: '#FFFFFF' }} />}
          <Txt size={mini ? 11.5 : 13} color={stale ? '#FBBF24' : '#E8EDF2'}>{stale ? 'Not answering' : mini ? 'Live' : 'Live · 5 fps'}</Txt>
        </Row>
      ) : null}
      {onPress && !mini ? (
        <View style={[badge, { top: 12, right: 12, width: 30, height: 30, alignItems: 'center', justifyContent: 'center' }]}>
          <Maximize2 size={15} color="#E8EDF2" />
        </View>
      ) : null}
    </Pressable>
  );
}

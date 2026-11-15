// The app's shared state: who is signed in, the robot list (asked from the hub once a second, like the
// web page), Stop, the toast, and the bottom sheet that is open. Screens read it with useHub().
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';

import { configure, get, HubError, normalizeHubAddress, post, robotPost } from './api';
import { live, type Robot } from './robot';

const ADDRESS_KEY = 'hub-address'; // only the address is remembered on the phone, never a password
const POLL_MS = 1000;

type Session = { ready: boolean; user: string | null; address: string };
// lastOk: when the hub last answered. checkedAt: when it was last asked (answered or not).
type Fleet = { robots: Robot[]; loaded: boolean; ok: boolean; lastOk: number; checkedAt: number };
type Toast = { text: string; bad: boolean } | null;
type OpenSheet = { content: ReactNode; onDismiss?: () => void } | null;

const NO_FLEET: Fleet = { robots: [], loaded: false, ok: true, lastOk: 0, checkedAt: 0 };

type Hub = Session & Fleet & {
  byName: Record<string, Robot>;
  signIn: (address: string, username: string, password: string) => Promise<void>;
  signOut: () => void;
  refresh: () => Promise<void>;
  /** Stop one robot. Never needs control. */
  stop: (name: string) => void;
  /** Stop every robot that is online. Resolves to what to show on the button for a moment. */
  stopAll: () => Promise<string>;
  /** Goes up by one on every Stop, so held drive sticks let go (see components/robot/drive.tsx). */
  stopCount: number;
  ping: (name: string) => void;
  toast: Toast;
  showToast: (text: string, bad?: boolean) => void;
  sheet: ReactNode;
  /** Show a bottom sheet. onDismiss runs when the person closes it (X, the dimmed area, Back), not on closeSheet. */
  openSheet: (content: ReactNode, onDismiss?: () => void) => void;
  closeSheet: () => void;
  dismissSheet: () => void;
  /** The terminal asks "are you sure?" once per sign-in. */
  terminalOk: boolean;
  allowTerminal: () => void;
};

const HubContext = createContext<Hub | null>(null);

export function useHub(): Hub {
  const hub = useContext(HubContext);
  if (!hub) throw new Error('useHub needs a HubProvider above it');
  return hub;
}

export function HubProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session>({ ready: false, user: null, address: '' });
  const [fleet, setFleet] = useState<Fleet>(NO_FLEET);
  const [toast, setToast] = useState<Toast>(null);
  const [sheet, setSheet] = useState<OpenSheet>(null);
  const [terminalOk, setTerminalOk] = useState(false);
  const [stopCount, setStopCount] = useState(0);
  const asking = useRef(false);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function endSession() {
    setSession((s) => ({ ...s, user: null }));
    setFleet(NO_FLEET);
    setSheet(null);
    setTerminalOk(false);
  }

  // On start: go back to the hub used last time. Its login cookie may still be good.
  useEffect(() => {
    configure({ onSignedOut: endSession });
    (async () => {
      const address = (await AsyncStorage.getItem(ADDRESS_KEY).catch(() => null)) || '';
      let user: string | null = null;
      if (address) {
        configure({ base: normalizeHubAddress(address) });
        try {
          const s = await get<{ user: string | null; csrf: string }>('/auth/session');
          configure({ csrf: s.csrf });
          user = s.user;
        } catch {
          // hub not reachable right now: show the sign-in screen with the address filled in
        }
      }
      setSession({ ready: true, user, address });
    })();
  }, []);

  async function refresh() {
    if (asking.current) return; // a slow hub must not pile requests up
    asking.current = true;
    try {
      const robots = await get<Robot[]>('/api/robots');
      setFleet({ robots, loaded: true, ok: true, lastOk: Date.now(), checkedAt: Date.now() });
    } catch (err) {
      if (!(err instanceof HubError && err.status === 401)) {
        // Never reached it at all: count "how long ago" from the first try.
        setFleet((f) => ({ ...f, ok: false, checkedAt: Date.now(), lastOk: f.lastOk || Date.now() }));
      }
    } finally {
      asking.current = false;
    }
  }

  const signedIn = !!session.user;
  useEffect(() => {
    if (!signedIn) return;
    const first = setTimeout(refresh, 0); // don't wait a second for the first list
    const timer = setInterval(refresh, POLL_MS);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [signedIn]);

  function showToast(text: string, bad = false) {
    setToast({ text, bad });
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 6000);
  }

  async function signIn(address: string, username: string, password: string) {
    const base = normalizeHubAddress(address);
    if (!base) throw new Error("Enter the hub's address, for example 192.168.1.20:8000.");
    configure({ base });
    try {
      const s = await post<{ user: string; csrf: string }>('/auth/login', { username: username.trim(), password });
      configure({ csrf: s.csrf });
      AsyncStorage.setItem(ADDRESS_KEY, address.trim()).catch(() => {}); // not remembered: type it again next time
      setSession({ ready: true, user: s.user, address: address.trim() });
    } catch (err) {
      if (err instanceof HubError && err.status === 0) {
        throw new Error(`Can't reach a hub at ${base}. Check the address, and that this phone is on the same network as the hub.`);
      }
      throw err;
    }
  }

  function signOut() {
    post('/auth/logout').catch(() => {}); // signed out here even if the hub can't be told
    endSession();
  }

  function stop(name: string) {
    setStopCount((n) => n + 1);
    robotPost(name, 'stop').then(refresh, (err) => showToast(`Couldn't stop ${name}: ${err.message}`, true));
  }

  async function stopAll() {
    setStopCount((n) => n + 1);
    const targets = fleet.robots.filter(live);
    const results = await Promise.allSettled(targets.map((r) => robotPost(r.name, 'stop')));
    const failed = targets.filter((_, i) => results[i].status === 'rejected').map((r) => r.name);
    if (failed.length) showToast(`Couldn't stop ${failed.join(', ')}. Is the hub reachable?`, true);
    refresh();
    return !targets.length ? 'None online' : failed.length ? 'Stop failed' : 'Stop sent';
  }

  function ping(name: string) {
    robotPost(name, 'ping').then(refresh, (err) => showToast(err.message, true));
  }

  const hub: Hub = {
    ...session,
    ...fleet,
    byName: Object.fromEntries(fleet.robots.map((r) => [r.name, r])),
    signIn, signOut, refresh, stop, stopAll, stopCount, ping,
    toast, showToast,
    sheet: sheet?.content,
    openSheet: (content, onDismiss) => setSheet({ content, onDismiss }),
    closeSheet: () => setSheet(null),
    dismissSheet: () => {
      setSheet(null);
      sheet?.onDismiss?.();
    },
    terminalOk, allowTerminal: () => setTerminalOk(true),
  };
  return <HubContext.Provider value={hub}>{children}</HubContext.Provider>;
}

// Talks to the hub's JSON API (hub/api.py and the /api/session routes in hub/auth.py).
// The phone keeps the hub's login cookie by itself; this file adds the CSRF token to every request.

export class HubError extends Error {
  status: number; // 0 = the hub couldn't be reached at all

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

const TIMEOUT_MS = 8000; // without this a request to a hub that is gone hangs for a minute or more
const DEFAULT_PORT = 8000; // the hub's port unless it was started with --port

let base = '';
let csrf = '';
let onSignedOut: () => void = () => {};

/**
 * Turns what a person types ("192.168.1.20", "hub.local:8001", "http://10.0.0.5:8000/") into the
 * hub's base URL. No scheme means http, and no port then means the hub's usual 8000.
 */
export function normalizeHubAddress(input: string): string {
  const text = input.trim().replace(/\/+$/, '');
  if (!text) return '';
  if (/^https?:\/\//i.test(text)) return text;
  return 'http://' + text + (/:\d+$/.test(text) ? '' : ':' + DEFAULT_PORT);
}

export function configure(options: { base?: string; csrf?: string; onSignedOut?: () => void }) {
  if (options.base !== undefined) base = options.base;
  if (options.csrf !== undefined) csrf = options.csrf;
  if (options.onSignedOut) onSignedOut = options.onSignedOut;
}

export const hubBase = () => base;

async function send(method: string, path: string, data?: unknown, timeoutMs = TIMEOUT_MS): Promise<Response> {
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), timeoutMs);
  try {
    return await fetch(base + path, {
      method,
      headers: { 'X-CSRF': csrf, 'Content-Type': 'application/json' },
      body: method === 'GET' ? undefined : JSON.stringify(data || {}),
      signal: abort.signal,
    });
  } catch {
    throw new HubError("Can't reach the hub.", 0);
  } finally {
    clearTimeout(timer);
  }
}

/** One API call. Throws a HubError with the hub's own plain-language message when it fails. */
export async function request<T = any>(method: string, path: string, data?: unknown, timeoutMs?: number): Promise<T> {
  const res = await send(method, path, data, timeoutMs);
  // A 401 from the sign-in route itself is a wrong password, not an expired session.
  if (res.status === 401 && path !== '/api/session') {
    onSignedOut();
    throw new HubError('You were signed out.', 401);
  }
  const out = await res.json().catch(() => ({}));
  if (!res.ok) throw new HubError(out.error || 'HTTP ' + res.status, res.status);
  return out as T;
}

export const get = <T = any>(path: string) => request<T>('GET', path);
export const post = <T = any>(path: string, data?: unknown, timeoutMs?: number) =>
  request<T>('POST', path, data, timeoutMs);

/** A command for one robot, e.g. robotPost('Clanker', 'stop'). */
export const robotPost = <T = any>(name: string, action: string, data?: unknown, timeoutMs?: number) =>
  post<T>('/api/robots/' + encodeURIComponent(name) + '/' + action, data, timeoutMs);

export type Snapshot = { state: 'frame'; uri: string; id: string } | { state: 'waiting' } | { state: 'offline' };

// shortcut: each picture is copied through React Native's Blob store, fine for small 5 fps frames;
// switch to expo-blob (or the /ui WebSocket, ARCHITECTURE.md S3) if pictures get big or faster.
function toDataUri(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(String(reader.result));
    reader.onerror = () => reject(new HubError("Couldn't read the picture.", 0));
    reader.readAsDataURL(blob);
  });
}

/**
 * The camera's newest picture. Asking is what keeps the robot's camera on. `lastId` is the frame
 * already on screen: if the hub has nothing newer, the picture isn't downloaded into memory again.
 */
export async function snapshot(name: string, lastId?: string): Promise<Snapshot | null> {
  const res = await send('GET', '/api/robots/' + encodeURIComponent(name) + '/snapshot');
  if (res.status === 401) {
    onSignedOut();
    throw new HubError('You were signed out.', 401);
  }
  if (res.status === 204) return { state: 'waiting' };
  if (res.status === 409) return { state: 'offline' };
  if (!res.ok) throw new HubError('HTTP ' + res.status, res.status);
  const id = res.headers.get('X-Frame-Id') || '';
  if (id && id === lastId) return null; // same picture as before
  return { state: 'frame', uri: await toDataUri(await res.blob()), id };
}

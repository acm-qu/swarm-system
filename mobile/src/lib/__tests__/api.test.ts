import { configure, get, HubError, normalizeHubAddress, post, robotPost } from '../api';

const reply = (status: number, body: unknown) =>
  ({ status, ok: status >= 200 && status < 300, json: async () => body }) as Response;

describe('normalizeHubAddress', () => {
  it('adds http and the hub port to a bare address', () => {
    expect(normalizeHubAddress(' 192.168.1.20 ')).toBe('http://192.168.1.20:8000');
    expect(normalizeHubAddress('hub.local')).toBe('http://hub.local:8000');
  });

  it('keeps a port or a full address that was typed', () => {
    expect(normalizeHubAddress('192.168.1.20:8001')).toBe('http://192.168.1.20:8001');
    expect(normalizeHubAddress('https://hub.example.org/')).toBe('https://hub.example.org');
    expect(normalizeHubAddress('HTTP://10.0.0.5:8000//')).toBe('HTTP://10.0.0.5:8000');
  });

  it('is empty for nothing', () => {
    expect(normalizeHubAddress('   ')).toBe('');
  });
});

describe('request', () => {
  const fetchMock = jest.fn();
  const signedOut = jest.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    signedOut.mockReset();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    configure({ base: 'http://hub:8000', csrf: 'tok', onSignedOut: signedOut });
  });

  it('sends the CSRF token and JSON body to the hub', async () => {
    fetchMock.mockResolvedValue(reply(200, { ok: true }));
    await expect(robotPost('Clank er', 'drive', { forward: 0.4 })).resolves.toEqual({ ok: true });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('http://hub:8000/api/robots/Clank%20er/drive');
    expect(init.method).toBe('POST');
    expect(init.headers['X-CSRF']).toBe('tok');
    expect(JSON.parse(init.body)).toEqual({ forward: 0.4 });
  });

  it("throws the hub's own message", async () => {
    fetchMock.mockResolvedValue(reply(409, { error: 'sara is controlling Clanker right now.' }));
    await expect(robotPost('Clanker', 'drive')).rejects.toMatchObject({
      message: 'sara is controlling Clanker right now.',
      status: 409,
    });
    expect(signedOut).not.toHaveBeenCalled();
  });

  it('signs the app out when the session has ended', async () => {
    fetchMock.mockResolvedValue(reply(401, { error: 'not signed in' }));
    await expect(get('/api/robots')).rejects.toBeInstanceOf(HubError);
    expect(signedOut).toHaveBeenCalledTimes(1);
  });

  it('treats a 401 from sign-in as a wrong password, not an ended session', async () => {
    fetchMock.mockResolvedValue(reply(401, { error: 'Wrong username or password.' }));
    await expect(post('/auth/login', {})).rejects.toMatchObject({ message: 'Wrong username or password.' });
    expect(signedOut).not.toHaveBeenCalled();
  });

  it('reports an unreachable hub with status 0', async () => {
    fetchMock.mockRejectedValue(new TypeError('Network request failed'));
    await expect(get('/api/robots')).rejects.toMatchObject({ status: 0 });
  });
});

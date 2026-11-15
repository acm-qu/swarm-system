// Add, Update and Remove a robot: a short form, then the job's steps as the hub works through
// them (mockups phone-22 to phone-27). The robot's password lives only in this sheet while it is
// open; it is sent once and never stored on the phone.
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { get, HubError, post, robotPost } from '@/lib/api';
import { useHub } from '@/lib/hub';
import { live } from '@/lib/robot';
import { useTheme } from '@/theme';
import { ArrowRight, Check, CircleCheck, CircleX, Download, EyeOff, RefreshCw, Trash2, TriangleAlert, X } from '../icons';
import { Sheet } from '../sheet';
import { Btn, Checkbox, ErrorLine, Field, Monogram, Note, Pill, Row, StatusPill, Txt } from '../ui';

type Mode = 'add' | 'update' | 'remove';
type Step = { text: string; state: 'run' | 'ok' | 'fail' | 'info' };
type Job = { state: 'running' | 'done' | 'warning' | 'failed'; robot: string | null; message: string; steps: Step[] };

const TEXT: Record<Mode, { title: (name: string) => string; sub: string; go: string; working: (name: string) => string }> = {
  add: {
    title: () => 'Add robot', go: 'Install', working: () => 'Installing the robot',
    sub: 'The hub connects to the robot over the lab network and installs its program.',
  },
  update: {
    title: (name) => 'Update ' + name, go: 'Update', working: (name) => 'Updating ' + name,
    sub: 'Copies the latest robot code from the hub to the robot and restarts it.',
  },
  remove: {
    title: (name) => 'Remove ' + name + '?', go: 'Remove', working: (name) => 'Removing ' + name,
    sub: 'Stops the robot program, removes it from the robot, and takes the robot off this list.',
  },
};

export function RobotFormSheet({ mode, name = '' }: { mode: Mode; name?: string }) {
  const hub = useHub();
  const robot = name ? hub.byName[name] : undefined;
  const [host, setHost] = useState('');
  const [user, setUser] = useState('pi');
  const [password, setPassword] = useState('');
  const [wantedName, setWantedName] = useState('');
  const [reboot, setReboot] = useState(false); // opt-in: adding a robot from another device shouldn't restart it
  const [forget, setForget] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const refresh = hub.refresh;

  // Ask the hub how the job is going until it finishes.
  useEffect(() => {
    if (!jobId) return;
    let timer: ReturnType<typeof setTimeout>;
    let gone = false;
    const ask = async () => {
      let next = 600;
      try {
        const j = await get<Job>('/api/jobs/' + jobId);
        if (gone) return;
        setJob(j);
        if (j.state !== 'running') {
          refresh();
          return;
        }
      } catch {
        next = 1500; // hub hiccup: keep asking, a little slower
      }
      if (!gone) timer = setTimeout(ask, next);
    };
    timer = setTimeout(ask, 0);
    return () => {
      gone = true;
      clearTimeout(timer);
    };
  }, [jobId, refresh]);

  async function submit() {
    setBusy(true);
    setError('');
    try {
      const out = mode === 'add'
        ? await post<{ job: string }>('/api/robots', { host: host.trim(), user: user.trim(), password, name: wantedName.trim(), reboot })
        : await robotPost<{ job: string }>(name, mode, { password, reboot, forget });
      setJob(null);
      setJobId(out.job);
    } catch (err) {
      setError(err instanceof HubError ? err.message : 'Something went wrong. Try again.');
    }
    setBusy(false);
  }

  if (jobId) {
    return (
      <JobProgress
        mode={mode} name={name} adding={`${user.trim() || 'pi'}@${host.trim()}`} job={job}
        onRetry={() => { setJobId(null); setJob(null); }}
      />
    );
  }

  const text = TEXT[mode];
  return (
    <Sheet
      title={text.title(name)} sub={text.sub} danger={mode === 'remove'} icon={mode === 'remove' ? Trash2 : undefined}
      footer={
        <>
          <Btn
            label={text.go} icon={mode === 'remove' ? Trash2 : Download} kind={mode === 'remove' ? 'danger' : 'primary'} size="lg"
            busy={busy} disabled={mode === 'add' && (!host.trim() || !password)} onPress={submit}
          />
          <Btn label="Cancel" size="lg" onPress={hub.dismissSheet} />
        </>
      }>
      {mode === 'remove' && robot ? <RobotSummary name={name} /> : null}
      {mode === 'add' ? (
        <>
          <Field
            label="IP address" value={host} onChangeText={setHost} placeholder="192.168.149.1" keyboardType="url"
            hint="Shown on the robot's screen, or in your router's list of devices."
          />
          <Row gap={12} align="flex-start">
            <Field label="Username" value={user} onChangeText={setUser} mono style={{ flex: 1 }} />
            <Field label="Password" value={password} onChangeText={setPassword} secureTextEntry autoComplete="off" style={{ flex: 1 }} />
          </Row>
          <Txt size={13} tone="text2" style={{ marginTop: -6 }}>Password: used once to install. It is not saved.</Txt>
          <Field label="Name" optional value={wantedName} onChangeText={setWantedName} placeholder="picked for you, e.g. masterpi-01" />
        </>
      ) : (
        <Field
          label="Password" optional value={password} onChangeText={setPassword} secureTextEntry autoComplete="off"
          placeholder="Robot password" hint="Usually not needed. Fill it in only if the robot asks for it."
        />
      )}
      {mode === 'remove' ? (
        <Checkbox
          checked={forget} onChange={setForget}
          label="The robot is gone or can't be reached. Just take it off this list."
          hint={robot && !live(robot) ? `${name} is offline, so the hub can't clean up the robot itself.` : undefined}
        />
      ) : (
        <Checkbox
          checked={reboot} onChange={setReboot} label="Reboot the robot when done"
          hint="Proves it starts by itself and opens the status screen on its desktop. Takes about a minute."
        />
      )}
      {mode === 'update' ? (
        <Note kind="info">The robot stops and restarts its program during the update, so it can&apos;t be driven for a few seconds.</Note>
      ) : null}
      <ErrorLine text={error} />
    </Sheet>
  );
}

function RobotSummary({ name }: { name: string }) {
  const hub = useHub();
  const t = useTheme();
  const r = hub.byName[name];
  if (!r) return null;
  return (
    <Row gap={12} style={{ borderWidth: 1, borderColor: t.border, borderRadius: 12, padding: 12, backgroundColor: t.surfaceDeep }}>
      <Monogram text={r.name} />
      <View style={{ flex: 1 }}>
        <Txt>{r.name}</Txt>
        <Txt size={12.5} tone="text2" numberOfLines={1}>
          <Txt size={12.5} tone="text2" mono>{r.hostname || '—'}</Txt>
          {' · ' + (r.address || '—')}
        </Txt>
      </View>
      <StatusPill robot={r} />
    </Row>
  );
}

function StepIcon({ state }: { state: Step['state'] }) {
  const t = useTheme();
  const look = {
    ok: { bg: t.okBg, border: t.okBorder, icon: <Check size={13} color={t.okText} /> },
    fail: { bg: t.stopBg, border: t.stopBorder, icon: <X size={13} color={t.badIcon} /> },
    run: { bg: t.infoBg, border: t.info, icon: <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: t.info }} /> },
    info: { bg: 'transparent', border: 'transparent', icon: null },
  }[state];
  return (
    <View style={{
      width: 22, height: 22, borderRadius: 11, alignItems: 'center', justifyContent: 'center', marginTop: 1,
      backgroundColor: look.bg, borderWidth: 1, borderColor: look.border,
    }}>
      {look.icon}
    </View>
  );
}

function JobProgress({
  mode, name, adding, job, onRetry,
}: { mode: Mode; name: string; adding: string; job: Job | null; onRetry: () => void }) {
  const hub = useHub();
  const t = useTheme();
  const state = job?.state || 'running';
  const pill = {
    running: <Pill kind="info" busy label="Working…" />,
    done: <Pill kind="ok" icon={CircleCheck} label="Done" />,
    warning: <Pill kind="warn" icon={TriangleAlert} label="Check this" />,
    failed: <Pill kind="fail" icon={CircleX} label="Failed" />,
  }[state];
  const newRobot = job?.robot;

  let footer;
  if (state === 'running') {
    footer = <Btn label="Hide (keeps running)" icon={EyeOff} size="lg" onPress={hub.closeSheet} />;
  } else if (state === 'failed') {
    footer = (
      <>
        <Btn label="Try again" icon={RefreshCw} kind="primary" size="lg" onPress={onRetry} />
        <Btn label="Close" size="lg" onPress={hub.closeSheet} />
      </>
    );
  } else {
    footer = (
      <>
        {mode === 'add' && newRobot ? (
          <Btn
            label="Open robot" iconRight={ArrowRight} kind="primary" size="lg"
            onPress={() => { hub.closeSheet(); router.navigate({ pathname: '/robot/[name]', params: { name: newRobot } }); }}
          />
        ) : null}
        <Btn label="Close" size="lg" onPress={hub.closeSheet} />
      </>
    );
  }

  return (
    <Sheet
      title={TEXT[mode].working(name)}
      lead={<View style={{ alignSelf: 'flex-start', marginBottom: 4 }}>{pill}</View>}
      sub={mode === 'add' ? <Txt size={13.5} tone="text2">Adding <Txt size={13.5} tone="text2" mono>{adding}</Txt></Txt> : undefined}
      footer={footer}>
      <View accessibilityLiveRegion="polite">
        {(job?.steps || []).map((s, i) => s.state === 'info' ? (
          <View key={i} style={{ backgroundColor: t.surfaceDeep, borderWidth: 1, borderColor: t.border, borderRadius: 8, paddingVertical: 8, paddingHorizontal: 10, marginVertical: 4 }}>
            <Txt size={12} tone="text2" mono>{s.text}</Txt>
          </View>
        ) : (
          <Row key={i} gap={12} align="flex-start" style={{ paddingVertical: 7 }}>
            <StepIcon state={s.state} />
            <Txt weight={s.state === 'run' ? '500' : '400'} style={{ flex: 1 }}>{s.text + (s.state === 'run' ? '…' : '')}</Txt>
          </Row>
        ))}
      </View>
      {state === 'running' ? (
        <Txt size={13.5} tone="text2">You can hide this sheet. The job keeps running, and the robot&apos;s card shows its current step.</Txt>
      ) : (
        <Note kind={state === 'done' ? 'good' : state === 'warning' ? 'warn' : 'bad'}>{job?.message || ''}</Note>
      )}
    </Sheet>
  );
}

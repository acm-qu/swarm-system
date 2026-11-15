// Terminal: runs one command at a time on the robot over SSH (mockups phone-14, phone-15). The hub
// says which folder each command ended in, so "cd" is remembered. Output is always shown as text.
import { useRef, useState, type ComponentRef } from 'react';
import { ScrollView, TextInput, View } from 'react-native';

import { HubError, robotPost } from '@/lib/api';
import { useHub } from '@/lib/hub';
import type { Robot } from '@/lib/robot';
import { MONO, useTheme } from '@/theme';
import { CornerDownLeft, Terminal as TerminalIcon } from '../icons';
import { Btn, Card, Grow, Note, Row, Txt } from '../ui';

const EXEC_TIMEOUT_MS = 45_000; // the hub stops a command after 30 s; allow for the SSH login on top

export type TermEntry = { prompt: string; command: string; output: string; meta: string; bad: boolean };
export type Term = { cwd: string; entries: TermEntry[] };
export const NEW_TERM: Term = { cwd: '', entries: [] };

type ExecResult = { output: string; cwd?: string; code?: number; timed_out?: boolean; limit?: number; truncated?: boolean };

export function TerminalCard({ robot, term, onTerm }: { robot: Robot; term: Term; onTerm: (update: (t: Term) => Term) => void }) {
  const hub = useHub();
  const t = useTheme();
  const [command, setCommand] = useState('');
  const [busy, setBusy] = useState(false);
  const scroll = useRef<ComponentRef<typeof ScrollView>>(null);
  const prompt = (term.cwd || '~') + ' $';

  if (!robot.installed) {
    return <Note kind="info">This robot wasn&apos;t installed by this hub, so the hub can&apos;t log in to it.</Note>;
  }

  async function run() {
    const text = command.trim();
    if (!text || busy) return;
    setBusy(true);
    setCommand('');
    let entry: TermEntry;
    let cwd: string | undefined;
    try {
      const out = await robotPost<ExecResult>(robot.name, 'exec', { command: text, cwd: term.cwd }, EXEC_TIMEOUT_MS);
      cwd = out.cwd;
      let meta = out.timed_out ? `stopped: it took longer than ${out.limit} seconds` : out.code ? 'exit code ' + out.code : '';
      if (out.truncated) meta += (meta ? ' · ' : '') + 'output cut short';
      entry = { prompt, command: text, output: out.output, meta, bad: !!out.code || !!out.timed_out };
    } catch (err) {
      const meta = err instanceof HubError ? err.message : 'Something went wrong.';
      entry = { prompt, command: text, output: '', meta, bad: true };
    }
    onTerm((old) => ({ cwd: cwd || old.cwd, entries: [...old.entries, entry].slice(-200) }));
    setBusy(false);
  }

  return (
    <Card style={{ borderColor: t.stopBorder, overflow: 'hidden' }}>
      <View style={{ paddingVertical: 12, paddingHorizontal: 14, backgroundColor: t.stopBg, borderBottomWidth: 1, borderBottomColor: t.stopBorder }}>
        <Row gap={8}>
          <TerminalIcon size={17} color={t.badIcon} />
          <Txt weight="600" accessibilityRole="header">Terminal on {robot.name}</Txt>
        </Row>
        <Txt size={12.5} tone="text2" style={{ marginTop: 3 }}>Runs as the robot&apos;s user</Txt>
      </View>
      <ScrollView
        ref={scroll} nestedScrollEnabled style={{ maxHeight: 260, minHeight: 90, backgroundColor: t.surfaceDeep }}
        contentContainerStyle={{ padding: 12 }} accessibilityLiveRegion="polite"
        onContentSizeChange={() => scroll.current?.scrollToEnd({ animated: false })}>
        {term.entries.length ? term.entries.map((e, i) => (
          <View key={i} style={{ marginBottom: 8 }}>
            <Txt size={11} mono selectable><Txt size={11} mono tone="text3">{e.prompt}</Txt> {e.command}</Txt>
            {e.output ? <Txt size={11} mono selectable style={{ lineHeight: 17 }}>{e.output.replace(/\n$/, '')}</Txt> : null}
            {e.meta ? <Txt size={11} mono color={e.bad ? t.stopSoftText : t.text3}>{e.meta}</Txt> : null}
          </View>
        )) : <Txt size={12} mono tone="text3">Nothing run yet.</Txt>}
      </ScrollView>
      <Row gap={8} style={{ paddingVertical: 10, paddingHorizontal: 12, borderTopWidth: 1, borderTopColor: t.border }}>
        <Row gap={8} style={{
          flex: 1, height: 42, borderWidth: 1, borderColor: t.borderStrong, borderRadius: 10, backgroundColor: t.surfaceDeep, paddingHorizontal: 10,
        }}>
          <Txt size={12.5} mono tone="text3" numberOfLines={1} style={{ maxWidth: 110 }}>{prompt}</Txt>
          <TextInput
            accessibilityLabel="Command" value={command} onChangeText={setCommand} onSubmitEditing={run}
            editable={hub.terminalOk} autoCapitalize="none" autoCorrect={false} spellCheck={false}
            returnKeyType="send" submitBehavior="submit"
            style={{ flex: 1, height: 40, color: t.text, fontFamily: MONO, fontSize: 12.5 }}
          />
        </Row>
        <Btn label="Run" icon={CornerDownLeft} kind="primary" busy={busy} disabled={!hub.terminalOk || !command.trim()} onPress={run} style={{ height: 42 }} />
      </Row>
      <Row gap={8} align="flex-start" style={{ paddingTop: 10, paddingHorizontal: 14, paddingBottom: 12, borderTopWidth: 1, borderTopColor: t.border }}>
        <Txt size={12.5} tone="text2" style={{ flex: 1 }}>
          One command at a time, stops after 30 seconds. A folder change (cd) is remembered. Programs that need typing
          (nano, top) won&apos;t work. Works even when the robot&apos;s program is offline.
        </Txt>
        <Grow />
        <Btn label="Clear" size="sm" disabled={!term.entries.length} onPress={() => onTerm((old) => ({ ...old, entries: [] }))} />
      </Row>
    </Card>
  );
}

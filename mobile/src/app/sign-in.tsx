import { useState } from 'react';
import { KeyboardAvoidingView, ScrollView, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Btn, Card, Field, Logo, Note, Row, Txt } from '@/components/ui';
import { useHub } from '@/lib/hub';
import { useTheme } from '@/theme';

export default function SignIn() {
  const hub = useHub();
  const t = useTheme();
  const insets = useSafeAreaInsets();
  const [address, setAddress] = useState(hub.address);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const wrong = error.startsWith('Wrong');

  async function submit() {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      await hub.signIn(address, username, password);
    } catch (err) {
      setPassword('');
      setError(err instanceof Error ? err.message : 'Something went wrong. Try again.');
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: t.bg }} behavior="padding">
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{
          flexGrow: 1, justifyContent: 'center', padding: 16,
          paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16,
        }}>
        <Row gap={12} style={{ justifyContent: 'center', marginBottom: 22 }}>
          <Logo size={40} />
          <View>
            <Txt size={20} weight="600">Swarm Hub</Txt>
            <Txt size={13} tone="text2">Robot lab · sign in to continue</Txt>
          </View>
        </Row>
        <Card style={{ padding: 22, gap: 16 }}>
          <View style={{ gap: 4 }}>
            <Txt size={22} weight="600" accessibilityRole="header">Sign in</Txt>
            <Txt tone="text2">Use your hub login.</Txt>
          </View>
          {error ? <Note kind="warn">{error}</Note> : null}
          <Field
            label="Hub address" value={address} onChangeText={setAddress} mono
            placeholder="192.168.1.20:8000" keyboardType="url" returnKeyType="next"
            hint="Printed as &quot;Web page&quot; when the hub starts. Remembered on this phone."
          />
          <Field
            label="Username" value={username} onChangeText={setUsername}
            autoComplete="username" textContentType="username" returnKeyType="next"
          />
          <Field
            label="Password" value={password} onChangeText={setPassword} error={wrong}
            secureTextEntry autoComplete="current-password" textContentType="password"
            returnKeyType="go" onSubmitEditing={submit}
            hint={wrong ? 'Check your password and try again. After 5 wrong tries, sign-in pauses for a minute.' : undefined}
          />
          <Btn label="Sign in" kind="primary" size="lg" busy={busy} disabled={!address.trim() || !username.trim() || !password} onPress={submit} />
        </Card>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

// Bottom sheets (the phone's version of dialogs) and the toast. The dimmed area starts under the
// top bar, so Stop all stays in reach while a sheet is open.
import { useEffect, type ReactNode } from 'react';
import { BackHandler, KeyboardAvoidingView, Platform, Pressable, ScrollView, useWindowDimensions, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useHub } from '@/lib/hub';
import { useTheme } from '@/theme';
import { X, type LucideIcon } from './icons';
import { Btn, Row, Txt } from './ui';

/** Draws the open sheet, if any. Sits inside the app frame, below the top bar. */
export function SheetHost() {
  const hub = useHub();
  const t = useTheme();
  const open = !!hub.sheet;
  const dismiss = hub.dismissSheet;

  useEffect(() => {
    if (!open) return;
    // Android's Back button closes the sheet instead of leaving the screen.
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      dismiss();
      return true;
    });
    return () => sub.remove();
  }, [open, dismiss]);

  if (!open) return null;
  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={{ position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, justifyContent: 'flex-end' }}>
      <Pressable
        accessibilityLabel="Close" accessibilityRole="button" onPress={dismiss}
        style={{ position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, backgroundColor: t.overlay }}
      />
      {hub.sheet}
    </KeyboardAvoidingView>
  );
}

/** The frame of a sheet: title, body that scrolls if it is long, and full-width buttons underneath. */
export function Sheet({
  title, sub, lead, icon: Icon, danger, footer, children,
}: {
  title: string; sub?: ReactNode; lead?: ReactNode; icon?: LucideIcon; danger?: boolean; footer?: ReactNode; children?: ReactNode;
}) {
  const hub = useHub();
  const t = useTheme();
  const insets = useSafeAreaInsets();
  const { height } = useWindowDimensions();
  return (
    <View
      accessibilityViewIsModal
      style={{
        backgroundColor: t.surface, borderTopLeftRadius: 22, borderTopRightRadius: 22, borderWidth: 1, borderBottomWidth: 0,
        borderColor: t.borderStrong, borderTopColor: danger ? t.stop : t.borderStrong, borderTopWidth: danger ? 3 : 1,
        maxHeight: height * 0.78,
      }}>
      <View style={{ alignSelf: 'center', width: 40, height: 5, borderRadius: 3, backgroundColor: t.borderStrong, marginTop: 8 }} />
      <Row gap={14} align="flex-start" style={{ paddingHorizontal: 18, paddingTop: 13 }}>
        {Icon ? (
          <View style={{
            width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center',
            backgroundColor: t.stopBg, borderWidth: 1, borderColor: t.stopBorder,
          }}>
            <Icon size={18} color={t.badIcon} />
          </View>
        ) : null}
        <View style={{ flex: 1, gap: 4 }}>
          {lead}
          <Txt size={18} weight="600" accessibilityRole="header">{title}</Txt>
          {typeof sub === 'string' ? <Txt size={13.5} tone="text2">{sub}</Txt> : sub}
        </View>
        <Pressable accessibilityRole="button" accessibilityLabel="Close" hitSlop={12} onPress={hub.dismissSheet}>
          <X size={18} color={t.text2} />
        </Pressable>
      </Row>
      <ScrollView
        keyboardShouldPersistTaps="handled"
        style={{ flexGrow: 0 }}
        contentContainerStyle={{ paddingHorizontal: 18, paddingTop: 14, paddingBottom: 16, gap: 14 }}>
        {children}
      </ScrollView>
      {footer ? (
        <View style={{ gap: 8, paddingHorizontal: 18, paddingTop: 12, paddingBottom: Math.max(insets.bottom, 16), borderTopWidth: 1, borderTopColor: t.border }}>
          {footer}
        </View>
      ) : null}
    </View>
  );
}

/** "Are you sure?" for something risky. Cancel is the safe default and sits lowest, nearest the thumb. */
export function ConfirmSheet({
  title, icon, text, note, confirmLabel, onConfirm,
}: { title: string; icon: LucideIcon; text: string; note?: ReactNode; confirmLabel: string; onConfirm: () => void }) {
  const hub = useHub();
  return (
    <Sheet
      title={title} icon={icon} danger
      footer={
        <>
          <Btn label={confirmLabel} icon={icon} kind="danger" size="lg" onPress={onConfirm} />
          <Btn label="Cancel" size="lg" onPress={hub.dismissSheet} />
        </>
      }>
      <Txt size={15}>{text}</Txt>
      {note}
    </Sheet>
  );
}

/** A short message about something you just did that went wrong (for example a Stop that failed). */
export function ToastView() {
  const hub = useHub();
  const t = useTheme();
  if (!hub.toast) return null;
  return (
    <View
      accessibilityRole="alert" accessibilityLiveRegion="assertive" pointerEvents="none"
      style={{
        position: 'absolute', left: 14, right: 14, bottom: 84, borderRadius: 12, borderWidth: 1, padding: 12,
        backgroundColor: t.surfaceRaised, borderColor: hub.toast.bad ? t.stopBorder : t.borderStrong,
      }}>
      <Txt size={13.5}>{hub.toast.text}</Txt>
    </View>
  );
}

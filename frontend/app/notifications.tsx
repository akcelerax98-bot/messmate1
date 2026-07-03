// Notifications screen — shared between roles (modal route).
// - Students see notifications for their hostel (scheduled ones appear only after they've been sent).
// - Admins can compose a notification with optional date/time scheduling.

import DateTimePicker, {
  type DateTimePickerEvent,
} from "@react-native-community/datetimepicker";
import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { api } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { Button } from "@/src/components/Button";
import { Toast } from "@/src/components/Toast";
import { radius, shadow, spacing, typography, useTheme } from "@/src/theme";

type Item = {
  id: string;
  title: string;
  body: string;
  type: string;
  scheduled_for: string;
  send_at?: string | null;
  sent?: boolean;
  sent_at?: string | null;
  created_at: string;
  read?: boolean;
};

type ToastState = {
  message: string;
  variant: "success" | "error" | "info";
} | null;

const DEFAULT_TITLE_FALLBACK = "Help reduce food waste — mark your meals";
const DEFAULT_BODY_FALLBACK =
  "Hi! Please open MessMate and mark whether you'll be eating today's meals and pick the items you'd like. This helps the mess cook the right quantity and cut down on food waste. It only takes a few seconds — thank you for participating!";

// Add a small buffer so "now" doesn't fail with "past send_at" server-side.
function nowPlus(minutes: number) {
  const d = new Date();
  d.setMinutes(d.getMinutes() + minutes);
  return d;
}

function formatDateTime(d: Date): string {
  try {
    return d.toLocaleString(undefined, {
      weekday: "short",
      day: "numeric",
      month: "short",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return d.toISOString();
  }
}

function formatScheduledLabel(item: Item): string {
  if (item.send_at) {
    try {
      return `For ${new Date(item.send_at).toLocaleString(undefined, {
        weekday: "short",
        day: "numeric",
        month: "short",
        hour: "numeric",
        minute: "2-digit",
      })}`;
    } catch {
      /* noop */
    }
  }
  return `For ${item.scheduled_for}`;
}

export default function Notifications() {
  const { c } = useTheme();
  const { token, user } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "admin";
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState<ToastState>(null);

  const [composer, setComposer] = useState(false);
  const [title, setTitle] = useState(DEFAULT_TITLE_FALLBACK);
  const [body, setBody] = useState(DEFAULT_BODY_FALLBACK);
  const [sending, setSending] = useState(false);

  // Scheduling state
  const [scheduleMode, setScheduleMode] = useState<"now" | "later">("now");
  const [sendAt, setSendAt] = useState<Date>(() => nowPlus(60)); // default: 1h from now
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [showTimePicker, setShowTimePicker] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      if (isAdmin) {
        const res = await api.adminNotifications(token);
        setItems(res.items as Item[]);
      } else {
        const res = await api.studentNotifications(token);
        setItems(res.items as Item[]);
      }
    } catch (e: any) {
      setToast({ message: e?.message || "Failed to load", variant: "error" });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token, isAdmin]);

  useEffect(() => {
    load();
  }, [load]);

  // Load default template from backend (falls back to constants if the request fails).
  useEffect(() => {
    if (!token || !isAdmin) return;
    (async () => {
      try {
        const t = await api.adminNotificationDefaultTemplate(token);
        setTitle(t.title);
        setBody(t.body);
      } catch {
        /* keep fallback */
      }
    })();
  }, [token, isAdmin]);

  const markRead = async (id: string) => {
    if (!token || isAdmin) return;
    try {
      await api.markNotifRead(token, id);
      setItems((arr) => arr.map((i) => (i.id === id ? { ...i, read: true } : i)));
    } catch {
      /* silent */
    }
  };

  const sendMenuReminder = async () => {
    if (!token) return;
    setSending(true);
    try {
      await api.adminMenuReminder(token);
      setToast({ message: "Tomorrow's menu reminder sent", variant: "success" });
      await load();
    } catch (e: any) {
      setToast({ message: e?.message || "Could not send", variant: "error" });
    } finally {
      setSending(false);
    }
  };

  const sendAnnouncement = async () => {
    if (!token || !title.trim() || !body.trim()) {
      setToast({ message: "Title and message required", variant: "info" });
      return;
    }
    if (scheduleMode === "later") {
      if (sendAt.getTime() <= Date.now() + 15_000) {
        setToast({
          message: "Please pick a time at least a minute in the future",
          variant: "info",
        });
        return;
      }
    }
    setSending(true);
    try {
      const payload: Parameters<typeof api.adminCreateNotification>[1] = {
        title: title.trim(),
        body: body.trim(),
        audience: "all",
        type: "announcement",
      };
      if (scheduleMode === "later") {
        payload.send_at = sendAt.toISOString();
      }
      await api.adminCreateNotification(token, payload);
      setToast({
        message:
          scheduleMode === "later"
            ? `Scheduled for ${formatDateTime(sendAt)}`
            : "Announcement sent",
        variant: "success",
      });
      setComposer(false);
      // Reset schedule state (but keep the default template loaded)
      setScheduleMode("now");
      setSendAt(nowPlus(60));
      await load();
    } catch (e: any) {
      setToast({ message: e?.message || "Could not send", variant: "error" });
    } finally {
      setSending(false);
    }
  };

  const resetToDefault = async () => {
    if (!token) return;
    try {
      const t = await api.adminNotificationDefaultTemplate(token);
      setTitle(t.title);
      setBody(t.body);
      setToast({ message: "Restored default text", variant: "info" });
    } catch {
      setTitle(DEFAULT_TITLE_FALLBACK);
      setBody(DEFAULT_BODY_FALLBACK);
    }
  };

  const onChangeDate = (event: DateTimePickerEvent, selected?: Date) => {
    if (Platform.OS !== "ios") setShowDatePicker(false);
    if (event.type === "dismissed" || !selected) return;
    // Preserve time, replace date parts
    const next = new Date(sendAt);
    next.setFullYear(selected.getFullYear(), selected.getMonth(), selected.getDate());
    setSendAt(next);
  };

  const onChangeTime = (event: DateTimePickerEvent, selected?: Date) => {
    if (Platform.OS !== "ios") setShowTimePicker(false);
    if (event.type === "dismissed" || !selected) return;
    const next = new Date(sendAt);
    next.setHours(selected.getHours(), selected.getMinutes(), 0, 0);
    setSendAt(next);
  };

  const scheduleSummary = useMemo(() => formatDateTime(sendAt), [sendAt]);
  const composerIsClean = useMemo(
    () =>
      title.trim() === DEFAULT_TITLE_FALLBACK && body.trim() === DEFAULT_BODY_FALLBACK,
    [title, body],
  );

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: c.bg }]} edges={["top", "bottom"]}>
      <Toast
        testID="notif-toast"
        message={toast?.message ?? null}
        variant={toast?.variant ?? "success"}
        onHide={() => setToast(null)}
      />
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <View style={styles.header}>
          <Text style={[styles.title, { color: c.textPrimary }]}>Notifications</Text>
          <TouchableOpacity
            testID="notif-close"
            onPress={() => router.back()}
            style={[styles.closeBtn, { backgroundColor: c.inputBg }]}
          >
            <Feather name="x" size={18} color={c.textPrimary} />
          </TouchableOpacity>
        </View>

        <ScrollView
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xl }}
          keyboardShouldPersistTaps="handled"
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => {
                setRefreshing(true);
                load();
              }}
              tintColor={c.primary}
            />
          }
        >
          {isAdmin ? (
            <View style={[styles.card, { backgroundColor: c.card, borderColor: c.border }]}>
              <Text style={[styles.cardTitle, { color: c.textPrimary }]}>
                Send notifications
              </Text>
              <Text style={[styles.cardHelp, { color: c.textSecondary }]}>
                Broadcasts to every student in your hostel. Students receive a push
                on their phone and can view all past messages here.
              </Text>

              <Button
                testID="notif-menu-reminder"
                label={sending ? "Sending..." : "Send tomorrow's menu reminder"}
                onPress={sendMenuReminder}
                loading={sending}
                style={{ marginTop: 12 }}
              />

              <TouchableOpacity
                testID="notif-toggle-composer"
                onPress={() => setComposer((v) => !v)}
                style={[styles.linkRow, { borderTopColor: c.divider }]}
              >
                <Feather
                  name={composer ? "chevron-up" : "edit-3"}
                  size={16}
                  color={c.primary}
                />
                <Text style={[styles.linkText, { color: c.primary }]}>
                  {composer ? "Hide composer" : "Compose a reminder to reduce food waste"}
                </Text>
              </TouchableOpacity>

              {composer ? (
                <View style={{ marginTop: 12 }}>
                  <View style={styles.composerLabelRow}>
                    <Text style={[styles.fieldLabel, { color: c.textSecondary }]}>
                      Title
                    </Text>
                    {!composerIsClean ? (
                      <TouchableOpacity
                        testID="notif-reset-default"
                        onPress={resetToDefault}
                        hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
                      >
                        <Text style={[styles.resetLink, { color: c.primary }]}>
                          Reset to default
                        </Text>
                      </TouchableOpacity>
                    ) : null}
                  </View>
                  <TextInput
                    testID="notif-title-input"
                    placeholder="Notification title"
                    placeholderTextColor={c.textSecondary}
                    value={title}
                    onChangeText={setTitle}
                    style={[
                      styles.input,
                      { backgroundColor: c.inputBg, color: c.textPrimary },
                    ]}
                  />

                  <Text
                    style={[
                      styles.fieldLabel,
                      { color: c.textSecondary, marginTop: 12 },
                    ]}
                  >
                    Message
                  </Text>
                  <TextInput
                    testID="notif-body-input"
                    placeholder="Message"
                    placeholderTextColor={c.textSecondary}
                    value={body}
                    onChangeText={setBody}
                    multiline
                    style={[
                      styles.input,
                      {
                        backgroundColor: c.inputBg,
                        color: c.textPrimary,
                        minHeight: 110,
                        textAlignVertical: "top",
                      },
                    ]}
                  />

                  <Text
                    style={[
                      styles.fieldLabel,
                      { color: c.textSecondary, marginTop: 16 },
                    ]}
                  >
                    Delivery
                  </Text>
                  <View style={styles.segment}>
                    {(["now", "later"] as const).map((opt) => {
                      const active = scheduleMode === opt;
                      return (
                        <TouchableOpacity
                          key={opt}
                          testID={`notif-schedule-${opt}`}
                          activeOpacity={0.85}
                          onPress={() => setScheduleMode(opt)}
                          style={[
                            styles.segmentBtn,
                            {
                              backgroundColor: active ? c.card : "transparent",
                              borderColor: active ? c.primary : "transparent",
                            },
                          ]}
                        >
                          <Feather
                            name={opt === "now" ? "send" : "clock"}
                            size={14}
                            color={active ? c.primary : c.textSecondary}
                          />
                          <Text
                            style={[
                              styles.segmentLabel,
                              { color: active ? c.textPrimary : c.textSecondary },
                            ]}
                          >
                            {opt === "now" ? "Send now" : "Schedule for later"}
                          </Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>

                  {scheduleMode === "later" ? (
                    <View style={styles.schedulePickerRow}>
                      <TouchableOpacity
                        testID="notif-pick-date"
                        activeOpacity={0.85}
                        onPress={() => setShowDatePicker(true)}
                        style={[
                          styles.pickerBtn,
                          { backgroundColor: c.inputBg, borderColor: c.border },
                        ]}
                      >
                        <Feather name="calendar" size={14} color={c.primary} />
                        <Text style={[styles.pickerText, { color: c.textPrimary }]}>
                          {sendAt.toLocaleDateString(undefined, {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          })}
                        </Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        testID="notif-pick-time"
                        activeOpacity={0.85}
                        onPress={() => setShowTimePicker(true)}
                        style={[
                          styles.pickerBtn,
                          { backgroundColor: c.inputBg, borderColor: c.border },
                        ]}
                      >
                        <Feather name="clock" size={14} color={c.primary} />
                        <Text style={[styles.pickerText, { color: c.textPrimary }]}>
                          {sendAt.toLocaleTimeString(undefined, {
                            hour: "numeric",
                            minute: "2-digit",
                          })}
                        </Text>
                      </TouchableOpacity>
                    </View>
                  ) : null}

                  {scheduleMode === "later" ? (
                    <Text style={[styles.scheduleHint, { color: c.textSecondary }]}>
                      Students will receive it on {scheduleSummary}.
                    </Text>
                  ) : null}

                  {showDatePicker ? (
                    <DateTimePicker
                      testID="notif-date-picker"
                      value={sendAt}
                      mode="date"
                      minimumDate={new Date()}
                      onChange={onChangeDate}
                    />
                  ) : null}
                  {showTimePicker ? (
                    <DateTimePicker
                      testID="notif-time-picker"
                      value={sendAt}
                      mode="time"
                      is24Hour={false}
                      onChange={onChangeTime}
                    />
                  ) : null}

                  <Button
                    testID="notif-send-announcement"
                    label={
                      scheduleMode === "later"
                        ? `Schedule for ${scheduleSummary}`
                        : "Send to all students now"
                    }
                    onPress={sendAnnouncement}
                    loading={sending}
                    style={{ marginTop: 14 }}
                  />
                </View>
              ) : null}
            </View>
          ) : null}

          {loading ? (
            <View style={styles.centerWrap}>
              <ActivityIndicator color={c.primary} />
            </View>
          ) : items.length === 0 ? (
            <View style={[styles.card, { backgroundColor: c.card, borderColor: c.border }]}>
              <Text style={[styles.empty, { color: c.textSecondary }]}>
                {isAdmin
                  ? "No notifications sent yet."
                  : "No notifications yet. You'll see updates here when the admin sends them."}
              </Text>
            </View>
          ) : (
            items.map((n) => {
              const scheduledFuture = isAdmin && n.sent === false;
              return (
                <TouchableOpacity
                  key={n.id}
                  testID={`notif-item-${n.id}`}
                  activeOpacity={isAdmin ? 1 : 0.85}
                  onPress={() => !isAdmin && !n.read && markRead(n.id)}
                  style={[
                    styles.notifCard,
                    {
                      backgroundColor: c.card,
                      borderColor: c.border,
                      opacity: !isAdmin && n.read ? 0.7 : 1,
                    },
                  ]}
                >
                  <View style={styles.notifRow}>
                    <View
                      style={[
                        styles.notifBadge,
                        {
                          backgroundColor:
                            n.type === "menu_reminder" ? c.primaryTint : c.inputBg,
                        },
                      ]}
                    >
                      <Feather
                        name={
                          n.type === "menu_reminder"
                            ? "calendar"
                            : n.type === "system"
                              ? "info"
                              : "bell"
                        }
                        size={16}
                        color={n.type === "menu_reminder" ? c.primary : c.textSecondary}
                      />
                    </View>
                    <View style={{ flex: 1 }}>
                      <View style={styles.notifTitleRow}>
                        <Text
                          style={[styles.notifTitle, { color: c.textPrimary }]}
                          numberOfLines={2}
                        >
                          {n.title}
                        </Text>
                        {scheduledFuture ? (
                          <View
                            style={[
                              styles.pill,
                              { backgroundColor: c.primaryTint },
                            ]}
                          >
                            <Feather name="clock" size={10} color={c.primary} />
                            <Text style={[styles.pillText, { color: c.primary }]}>
                              Scheduled
                            </Text>
                          </View>
                        ) : null}
                      </View>
                      <Text style={[styles.notifBody, { color: c.textSecondary }]}>
                        {n.body}
                      </Text>
                      <Text style={[styles.notifMeta, { color: c.textTertiary }]}>
                        {formatScheduledLabel(n)}
                      </Text>
                    </View>
                    {!isAdmin && !n.read ? (
                      <View style={[styles.dot, { backgroundColor: c.primary }]} />
                    ) : null}
                  </View>
                </TouchableOpacity>
              );
            })
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  title: { ...typography.title1 },
  closeBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
  },
  card: {
    borderRadius: radius.xl,
    padding: spacing.md,
    borderWidth: 1,
    marginBottom: spacing.md,
    ...shadow.card,
  },
  cardTitle: { ...typography.title2 },
  cardHelp: { ...typography.caption, marginTop: 6, lineHeight: 18 },
  linkRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 10,
    borderTopWidth: 1,
    marginTop: 12,
  },
  linkText: { ...typography.subhead, fontWeight: "600" },
  fieldLabel: {
    ...typography.footnote,
    fontWeight: "700",
    letterSpacing: 0.4,
    marginBottom: 6,
    textTransform: "uppercase",
  },
  composerLabelRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  resetLink: {
    ...typography.footnote,
    fontWeight: "700",
    marginBottom: 6,
  },
  input: {
    borderRadius: radius.md,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
  },
  segment: {
    flexDirection: "row",
    backgroundColor: "rgba(0,0,0,0.04)",
    borderRadius: 12,
    padding: 4,
    gap: 4,
  },
  segmentBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
  },
  segmentLabel: { ...typography.footnote, fontWeight: "700" },
  schedulePickerRow: {
    flexDirection: "row",
    gap: 10,
    marginTop: 12,
  },
  pickerBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 12,
    borderRadius: radius.md,
    borderWidth: 1,
  },
  pickerText: { ...typography.subhead, fontWeight: "600" },
  scheduleHint: { ...typography.caption, marginTop: 8, fontStyle: "italic" },
  centerWrap: { paddingVertical: 60, alignItems: "center" },
  empty: { ...typography.subhead, textAlign: "center" },
  notifCard: {
    borderRadius: radius.lg,
    padding: spacing.md,
    marginBottom: 10,
    borderWidth: 1,
    ...shadow.card,
  },
  notifRow: { flexDirection: "row", gap: 12, alignItems: "flex-start" },
  notifBadge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
  },
  notifTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap",
  },
  notifTitle: { ...typography.headline, flexShrink: 1 },
  notifBody: { ...typography.subhead, marginTop: 4, lineHeight: 20 },
  notifMeta: { ...typography.caption, marginTop: 6 },
  dot: { width: 10, height: 10, borderRadius: 5, marginTop: 6 },
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
  },
  pillText: { ...typography.caption, fontWeight: "700", fontSize: 11 },
});

// Notifications screen — shared between roles (modal route)

import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useCallback, useEffect, useState } from "react";
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
  created_at: string;
  read?: boolean;
};

export default function Notifications() {
  const { c } = useTheme();
  const { token, user } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "admin";
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState<{
    message: string;
    variant: "success" | "error" | "info";
  } | null>(null);

  const [composer, setComposer] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      if (isAdmin) {
        const res = await api.adminNotifications(token);
        setItems(res.items);
      } else {
        const res = await api.studentNotifications(token);
        setItems(res.items);
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
    setSending(true);
    try {
      await api.adminCreateNotification(token, {
        title: title.trim(),
        body: body.trim(),
        audience: "all",
        type: "announcement",
      });
      setToast({ message: "Announcement sent", variant: "success" });
      setTitle("");
      setBody("");
      setComposer(false);
      await load();
    } catch (e: any) {
      setToast({ message: e?.message || "Could not send", variant: "error" });
    } finally {
      setSending(false);
    }
  };

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
                Hosted in-app. Real push will fire on real devices after deploy.
              </Text>
              <Button
                testID="notif-menu-reminder"
                label={sending ? "Sending..." : "Send tomorrow's menu reminder"}
                onPress={sendMenuReminder}
                loading={sending}
                style={{ marginTop: 10 }}
              />
              <TouchableOpacity
                testID="notif-toggle-composer"
                onPress={() => setComposer((v) => !v)}
                style={[styles.linkRow, { borderTopColor: c.divider }]}
              >
                <Feather name="edit-3" size={16} color={c.primary} />
                <Text style={[styles.linkText, { color: c.primary }]}>
                  {composer ? "Cancel announcement" : "Compose custom announcement"}
                </Text>
              </TouchableOpacity>
              {composer ? (
                <View style={{ marginTop: 10 }}>
                  <TextInput
                    testID="notif-title-input"
                    placeholder="Title"
                    placeholderTextColor={c.textSecondary}
                    value={title}
                    onChangeText={setTitle}
                    style={[styles.input, { backgroundColor: c.inputBg, color: c.textPrimary }]}
                  />
                  <TextInput
                    testID="notif-body-input"
                    placeholder="Message"
                    placeholderTextColor={c.textSecondary}
                    value={body}
                    onChangeText={setBody}
                    multiline
                    style={[
                      styles.input,
                      { backgroundColor: c.inputBg, color: c.textPrimary, minHeight: 80, marginTop: 8 },
                    ]}
                  />
                  <Button
                    testID="notif-send-announcement"
                    label="Send to all students"
                    onPress={sendAnnouncement}
                    loading={sending}
                    style={{ marginTop: 10 }}
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
                No notifications yet.
              </Text>
            </View>
          ) : (
            items.map((n) => (
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
                          n.type === "menu_reminder"
                            ? c.primaryTint
                            : c.inputBg,
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
                    <Text style={[styles.notifTitle, { color: c.textPrimary }]}>
                      {n.title}
                    </Text>
                    <Text style={[styles.notifBody, { color: c.textSecondary }]}>
                      {n.body}
                    </Text>
                    <Text style={[styles.notifMeta, { color: c.textTertiary }]}>
                      For {n.scheduled_for}
                    </Text>
                  </View>
                  {!isAdmin && !n.read ? (
                    <View style={[styles.dot, { backgroundColor: c.primary }]} />
                  ) : null}
                </View>
              </TouchableOpacity>
            ))
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
  cardHelp: { ...typography.caption, marginTop: 4 },
  linkRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 10,
    borderTopWidth: 1,
    marginTop: 8,
  },
  linkText: { ...typography.subhead, fontWeight: "600" },
  input: {
    borderRadius: radius.md,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
  },
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
  notifTitle: { ...typography.headline },
  notifBody: { ...typography.subhead, marginTop: 4, lineHeight: 20 },
  notifMeta: { ...typography.caption, marginTop: 6 },
  dot: { width: 10, height: 10, borderRadius: 5, marginTop: 6 },
});

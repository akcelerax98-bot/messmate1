// Admin Tab 5 — Settings (profile + defaults + logout)

import { Feather } from "@expo/vector-icons";
import React, { useMemo, useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { api, type AppSettings, type Reaction } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { Button } from "@/src/components/Button";
import { NotifBell } from "@/src/components/NotifBell";
import { Segmented } from "@/src/components/Segmented";
import { ThemeToggle } from "@/src/components/ThemeToggle";
import { Toast } from "@/src/components/Toast";
import { radius, shadow, spacing, typography, useTheme, type ThemeColors } from "@/src/theme";

export default function AdminSettings() {
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const { user, token, logout } = useAuth();
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [toast, setToast] = useState<{
    message: string;
    variant: "success" | "error" | "info";
  } | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setSettings(await api.adminSettings(token));
    } catch (e: any) {
      setToast({ message: e?.message || "Failed to load settings", variant: "error" });
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const update = async (patch: Partial<AppSettings>, key: string) => {
    if (!token) return;
    setSavingKey(key);
    try {
      const next = await api.adminSettingsUpdate(token, patch);
      setSettings(next);
      setToast({ message: "Saved", variant: "success" });
    } catch (e: any) {
      setToast({ message: e?.message || "Save failed", variant: "error" });
    } finally {
      setSavingKey(null);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.safe} edges={["top"]}>
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <Toast
        testID="admin-settings-toast"
        message={toast?.message ?? null}
        variant={toast?.variant ?? "success"}
        onHide={() => setToast(null)}
      />
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.headerRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.eyebrow}>ADMIN</Text>
            <Text style={styles.title}>Settings</Text>
          </View>
          <NotifBell testID="admin-settings-bell" />
        </View>

        {/* Profile */}
        <View style={[styles.card, styles.profileCard]}>
          <View style={styles.avatar}>
            <Text style={styles.avatarLetter}>
              {(user?.full_name?.[0] || "A").toUpperCase()}
            </Text>
          </View>
          <Text style={styles.profileName}>{user?.full_name || "Admin"}</Text>
          <Text style={styles.profileSub}>{user?.institution_or_hostel_name}</Text>
          <View style={styles.adminBadge}>
            <Text style={styles.adminBadgeText}>Admin · {user?.mobile_or_user_id}</Text>
          </View>
        </View>

        {/* Defaults */}
        <Text style={styles.sectionLabel}>Default student behaviour</Text>

        <View style={styles.card}>
          <Text style={styles.rowLabel}>Default meal state (ON/OFF)</Text>
          <Text style={styles.rowHelp}>
            New students start with this for breakfast, lunch & dinner.
          </Text>
          <Segmented<"ON" | "OFF">
            testID="setting-meal-state"
            value={settings?.default_meal_state || "ON"}
            onChange={(v) => update({ default_meal_state: v }, "meal")}
            options={[
              { value: "ON", label: "ON (eating)" },
              { value: "OFF", label: "OFF (skip)" },
            ]}
            style={{ marginTop: 8 }}
          />
        </View>

        <View style={styles.card}>
          <Text style={styles.rowLabel}>Default like/dislike state</Text>
          <Text style={styles.rowHelp}>Initial menu reaction shown to students.</Text>
          <Segmented<Reaction>
            testID="setting-like-state"
            value={settings?.default_like_dislike_state || "no_response"}
            onChange={(v) => update({ default_like_dislike_state: v }, "like")}
            options={[
              { value: "no_response", label: "No response" },
              { value: "like", label: "Like" },
              { value: "dislike", label: "Dislike" },
            ]}
            style={{ marginTop: 8 }}
          />
        </View>

        <View style={styles.card}>
          <Text style={styles.rowLabel}>Default preference state</Text>
          <Text style={styles.rowHelp}>What items are pre-selected for new students.</Text>
          <Segmented<"none" | "all" | "previous">
            testID="setting-pref-state"
            value={settings?.default_preference_state || "none"}
            onChange={(v) => update({ default_preference_state: v }, "pref")}
            options={[
              { value: "none", label: "None" },
              { value: "all", label: "All items" },
              { value: "previous", label: "Previous" },
            ]}
            style={{ marginTop: 8 }}
          />
        </View>

        <Text style={styles.sectionLabel}>Appearance</Text>
        <View style={styles.card}>
          <ThemeToggle />
        </View>

        <Text style={styles.sectionLabel}>App</Text>
        <View style={styles.card}>
          <View style={styles.switchRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowLabel}>Notifications</Text>
              <Text style={styles.rowHelp}>
                Will be implemented when push notifications are added.
              </Text>
            </View>
            <Switch
              testID="setting-notifications"
              value={!!settings?.notifications_enabled}
              onValueChange={(v) =>
                update({ notifications_enabled: v }, "notifications")
              }
              trackColor={{ false: colors.inputBg, true: colors.primary }}
            />
          </View>
          <View style={styles.divider} />
          <TouchableOpacity activeOpacity={0.7} style={styles.row} testID="setting-language">
            <View style={styles.rowIcon}>
              <Feather name="globe" size={16} color={colors.primary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowLabel}>Language</Text>
              <Text style={styles.rowHelp}>{settings?.language || "English"}</Text>
            </View>
          </TouchableOpacity>
        </View>

        <Button
          testID="admin-settings-logout"
          label="Sign out"
          variant="secondary"
          onPress={logout}
          style={{ marginTop: spacing.lg }}
        />

        <Text style={styles.versionText}>MessMate · v0.2.0</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const makeStyles = (c: ThemeColors) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: c.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl + 32 },
  header: { marginBottom: spacing.md },
  headerRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    marginBottom: spacing.md,
  },
  eyebrow: {
    ...typography.caption,
    color: c.primary,
    letterSpacing: 1.5,
    fontWeight: "700",
    marginBottom: 6,
  },
  title: { ...typography.title1, color: c.textPrimary },
  card: {
    backgroundColor: c.card,
    borderRadius: radius.xl,
    padding: spacing.md,
    marginBottom: spacing.md,
    ...shadow.card,
  },
  profileCard: { alignItems: "center", paddingVertical: spacing.lg },
  avatar: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: c.primary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.md,
  },
  avatarLetter: { color: "#fff", fontSize: 30, fontWeight: "700" },
  profileName: { ...typography.title2, color: c.textPrimary },
  profileSub: { ...typography.subhead, color: c.textSecondary, marginTop: 4 },
  adminBadge: {
    marginTop: 10,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    backgroundColor: c.primaryLight,
  },
  adminBadgeText: { ...typography.caption, color: c.primaryDark, fontWeight: "700" },

  sectionLabel: {
    ...typography.caption,
    color: c.textSecondary,
    textTransform: "uppercase",
    letterSpacing: 1,
    marginLeft: 4,
    marginBottom: 8,
    marginTop: 4,
  },
  rowLabel: { ...typography.headline, color: c.textPrimary },
  rowHelp: { ...typography.caption, color: c.textSecondary, marginTop: 2 },
  switchRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 4, gap: 12 },
  rowIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: c.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  divider: { height: 1, backgroundColor: c.border, marginVertical: 12 },
  versionText: {
    ...typography.caption,
    color: c.textTertiary,
    textAlign: "center",
    marginTop: spacing.lg,
  },
});

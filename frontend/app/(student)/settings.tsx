// Student Settings — profile + account/app placeholders + logout.

import { Feather } from "@expo/vector-icons";
import React, { useMemo } from "react";
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth/AuthContext";
import { Button } from "@/src/components/Button";
import { NotifBell } from "@/src/components/NotifBell";
import { ThemeToggle } from "@/src/components/ThemeToggle";
import { radius, shadow, spacing, typography, colors, useTheme, type ThemeColors } from "@/src/theme";

type Row = {
  icon: keyof typeof Feather.glyphMap;
  label: string;
  value?: string;
  testID: string;
  onPress?: () => void;
  disabledNote?: boolean;
};

function SettingsRow({ icon, label, value, testID, onPress, disabledNote }: Row) {
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  return (
    <TouchableOpacity
      testID={testID}
      activeOpacity={onPress ? 0.7 : 1}
      onPress={onPress}
      disabled={!onPress}
      style={styles.row}
    >
      <View style={styles.rowIcon}>
        <Feather name={icon} size={18} color={c.primary} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.rowLabel}>{label}</Text>
        {value ? <Text style={styles.rowValue}>{value}</Text> : null}
        {disabledNote ? <Text style={styles.rowMuted}>Coming soon</Text> : null}
      </View>
      <Feather
        name="chevron-right"
        size={18}
        color={onPress ? c.textSecondary : c.textTertiary}
      />
    </TouchableOpacity>
  );
}

export default function StudentSettings() {
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const { user, logout } = useAuth();

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.headerRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.eyebrow}>STUDENT</Text>
            <Text style={styles.title}>Settings</Text>
          </View>
          <NotifBell testID="student-settings-bell" />
        </View>

        {/* Profile card */}
        <View style={[styles.card, styles.profileCard]} testID="student-profile-card">
          <View style={styles.avatar}>
            <Text style={styles.avatarLetter}>
              {(user?.full_name?.[0] || "S").toUpperCase()}
            </Text>
          </View>
          <Text style={styles.profileName} testID="student-profile-name">
            {user?.full_name || "Student"}
          </Text>
          <Text style={styles.profileSub} testID="student-profile-sub">
            {user?.institution_or_hostel_name || "—"}
          </Text>
          {user?.institution_or_hostel_name ? (
            <View style={styles.roomBadge}>
              <Text style={styles.roomBadgeText}>{user.institution_or_hostel_name}</Text>
            </View>
          ) : null}
        </View>

        {/* Profile details */}
        <Text style={styles.sectionLabel}>Profile</Text>
        <View style={styles.card}>
          <SettingsRow
            icon="user"
            label="Full name"
            value={user?.full_name || "—"}
            testID="student-row-name"
          />
          <View style={styles.divider} />
          <SettingsRow
            icon="mail"
            label="Email"
            value={user?.email || user?.mobile_or_user_id || "—"}
            testID="student-row-email"
          />
          <View style={styles.divider} />
          <SettingsRow
            icon="home"
            label="Institution / Hostel"
            value={user?.institution_or_hostel_name || "—"}
            testID="student-row-hostel"
          />
        </View>

        {/* Account */}
        <Text style={styles.sectionLabel}>Account</Text>
        <View style={styles.card}>
          <SettingsRow
            icon="lock"
            label="Change password"
            testID="student-row-change-password"
            disabledNote
          />
        </View>

        {/* App */}
        <Text style={styles.sectionLabel}>Appearance</Text>
        <View style={styles.card}>
          <ThemeToggle />
        </View>

        <Text style={styles.sectionLabel}>App</Text>
        <View style={styles.card}>
          <SettingsRow
            icon="bell"
            label="Notifications"
            testID="student-row-notifications"
            disabledNote
          />
          <View style={styles.divider} />
          <SettingsRow
            icon="globe"
            label="Language"
            value="English"
            testID="student-row-language"
            disabledNote
          />
        </View>

        <Button
          testID="student-settings-logout"
          label="Sign out"
          variant="secondary"
          onPress={logout}
          style={{ marginTop: spacing.lg }}
        />

        <Text style={styles.versionText}>MessMate · v0.1.0</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const makeStyles = (c: ThemeColors) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: c.bg },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl + 24 },
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
  profileCard: {
    alignItems: "center",
    paddingVertical: spacing.lg,
  },
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
  roomBadge: {
    marginTop: 10,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    backgroundColor: c.primaryLight,
  },
  roomBadgeText: {
    ...typography.caption,
    color: c.primaryDark,
    fontWeight: "700",
  },

  sectionLabel: {
    ...typography.caption,
    color: c.textSecondary,
    textTransform: "uppercase",
    letterSpacing: 1,
    marginLeft: 6,
    marginBottom: 8,
    marginTop: 4,
  },

  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
    gap: 12,
  },
  rowIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: c.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  rowLabel: { ...typography.subhead, color: c.textPrimary, fontWeight: "600" },
  rowValue: { ...typography.caption, color: c.textSecondary, marginTop: 2 },
  rowMuted: { ...typography.caption, color: c.textTertiary, marginTop: 2 },
  divider: { height: 1, backgroundColor: c.border, marginLeft: 48 },

  versionText: {
    ...typography.caption,
    color: c.textTertiary,
    textAlign: "center",
    marginTop: spacing.lg,
  },
});

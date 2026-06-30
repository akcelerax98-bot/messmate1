// Pending approval screen

import { Feather } from "@expo/vector-icons";
import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth/AuthContext";
import { Button } from "@/src/components/Button";
import { colors, spacing, typography } from "@/src/theme";

export default function Pending() {
  const { logout, user } = useAuth();

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <View style={styles.wrap}>
        <View style={[styles.icon, { backgroundColor: colors.badgePendingBg }]}>
          <Feather name="clock" size={36} color={colors.pending} />
        </View>
        <Text style={styles.title} testID="pending-title">
          Waiting for approval
        </Text>
        <Text style={styles.body} testID="pending-body">
          Your account is waiting for admin approval. You can access MessMate after
          the admin approves your account.
        </Text>

        {user ? (
          <View style={styles.metaBox} testID="pending-meta">
            <Text style={styles.metaLabel}>Account</Text>
            <Text style={styles.metaValue}>{user.full_name}</Text>
            <Text style={styles.metaValue}>{user.mobile_or_user_id}</Text>
            <Text style={styles.metaValue}>
              {user.institution_or_hostel_name} · Room {user.room_number}
            </Text>
          </View>
        ) : null}

        <Button
          testID="pending-logout"
          label="Sign out"
          variant="secondary"
          onPress={logout}
          style={{ alignSelf: "stretch", marginTop: spacing.xl }}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  wrap: {
    flex: 1,
    paddingHorizontal: spacing.lg,
    alignItems: "center",
    justifyContent: "center",
  },
  icon: {
    width: 84,
    height: 84,
    borderRadius: 42,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.lg,
  },
  title: {
    ...typography.title1,
    color: colors.textPrimary,
    textAlign: "center",
    marginBottom: spacing.sm,
  },
  body: {
    ...typography.callout,
    color: colors.textSecondary,
    textAlign: "center",
    lineHeight: 22,
  },
  metaBox: {
    marginTop: spacing.lg,
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: spacing.md,
    alignSelf: "stretch",
  },
  metaLabel: {
    ...typography.caption,
    color: colors.textSecondary,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  metaValue: { ...typography.subhead, color: colors.textPrimary, marginTop: 2 },
});

// Pending approval screen — Theme-reactive.

import { Feather } from "@expo/vector-icons";
import React, { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth/AuthContext";
import { Button } from "@/src/components/Button";
import { spacing, typography, useTheme, type ThemeColors } from "@/src/theme";

export default function Pending() {
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const { logout, user } = useAuth();

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <View style={styles.wrap}>
        <View style={[styles.icon, { backgroundColor: c.badgePendingBg }]}>
          <Feather name="clock" size={36} color={c.pending} />
        </View>
        <Text style={styles.title} testID="pending-title">Waiting for approval</Text>
        <Text style={styles.body} testID="pending-body">
          Your account is waiting for admin approval. You can access MessMate after the admin approves your account.
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

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    safe: { flex: 1, backgroundColor: c.bg },
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
      color: c.textPrimary,
      textAlign: "center",
      marginBottom: spacing.sm,
    },
    body: {
      ...typography.callout,
      color: c.textSecondary,
      textAlign: "center",
      lineHeight: 22,
    },
    metaBox: {
      marginTop: spacing.lg,
      backgroundColor: c.card,
      borderRadius: 16,
      padding: spacing.md,
      borderWidth: 1,
      borderColor: c.border,
      alignSelf: "stretch",
    },
    metaLabel: {
      ...typography.caption,
      color: c.textSecondary,
      textTransform: "uppercase",
      letterSpacing: 0.5,
      marginBottom: 6,
    },
    metaValue: { ...typography.subhead, color: c.textPrimary, marginTop: 2 },
  });

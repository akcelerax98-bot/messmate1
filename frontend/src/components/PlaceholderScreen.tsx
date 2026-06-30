// Shared placeholder screen. Theme-reactive.

import { Feather } from "@expo/vector-icons";
import React, { useMemo } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth/AuthContext";
import { Button } from "@/src/components/Button";
import { radius, shadow, spacing, typography, useTheme, type ThemeColors } from "@/src/theme";

type Props = {
  title: string;
  description: string;
  icon: keyof typeof Feather.glyphMap;
  testID: string;
  showLogout?: boolean;
};

export function PlaceholderScreen({
  title,
  description,
  icon,
  testID,
  showLogout = false,
}: Props) {
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const { user, logout } = useAuth();

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <Text style={styles.eyebrow}>{user?.role === "admin" ? "ADMIN" : "STUDENT"}</Text>
          <Text style={styles.title} testID={`${testID}-title`}>{title}</Text>
          {user ? (
            <Text style={styles.subtitle}>
              Signed in as {user.full_name} · {user.institution_or_hostel_name}
            </Text>
          ) : null}
        </View>

        <View style={styles.card} testID={testID}>
          <View style={styles.iconBubble}>
            <Feather name={icon} size={28} color={c.primary} />
          </View>
          <Text style={styles.cardTitle}>Coming soon</Text>
          <Text style={styles.cardBody}>{description}</Text>
        </View>

        {showLogout ? (
          <Button
            testID={`${testID}-logout`}
            label="Sign out"
            variant="secondary"
            onPress={logout}
            style={{ marginTop: spacing.lg }}
          />
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    safe: { flex: 1, backgroundColor: c.bg },
    content: { padding: spacing.lg, paddingBottom: spacing.xxl },
    header: { marginBottom: spacing.lg },
    eyebrow: {
      ...typography.caption,
      color: c.primary,
      letterSpacing: 1.5,
      fontWeight: "700",
      marginBottom: 6,
    },
    title: { ...typography.title1, color: c.textPrimary },
    subtitle: { ...typography.subhead, color: c.textSecondary, marginTop: 4 },
    card: {
      backgroundColor: c.card,
      borderRadius: radius.xl,
      padding: spacing.lg,
      alignItems: "center",
      borderWidth: 1,
      borderColor: c.border,
      ...shadow.card,
    },
    iconBubble: {
      width: 64,
      height: 64,
      borderRadius: 32,
      backgroundColor: c.primaryLight,
      alignItems: "center",
      justifyContent: "center",
      marginBottom: spacing.md,
    },
    cardTitle: {
      ...typography.title2,
      color: c.textPrimary,
      marginBottom: spacing.sm,
    },
    cardBody: {
      ...typography.callout,
      color: c.textSecondary,
      textAlign: "center",
      lineHeight: 22,
    },
  });

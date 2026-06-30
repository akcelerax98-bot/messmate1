// Blocked / Rejected screen — Theme-reactive.

import { Feather } from "@expo/vector-icons";
import React, { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth/AuthContext";
import { Button } from "@/src/components/Button";
import { spacing, typography, useTheme, type ThemeColors } from "@/src/theme";

export default function Blocked() {
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const { logout } = useAuth();

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <View style={styles.wrap}>
        <View style={[styles.icon, { backgroundColor: c.badgeBlockedBg }]}>
          <Feather name="x-octagon" size={36} color={c.danger} />
        </View>
        <Text style={styles.title} testID="blocked-title">Account not approved</Text>
        <Text style={styles.body} testID="blocked-body">
          Your account is not approved. Please contact your mess admin for more details.
        </Text>

        <Button
          testID="blocked-logout"
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
  });

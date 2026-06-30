// Blocked / Rejected screen

import { Feather } from "@expo/vector-icons";
import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth/AuthContext";
import { Button } from "@/src/components/Button";
import { colors, spacing, typography } from "@/src/theme";

export default function Blocked() {
  const { logout } = useAuth();

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <View style={styles.wrap}>
        <View style={[styles.icon, { backgroundColor: colors.badgeBlockedBg }]}>
          <Feather name="x-octagon" size={36} color={colors.danger} />
        </View>
        <Text style={styles.title} testID="blocked-title">
          Account not approved
        </Text>
        <Text style={styles.body} testID="blocked-body">
          Your account is not approved. Please contact your mess admin for more
          details.
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
});

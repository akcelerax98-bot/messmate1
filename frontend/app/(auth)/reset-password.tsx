// Reset password — step 3 of 3: enter new password (uses short-lived reset token).

import { Feather } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useMemo, useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { api } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { Button } from "@/src/components/Button";
import { Input } from "@/src/components/Input";
import { spacing, typography, useTheme, type ThemeColors } from "@/src/theme";

export default function ResetPassword() {
  const router = useRouter();
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const params = useLocalSearchParams<{ reset_token?: string; email?: string }>();
  const { setSession } = useAuth();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async () => {
    setError(null);
    if (!password || password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (!params.reset_token) {
      setError("Reset session missing. Please start again.");
      return;
    }
    setLoading(true);
    try {
      const resp = await api.resetPassword({
        reset_token: String(params.reset_token),
        new_password: password,
        confirm_password: confirm,
      });
      await setSession(resp);
      // Routing effect will navigate to the appropriate home.
    } catch (e: any) {
      setError(e?.message || "Could not reset password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.container}
          keyboardShouldPersistTaps="handled"
        >
          <TouchableOpacity
            testID="reset-back"
            onPress={() => router.back()}
            style={styles.back}
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          >
            <Feather name="chevron-left" size={26} color={c.textPrimary} />
          </TouchableOpacity>

          <View style={[styles.iconBubble, { backgroundColor: c.primaryLight }]}>
            <Feather name="lock" size={22} color={c.primary} />
          </View>

          <Text style={styles.title} testID="reset-title">Set a new password</Text>
          <Text style={styles.subtitle}>
            Choose a strong password for your MessMate account.
          </Text>

          <View style={{ marginTop: spacing.xl }}>
            <Input
              testID="reset-password-input"
              label="New password"
              placeholder="At least 6 characters"
              secureTextEntry
              value={password}
              onChangeText={setPassword}
            />
            <Input
              testID="reset-confirm-input"
              label="Confirm password"
              placeholder="Re-enter your password"
              secureTextEntry
              value={confirm}
              onChangeText={setConfirm}
            />

            {error ? (
              <Text style={[styles.error, { color: c.danger }]} testID="reset-error">
                {error}
              </Text>
            ) : null}

            <Button
              testID="reset-submit"
              label="Reset password"
              onPress={onSubmit}
              loading={loading}
              style={{ marginTop: spacing.md }}
            />
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    safe: { flex: 1, backgroundColor: c.bg },
    container: { padding: spacing.lg, paddingBottom: spacing.xl },
    back: { width: 36, height: 36, justifyContent: "center", marginBottom: spacing.md },
    iconBubble: {
      width: 56,
      height: 56,
      borderRadius: 28,
      alignItems: "center",
      justifyContent: "center",
      marginBottom: spacing.md,
    },
    title: { ...typography.largeTitle, color: c.textPrimary, marginBottom: 6 },
    subtitle: { ...typography.callout, color: c.textSecondary, lineHeight: 22 },
    error: { ...typography.subhead, marginTop: 8 },
  });

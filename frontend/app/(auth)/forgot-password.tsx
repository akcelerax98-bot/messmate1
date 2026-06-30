// Forgot password — step 1 of 3: enter email.

import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";
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
import { Button } from "@/src/components/Button";
import { Input } from "@/src/components/Input";
import { spacing, typography, useTheme, type ThemeColors } from "@/src/theme";

export default function ForgotPassword() {
  const router = useRouter();
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async () => {
    setError(null);
    if (!email.trim()) {
      setError("Please enter your email.");
      return;
    }
    setLoading(true);
    try {
      await api.forgotPassword({ email: email.trim() });
      router.push({
        pathname: "/(auth)/forgot-password-otp",
        params: { email: email.trim() },
      });
    } catch (e: any) {
      setError(e?.message || "Could not start password reset");
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
            testID="forgot-back"
            onPress={() => router.back()}
            style={styles.back}
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          >
            <Feather name="chevron-left" size={26} color={c.textPrimary} />
          </TouchableOpacity>

          <View style={[styles.iconBubble, { backgroundColor: c.primaryLight }]}>
            <Feather name="key" size={22} color={c.primary} />
          </View>

          <Text style={styles.title} testID="forgot-title">Forgot password</Text>
          <Text style={styles.subtitle}>
            Enter your account email and we'll send a 6-digit code to reset your password.
          </Text>

          <View style={{ marginTop: spacing.xl }}>
            <Input
              testID="forgot-email-input"
              label="Email"
              placeholder="you@example.com"
              keyboardType="email-address"
              autoCapitalize="none"
              autoComplete="email"
              value={email}
              onChangeText={setEmail}
            />

            {error ? (
              <Text style={[styles.error, { color: c.danger }]} testID="forgot-error">
                {error}
              </Text>
            ) : null}

            <Button
              testID="forgot-submit"
              label="Send code"
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

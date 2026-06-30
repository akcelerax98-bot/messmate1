// Student login — email + password.

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

import { ApiError } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { Button } from "@/src/components/Button";
import { Input } from "@/src/components/Input";
import { spacing, typography, useTheme, type ThemeColors } from "@/src/theme";

export default function StudentLogin() {
  const router = useRouter();
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const { loginEmail } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async () => {
    setError(null);
    if (!email.trim() || !password) {
      setError("Please enter your email and password.");
      return;
    }
    setLoading(true);
    try {
      const user = await loginEmail({ email: email.trim(), password });
      if (user.role === "admin") {
        setError("This is an admin account. Please use Admin login.");
      }
    } catch (e: any) {
      if (e instanceof ApiError && e.status === 403 && e.data?.detail?.code === "email_not_verified") {
        // Send to verify screen with this email
        router.push({
          pathname: "/(auth)/verify-email",
          params: { email: email.trim(), from: "login" },
        });
        return;
      }
      setError(e?.message || "Login failed");
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
            testID="back-button"
            onPress={() => router.back()}
            style={styles.back}
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          >
            <Feather name="chevron-left" size={26} color={c.textPrimary} />
          </TouchableOpacity>

          <Text style={styles.title} testID="student-login-title">Welcome back</Text>
          <Text style={styles.subtitle}>Log in to mark your meals and share preferences.</Text>

          <View style={{ marginTop: spacing.xl }}>
            <Input
              testID="student-email-input"
              label="Email"
              placeholder="you@example.com"
              keyboardType="email-address"
              autoCapitalize="none"
              autoComplete="email"
              value={email}
              onChangeText={setEmail}
            />
            <Input
              testID="student-password-input"
              label="Password"
              placeholder="Enter your password"
              value={password}
              onChangeText={setPassword}
              secureTextEntry
            />

            <TouchableOpacity
              testID="student-forgot-link"
              onPress={() => router.push("/(auth)/forgot-password")}
              style={styles.forgot}
            >
              <Text style={[styles.forgotText, { color: c.primary }]}>Forgot password?</Text>
            </TouchableOpacity>

            {error ? (
              <Text style={styles.error} testID="student-login-error">{error}</Text>
            ) : null}

            <Button
              testID="student-login-submit"
              label="Log in"
              onPress={onSubmit}
              loading={loading}
              style={{ marginTop: spacing.md }}
            />
          </View>

          <View style={styles.footer}>
            <Text style={styles.footerText}>New to MessMate?</Text>
            <TouchableOpacity
              testID="register-link"
              onPress={() =>
                router.push({ pathname: "/(auth)/register", params: { role: "student" } })
              }
            >
              <Text style={styles.linkStrong}> Register as student</Text>
            </TouchableOpacity>
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
    title: { ...typography.largeTitle, color: c.textPrimary, marginBottom: 6 },
    subtitle: { ...typography.callout, color: c.textSecondary },
    forgot: { alignSelf: "flex-end", marginTop: 4, marginBottom: 8 },
    forgotText: { ...typography.subhead, fontWeight: "600" },
    error: {
      color: c.danger,
      ...typography.subhead,
      marginTop: 4,
      marginBottom: 4,
    },
    footer: {
      marginTop: spacing.lg,
      flexDirection: "row",
      justifyContent: "center",
    },
    footerText: { ...typography.subhead, color: c.textSecondary },
    linkStrong: { ...typography.subhead, color: c.primary, fontWeight: "600" },
  });

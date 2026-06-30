// Student login

import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useState } from "react";
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

import { useAuth } from "@/src/auth/AuthContext";
import { Button } from "@/src/components/Button";
import { Input } from "@/src/components/Input";
import { colors, spacing, typography } from "@/src/theme";

export default function StudentLogin() {
  const router = useRouter();
  const { login } = useAuth();
  const [mobile, setMobile] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async () => {
    setError(null);
    if (!mobile.trim() || !password.trim()) {
      setError("Please enter mobile number / user ID and password.");
      return;
    }
    setLoading(true);
    try {
      const user = await login({
        mobile_or_user_id: mobile.trim(),
        password,
      });
      if (user.role === "admin") {
        setError("This account is an admin account. Use Admin login.");
      }
      // routing is handled by useAuthRouting
    } catch (e: any) {
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
            <Feather name="chevron-left" size={26} color={colors.textPrimary} />
          </TouchableOpacity>

          <Text style={styles.title} testID="student-login-title">
            Welcome back
          </Text>
          <Text style={styles.subtitle}>
            Log in to mark your meals and share preferences.
          </Text>

          <View style={{ marginTop: spacing.xl }}>
            <Input
              testID="student-mobile-input"
              label="Mobile number or User ID"
              placeholder="e.g., 9876543210 or student"
              autoCapitalize="none"
              keyboardType="default"
              value={mobile}
              onChangeText={setMobile}
            />
            <Input
              testID="student-password-input"
              label="Password"
              placeholder="Enter your password"
              value={password}
              onChangeText={setPassword}
              secureTextEntry
            />

            {error ? (
              <Text style={styles.error} testID="student-login-error">
                {error}
              </Text>
            ) : null}

            <Button
              testID="student-login-submit"
              label="Log in"
              onPress={onSubmit}
              loading={loading}
              style={{ marginTop: spacing.md }}
            />

            <TouchableOpacity
              testID="forgot-password-link"
              onPress={() =>
                setError("Forgot password is not available yet. Please contact admin.")
              }
              style={styles.linkRow}
            >
              <Text style={styles.linkSubtle}>Forgot password?</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.footer}>
            <Text style={styles.footerText}>New to MessMate?</Text>
            <TouchableOpacity
              testID="register-link"
              onPress={() => router.push("/(auth)/register")}
            >
              <Text style={styles.linkStrong}> Register as student</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.demoBox} testID="student-demo-hint">
            <Text style={styles.demoTitle}>Demo accounts</Text>
            <Text style={styles.demoLine}>Approved: student / student123</Text>
            <Text style={styles.demoLine}>Pending: pending / pending123</Text>
            <Text style={styles.demoLine}>Blocked: blocked / blocked123</Text>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  container: { padding: spacing.lg, paddingBottom: spacing.xl },
  back: { width: 36, height: 36, justifyContent: "center", marginBottom: spacing.md },
  title: { ...typography.largeTitle, color: colors.textPrimary, marginBottom: 6 },
  subtitle: { ...typography.callout, color: colors.textSecondary },
  error: {
    color: colors.danger,
    ...typography.subhead,
    marginTop: 4,
    marginBottom: 4,
  },
  linkRow: { alignItems: "center", marginTop: spacing.md },
  linkSubtle: { ...typography.subhead, color: colors.textSecondary },
  linkStrong: { ...typography.subhead, color: colors.primary, fontWeight: "600" },
  footer: {
    marginTop: spacing.lg,
    flexDirection: "row",
    justifyContent: "center",
  },
  footerText: { ...typography.subhead, color: colors.textSecondary },
  demoBox: {
    marginTop: spacing.xl,
    backgroundColor: colors.primaryLight,
    borderRadius: 16,
    padding: spacing.md,
  },
  demoTitle: {
    ...typography.footnote,
    color: colors.primaryDark,
    marginBottom: 6,
    fontWeight: "700",
  },
  demoLine: { ...typography.caption, color: colors.primaryDark, marginTop: 2 },
});

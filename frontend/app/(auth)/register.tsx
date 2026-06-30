// Registration — email + password + institution. Sends OTP to email then
// navigates to verify-email.

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
import { Button } from "@/src/components/Button";
import { Input } from "@/src/components/Input";
import { spacing, typography, useTheme, type ThemeColors } from "@/src/theme";

function validEmail(s: string): boolean {
  return /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/.test(s.trim());
}

export default function Register() {
  const router = useRouter();
  const params = useLocalSearchParams<{ role?: string }>();
  const role = (params.role === "admin" ? "admin" : "student") as "student" | "admin";
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [hostel, setHostel] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async () => {
    setError(null);
    if (!fullName.trim() || !email.trim() || !hostel.trim() || !password) {
      setError("Please fill in all fields.");
      return;
    }
    if (!validEmail(email)) {
      setError("Please enter a valid email address.");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      await api.register({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        confirm_password: confirm,
        institution_or_hostel_name: hostel.trim(),
        role,
      });
      router.replace({
        pathname: "/(auth)/verify-email",
        params: { email: email.trim(), from: "register" },
      });
    } catch (e: any) {
      setError(e?.message || "Registration failed");
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

          <Text style={styles.title} testID="register-title">
            {role === "admin" ? "Create admin account" : "Create your account"}
          </Text>
          <Text style={styles.subtitle}>
            {role === "admin"
              ? "You'll get started right after verifying your email."
              : "Submit your details — the admin will approve you after email verification."}
          </Text>

          <View style={{ marginTop: spacing.xl }}>
            <Input testID="register-fullname-input" label="Full name" placeholder="e.g., Aarav Kumar" value={fullName} onChangeText={setFullName} autoCapitalize="words" />
            <Input
              testID="register-email-input"
              label="Email"
              placeholder="you@example.com"
              keyboardType="email-address"
              autoCapitalize="none"
              autoComplete="email"
              value={email}
              onChangeText={setEmail}
            />
            <Input
              testID="register-hostel-input"
              label="Institution / Hostel name"
              placeholder="e.g., Sunrise Hostel"
              value={hostel}
              onChangeText={setHostel}
              autoCapitalize="words"
            />
            <Input testID="register-password-input" label="Password" placeholder="At least 6 characters" value={password} onChangeText={setPassword} secureTextEntry />
            <Input testID="register-confirm-input" label="Confirm password" placeholder="Re-enter your password" value={confirm} onChangeText={setConfirm} secureTextEntry />

            {error ? (
              <Text style={styles.error} testID="register-error">{error}</Text>
            ) : null}

            <Button
              testID="register-submit"
              label="Create account"
              onPress={onSubmit}
              loading={loading}
              style={{ marginTop: spacing.md }}
            />

            <View style={styles.footer}>
              <Text style={styles.footerText}>Already have an account?</Text>
              <TouchableOpacity
                testID="register-back-to-login"
                onPress={() =>
                  router.replace(role === "admin" ? "/(auth)/admin-login" : "/(auth)/student-login")
                }
              >
                <Text style={styles.linkStrong}> Sign in</Text>
              </TouchableOpacity>
            </View>
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
    subtitle: { ...typography.callout, color: c.textSecondary, lineHeight: 22 },
    error: { color: c.danger, ...typography.subhead, marginTop: 4, marginBottom: 4 },
    footer: { marginTop: spacing.md, flexDirection: "row", justifyContent: "center" },
    footerText: { ...typography.subhead, color: c.textSecondary },
    linkStrong: { ...typography.subhead, color: c.primary, fontWeight: "600" },
  });

// Admin login

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

export default function AdminLogin() {
  const router = useRouter();
  const { login } = useAuth();
  const [institution, setInstitution] = useState("");
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async () => {
    setError(null);
    if (!institution.trim() || !userId.trim() || !password.trim()) {
      setError("Please fill in all fields.");
      return;
    }
    setLoading(true);
    try {
      const user = await login({
        mobile_or_user_id: userId.trim(),
        password,
        institution_or_hostel_name: institution.trim(),
      });
      if (user.role !== "admin") {
        setError(
          "This account is not an admin account. Please use Student/User login.",
        );
      }
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

          <View style={styles.iconBubble}>
            <Feather name="shield" size={22} color={colors.primary} />
          </View>

          <Text style={styles.title} testID="admin-login-title">
            Admin sign in
          </Text>
          <Text style={styles.subtitle}>
            Mess manager, warden, or whoever plans meals.
          </Text>

          <View style={{ marginTop: spacing.xl }}>
            <Input
              testID="admin-institution-input"
              label="Institution / Hostel name"
              placeholder="e.g., Demo Hostel"
              value={institution}
              onChangeText={setInstitution}
              autoCapitalize="words"
            />
            <Input
              testID="admin-userid-input"
              label="Admin User ID or Mobile"
              placeholder="e.g., admin"
              value={userId}
              onChangeText={setUserId}
              autoCapitalize="none"
            />
            <Input
              testID="admin-password-input"
              label="Password"
              placeholder="Enter your password"
              value={password}
              onChangeText={setPassword}
              secureTextEntry
            />

            {error ? (
              <Text style={styles.error} testID="admin-login-error">
                {error}
              </Text>
            ) : null}

            <Button
              testID="admin-login-submit"
              label="Log in as Admin"
              onPress={onSubmit}
              loading={loading}
              style={{ marginTop: spacing.md }}
            />

            <TouchableOpacity
              testID="admin-forgot-password-link"
              onPress={() =>
                setError("Forgot password is not available yet for admin.")
              }
              style={styles.linkRow}
            >
              <Text style={styles.linkSubtle}>Forgot password?</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.demoBox} testID="admin-demo-hint">
            <Text style={styles.demoTitle}>Demo admin</Text>
            <Text style={styles.demoLine}>Institution: Demo Hostel</Text>
            <Text style={styles.demoLine}>User ID: admin</Text>
            <Text style={styles.demoLine}>Password: admin123</Text>
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
  iconBubble: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.md,
  },
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

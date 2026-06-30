// Student login — Theme-reactive. No demo hints (production).

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

export default function StudentLogin() {
  const router = useRouter();
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const [hostel, setHostel] = useState("");
  const [mobile, setMobile] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async () => {
    setError(null);
    if (!hostel.trim() || !mobile.trim() || !password.trim()) {
      setError("Please fill in all fields.");
      return;
    }
    setLoading(true);
    try {
      const res = await api.login({
        mobile_or_user_id: mobile.trim(),
        password,
        institution_or_hostel_name: hostel.trim(),
      });
      if (res.user_preview.role === "admin") {
        setError("This account is an admin account. Use Admin login.");
        return;
      }
      router.push({
        pathname: "/(auth)/otp",
        params: {
          challenge: res.challenge,
          delivery: res.delivery,
          dev_otp: res.dev_otp || "",
          masked_mobile: res.masked_mobile,
          full_name: res.user_preview.full_name,
        },
      });
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
            <Feather name="chevron-left" size={26} color={c.textPrimary} />
          </TouchableOpacity>

          <Text style={styles.title} testID="student-login-title">Welcome back</Text>
          <Text style={styles.subtitle}>Log in to mark your meals and share preferences.</Text>

          <View style={{ marginTop: spacing.xl }}>
            <Input
              testID="student-hostel-input"
              label="Institution / Hostel name"
              placeholder="e.g., Sunrise Hostel"
              autoCapitalize="words"
              value={hostel}
              onChangeText={setHostel}
            />
            <Input
              testID="student-mobile-input"
              label="Mobile number"
              placeholder="10-digit mobile number"
              keyboardType="phone-pad"
              autoCapitalize="none"
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
              onPress={() => router.push("/(auth)/register")}
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

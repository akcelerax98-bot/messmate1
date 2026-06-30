// Admin login — Theme-reactive. No demo hints (production).

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

export default function AdminLogin() {
  const router = useRouter();
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
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
      const res = await api.login({
        mobile_or_user_id: userId.trim(),
        password,
        institution_or_hostel_name: institution.trim(),
      });
      if (res.user_preview.role !== "admin") {
        setError("This account is not an admin account. Please use Student/User login.");
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

          <View style={styles.iconBubble}>
            <Feather name="shield" size={22} color={c.primary} />
          </View>

          <Text style={styles.title} testID="admin-login-title">Admin sign in</Text>
          <Text style={styles.subtitle}>Mess manager, warden, or whoever plans meals.</Text>

          <View style={{ marginTop: spacing.xl }}>
            <Input
              testID="admin-hostel-input"
              label="Institution / Hostel name"
              placeholder="e.g., Sunrise Hostel"
              value={institution}
              onChangeText={setInstitution}
              autoCapitalize="words"
            />
            <Input
              testID="admin-userid-input"
              label="Admin Mobile or User ID"
              placeholder="e.g., 9876543210"
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
              <Text style={styles.error} testID="admin-login-error">{error}</Text>
            ) : null}

            <Button
              testID="admin-login-submit"
              label="Log in as Admin"
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
      backgroundColor: c.primaryLight,
      alignItems: "center",
      justifyContent: "center",
      marginBottom: spacing.md,
    },
    title: { ...typography.largeTitle, color: c.textPrimary, marginBottom: 6 },
    subtitle: { ...typography.callout, color: c.textSecondary },
    error: {
      color: c.danger,
      ...typography.subhead,
      marginTop: 4,
      marginBottom: 4,
    },
  });

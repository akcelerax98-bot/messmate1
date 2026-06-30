// OTP verification screen — step 2 of the login flow.

import { Feather } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth/AuthContext";
import { Button } from "@/src/components/Button";
import { Input } from "@/src/components/Input";
import { spacing, typography, useTheme } from "@/src/theme";

export default function OtpScreen() {
  const { c } = useTheme();
  const router = useRouter();
  const { login } = useAuth();
  const params = useLocalSearchParams<{
    challenge?: string;
    mock_otp?: string;
    full_name?: string;
  }>();
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onVerify = async () => {
    setError(null);
    if (!params.challenge || !otp.trim()) {
      setError("Please enter the 6-digit OTP.");
      return;
    }
    setLoading(true);
    try {
      await login({ challenge: params.challenge, otp: otp.trim() });
    } catch (e: any) {
      setError(e?.message || "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: c.bg }]} edges={["top", "bottom"]}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <View style={styles.container}>
          <TouchableOpacity
            testID="otp-back"
            onPress={() => router.back()}
            style={styles.back}
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          >
            <Feather name="chevron-left" size={26} color={c.textPrimary} />
          </TouchableOpacity>

          <View style={[styles.iconBubble, { backgroundColor: c.primaryLight }]}>
            <Feather name="shield" size={22} color={c.primary} />
          </View>

          <Text style={[styles.title, { color: c.textPrimary }]} testID="otp-title">
            Verify it's you
          </Text>
          <Text style={[styles.subtitle, { color: c.textSecondary }]}>
            We sent a 6-digit code to {params.full_name || "your phone"}.
          </Text>

          <View style={{ marginTop: spacing.xl }}>
            <Input
              testID="otp-input"
              label="6-digit OTP"
              placeholder="123456"
              keyboardType="number-pad"
              maxLength={6}
              value={otp}
              onChangeText={setOtp}
            />
            {params.mock_otp ? (
              <View style={[styles.devBox, { backgroundColor: c.primaryLight }]}>
                <Feather name="info" size={14} color={c.primaryDark} />
                <Text style={[styles.devText, { color: c.primaryDark }]}>
                  Mock OTP (dev): {params.mock_otp} — real SMS will be wired before deploy.
                </Text>
              </View>
            ) : null}
            {error ? (
              <Text style={[styles.error, { color: c.danger }]} testID="otp-error">
                {error}
              </Text>
            ) : null}
            <Button
              testID="otp-verify"
              label="Verify & sign in"
              onPress={onVerify}
              loading={loading}
              style={{ marginTop: spacing.md }}
            />
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  container: { padding: spacing.lg, flex: 1 },
  back: { width: 36, height: 36, justifyContent: "center", marginBottom: spacing.md },
  iconBubble: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.md,
  },
  title: { ...typography.largeTitle, marginBottom: 6 },
  subtitle: { ...typography.callout },
  devBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    padding: 12,
    borderRadius: 12,
    marginBottom: 8,
  },
  devText: { ...typography.caption, flex: 1, fontWeight: "600" },
  error: { ...typography.subhead, marginTop: 4, marginBottom: 4 },
});

// OTP verification screen — step 2 of the login flow. Theme-reactive.
// Supports both real MSG91 SMS delivery and "dev" delivery (auto-fills mock).

import { Feather } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useMemo, useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
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
import { radius, spacing, typography, useTheme, type ThemeColors } from "@/src/theme";

export default function OtpScreen() {
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const router = useRouter();
  const { login } = useAuth();
  const params = useLocalSearchParams<{
    challenge?: string;
    delivery?: string;
    dev_otp?: string;
    masked_mobile?: string;
    full_name?: string;
  }>();
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [devOtp, setDevOtp] = useState<string | null>(params.dev_otp || null);
  const [delivery, setDelivery] = useState<string>(params.delivery || "sms");

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

  const onResend = async () => {
    if (!params.challenge) return;
    setResending(true);
    setError(null);
    setInfo(null);
    try {
      const r = await api.resendOtp({ challenge: params.challenge });
      setDelivery(r.delivery);
      setDevOtp(r.dev_otp || null);
      setInfo(r.delivery === "sms" ? "A new OTP has been sent." : "A new OTP is shown below.");
    } catch (e: any) {
      setError(e?.message || "Could not resend");
    } finally {
      setResending(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
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

          <Text style={styles.title} testID="otp-title">Verify it's you</Text>
          <Text style={styles.subtitle}>
            {delivery === "sms"
              ? `We sent a 6-digit code to ${params.masked_mobile || "your phone"}.`
              : `Hi ${params.full_name || "there"} — enter the dev OTP below to continue.`}
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
            {devOtp ? (
              <View style={[styles.devBox, { backgroundColor: c.primaryLight }]}>
                <Feather name="info" size={14} color={c.primaryDark} />
                <Text style={[styles.devText, { color: c.primaryDark }]}>
                  Dev OTP: {devOtp} · set MSG91 keys in backend .env to enable real SMS.
                </Text>
              </View>
            ) : null}
            {info ? (
              <Text style={[styles.info, { color: c.success }]}>{info}</Text>
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
            <TouchableOpacity
              testID="otp-resend"
              onPress={onResend}
              disabled={resending}
              style={styles.resendRow}
            >
              <Text style={[styles.resendText, { color: c.primary }]}>
                {resending ? "Sending..." : "Resend OTP"}
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    safe: { flex: 1, backgroundColor: c.bg },
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
    title: { ...typography.largeTitle, color: c.textPrimary, marginBottom: 6 },
    subtitle: { ...typography.callout, color: c.textSecondary, lineHeight: 22 },
    devBox: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      padding: 12,
      borderRadius: radius.md,
      marginBottom: 8,
    },
    devText: { ...typography.caption, flex: 1, fontWeight: "600" },
    info: { ...typography.subhead, marginTop: 4, marginBottom: 4 },
    error: { ...typography.subhead, marginTop: 4, marginBottom: 4 },
    resendRow: { alignItems: "center", marginTop: spacing.md },
    resendText: { ...typography.subhead, fontWeight: "700" },
  });

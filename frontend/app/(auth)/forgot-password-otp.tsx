// Forgot password — step 2 of 3: enter OTP. On success → reset password screen.

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
import { Button } from "@/src/components/Button";
import { OtpInput } from "@/src/components/OtpInput";
import { useCountdown } from "@/src/hooks/useCountdown";
import { spacing, typography, useTheme, type ThemeColors } from "@/src/theme";

export default function ForgotPasswordOtp() {
  const router = useRouter();
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const params = useLocalSearchParams<{ email?: string }>();
  const email = (params.email || "").trim();

  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { seconds: cooldown, reset: resetCooldown } = useCountdown(60);

  const verify = async (code?: string) => {
    setError(null);
    const otpToUse = (code ?? otp).trim();
    if (otpToUse.length < 6) return;
    setLoading(true);
    try {
      const r = await api.forgotPasswordVerify({ email, otp: otpToUse });
      router.replace({
        pathname: "/(auth)/reset-password",
        params: { reset_token: r.reset_token, email },
      });
    } catch (e: any) {
      setError(e?.message || "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  const resend = async () => {
    if (cooldown > 0) return;
    setError(null);
    setInfo(null);
    setResending(true);
    try {
      const r = await api.resendOtp({ email, purpose: "forgot_password" });
      resetCooldown(r.resend_available_in || 60);
      setInfo("A new code has been sent to your email.");
      setOtp("");
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
            testID="fp-otp-back"
            onPress={() => router.back()}
            style={styles.back}
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          >
            <Feather name="chevron-left" size={26} color={c.textPrimary} />
          </TouchableOpacity>

          <View style={[styles.iconBubble, { backgroundColor: c.primaryLight }]}>
            <Feather name="shield" size={22} color={c.primary} />
          </View>

          <Text style={styles.title} testID="fp-otp-title">Verify it's you</Text>
          <Text style={styles.subtitle}>
            Enter the 6-digit code we sent to{" "}
            <Text style={[styles.subtitle, { color: c.textPrimary, fontWeight: "600" }]}>{email}</Text>.
          </Text>

          <View style={{ marginTop: spacing.xl }}>
            <OtpInput
              testID="fp-otp-input"
              value={otp}
              onChange={setOtp}
              onComplete={(v) => verify(v)}
              disabled={loading}
            />
            {info ? <Text style={[styles.info, { color: c.success }]}>{info}</Text> : null}
            {error ? (
              <Text style={[styles.error, { color: c.danger }]} testID="fp-otp-error">
                {error}
              </Text>
            ) : null}
            <Button
              testID="fp-otp-submit"
              label="Verify"
              onPress={() => verify()}
              loading={loading}
              disabled={otp.length < 6}
              style={{ marginTop: spacing.md }}
            />
            <View style={styles.resendRow}>
              <Text style={[styles.subtitle, { color: c.textSecondary }]}>Didn't get the code?</Text>
              <TouchableOpacity
                testID="fp-otp-resend"
                onPress={resend}
                disabled={cooldown > 0 || resending}
              >
                <Text
                  style={[
                    styles.resendText,
                    { color: cooldown > 0 ? c.textTertiary : c.primary },
                  ]}
                >
                  {" "}
                  {resending
                    ? "Sending…"
                    : cooldown > 0
                      ? `Resend in ${cooldown}s`
                      : "Resend code"}
                </Text>
              </TouchableOpacity>
            </View>
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
    info: { ...typography.subhead, marginTop: 12 },
    error: { ...typography.subhead, marginTop: 12 },
    resendRow: { flexDirection: "row", justifyContent: "center", marginTop: spacing.lg },
    resendText: { ...typography.subhead, fontWeight: "700" },
  });

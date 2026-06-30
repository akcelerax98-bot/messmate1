// Student registration — Theme-reactive.

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

import { useAuth } from "@/src/auth/AuthContext";
import { Button } from "@/src/components/Button";
import { Input } from "@/src/components/Input";
import { radius, spacing, typography, useTheme, type ThemeColors } from "@/src/theme";

export default function Register() {
  const router = useRouter();
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const { registerStudent } = useAuth();

  const [fullName, setFullName] = useState("");
  const [mobile, setMobile] = useState("");
  const [hostel, setHostel] = useState("");
  const [room, setRoom] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const onSubmit = async () => {
    setError(null);
    if (!fullName.trim() || !mobile.trim() || !hostel.trim() || !room.trim() || !password) {
      setError("Please fill in all fields.");
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
      await registerStudent({
        full_name: fullName.trim(),
        mobile_or_user_id: mobile.trim(),
        institution_or_hostel_name: hostel.trim(),
        room_number: room.trim(),
        password,
      });
      setSuccess(true);
    } catch (e: any) {
      setError(e?.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
        <View style={styles.centerWrap}>
          <View style={[styles.statusIcon, { backgroundColor: c.primaryLight }]}>
            <Feather name="check" size={32} color={c.primary} />
          </View>
          <Text style={styles.statusTitle} testID="register-success-title">
            Registration submitted
          </Text>
          <Text style={styles.statusBody}>
            Your account is waiting for admin approval. You'll be able to log in once approved.
          </Text>
          <Button
            testID="register-back-to-login"
            label="Back to login"
            onPress={() => router.replace("/(auth)/student-login")}
            style={{ marginTop: spacing.xl, alignSelf: "stretch" }}
          />
        </View>
      </SafeAreaView>
    );
  }

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

          <Text style={styles.title} testID="register-title">Create your account</Text>
          <Text style={styles.subtitle}>
            Submit your details — the admin will approve you.
          </Text>

          <View style={{ marginTop: spacing.xl }}>
            <Input testID="register-fullname-input" label="Full name" placeholder="e.g., Aarav Kumar" value={fullName} onChangeText={setFullName} autoCapitalize="words" />
            <Input testID="register-mobile-input" label="Mobile number" placeholder="10-digit mobile number" value={mobile} onChangeText={setMobile} keyboardType="phone-pad" autoCapitalize="none" />
            <Input testID="register-hostel-input" label="Institution / Hostel name" placeholder="e.g., Sunrise Hostel" value={hostel} onChangeText={setHostel} autoCapitalize="words" />
            <Input testID="register-room-input" label="Room number or User ID" placeholder="e.g., A101" value={room} onChangeText={setRoom} autoCapitalize="characters" />
            <Input testID="register-password-input" label="Password" placeholder="At least 6 characters" value={password} onChangeText={setPassword} secureTextEntry />
            <Input testID="register-confirm-input" label="Confirm password" placeholder="Re-enter your password" value={confirm} onChangeText={setConfirm} secureTextEntry />

            <View style={styles.otpBox} testID="otp-placeholder">
              <Feather name="info" size={16} color={c.textSecondary} />
              <Text style={styles.otpText}>
                You'll verify via SMS OTP at first login.
              </Text>
            </View>

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
    otpBox: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      backgroundColor: c.inputBg,
      borderRadius: radius.md,
      padding: 12,
      marginBottom: 10,
    },
    otpText: { ...typography.caption, color: c.textSecondary, flex: 1 },
    error: {
      color: c.danger,
      ...typography.subhead,
      marginTop: 4,
      marginBottom: 4,
    },
    centerWrap: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: spacing.lg,
    },
    statusIcon: {
      width: 72,
      height: 72,
      borderRadius: 36,
      alignItems: "center",
      justifyContent: "center",
      marginBottom: spacing.lg,
    },
    statusTitle: {
      ...typography.title1,
      color: c.textPrimary,
      marginBottom: 10,
      textAlign: "center",
    },
    statusBody: {
      ...typography.callout,
      color: c.textSecondary,
      textAlign: "center",
      lineHeight: 22,
    },
  });

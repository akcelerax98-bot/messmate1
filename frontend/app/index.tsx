// Welcome / Role selection — MessMate. Theme-reactive.

import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Animated, { FadeInDown, FadeInUp } from "react-native-reanimated";

import { radius, shadow, spacing, typography, useTheme, type ThemeColors } from "@/src/theme";

export default function Welcome() {
  const router = useRouter();
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <View style={styles.container}>
        <Animated.View entering={FadeInUp.duration(450)} style={styles.heroWrap}>
          <View style={styles.logoCircle} testID="messmate-logo">
            <Feather name="award" size={42} color={c.primary} />
          </View>
          <Text style={styles.brand} testID="welcome-title">MessMate</Text>
          <Text style={styles.subtitle} testID="welcome-subtitle">
            Reduce food waste. Plan meals smarter. Improve mess transparency.
          </Text>
        </Animated.View>

        <Animated.View entering={FadeInDown.duration(500).delay(120)} style={styles.cards}>
          <Pressable
            testID="role-student-card"
            android_ripple={{ color: c.primaryTint }}
            style={({ pressed }) => [
              styles.card,
              pressed && { transform: [{ scale: 0.985 }] },
            ]}
            onPress={() => router.push("/(auth)/student-login")}
          >
            <View style={[styles.iconBubble, { backgroundColor: c.primary }]}>
              <Feather name="user" size={24} color="#fff" />
            </View>
            <View style={styles.cardText}>
              <Text style={styles.cardTitle}>I am a Student</Text>
              <Text style={styles.cardSub}>
                Mark your meals, share preferences, see wastage
              </Text>
            </View>
            <Feather name="chevron-right" size={22} color={c.textSecondary} />
          </Pressable>

          <Pressable
            testID="role-admin-card"
            android_ripple={{ color: c.primaryTint }}
            style={({ pressed }) => [
              styles.card,
              pressed && { transform: [{ scale: 0.985 }] },
            ]}
            onPress={() => router.push("/(auth)/admin-login")}
          >
            <View style={[styles.iconBubble, { backgroundColor: c.primaryDark }]}>
              <Feather name="shield" size={24} color="#fff" />
            </View>
            <View style={styles.cardText}>
              <Text style={styles.cardTitle}>I am an Admin</Text>
              <Text style={styles.cardSub}>
                Plan cook quantity, track wastage, manage students
              </Text>
            </View>
            <Feather name="chevron-right" size={22} color={c.textSecondary} />
          </Pressable>
        </Animated.View>

        <Text style={styles.footer} testID="welcome-footer">
          Built for hostels, PGs, canteens & institutional dining.
        </Text>
      </View>
    </SafeAreaView>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    safe: { flex: 1, backgroundColor: c.bg },
    container: {
      flex: 1,
      paddingHorizontal: spacing.lg,
      paddingTop: spacing.xl,
      paddingBottom: spacing.lg,
      justifyContent: "space-between",
    },
    heroWrap: { alignItems: "center", marginTop: spacing.xxl },
    logoCircle: {
      width: 84,
      height: 84,
      borderRadius: 42,
      backgroundColor: c.primaryLight,
      alignItems: "center",
      justifyContent: "center",
      marginBottom: spacing.lg,
    },
    brand: { ...typography.largeTitle, color: c.textPrimary, marginBottom: 8 },
    subtitle: {
      ...typography.callout,
      color: c.textSecondary,
      textAlign: "center",
      paddingHorizontal: spacing.md,
      lineHeight: 22,
    },
    cards: { gap: spacing.md },
    card: {
      flexDirection: "row",
      alignItems: "center",
      backgroundColor: c.card,
      borderRadius: radius.xl,
      padding: spacing.md + 4,
      borderWidth: 1,
      borderColor: c.border,
      ...shadow.card,
    },
    iconBubble: {
      width: 48,
      height: 48,
      borderRadius: 24,
      alignItems: "center",
      justifyContent: "center",
      marginRight: spacing.md,
    },
    cardText: { flex: 1 },
    cardTitle: { ...typography.headline, color: c.textPrimary, marginBottom: 2 },
    cardSub: { ...typography.subhead, color: c.textSecondary },
    footer: {
      textAlign: "center",
      color: c.textTertiary,
      ...typography.caption,
    },
  });

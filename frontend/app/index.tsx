// Welcome / Role selection — MessMate

import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { colors, radius, shadow, spacing, typography } from "@/src/theme";

export default function Welcome() {
  const router = useRouter();

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <View style={styles.container}>
        {/* Hero */}
        <View style={styles.heroWrap}>
          <View style={styles.logoCircle} testID="messmate-logo">
            <Feather name="award" size={42} color={colors.primary} />
          </View>
          <Text style={styles.brand} testID="welcome-title">
            MessMate
          </Text>
          <Text style={styles.subtitle} testID="welcome-subtitle">
            Reduce food waste. Plan meals smarter. Improve mess transparency.
          </Text>
        </View>

        {/* Role cards */}
        <View style={styles.cards}>
          <TouchableOpacity
            testID="role-student-card"
            activeOpacity={0.85}
            style={[styles.card, styles.cardStudent]}
            onPress={() => router.push("/(auth)/student-login")}
          >
            <View style={[styles.iconBubble, { backgroundColor: colors.primary }]}>
              <Feather name="user" size={24} color="#fff" />
            </View>
            <View style={styles.cardText}>
              <Text style={styles.cardTitle}>I am a Student</Text>
              <Text style={styles.cardSub}>
                Mark your meals, share preferences, see wastage
              </Text>
            </View>
            <Feather name="chevron-right" size={22} color={colors.textSecondary} />
          </TouchableOpacity>

          <TouchableOpacity
            testID="role-admin-card"
            activeOpacity={0.85}
            style={[styles.card, styles.cardAdmin]}
            onPress={() => router.push("/(auth)/admin-login")}
          >
            <View style={[styles.iconBubble, { backgroundColor: colors.primaryDark }]}>
              <Feather name="shield" size={24} color="#fff" />
            </View>
            <View style={styles.cardText}>
              <Text style={styles.cardTitle}>I am an Admin</Text>
              <Text style={styles.cardSub}>
                Plan cook quantity, track wastage, manage students
              </Text>
            </View>
            <Feather name="chevron-right" size={22} color={colors.textSecondary} />
          </TouchableOpacity>
        </View>

        <Text style={styles.footer} testID="welcome-footer">
          Built for hostels, PGs, canteens & institutional dining.
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
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
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.lg,
  },
  brand: { ...typography.largeTitle, color: colors.textPrimary, marginBottom: 8 },
  subtitle: {
    ...typography.callout,
    color: colors.textSecondary,
    textAlign: "center",
    paddingHorizontal: spacing.md,
    lineHeight: 22,
  },
  cards: { gap: spacing.md },
  card: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.card,
    borderRadius: radius.xl,
    padding: spacing.md + 4,
    ...shadow.card,
  },
  cardStudent: {},
  cardAdmin: {},
  iconBubble: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  cardText: { flex: 1 },
  cardTitle: { ...typography.headline, color: colors.textPrimary, marginBottom: 2 },
  cardSub: { ...typography.subhead, color: colors.textSecondary },
  footer: {
    textAlign: "center",
    color: colors.textTertiary,
    ...typography.caption,
  },
});

// Student Menu — Weekly & Monthly menu with Like/Dislike reactions per meal.

import { Feather } from "@expo/vector-icons";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  api,
  type MealType,
  type Reaction,
  type WeeklyDay,
} from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { Segmented } from "@/src/components/Segmented";
import { Toast } from "@/src/components/Toast";
import { colors, radius, shadow, spacing, typography } from "@/src/theme";

type ViewMode = "weekly" | "monthly";

const MEAL_ICON: Record<MealType, keyof typeof Feather.glyphMap> = {
  breakfast: "coffee",
  lunch: "sun",
  dinner: "moon",
};

function cap(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export default function StudentMenu() {
  const { token } = useAuth();
  const [mode, setMode] = useState<ViewMode>("weekly");
  const [weekDays, setWeekDays] = useState<WeeklyDay[]>([]);
  const [monthWeeks, setMonthWeeks] = useState<{ label: string; days: WeeklyDay[] }[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState<{
    message: string;
    variant: "success" | "error" | "info";
  } | null>(null);
  // Optimistic UI cache keyed by `${day}:${meal}` -> Reaction
  const [overrides, setOverrides] = useState<Record<string, Reaction>>({});

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [w, m] = await Promise.all([api.menuWeek(token), api.menuMonth(token)]);
      setWeekDays(w.days);
      setMonthWeeks(m.weeks);
    } catch (e: any) {
      setToast({ message: e?.message || "Failed to load menu", variant: "error" });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const handleReact = async (day: string, meal: MealType, current: Reaction, next: Reaction) => {
    if (!token) return;
    const key = `${day}:${meal}`;
    const optimistic = current === next ? "no_response" : next;
    setOverrides((p) => ({ ...p, [key]: optimistic }));
    try {
      await api.setReaction(token, { day, meal_type: meal, reaction: optimistic });
    } catch (e: any) {
      // revert
      setOverrides((p) => ({ ...p, [key]: current }));
      setToast({ message: e?.message || "Could not save reaction", variant: "error" });
    }
  };

  const getReaction = (day: WeeklyDay, meal: MealType): Reaction => {
    const k = `${day.day}:${meal}`;
    return overrides[k] ?? day.reactions[meal];
  };

  const renderDay = (day: WeeklyDay, keyPrefix = "") => (
    <View key={`${keyPrefix}${day.day}`} style={styles.dayCard} testID={`day-${keyPrefix}${day.day}`}>
      <Text style={styles.dayTitle}>{cap(day.day)}</Text>

      {(["breakfast", "lunch", "dinner"] as MealType[]).map((m) => {
        const items =
          m === "breakfast"
            ? day.breakfast_items
            : m === "lunch"
              ? day.lunch_items
              : day.dinner_items;
        const reaction = getReaction(day, m);
        return (
          <View key={m} style={styles.mealRow}>
            <View style={styles.mealHead}>
              <View style={styles.mealHeadLeft}>
                <View style={styles.mealIconBubble}>
                  <Feather name={MEAL_ICON[m]} size={14} color={colors.primary} />
                </View>
                <Text style={styles.mealTitle}>{cap(m)}</Text>
              </View>
              <View style={styles.reactionRow}>
                <TouchableOpacity
                  testID={`${keyPrefix}${day.day}-${m}-like`}
                  activeOpacity={0.8}
                  onPress={() => handleReact(day.day, m, reaction, "like")}
                  style={[
                    styles.reactBtn,
                    reaction === "like" && {
                      backgroundColor: colors.primary,
                      borderColor: colors.primary,
                    },
                  ]}
                >
                  <Feather
                    name="thumbs-up"
                    size={14}
                    color={reaction === "like" ? "#fff" : colors.textSecondary}
                  />
                </TouchableOpacity>
                <TouchableOpacity
                  testID={`${keyPrefix}${day.day}-${m}-dislike`}
                  activeOpacity={0.8}
                  onPress={() => handleReact(day.day, m, reaction, "dislike")}
                  style={[
                    styles.reactBtn,
                    reaction === "dislike" && {
                      backgroundColor: colors.danger,
                      borderColor: colors.danger,
                    },
                  ]}
                >
                  <Feather
                    name="thumbs-down"
                    size={14}
                    color={reaction === "dislike" ? "#fff" : colors.textSecondary}
                  />
                </TouchableOpacity>
              </View>
            </View>
            <Text style={styles.mealItems}>
              {items.length ? items.join(", ") : "—"}
            </Text>
          </View>
        );
      })}
    </View>
  );

  const content = useMemo(() => {
    if (mode === "weekly") {
      if (weekDays.length === 0)
        return <Text style={styles.empty}>Menu not added yet.</Text>;
      return weekDays.map((d) => renderDay(d));
    }
    if (monthWeeks.length === 0)
      return <Text style={styles.empty}>Menu not added yet.</Text>;
    return monthWeeks.map((wk) => (
      <View key={wk.label} style={{ marginBottom: spacing.md }}>
        <Text style={styles.weekLabel}>{wk.label}</Text>
        {wk.days.map((d) => renderDay(d, `${wk.label.toLowerCase().replace(/\s+/g, "-")}-`))}
      </View>
    ));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, weekDays, monthWeeks, overrides]);

  if (loading) {
    return (
      <SafeAreaView style={styles.safe} edges={["top"]}>
        <View style={styles.loadingWrap}>
          <ActivityIndicator color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <Toast
        testID="menu-toast"
        message={toast?.message ?? null}
        variant={toast?.variant ?? "success"}
        onHide={() => setToast(null)}
      />
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              load();
            }}
            tintColor={colors.primary}
          />
        }
      >
        <View style={styles.header}>
          <Text style={styles.eyebrow}>MENU</Text>
          <Text style={styles.title}>This Week & Month</Text>
          <Text style={styles.subtitle}>
            Like or dislike each meal — anonymous, sent to admin as % only.
          </Text>
        </View>

        <Segmented<ViewMode>
          testID="menu-mode"
          value={mode}
          onChange={setMode}
          options={[
            { value: "weekly", label: "Weekly", testID: "menu-mode-weekly" },
            { value: "monthly", label: "Monthly", testID: "menu-mode-monthly" },
          ]}
          style={{ marginBottom: spacing.lg }}
        />

        {content}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  loadingWrap: { flex: 1, alignItems: "center", justifyContent: "center" },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl + 24 },
  header: { marginBottom: spacing.md },
  eyebrow: {
    ...typography.caption,
    color: colors.primary,
    letterSpacing: 1.5,
    fontWeight: "700",
    marginBottom: 6,
  },
  title: { ...typography.title1, color: colors.textPrimary },
  subtitle: { ...typography.subhead, color: colors.textSecondary, marginTop: 4 },

  weekLabel: {
    ...typography.footnote,
    color: colors.primary,
    letterSpacing: 1,
    fontWeight: "700",
    marginBottom: 8,
    marginTop: 4,
  },

  dayCard: {
    backgroundColor: colors.card,
    borderRadius: radius.xl,
    padding: spacing.md + 2,
    marginBottom: spacing.sm + 4,
    ...shadow.card,
  },
  dayTitle: {
    ...typography.title2,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  mealRow: { paddingVertical: 8 },
  mealHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 4,
  },
  mealHeadLeft: { flexDirection: "row", alignItems: "center", gap: 8 },
  mealIconBubble: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  mealTitle: { ...typography.headline, color: colors.textPrimary },
  mealItems: { ...typography.subhead, color: colors.textSecondary, marginLeft: 32 },
  reactionRow: { flexDirection: "row", gap: 8 },
  reactBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.card,
  },
  empty: { ...typography.subhead, color: colors.textSecondary, textAlign: "center" },
});

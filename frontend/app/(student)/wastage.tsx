// Student Wastage — read-only transparency view.
// Summary cards (today / yesterday / last week same day) + bar chart with filters.

import { Feather } from "@expo/vector-icons";
import React, { useMemo, useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { api, type WastageResponse } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { BarChart } from "@/src/components/BarChart";
import { Segmented } from "@/src/components/Segmented";
import { Toast } from "@/src/components/Toast";
import { radius, shadow, spacing, typography, useTheme, type ThemeColors } from "@/src/theme";

type Range = "7" | "30" | "90";
type MealFilter = "all" | "breakfast" | "lunch" | "dinner";

function fmt(v: number | null | undefined, suffix = "kg"): string {
  if (v === null || v === undefined) return "—";
  return `${v.toFixed(1)} ${suffix}`;
}

export default function StudentWastage() {
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const { token } = useAuth();
  const [range, setRange] = useState<Range>("7");
  const [meal, setMeal] = useState<MealFilter>("all");
  const [data, setData] = useState<WastageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const res = await api.wastage(token, Number(range) as 7 | 30 | 90, meal);
      setData(res);
    } catch (e: any) {
      setToast(e?.message || "Failed to load wastage");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token, range, meal]);

  useEffect(() => {
    load();
  }, [load]);

  const summary = data?.summary;
  const series = data?.series ?? [];

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <Toast
        testID="wastage-toast"
        message={toast}
        variant="error"
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
          <Text style={styles.eyebrow}>WASTAGE</Text>
          <Text style={styles.title}>Mess wastage transparency</Text>
          <Text style={styles.subtitle}>
            Your meal responses help reduce this wastage.
          </Text>
        </View>

        {loading ? (
          <View style={styles.loadingWrap}>
            <ActivityIndicator color={colors.primary} />
          </View>
        ) : (
          <>
            {/* Today */}
            <View style={[styles.card]} testID="wastage-today-card">
              <Text style={styles.cardLabel}>Today's wastage</Text>
              <Text style={styles.bigNumber} testID="wastage-today-total">
                {fmt(summary?.today?.total)}
              </Text>
              <View style={styles.divider} />
              <View style={styles.row3}>
                <View style={styles.tinyStat}>
                  <Feather name="coffee" size={14} color={colors.primary} />
                  <Text style={styles.tinyLabel}>Breakfast</Text>
                  <Text style={styles.tinyValue} testID="wastage-today-breakfast">
                    {fmt(summary?.today?.breakfast)}
                  </Text>
                </View>
                <View style={styles.tinyStat}>
                  <Feather name="sun" size={14} color={colors.primary} />
                  <Text style={styles.tinyLabel}>Lunch</Text>
                  <Text style={styles.tinyValue} testID="wastage-today-lunch">
                    {fmt(summary?.today?.lunch)}
                  </Text>
                </View>
                <View style={styles.tinyStat}>
                  <Feather name="moon" size={14} color={colors.primary} />
                  <Text style={styles.tinyLabel}>Dinner</Text>
                  <Text style={styles.tinyValue} testID="wastage-today-dinner">
                    {fmt(summary?.today?.dinner)}
                  </Text>
                </View>
              </View>
            </View>

            {/* Comparisons */}
            <View style={styles.row2}>
              <View style={[styles.card, styles.compareCard]} testID="wastage-yesterday-card">
                <Text style={styles.cardLabel}>Yesterday</Text>
                <Text style={styles.midNumber} testID="wastage-yesterday-total">
                  {fmt(summary?.yesterday_total)}
                </Text>
              </View>
              <View style={[styles.card, styles.compareCard]} testID="wastage-lastweek-card">
                <Text style={styles.cardLabel}>Last week, same day</Text>
                <Text style={styles.midNumber} testID="wastage-lastweek-total">
                  {fmt(summary?.last_week_same_day_total)}
                </Text>
              </View>
            </View>

            {/* Chart */}
            <View style={styles.card} testID="wastage-chart-card">
              <Text style={styles.cardTitle}>Trend</Text>

              <Text style={styles.filterLabel}>Range</Text>
              <Segmented<Range>
                testID="wastage-range"
                value={range}
                onChange={setRange}
                options={[
                  { value: "7", label: "7 days", testID: "wastage-range-7" },
                  { value: "30", label: "30 days", testID: "wastage-range-30" },
                  { value: "90", label: "90 days", testID: "wastage-range-90" },
                ]}
                style={{ marginBottom: spacing.md }}
              />

              <Text style={styles.filterLabel}>Meal</Text>
              <Segmented<MealFilter>
                testID="wastage-meal"
                value={meal}
                onChange={setMeal}
                options={[
                  { value: "all", label: "All", testID: "wastage-meal-all" },
                  { value: "breakfast", label: "B'fast", testID: "wastage-meal-breakfast" },
                  { value: "lunch", label: "Lunch", testID: "wastage-meal-lunch" },
                  { value: "dinner", label: "Dinner", testID: "wastage-meal-dinner" },
                ]}
                style={{ marginBottom: spacing.md }}
              />

              {series.length === 0 ? (
                <Text style={styles.empty}>
                  Wastage data will appear here after admin updates it.
                </Text>
              ) : (
                <BarChart data={series} height={180} testID="wastage-bar-chart" />
              )}
            </View>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const makeStyles = (c: ThemeColors) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: c.bg },
  loadingWrap: { paddingVertical: 60, alignItems: "center" },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl + 24 },
  header: { marginBottom: spacing.lg },
  eyebrow: {
    ...typography.caption,
    color: c.primary,
    letterSpacing: 1.5,
    fontWeight: "700",
    marginBottom: 6,
  },
  title: { ...typography.title1, color: c.textPrimary },
  subtitle: { ...typography.subhead, color: c.textSecondary, marginTop: 4 },

  card: {
    backgroundColor: c.card,
    borderRadius: radius.xl,
    padding: spacing.md + 4,
    marginBottom: spacing.md,
    ...shadow.card,
  },
  cardLabel: {
    ...typography.footnote,
    color: c.textSecondary,
    marginBottom: 6,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  cardTitle: { ...typography.title2, color: c.textPrimary, marginBottom: spacing.md },
  bigNumber: {
    ...typography.largeTitle,
    color: c.textPrimary,
    fontSize: 40,
    lineHeight: 44,
  },
  midNumber: { ...typography.title1, color: c.textPrimary, fontSize: 24 },
  divider: {
    height: 1,
    backgroundColor: c.border,
    marginVertical: spacing.md,
  },
  row3: { flexDirection: "row", justifyContent: "space-between" },
  tinyStat: { flex: 1, gap: 4 },
  tinyLabel: { ...typography.caption, color: c.textSecondary },
  tinyValue: { ...typography.headline, color: c.textPrimary },

  row2: { flexDirection: "row", gap: spacing.md, marginBottom: 0 },
  compareCard: { flex: 1, marginBottom: spacing.md },

  filterLabel: {
    ...typography.caption,
    color: c.textSecondary,
    marginBottom: 6,
    marginTop: 2,
  },
  empty: {
    ...typography.subhead,
    color: c.textSecondary,
    textAlign: "center",
    paddingVertical: spacing.lg,
  },
});

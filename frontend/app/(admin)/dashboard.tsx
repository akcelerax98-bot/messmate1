// Admin Tab 2 — Dashboard. Suggested cook quantity per meal item with a
// Today/Tomorrow toggle.

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

import { api, type DashboardMeal, type DashboardResponse, type MealType } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { StatTile } from "@/src/components/StatTile";
import { Toast } from "@/src/components/Toast";
import { radius, shadow, spacing, typography, useTheme, type ThemeColors } from "@/src/theme";

type ForDay = "today" | "tomorrow";

const ICON: Record<MealType, keyof typeof Feather.glyphMap> = {
  breakfast: "coffee",
  lunch: "sun",
  dinner: "moon",
};

function cap(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function MealBlock({
  meal,
  data,
  styles,
  c,
}: {
  meal: MealType;
  data: DashboardMeal;
  styles: ReturnType<typeof makeStyles>;
  c: ThemeColors;
}) {
  return (
    <View style={styles.card} testID={`dash-${meal}`}>
      <View style={styles.titleRow}>
        <View style={styles.iconBubble}>
          <Feather name={ICON[meal]} size={18} color={c.primary} />
        </View>
        <Text style={styles.cardTitle}>{cap(meal)}</Text>
        <View style={{ flex: 1 }} />
        <Text style={styles.eatPill}>{data.eating_count} eating</Text>
      </View>

      {data.warnings.length > 0 ? (
        <View style={styles.warnBox}>
          {data.warnings.map((w, i) => (
            <View key={i} style={styles.warnRow}>
              <Feather name="alert-circle" size={14} color={c.warning} />
              <Text style={styles.warnText}>{w}</Text>
            </View>
          ))}
        </View>
      ) : null}

      {data.items.length === 0 ? (
        <Text style={styles.muted}>No item demand yet.</Text>
      ) : (
        data.items.map((row) => (
          <View
            key={row.item_name}
            style={styles.itemRow}
            testID={`dash-${meal}-item-${row.item_name.toLowerCase().replace(/\s+/g, "-")}`}
          >
            <View style={{ flex: 1 }}>
              <Text style={styles.itemName}>{row.item_name}</Text>
              <Text style={styles.itemSub}>
                {row.preference_count} pref ·{" "}
                {row.quantity_per_person !== null
                  ? `${row.quantity_per_person} ${row.unit}/person`
                  : "qty/person not set"}
              </Text>
            </View>
            <View style={styles.itemSuggestBox}>
              {row.display ? (
                <>
                  <Text style={styles.itemSuggestNum}>{row.display.value}</Text>
                  <Text style={styles.itemSuggestUnit}>{row.display.unit}</Text>
                </>
              ) : (
                <Text style={styles.itemMissing}>missing info</Text>
              )}
            </View>
          </View>
        ))
      )}
    </View>
  );
}

function DayToggle({
  value,
  onChange,
  c,
  styles,
}: {
  value: ForDay;
  onChange: (v: ForDay) => void;
  c: ThemeColors;
  styles: ReturnType<typeof makeStyles>;
}) {
  return (
    <View style={styles.toggleWrap} testID="dash-day-toggle">
      {(["today", "tomorrow"] as ForDay[]).map((opt) => {
        const active = value === opt;
        return (
          <TouchableOpacity
            key={opt}
            testID={`dash-day-${opt}`}
            activeOpacity={0.85}
            onPress={() => onChange(opt)}
            style={[styles.toggleBtn, active && { backgroundColor: c.card }]}
          >
            <Feather
              name={opt === "today" ? "sun" : "sunrise"}
              size={14}
              color={active ? c.primary : c.textSecondary}
            />
            <Text
              style={[
                styles.toggleLabel,
                { color: active ? c.textPrimary : c.textSecondary },
              ]}
            >
              {opt === "today" ? "Today" : "Tomorrow"}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

export default function AdminDashboard() {
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const { token } = useAuth();
  const [forDay, setForDay] = useState<ForDay>("today");
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(
    async (which: ForDay) => {
      if (!token) return;
      try {
        const res = await api.adminDashboard(token, which);
        setData(res);
      } catch (e: any) {
        setToast(e?.message || "Failed to load dashboard");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [token],
  );

  useEffect(() => {
    setLoading(true);
    load(forDay);
  }, [forDay, load]);

  const dateLabel = useMemo(() => {
    if (!data?.date) return "";
    try {
      const d = new Date(data.date + "T00:00:00");
      return d.toLocaleDateString(undefined, {
        weekday: "long",
        day: "numeric",
        month: "short",
      });
    } catch {
      return data.date;
    }
  }, [data?.date]);

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <Toast
        testID="dash-toast"
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
              load(forDay);
            }}
            tintColor={c.primary}
          />
        }
      >
        <View style={styles.header}>
          <Text style={styles.eyebrow}>ADMIN</Text>
          <Text style={styles.title}>
            {forDay === "today" ? "Today's cooking plan" : "Tomorrow's cooking plan"}
          </Text>
          <Text style={styles.subtitle}>
            {forDay === "today"
              ? `Suggested quantity per item = student preference × qty/person · ${dateLabel}`
              : `Quantities based on early submissions for ${dateLabel}. Will keep updating as students respond.`}
          </Text>
        </View>

        <DayToggle value={forDay} onChange={setForDay} c={c} styles={styles} />

        {loading ? (
          <View style={[styles.center, { paddingVertical: 64 }]}>
            <ActivityIndicator color={c.primary} />
          </View>
        ) : (
          <>
            <View style={styles.tilesGrid}>
              <StatTile
                testID="dash-tile-breakfast"
                icon="coffee"
                label="Eating breakfast"
                value={data?.summary.breakfast_eating ?? 0}
              />
              <StatTile
                testID="dash-tile-lunch"
                icon="sun"
                label="Eating lunch"
                value={data?.summary.lunch_eating ?? 0}
              />
              <StatTile
                testID="dash-tile-dinner"
                icon="moon"
                label="Eating dinner"
                value={data?.summary.dinner_eating ?? 0}
              />
              <StatTile
                testID="dash-tile-responses"
                icon="check-square"
                label="Total responses"
                value={data?.summary.total_responses ?? 0}
              />
            </View>

            {data?.summary.most_demanded || data?.summary.least_demanded ? (
              <View style={[styles.card, styles.highlightCard]}>
                {data?.summary.most_demanded ? (
                  <View style={styles.highlightRow}>
                    <Feather name="trending-up" size={16} color={c.primary} />
                    <Text style={styles.highlightText}>
                      Most demanded:{" "}
                      <Text style={styles.bold}>{data.summary.most_demanded.item}</Text>{" "}
                      ({data.summary.most_demanded.count})
                    </Text>
                  </View>
                ) : null}
                {data?.summary.least_demanded ? (
                  <View style={styles.highlightRow}>
                    <Feather name="trending-down" size={16} color={c.warning} />
                    <Text style={styles.highlightText}>
                      Lowest demanded:{" "}
                      <Text style={styles.bold}>{data.summary.least_demanded.item}</Text>{" "}
                      ({data.summary.least_demanded.count})
                    </Text>
                  </View>
                ) : null}
              </View>
            ) : null}

            {data ? (
              <>
                <MealBlock meal="breakfast" data={data.meals.breakfast} styles={styles} c={c} />
                <MealBlock meal="lunch" data={data.meals.lunch} styles={styles} c={c} />
                <MealBlock meal="dinner" data={data.meals.dinner} styles={styles} c={c} />
              </>
            ) : null}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    safe: { flex: 1, backgroundColor: c.bg },
    center: { flex: 1, alignItems: "center", justifyContent: "center" },
    content: { padding: spacing.lg, paddingBottom: spacing.xxl + 32 },
    header: { marginBottom: spacing.md },
    eyebrow: {
      ...typography.caption,
      color: c.primary,
      letterSpacing: 1.5,
      fontWeight: "700",
      marginBottom: 6,
    },
    title: { ...typography.title1, color: c.textPrimary },
    subtitle: { ...typography.subhead, color: c.textSecondary, marginTop: 4 },
    tilesGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginBottom: spacing.md },

    toggleWrap: {
      flexDirection: "row",
      backgroundColor: c.inputBg,
      borderRadius: 14,
      padding: 4,
      marginBottom: spacing.md,
    },
    toggleBtn: {
      flex: 1,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 6,
      paddingVertical: 10,
      borderRadius: 10,
    },
    toggleLabel: { ...typography.footnote, fontWeight: "700" },

    card: {
      backgroundColor: c.card,
      borderRadius: radius.xl,
      padding: spacing.md,
      marginBottom: spacing.md,
      ...shadow.card,
    },
    highlightCard: { gap: 6, paddingVertical: 14 },
    highlightRow: { flexDirection: "row", alignItems: "center", gap: 8 },
    highlightText: { ...typography.subhead, color: c.textSecondary },
    bold: { color: c.textPrimary, fontWeight: "700" },

    titleRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      marginBottom: spacing.md,
    },
    iconBubble: {
      width: 30,
      height: 30,
      borderRadius: 15,
      backgroundColor: c.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    cardTitle: { ...typography.title2, color: c.textPrimary },
    eatPill: {
      ...typography.caption,
      backgroundColor: c.primaryLight,
      color: c.primary,
      paddingHorizontal: 10,
      paddingVertical: 4,
      borderRadius: 999,
      fontWeight: "700",
    },

    warnBox: {
      backgroundColor: c.badgePendingBg,
      padding: 10,
      borderRadius: 10,
      marginBottom: 10,
      gap: 6,
    },
    warnRow: { flexDirection: "row", alignItems: "flex-start", gap: 6 },
    warnText: { ...typography.caption, color: c.badgePendingText, flex: 1 },

    itemRow: {
      flexDirection: "row",
      alignItems: "center",
      paddingVertical: 10,
      borderTopWidth: 1,
      borderTopColor: c.border,
    },
    itemName: { ...typography.headline, color: c.textPrimary },
    itemSub: { ...typography.caption, color: c.textSecondary, marginTop: 2 },
    itemSuggestBox: { alignItems: "flex-end" },
    itemSuggestNum: { ...typography.title2, color: c.primary, fontSize: 20 },
    itemSuggestUnit: { ...typography.caption, color: c.textSecondary, marginTop: -2 },
    itemMissing: { ...typography.caption, color: c.warning, fontStyle: "italic" },
    muted: { ...typography.subhead, color: c.textSecondary, textAlign: "center", paddingVertical: 8 },
  });

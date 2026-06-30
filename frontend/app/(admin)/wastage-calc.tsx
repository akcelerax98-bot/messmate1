// Admin Tab 3 — Wastage & Calculation
// Inputs per meal-item (qty + unit), computed loss/savings + trend chart.

import { Feather } from "@expo/vector-icons";
import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  api,
  type AdminWastageToday,
  type AdminWastageTrend,
  type MealType,
  type Unit,
} from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { BarChart } from "@/src/components/BarChart";
import { Button } from "@/src/components/Button";
import { Segmented } from "@/src/components/Segmented";
import { StatTile } from "@/src/components/StatTile";
import { Toast } from "@/src/components/Toast";
import { colors, radius, shadow, spacing, typography } from "@/src/theme";

type Range = "7" | "30" | "90";
type MealFilter = "all" | MealType;

const UNITS: Unit[] = ["pieces", "grams", "kg", "ml", "litres"];

const ICON: Record<MealType, keyof typeof Feather.glyphMap> = {
  breakfast: "coffee",
  lunch: "sun",
  dinner: "moon",
};

type Draft = { item_name: string; quantity: string; unit: Unit };

function newDraft(): Draft {
  return { item_name: "", quantity: "", unit: "kg" };
}

function MealEntryEditor({
  meal,
  drafts,
  setDrafts,
}: {
  meal: MealType;
  drafts: Draft[];
  setDrafts: (d: Draft[]) => void;
}) {
  const update = (i: number, patch: Partial<Draft>) => {
    setDrafts(drafts.map((d, idx) => (idx === i ? { ...d, ...patch } : d)));
  };
  const remove = (i: number) => {
    setDrafts(drafts.filter((_, idx) => idx !== i));
  };
  return (
    <View style={styles.editorBlock} testID={`wastage-editor-${meal}`}>
      <View style={styles.editorHead}>
        <View style={styles.editorIcon}>
          <Feather name={ICON[meal]} size={16} color={colors.primary} />
        </View>
        <Text style={styles.editorTitle}>{meal.charAt(0).toUpperCase() + meal.slice(1)}</Text>
        <View style={{ flex: 1 }} />
        <TouchableOpacity
          testID={`wastage-add-${meal}`}
          onPress={() => setDrafts([...drafts, newDraft()])}
          style={styles.addBtn}
        >
          <Feather name="plus" size={14} color={colors.primary} />
          <Text style={styles.addBtnText}>Add</Text>
        </TouchableOpacity>
      </View>
      {drafts.length === 0 ? (
        <Text style={styles.editorMuted}>No items added.</Text>
      ) : (
        drafts.map((d, i) => (
          <View key={`${meal}-${i}`} style={styles.draftRow}>
            <TextInput
              testID={`wastage-${meal}-name-${i}`}
              placeholder="Item"
              placeholderTextColor={colors.textSecondary}
              style={[styles.input, { flex: 1.4 }]}
              value={d.item_name}
              onChangeText={(t) => update(i, { item_name: t })}
            />
            <TextInput
              testID={`wastage-${meal}-qty-${i}`}
              placeholder="Qty"
              placeholderTextColor={colors.textSecondary}
              style={[styles.input, { flex: 0.8 }]}
              keyboardType="decimal-pad"
              value={d.quantity}
              onChangeText={(t) => update(i, { quantity: t })}
            />
            <View style={[styles.unitPicker, { flex: 1 }]}>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                {UNITS.map((u) => (
                  <TouchableOpacity
                    key={u}
                    testID={`wastage-${meal}-unit-${i}-${u}`}
                    onPress={() => update(i, { unit: u })}
                    style={[
                      styles.unitChip,
                      d.unit === u && { backgroundColor: colors.primary },
                    ]}
                  >
                    <Text
                      style={[
                        styles.unitChipText,
                        d.unit === u && { color: "#fff" },
                      ]}
                    >
                      {u}
                    </Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
            <TouchableOpacity
              testID={`wastage-${meal}-remove-${i}`}
              onPress={() => remove(i)}
              style={styles.removeBtn}
            >
              <Feather name="x" size={16} color={colors.danger} />
            </TouchableOpacity>
          </View>
        ))
      )}
    </View>
  );
}

export default function AdminWastageCalc() {
  const { token } = useAuth();
  const [data, setData] = useState<AdminWastageToday | null>(null);
  const [trend, setTrend] = useState<AdminWastageTrend | null>(null);
  const [range, setRange] = useState<Range>("7");
  const [meal, setMeal] = useState<MealFilter>("all");
  const [showSaved, setShowSaved] = useState<"wastage" | "saved">("wastage");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{
    message: string;
    variant: "success" | "error" | "info";
  } | null>(null);

  const [breakfast, setBreakfast] = useState<Draft[]>([]);
  const [lunch, setLunch] = useState<Draft[]>([]);
  const [dinner, setDinner] = useState<Draft[]>([]);

  const hydrateDrafts = (today: AdminWastageToday | null) => {
    const toDrafts = (items: any[] | undefined): Draft[] =>
      (items || []).map((it) => ({
        item_name: it.item_name,
        quantity: String(it.quantity ?? ""),
        unit: it.unit,
      }));
    setBreakfast(toDrafts(today?.today?.breakfast_items));
    setLunch(toDrafts(today?.today?.lunch_items));
    setDinner(toDrafts(today?.today?.dinner_items));
  };

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [t, tr] = await Promise.all([
        api.adminWastageToday(token),
        api.adminWastageTrend(token, Number(range) as 7 | 30 | 90, meal),
      ]);
      setData(t);
      setTrend(tr);
      hydrateDrafts(t);
    } catch (e: any) {
      setToast({ message: e?.message || "Failed to load", variant: "error" });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token, range, meal]);

  useEffect(() => {
    load();
  }, [load]);

  const onSave = async () => {
    if (!token || !data) return;
    const parse = (drafts: Draft[]) =>
      drafts
        .filter((d) => d.item_name.trim() && d.quantity.trim())
        .map((d) => ({
          item_name: d.item_name.trim(),
          quantity: parseFloat(d.quantity) || 0,
          unit: d.unit,
        }));
    setSaving(true);
    try {
      await api.adminWastageUpsert(token, data.date, {
        breakfast_items: parse(breakfast),
        lunch_items: parse(lunch),
        dinner_items: parse(dinner),
      });
      setToast({ message: "Wastage saved", variant: "success" });
      await load();
    } catch (e: any) {
      setToast({ message: e?.message || "Save failed", variant: "error" });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.safe} edges={["top"]}>
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  const today = data?.today;
  const fmtKg = (n: number | null | undefined) =>
    n === null || n === undefined ? "—" : `${n.toFixed(1)} kg`;
  const fmtMoney = (n: number | null | undefined) =>
    n === null || n === undefined ? "—" : `₹${n.toFixed(0)}`;
  const totalWastageToday =
    today
      ? (today.breakfast_wastage_kg + today.lunch_wastage_kg + today.dinner_wastage_kg)
      : null;
  const yesterdayTotal = data?.yesterday
    ? data.yesterday.breakfast_wastage_kg +
      data.yesterday.lunch_wastage_kg +
      data.yesterday.dinner_wastage_kg
    : null;
  const lastWeekTotal = data?.last_week_same_day
    ? data.last_week_same_day.breakfast_wastage_kg +
      data.last_week_same_day.lunch_wastage_kg +
      data.last_week_same_day.dinner_wastage_kg
    : null;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <Toast
        testID="wcalc-toast"
        message={toast?.message ?? null}
        variant={toast?.variant ?? "success"}
        onHide={() => setToast(null)}
      />
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
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
            <Text style={styles.eyebrow}>ADMIN</Text>
            <Text style={styles.title}>Wastage & Calculation</Text>
            <Text style={styles.subtitle}>
              Record actual wastage. Loss & savings are computed automatically.
            </Text>
          </View>

          {/* Today summary tiles */}
          <View style={styles.tilesGrid}>
            <StatTile
              testID="wcalc-tile-total"
              icon="trash-2"
              label="Today wastage"
              value={fmtKg(totalWastageToday)}
            />
            <StatTile
              testID="wcalc-tile-loss"
              icon="dollar-sign"
              label="Today loss"
              tone="danger"
              value={fmtMoney(today?.total_loss)}
            />
            <StatTile
              testID="wcalc-tile-avg"
              icon="bar-chart"
              label="Avg loss (30d)"
              value={fmtMoney(data?.average_loss_30d)}
            />
            <StatTile
              testID="wcalc-tile-saved"
              icon="trending-down"
              label="Saved vs avg"
              tone={
                (data?.saved_amount_vs_avg ?? 0) >= 0 ? "success" : "danger"
              }
              value={fmtMoney(data?.saved_amount_vs_avg)}
            />
          </View>

          {/* Breakdown */}
          <View style={styles.card}>
            <Text style={styles.subLabel}>Today by meal</Text>
            <View style={styles.row3}>
              <View style={styles.tiny}>
                <Feather name="coffee" size={14} color={colors.primary} />
                <Text style={styles.tinyLabel}>Breakfast</Text>
                <Text style={styles.tinyValue}>{fmtKg(today?.breakfast_wastage_kg)}</Text>
                <Text style={styles.tinyMoney}>{fmtMoney(today?.breakfast_loss)}</Text>
              </View>
              <View style={styles.tiny}>
                <Feather name="sun" size={14} color={colors.primary} />
                <Text style={styles.tinyLabel}>Lunch</Text>
                <Text style={styles.tinyValue}>{fmtKg(today?.lunch_wastage_kg)}</Text>
                <Text style={styles.tinyMoney}>{fmtMoney(today?.lunch_loss)}</Text>
              </View>
              <View style={styles.tiny}>
                <Feather name="moon" size={14} color={colors.primary} />
                <Text style={styles.tinyLabel}>Dinner</Text>
                <Text style={styles.tinyValue}>{fmtKg(today?.dinner_wastage_kg)}</Text>
                <Text style={styles.tinyMoney}>{fmtMoney(today?.dinner_loss)}</Text>
              </View>
            </View>
          </View>

          <View style={styles.row2}>
            <View style={[styles.card, styles.compareCard]}>
              <Text style={styles.cardLabel}>Yesterday</Text>
              <Text style={styles.midNumber}>{fmtKg(yesterdayTotal)}</Text>
              <Text style={styles.midMoney}>{fmtMoney(data?.yesterday?.total_loss)}</Text>
            </View>
            <View style={[styles.card, styles.compareCard]}>
              <Text style={styles.cardLabel}>Last week, same day</Text>
              <Text style={styles.midNumber}>{fmtKg(lastWeekTotal)}</Text>
              <Text style={styles.midMoney}>
                {fmtMoney(data?.last_week_same_day?.total_loss)}
              </Text>
            </View>
          </View>

          {/* Entry editor */}
          <Text style={styles.sectionLabel}>Record today's wastage</Text>
          <View style={styles.card}>
            <MealEntryEditor meal="breakfast" drafts={breakfast} setDrafts={setBreakfast} />
            <MealEntryEditor meal="lunch" drafts={lunch} setDrafts={setLunch} />
            <MealEntryEditor meal="dinner" drafts={dinner} setDrafts={setDinner} />
            <Button
              testID="wcalc-save"
              label={saving ? "Saving..." : "Save wastage"}
              onPress={onSave}
              loading={saving}
              style={{ marginTop: 10 }}
            />
            <Text style={styles.hint}>
              Price comes from Necessary Info. Loss = Quantity × Price/unit.
            </Text>
          </View>

          {/* Trend chart */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Trend</Text>

            <Text style={styles.filterLabel}>View</Text>
            <Segmented<"wastage" | "saved">
              testID="wcalc-chart-mode"
              value={showSaved}
              onChange={setShowSaved}
              options={[
                { value: "wastage", label: "Wastage (kg)", testID: "wcalc-chart-wastage" },
                { value: "saved", label: "Saved (₹)", testID: "wcalc-chart-saved" },
              ]}
              style={{ marginBottom: spacing.sm }}
            />

            <Text style={styles.filterLabel}>Range</Text>
            <Segmented<Range>
              testID="wcalc-range"
              value={range}
              onChange={setRange}
              options={[
                { value: "7", label: "7 days", testID: "wcalc-range-7" },
                { value: "30", label: "30 days", testID: "wcalc-range-30" },
                { value: "90", label: "90 days", testID: "wcalc-range-90" },
              ]}
              style={{ marginBottom: spacing.sm }}
            />

            <Text style={styles.filterLabel}>Meal</Text>
            <Segmented<MealFilter>
              testID="wcalc-meal"
              value={meal}
              onChange={setMeal}
              options={[
                { value: "all", label: "All", testID: "wcalc-meal-all" },
                { value: "breakfast", label: "B'fast", testID: "wcalc-meal-breakfast" },
                { value: "lunch", label: "Lunch", testID: "wcalc-meal-lunch" },
                { value: "dinner", label: "Dinner", testID: "wcalc-meal-dinner" },
              ]}
              style={{ marginBottom: spacing.md }}
            />

            {trend ? (
              <BarChart
                testID="wcalc-chart"
                data={
                  showSaved === "wastage"
                    ? trend.wastage_series
                    : trend.saved_series.map((p) => ({ ...p, value: Math.max(0, p.value) }))
                }
                height={180}
              />
            ) : null}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl + 32 },
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
  tilesGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginBottom: spacing.md },

  card: {
    backgroundColor: colors.card,
    borderRadius: radius.xl,
    padding: spacing.md,
    marginBottom: spacing.md,
    ...shadow.card,
  },
  cardLabel: {
    ...typography.footnote,
    color: colors.textSecondary,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  cardTitle: { ...typography.title2, color: colors.textPrimary, marginBottom: spacing.md },
  midNumber: { ...typography.title1, fontSize: 22, color: colors.textPrimary },
  midMoney: { ...typography.subhead, color: colors.danger, marginTop: 2, fontWeight: "700" },
  row2: { flexDirection: "row", gap: 10 },
  compareCard: { flex: 1 },
  row3: { flexDirection: "row", gap: 10 },
  tiny: { flex: 1, gap: 2 },
  tinyLabel: { ...typography.caption, color: colors.textSecondary },
  tinyValue: { ...typography.headline, color: colors.textPrimary },
  tinyMoney: { ...typography.caption, color: colors.danger, fontWeight: "700" },

  subLabel: {
    ...typography.footnote,
    color: colors.textSecondary,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  sectionLabel: {
    ...typography.caption,
    color: colors.textSecondary,
    textTransform: "uppercase",
    letterSpacing: 1,
    marginLeft: 4,
    marginBottom: 8,
    marginTop: 6,
  },

  editorBlock: { marginBottom: 14 },
  editorHead: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 8,
  },
  editorIcon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  editorTitle: { ...typography.headline, color: colors.textPrimary },
  editorMuted: { ...typography.caption, color: colors.textSecondary, fontStyle: "italic" },
  addBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: colors.primaryLight,
    borderRadius: 8,
  },
  addBtnText: { ...typography.caption, color: colors.primary, fontWeight: "700" },

  draftRow: { flexDirection: "row", gap: 6, alignItems: "center", marginBottom: 6 },
  input: {
    backgroundColor: colors.inputBg,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 13,
    color: colors.textPrimary,
  },
  unitPicker: {},
  unitChip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: colors.inputBg,
    borderRadius: 8,
    marginRight: 4,
  },
  unitChipText: { ...typography.caption, color: colors.textPrimary, fontWeight: "600" },
  removeBtn: { padding: 6 },
  hint: { ...typography.caption, color: colors.textSecondary, marginTop: 6, textAlign: "center" },

  filterLabel: {
    ...typography.caption,
    color: colors.textSecondary,
    marginBottom: 6,
  },
});

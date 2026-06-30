// Student Home / Today's Plan — collects ON/OFF, item preferences, reasons,
// custom answers per meal, and anonymous feedback. Saves into /api/student/today.

import { Feather } from "@expo/vector-icons";
import React, { useCallback, useEffect, useMemo, useState } from "react";
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

import { api, type CustomQuestion, type MealPlan, type MealType, type TodayResponse } from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { BarChart as _unused } from "@/src/components/BarChart"; // eslint-disable-line @typescript-eslint/no-unused-vars
import { Button } from "@/src/components/Button";
import { Chip } from "@/src/components/Chip";
import { Toast } from "@/src/components/Toast";
import { ToggleOnOff } from "@/src/components/ToggleOnOff";
import { colors, radius, shadow, spacing, typography } from "@/src/theme";

const DEFAULT_PLAN: MealPlan = {
  status: null,
  selected_items: [],
  reason_if_off: null,
  custom_answer: null,
};

const DATE_FMT: Intl.DateTimeFormatOptions = {
  weekday: "long",
  day: "numeric",
  month: "long",
};

const MEAL_TITLES: Record<MealType, string> = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  dinner: "Dinner",
};

const MEAL_ICONS: Record<MealType, keyof typeof Feather.glyphMap> = {
  breakfast: "coffee",
  lunch: "sun",
  dinner: "moon",
};

type ToastState = { message: string; variant: "success" | "error" | "info" } | null;

export default function StudentHome() {
  const { token, user } = useAuth();
  const [data, setData] = useState<TodayResponse | null>(null);
  const [reasons, setReasons] = useState<string[]>([]);
  const [breakfast, setBreakfast] = useState<MealPlan>(DEFAULT_PLAN);
  const [lunch, setLunch] = useState<MealPlan>(DEFAULT_PLAN);
  const [dinner, setDinner] = useState<MealPlan>(DEFAULT_PLAN);
  const [otherReasonInputs, setOtherReasonInputs] = useState<Record<MealType, string>>({
    breakfast: "",
    lunch: "",
    dinner: "",
  });
  const [feedback, setFeedback] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [toast, setToast] = useState<ToastState>(null);

  const dateLabel = useMemo(() => {
    if (!data?.date) return "";
    try {
      return new Date(data.date).toLocaleDateString(undefined, DATE_FMT);
    } catch {
      return data.date;
    }
  }, [data?.date]);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [todayRes, metaRes] = await Promise.all([
        api.studentToday(token),
        api.studentMeta(token),
      ]);
      setData(todayRes);
      setReasons(metaRes.reasons);

      // hydrate per-meal state if a plan exists
      const fromPlan = (key: MealType): MealPlan => {
        const p = todayRes.plan?.[key];
        const partial = (p as Partial<MealPlan>) || {};
        return {
          status: partial.status ?? null,
          selected_items: partial.selected_items ?? [],
          reason_if_off: partial.reason_if_off ?? null,
          custom_answer: partial.custom_answer ?? null,
        };
      };
      const b = fromPlan("breakfast");
      const l = fromPlan("lunch");
      const d = fromPlan("dinner");
      setBreakfast(b);
      setLunch(l);
      setDinner(d);

      // Pre-fill "Other" inputs if previously saved as "Other: ..."
      const parseOther = (mp: MealPlan): string =>
        mp.reason_if_off && mp.reason_if_off.startsWith("Other:")
          ? mp.reason_if_off.slice("Other:".length).trim()
          : "";
      setOtherReasonInputs({
        breakfast: parseOther(b),
        lunch: parseOther(l),
        dinner: parseOther(d),
      });
    } catch (e: any) {
      setToast({ message: e?.message || "Failed to load today's plan", variant: "error" });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const stateFor = (m: MealType) =>
    m === "breakfast" ? breakfast : m === "lunch" ? lunch : dinner;

  const setFor = (m: MealType) =>
    m === "breakfast"
      ? setBreakfast
      : m === "lunch"
        ? setLunch
        : setDinner;

  const toggleItem = (m: MealType, item: string) => {
    const set = setFor(m);
    set((prev) => {
      const has = prev.selected_items.includes(item);
      return {
        ...prev,
        selected_items: has
          ? prev.selected_items.filter((x) => x !== item)
          : [...prev.selected_items, item],
      };
    });
  };

  const setStatus = (m: MealType, v: "ON" | "OFF") => {
    setFor(m)((prev) => ({
      ...prev,
      status: v,
      // Clear reason if switching back to ON
      reason_if_off: v === "ON" ? null : prev.reason_if_off,
    }));
  };

  const selectReason = (m: MealType, r: string) => {
    setFor(m)((prev) => ({ ...prev, reason_if_off: r === "Other" ? "Other:" : r }));
  };

  const updateOtherText = (m: MealType, txt: string) => {
    setOtherReasonInputs((prev) => ({ ...prev, [m]: txt }));
    setFor(m)((prev) => ({ ...prev, reason_if_off: `Other: ${txt}` }));
  };

  const selectCustom = (m: MealType, opt: string) => {
    setFor(m)((prev) => ({ ...prev, custom_answer: opt }));
  };

  const onSave = async () => {
    if (!token) return;
    setSaving(true);
    try {
      await api.upsertToday(token, { breakfast, lunch, dinner });
      setToast({ message: "Today's plan saved", variant: "success" });
    } catch (e: any) {
      setToast({ message: e?.message || "Save failed", variant: "error" });
    } finally {
      setSaving(false);
    }
  };

  const onSendFeedback = async () => {
    if (!token) return;
    const txt = feedback.trim();
    if (!txt) {
      setToast({ message: "Please write something first", variant: "info" });
      return;
    }
    setSubmittingFeedback(true);
    try {
      await api.postFeedback(token, txt);
      setFeedback("");
      setToast({ message: "Feedback sent anonymously", variant: "success" });
    } catch (e: any) {
      setToast({ message: e?.message || "Could not send feedback", variant: "error" });
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const renderMeal = (m: MealType, items: string[], cq: CustomQuestion) => {
    const s = stateFor(m);
    const reasonValue = s.reason_if_off || "";
    const reasonSelected = reasonValue.startsWith("Other:")
      ? "Other"
      : reasonValue;
    return (
      <View style={styles.card} testID={`meal-${m}-card`}>
        <View style={styles.cardHead}>
          <View style={styles.titleRow}>
            <View style={styles.iconBubble}>
              <Feather name={MEAL_ICONS[m]} size={18} color={colors.primary} />
            </View>
            <Text style={styles.cardTitle}>{MEAL_TITLES[m]}</Text>
          </View>
          <ToggleOnOff
            testIDPrefix={`meal-${m}-toggle`}
            value={s.status}
            onChange={(v) => setStatus(m, v)}
          />
        </View>

        {items.length === 0 ? (
          <Text style={styles.emptyText}>Menu not added yet.</Text>
        ) : (
          <>
            <Text style={styles.sectionLabel}>Menu — tap items you prefer</Text>
            <View style={styles.chipRow}>
              {items.map((it) => (
                <Chip
                  key={it}
                  testID={`meal-${m}-item-${it.toLowerCase().replace(/\s+/g, "-")}`}
                  label={it}
                  selected={s.selected_items.includes(it)}
                  onPress={() => toggleItem(m, it)}
                />
              ))}
            </View>
          </>
        )}

        {s.status === "OFF" ? (
          <View style={{ marginTop: spacing.md }}>
            <Text style={styles.sectionLabel}>Reason (optional)</Text>
            <View style={styles.chipRow}>
              {reasons.map((r) => (
                <Chip
                  key={r}
                  testID={`meal-${m}-reason-${r.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
                  label={r}
                  selected={reasonSelected === r}
                  onPress={() => selectReason(m, r)}
                />
              ))}
            </View>
            {reasonSelected === "Other" ? (
              <TextInput
                testID={`meal-${m}-reason-other-input`}
                value={otherReasonInputs[m]}
                onChangeText={(t) => updateOtherText(m, t)}
                placeholder="Tell us more (optional)"
                placeholderTextColor={colors.textSecondary}
                style={styles.otherInput}
              />
            ) : null}
          </View>
        ) : null}

        {cq ? (
          <View style={{ marginTop: spacing.md }}>
            <Text style={styles.sectionLabel}>{cq.text}</Text>
            <View style={styles.chipRow}>
              {cq.options.map((opt) => (
                <Chip
                  key={opt}
                  testID={`meal-${m}-custom-${opt.toLowerCase().replace(/\s+/g, "-")}`}
                  label={opt}
                  selected={s.custom_answer === opt}
                  onPress={() => selectCustom(m, opt)}
                />
              ))}
            </View>
          </View>
        ) : null}
      </View>
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.safe} edges={["top"]}>
        <View style={styles.loadingWrap}>
          <ActivityIndicator color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  const menu = data?.menu;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <Toast
          testID="home-toast"
          message={toast?.message ?? null}
          variant={toast?.variant ?? "success"}
          onHide={() => setToast(null)}
        />
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
          {/* Greeting */}
          <View style={styles.headerBlock}>
            <Text style={styles.eyebrow}>TODAY'S PLAN</Text>
            <Text style={styles.greeting} testID="home-greeting">
              Hi, {user?.full_name || "there"}
            </Text>
            <Text style={styles.dateLine} testID="home-date">
              {dateLabel}
            </Text>
          </View>

          {/* Menu summary */}
          {menu ? (
            <View style={[styles.card, styles.summaryCard]} testID="home-menu-summary">
              <View style={styles.summaryRow}>
                <Feather name="coffee" size={16} color={colors.primary} />
                <Text style={styles.summaryLabel}>Breakfast</Text>
                <Text style={styles.summaryValue} numberOfLines={2}>
                  {menu.breakfast_items.join(", ") || "—"}
                </Text>
              </View>
              <View style={styles.summaryRow}>
                <Feather name="sun" size={16} color={colors.primary} />
                <Text style={styles.summaryLabel}>Lunch</Text>
                <Text style={styles.summaryValue} numberOfLines={2}>
                  {menu.lunch_items.join(", ") || "—"}
                </Text>
              </View>
              <View style={styles.summaryRow}>
                <Feather name="moon" size={16} color={colors.primary} />
                <Text style={styles.summaryLabel}>Dinner</Text>
                <Text style={styles.summaryValue} numberOfLines={2}>
                  {menu.dinner_items.join(", ") || "—"}
                </Text>
              </View>
            </View>
          ) : (
            <View style={styles.card}>
              <Text style={styles.emptyText}>Menu not added yet.</Text>
            </View>
          )}

          {menu ? (
            <>
              {renderMeal("breakfast", menu.breakfast_items, menu.breakfast_custom_question)}
              {renderMeal("lunch", menu.lunch_items, menu.lunch_custom_question)}
              {renderMeal("dinner", menu.dinner_items, menu.dinner_custom_question)}

              <Button
                testID="home-save-plan"
                label={saving ? "Saving..." : "Save today's plan"}
                onPress={onSave}
                loading={saving}
                style={{ marginTop: spacing.md }}
              />
            </>
          ) : null}

          {/* Feedback */}
          <View style={[styles.card, { marginTop: spacing.md }]} testID="home-feedback-card">
            <View style={styles.titleRow}>
              <View style={styles.iconBubble}>
                <Feather name="message-circle" size={18} color={colors.primary} />
              </View>
              <Text style={styles.cardTitle}>Today's Feedback / Suggestion</Text>
            </View>
            <Text style={styles.feedbackHint}>
              Sent anonymously — admin will not see your name.
            </Text>
            <TextInput
              testID="home-feedback-input"
              value={feedback}
              onChangeText={setFeedback}
              placeholder="Share today's feedback or suggestion about food"
              placeholderTextColor={colors.textSecondary}
              multiline
              style={styles.feedbackInput}
            />
            <TouchableOpacity
              testID="home-feedback-submit"
              activeOpacity={0.85}
              onPress={onSendFeedback}
              disabled={submittingFeedback}
              style={[
                styles.feedbackBtn,
                {
                  backgroundColor:
                    submittingFeedback || !feedback.trim()
                      ? colors.inputBg
                      : colors.primaryLight,
                },
              ]}
            >
              <Feather
                name="send"
                size={16}
                color={
                  !feedback.trim() ? colors.textSecondary : colors.primary
                }
              />
              <Text
                style={[
                  styles.feedbackBtnText,
                  { color: !feedback.trim() ? colors.textSecondary : colors.primary },
                ]}
              >
                {submittingFeedback ? "Sending..." : "Send anonymously"}
              </Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  loadingWrap: { flex: 1, alignItems: "center", justifyContent: "center" },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl + 24 },

  headerBlock: { marginBottom: spacing.lg },
  eyebrow: {
    ...typography.caption,
    color: colors.primary,
    letterSpacing: 1.5,
    fontWeight: "700",
    marginBottom: 6,
  },
  greeting: { ...typography.title1, color: colors.textPrimary },
  dateLine: { ...typography.subhead, color: colors.textSecondary, marginTop: 4 },

  card: {
    backgroundColor: colors.card,
    borderRadius: radius.xl,
    padding: spacing.md + 4,
    marginBottom: spacing.md,
    ...shadow.card,
  },
  summaryCard: { gap: 8, paddingVertical: spacing.md },
  summaryRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  summaryLabel: {
    ...typography.footnote,
    color: colors.textSecondary,
    width: 70,
  },
  summaryValue: { ...typography.subhead, color: colors.textPrimary, flex: 1 },

  cardHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.md,
  },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 10, flexShrink: 1 },
  iconBubble: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  cardTitle: { ...typography.title2, color: colors.textPrimary, flexShrink: 1 },

  sectionLabel: {
    ...typography.footnote,
    color: colors.textSecondary,
    marginBottom: 8,
  },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  emptyText: {
    ...typography.subhead,
    color: colors.textSecondary,
    paddingVertical: 8,
  },

  otherInput: {
    marginTop: 10,
    backgroundColor: colors.inputBg,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: colors.textPrimary,
  },

  feedbackHint: { ...typography.caption, color: colors.textSecondary, marginBottom: 10 },
  feedbackInput: {
    backgroundColor: colors.inputBg,
    borderRadius: radius.md,
    padding: 14,
    minHeight: 96,
    color: colors.textPrimary,
    fontSize: 15,
    textAlignVertical: "top",
  },
  feedbackBtn: {
    marginTop: 10,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 12,
    borderRadius: radius.md,
  },
  feedbackBtnText: { ...typography.headline, fontWeight: "600" },
});

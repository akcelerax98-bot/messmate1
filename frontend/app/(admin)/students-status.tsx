// Admin Tab 1 — Students Status.
// Approval list (pending) + meal-wise breakdown (eating/items/reasons/custom Q) + feedback.

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
  type AdminTodayResponse,
  type MealStat,
  type MealType,
  type StudentRow,
  type StudentsSummary,
} from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { LikeDislikeBar } from "@/src/components/LikeDislikeBar";
import { Segmented } from "@/src/components/Segmented";
import { StatTile } from "@/src/components/StatTile";
import { Toast } from "@/src/components/Toast";
import { colors, radius, shadow, spacing, typography } from "@/src/theme";

const MEAL_ICON: Record<MealType, keyof typeof Feather.glyphMap> = {
  breakfast: "coffee",
  lunch: "sun",
  dinner: "moon",
};

function cap(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export default function AdminStudentsStatus() {
  const { token } = useAuth();
  const [summary, setSummary] = useState<StudentsSummary | null>(null);
  const [pending, setPending] = useState<StudentRow[]>([]);
  const [today, setToday] = useState<AdminTodayResponse | null>(null);
  const [feedback, setFeedback] = useState<
    { id: string; date: string; feedback_text: string; created_at: string }[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [acting, setActing] = useState<string | null>(null);
  const [activeMeal, setActiveMeal] = useState<MealType>("breakfast");
  const [toast, setToast] = useState<{
    message: string;
    variant: "success" | "error" | "info";
  } | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [s, p, t, f] = await Promise.all([
        api.adminStudentsSummary(token),
        api.adminStudentsList(token, "pending"),
        api.adminToday(token),
        api.adminFeedback(token, 7),
      ]);
      setSummary(s);
      setPending(p.students);
      setToday(t);
      setFeedback(f.items);
    } catch (e: any) {
      setToast({ message: e?.message || "Failed to load", variant: "error" });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const onApprove = async (id: string) => {
    if (!token) return;
    setActing(id);
    try {
      await api.adminApprove(token, id);
      setToast({ message: "Student approved", variant: "success" });
      await load();
    } catch (e: any) {
      setToast({ message: e?.message || "Failed", variant: "error" });
    } finally {
      setActing(null);
    }
  };

  const onReject = async (id: string) => {
    if (!token) return;
    setActing(id);
    try {
      await api.adminReject(token, id);
      setToast({ message: "Student rejected", variant: "info" });
      await load();
    } catch (e: any) {
      setToast({ message: e?.message || "Failed", variant: "error" });
    } finally {
      setActing(null);
    }
  };

  const meal: MealStat | null = useMemo(() => {
    if (!today) return null;
    return today[activeMeal];
  }, [today, activeMeal]);

  if (loading) {
    return (
      <SafeAreaView style={styles.safe} edges={["top"]}>
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <Toast
        testID="admin-status-toast"
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
          <Text style={styles.eyebrow}>ADMIN</Text>
          <Text style={styles.title}>Students Status</Text>
          <Text style={styles.subtitle}>
            Approvals, eating intent, preferences, reactions, reasons & feedback.
          </Text>
        </View>

        {/* Summary tiles */}
        <View style={styles.tilesGrid}>
          <StatTile
            testID="tile-total"
            icon="users"
            label="Total students"
            value={summary?.total_students ?? 0}
          />
          <StatTile
            testID="tile-approved"
            icon="check-circle"
            label="Approved"
            tone="success"
            value={summary?.approved ?? 0}
          />
          <StatTile
            testID="tile-pending"
            icon="clock"
            label="Pending"
            tone="warning"
            value={summary?.pending ?? 0}
          />
          <StatTile
            testID="tile-blocked"
            icon="x-octagon"
            label="Blocked"
            tone="danger"
            value={summary?.blocked ?? 0}
          />
        </View>

        {/* Pending approvals */}
        <Text style={styles.sectionLabel}>Pending approvals ({pending.length})</Text>
        {pending.length === 0 ? (
          <View style={styles.card}>
            <Text style={styles.muted}>No pending approvals 🎉</Text>
          </View>
        ) : (
          pending.map((s) => (
            <View key={s.id} style={styles.studentCard} testID={`pending-${s.mobile_or_user_id}`}>
              <View style={styles.studentRow}>
                <View style={styles.avatar}>
                  <Text style={styles.avatarLetter}>
                    {(s.full_name[0] || "?").toUpperCase()}
                  </Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.studentName}>{s.full_name}</Text>
                  <Text style={styles.studentMeta}>
                    {s.mobile_or_user_id} · Room {s.room_number || "—"}
                  </Text>
                  <Text style={styles.studentMeta}>{s.institution_or_hostel_name}</Text>
                </View>
              </View>
              <View style={styles.actionRow}>
                <TouchableOpacity
                  testID={`approve-${s.mobile_or_user_id}`}
                  activeOpacity={0.85}
                  style={[styles.actBtn, { backgroundColor: colors.primary }]}
                  onPress={() => onApprove(s.id)}
                  disabled={acting === s.id}
                >
                  <Feather name="check" size={16} color="#fff" />
                  <Text style={styles.actBtnText}>Approve</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  testID={`reject-${s.mobile_or_user_id}`}
                  activeOpacity={0.85}
                  style={[styles.actBtn, { backgroundColor: colors.inputBg }]}
                  onPress={() => onReject(s.id)}
                  disabled={acting === s.id}
                >
                  <Feather name="x" size={16} color={colors.danger} />
                  <Text style={[styles.actBtnText, { color: colors.danger }]}>
                    Reject
                  </Text>
                </TouchableOpacity>
              </View>
            </View>
          ))
        )}

        {/* Today's summary */}
        <Text style={styles.sectionLabel}>Today · {today?.day ? cap(today.day) : ""}</Text>

        <View style={styles.tilesGrid}>
          <StatTile
            testID="tile-eating-breakfast"
            icon="coffee"
            label="Eating breakfast"
            value={today?.breakfast.eating_count ?? 0}
          />
          <StatTile
            testID="tile-eating-lunch"
            icon="sun"
            label="Eating lunch"
            value={today?.lunch.eating_count ?? 0}
          />
          <StatTile
            testID="tile-eating-dinner"
            icon="moon"
            label="Eating dinner"
            value={today?.dinner.eating_count ?? 0}
          />
          <StatTile
            testID="tile-responses"
            icon="check-square"
            label="Total responses"
            value={today?.total_responses ?? 0}
          />
        </View>

        {/* Meal-wise breakdown */}
        <Segmented<MealType>
          testID="status-meal"
          value={activeMeal}
          onChange={setActiveMeal}
          options={[
            { value: "breakfast", label: "Breakfast", testID: "status-meal-breakfast" },
            { value: "lunch", label: "Lunch", testID: "status-meal-lunch" },
            { value: "dinner", label: "Dinner", testID: "status-meal-dinner" },
          ]}
          style={{ marginVertical: spacing.md }}
        />

        {meal ? (
          <View style={styles.card} testID={`meal-detail-${activeMeal}`}>
            <View style={styles.titleRow}>
              <View style={styles.titleIcon}>
                <Feather name={MEAL_ICON[activeMeal]} size={18} color={colors.primary} />
              </View>
              <Text style={styles.cardTitle}>{cap(activeMeal)}</Text>
            </View>

            <View style={styles.eatRow}>
              <View style={styles.eatBox}>
                <Text style={styles.eatNum}>{meal.eating_count}</Text>
                <Text style={styles.eatLabel}>Eating</Text>
              </View>
              <View style={styles.eatBox}>
                <Text style={[styles.eatNum, { color: colors.danger }]}>
                  {meal.not_eating_count}
                </Text>
                <Text style={styles.eatLabel}>Not eating</Text>
              </View>
            </View>

            <Text style={styles.subLabel}>Menu satisfaction</Text>
            <LikeDislikeBar
              testID={`like-bar-${activeMeal}`}
              likePct={meal.like_pct}
              dislikePct={meal.dislike_pct}
            />

            <Text style={styles.subLabel}>Item preference demand</Text>
            {meal.item_counts.length === 0 ? (
              <Text style={styles.muted}>No preferences submitted yet.</Text>
            ) : (
              meal.item_counts.map((row) => (
                <View key={row.item_name} style={styles.barRow}>
                  <Text style={styles.barName}>{row.item_name}</Text>
                  <View style={styles.barTrack}>
                    <View
                      style={[
                        styles.barFill,
                        {
                          width: `${
                            meal.item_counts.length === 0
                              ? 0
                              : Math.min(
                                  100,
                                  (row.count /
                                    Math.max(
                                      1,
                                      Math.max(
                                        ...meal.item_counts.map((x) => x.count),
                                      ),
                                    )) *
                                    100,
                                )
                          }%`,
                        },
                      ]}
                    />
                  </View>
                  <Text style={styles.barCount}>{row.count}</Text>
                </View>
              ))
            )}

            <Text style={styles.subLabel}>Reasons for not eating</Text>
            {meal.reason_counts.length === 0 ? (
              <Text style={styles.muted}>No reasons recorded.</Text>
            ) : (
              <View style={styles.kvList}>
                {meal.reason_counts.map((r) => (
                  <View key={r.reason} style={styles.kvRow}>
                    <Text style={styles.kvKey}>{r.reason}</Text>
                    <Text style={styles.kvValue}>{r.count}</Text>
                  </View>
                ))}
              </View>
            )}

            {meal.custom_question ? (
              <>
                <Text style={styles.subLabel}>{meal.custom_question.text}</Text>
                {meal.custom_answer_counts.length === 0 ? (
                  <Text style={styles.muted}>No answers yet.</Text>
                ) : (
                  <View style={styles.kvList}>
                    {meal.custom_answer_counts.map((a) => (
                      <View key={a.answer} style={styles.kvRow}>
                        <Text style={styles.kvKey}>{a.answer}</Text>
                        <Text style={styles.kvValue}>{a.count}</Text>
                      </View>
                    ))}
                  </View>
                )}
              </>
            ) : null}
          </View>
        ) : null}

        {/* Anonymous feedback */}
        <Text style={styles.sectionLabel}>Anonymous feedback · last 7 days</Text>
        {feedback.length === 0 ? (
          <View style={styles.card}>
            <Text style={styles.muted}>No feedback yet.</Text>
          </View>
        ) : (
          <View style={styles.card}>
            {feedback.map((f, i) => (
              <View key={f.id}>
                {i > 0 ? <View style={styles.divider} /> : null}
                <View style={styles.fbRow}>
                  <Feather
                    name="message-circle"
                    size={14}
                    color={colors.primary}
                    style={{ marginTop: 3 }}
                  />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.fbText}>"{f.feedback_text}"</Text>
                    <Text style={styles.fbMeta}>Anonymous · {f.date}</Text>
                  </View>
                </View>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
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
  sectionLabel: {
    ...typography.caption,
    color: colors.textSecondary,
    textTransform: "uppercase",
    letterSpacing: 1,
    marginTop: spacing.md,
    marginLeft: 4,
    marginBottom: 8,
  },
  tilesGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.xl,
    padding: spacing.md,
    marginBottom: spacing.sm,
    ...shadow.card,
  },
  studentCard: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginBottom: 10,
    ...shadow.card,
  },
  studentRow: { flexDirection: "row", gap: 12, alignItems: "center" },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarLetter: { color: colors.primary, fontSize: 18, fontWeight: "700" },
  studentName: { ...typography.headline, color: colors.textPrimary },
  studentMeta: { ...typography.caption, color: colors.textSecondary, marginTop: 1 },
  actionRow: { flexDirection: "row", gap: 8, marginTop: spacing.sm },
  actBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 10,
    borderRadius: radius.md,
  },
  actBtnText: { ...typography.subhead, color: "#fff", fontWeight: "700" },

  titleRow: { flexDirection: "row", alignItems: "center", gap: 10, marginBottom: spacing.md },
  titleIcon: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  cardTitle: { ...typography.title2, color: colors.textPrimary },

  eatRow: { flexDirection: "row", gap: 12 },
  eatBox: {
    flex: 1,
    backgroundColor: colors.inputBg,
    borderRadius: radius.md,
    padding: 12,
    alignItems: "center",
  },
  eatNum: { ...typography.title1, color: colors.primary, fontSize: 26 },
  eatLabel: { ...typography.caption, color: colors.textSecondary, marginTop: 2 },

  subLabel: {
    ...typography.footnote,
    color: colors.textSecondary,
    marginTop: spacing.md,
    marginBottom: 6,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  muted: { ...typography.subhead, color: colors.textSecondary },

  barRow: { flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 6 },
  barName: { ...typography.subhead, color: colors.textPrimary, width: 100 },
  barTrack: {
    flex: 1,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.inputBg,
    overflow: "hidden",
  },
  barFill: { height: "100%", backgroundColor: colors.primary, borderRadius: 4 },
  barCount: {
    ...typography.subhead,
    color: colors.textPrimary,
    fontWeight: "700",
    width: 40,
    textAlign: "right",
  },

  kvList: { gap: 6 },
  kvRow: { flexDirection: "row", justifyContent: "space-between" },
  kvKey: { ...typography.subhead, color: colors.textSecondary },
  kvValue: { ...typography.subhead, color: colors.textPrimary, fontWeight: "700" },

  divider: { height: 1, backgroundColor: colors.border, marginVertical: 8 },
  fbRow: { flexDirection: "row", gap: 8, paddingVertical: 6 },
  fbText: { ...typography.subhead, color: colors.textPrimary, lineHeight: 20 },
  fbMeta: { ...typography.caption, color: colors.textTertiary, marginTop: 2 },
});

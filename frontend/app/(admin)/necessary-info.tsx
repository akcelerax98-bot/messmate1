// Admin Tab 4 — Necessary Info
// Menu plan editor (per weekday), Qty/person + Price/unit (per item),
// Custom questions live inside the weekday menu (per meal slot).

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

import {
  api,
  type DailyMenu,
  type MealType,
  type NecessaryItem,
  type Unit,
} from "@/src/api/client";
import { useAuth } from "@/src/auth/AuthContext";
import { Button } from "@/src/components/Button";
import { Segmented } from "@/src/components/Segmented";
import { Toast } from "@/src/components/Toast";
import { colors, radius, shadow, spacing, typography } from "@/src/theme";

const DAYS = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];
const UNITS: Unit[] = ["pieces", "grams", "kg", "ml", "litres"];

type TabKey = "menu" | "items" | "custom";

function cap(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// --- Menu editor ---------------------------------------------------------
function MenuEditor({ data, onSave }: { data: DailyMenu; onSave: (d: DailyMenu) => Promise<void> }) {
  const [b, setB] = useState(data.breakfast_items.join(", "));
  const [l, setL] = useState(data.lunch_items.join(", "));
  const [d, setD] = useState(data.dinner_items.join(", "));
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    setB(data.breakfast_items.join(", "));
    setL(data.lunch_items.join(", "));
    setD(data.dinner_items.join(", "));
  }, [data]);

  const split = (s: string) =>
    s.split(",").map((t) => t.trim()).filter((t) => t.length > 0);

  const save = async () => {
    setSaving(true);
    try {
      await onSave({
        ...data,
        breakfast_items: split(b),
        lunch_items: split(l),
        dinner_items: split(d),
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>{cap(data.day)} menu</Text>
      <Text style={styles.subLabel}>Breakfast items (comma separated)</Text>
      <TextInput
        testID={`menu-bf-${data.day}`}
        style={styles.input}
        value={b}
        onChangeText={setB}
        placeholder="Idly, Dosa, Sambar"
        placeholderTextColor={colors.textSecondary}
      />
      <Text style={styles.subLabel}>Lunch items</Text>
      <TextInput
        testID={`menu-l-${data.day}`}
        style={styles.input}
        value={l}
        onChangeText={setL}
        placeholder="Rice, Sambar, Rasam"
        placeholderTextColor={colors.textSecondary}
      />
      <Text style={styles.subLabel}>Dinner items</Text>
      <TextInput
        testID={`menu-d-${data.day}`}
        style={styles.input}
        value={d}
        onChangeText={setD}
        placeholder="Chapati, Kurma"
        placeholderTextColor={colors.textSecondary}
      />
      <Button
        testID={`menu-save-${data.day}`}
        label={saving ? "Saving..." : "Save menu"}
        onPress={save}
        loading={saving}
        style={{ marginTop: 8 }}
      />
    </View>
  );
}

// --- Item Qty/Price editor -----------------------------------------------
type DraftItem = {
  id?: string;
  item_name: string;
  meal_type: MealType;
  quantity_per_person: string;
  unit: Unit;
  price_per_unit: string;
  price_unit: Unit;
};

function ItemEditor({
  draft,
  onSave,
  onDelete,
  onCancel,
  isNew,
}: {
  draft: DraftItem;
  onSave: (d: DraftItem) => Promise<void>;
  onDelete?: () => Promise<void>;
  onCancel?: () => void;
  isNew?: boolean;
}) {
  const [d, setD] = useState<DraftItem>(draft);
  const [saving, setSaving] = useState(false);
  return (
    <View style={[styles.card, { gap: 4 }]}>
      <Text style={styles.subLabel}>Item name</Text>
      <TextInput
        testID="ni-name"
        style={styles.input}
        value={d.item_name}
        onChangeText={(t) => setD({ ...d, item_name: t })}
        placeholder="e.g., Idly"
        placeholderTextColor={colors.textSecondary}
      />

      <Text style={styles.subLabel}>Meal</Text>
      <Segmented<MealType>
        testID="ni-meal"
        value={d.meal_type}
        onChange={(v) => setD({ ...d, meal_type: v })}
        options={[
          { value: "breakfast", label: "Breakfast" },
          { value: "lunch", label: "Lunch" },
          { value: "dinner", label: "Dinner" },
        ]}
      />

      <Text style={styles.subLabel}>Quantity per person</Text>
      <View style={{ flexDirection: "row", gap: 6 }}>
        <TextInput
          testID="ni-qty"
          style={[styles.input, { flex: 1 }]}
          value={d.quantity_per_person}
          onChangeText={(t) => setD({ ...d, quantity_per_person: t })}
          keyboardType="decimal-pad"
          placeholder="e.g., 4"
          placeholderTextColor={colors.textSecondary}
        />
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flex: 1.5 }}>
          {UNITS.map((u) => (
            <TouchableOpacity
              key={u}
              testID={`ni-unit-${u}`}
              onPress={() => setD({ ...d, unit: u })}
              style={[styles.unitChip, d.unit === u && { backgroundColor: colors.primary }]}
            >
              <Text style={[styles.unitChipText, d.unit === u && { color: "#fff" }]}>{u}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      <Text style={styles.subLabel}>Price per unit</Text>
      <View style={{ flexDirection: "row", gap: 6 }}>
        <TextInput
          testID="ni-price"
          style={[styles.input, { flex: 1 }]}
          value={d.price_per_unit}
          onChangeText={(t) => setD({ ...d, price_per_unit: t })}
          keyboardType="decimal-pad"
          placeholder="e.g., 50"
          placeholderTextColor={colors.textSecondary}
        />
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flex: 1.5 }}>
          {UNITS.map((u) => (
            <TouchableOpacity
              key={u}
              testID={`ni-priceunit-${u}`}
              onPress={() => setD({ ...d, price_unit: u })}
              style={[
                styles.unitChip,
                d.price_unit === u && { backgroundColor: colors.primary },
              ]}
            >
              <Text
                style={[styles.unitChipText, d.price_unit === u && { color: "#fff" }]}
              >
                {u}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      <View style={{ flexDirection: "row", gap: 8, marginTop: 8 }}>
        <Button
          testID="ni-save"
          label={saving ? "Saving..." : isNew ? "Add item" : "Save"}
          loading={saving}
          onPress={async () => {
            setSaving(true);
            try {
              await onSave(d);
            } finally {
              setSaving(false);
            }
          }}
          style={{ flex: 1 }}
        />
        {onCancel ? (
          <Button
            testID="ni-cancel"
            label="Cancel"
            variant="secondary"
            onPress={onCancel}
            style={{ flex: 1 }}
          />
        ) : null}
      </View>
      {onDelete ? (
        <TouchableOpacity testID="ni-delete" onPress={onDelete} style={styles.deleteRow}>
          <Feather name="trash-2" size={14} color={colors.danger} />
          <Text style={styles.deleteText}>Delete item</Text>
        </TouchableOpacity>
      ) : null}
    </View>
  );
}

// --- Custom Questions editor ---------------------------------------------
function CustomQEditor({ menu, onSave }: { menu: DailyMenu; onSave: (d: DailyMenu) => Promise<void> }) {
  type Slot = "breakfast_custom_question" | "lunch_custom_question" | "dinner_custom_question";

  const initial = (slot: Slot) => {
    const q = menu[slot];
    return {
      text: q?.text || "",
      options: q?.options.join(", ") || "",
    };
  };

  const [b, setB] = useState(initial("breakfast_custom_question"));
  const [l, setL] = useState(initial("lunch_custom_question"));
  const [d, setD] = useState(initial("dinner_custom_question"));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setB(initial("breakfast_custom_question"));
    setL(initial("lunch_custom_question"));
    setD(initial("dinner_custom_question"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [menu]);

  const build = (q: { text: string; options: string }) => {
    if (!q.text.trim()) return null;
    const opts = q.options.split(",").map((s) => s.trim()).filter(Boolean);
    if (opts.length === 0) return null;
    return { text: q.text.trim(), options: opts };
  };

  const save = async () => {
    setSaving(true);
    try {
      await onSave({
        ...menu,
        breakfast_custom_question: build(b),
        lunch_custom_question: build(l),
        dinner_custom_question: build(d),
      });
    } finally {
      setSaving(false);
    }
  };

  const renderSlot = (
    title: string,
    state: { text: string; options: string },
    setState: (s: { text: string; options: string }) => void,
    prefix: string,
  ) => (
    <View>
      <Text style={styles.subLabel}>{title}</Text>
      <TextInput
        testID={`${prefix}-text`}
        style={styles.input}
        value={state.text}
        onChangeText={(t) => setState({ ...state, text: t })}
        placeholder="Question text (leave blank to remove)"
        placeholderTextColor={colors.textSecondary}
      />
      <TextInput
        testID={`${prefix}-options`}
        style={[styles.input, { marginTop: 6 }]}
        value={state.options}
        onChangeText={(t) => setState({ ...state, options: t })}
        placeholder="Options (comma separated, e.g., Yes, No)"
        placeholderTextColor={colors.textSecondary}
      />
    </View>
  );

  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>{cap(menu.day)} custom questions</Text>
      {renderSlot("Breakfast question", b, setB, "cq-breakfast")}
      {renderSlot("Lunch question", l, setL, "cq-lunch")}
      {renderSlot("Dinner question", d, setD, "cq-dinner")}
      <Button
        testID={`cq-save-${menu.day}`}
        label={saving ? "Saving..." : "Save questions"}
        onPress={save}
        loading={saving}
        style={{ marginTop: 10 }}
      />
    </View>
  );
}

// --- Main screen ---------------------------------------------------------
export default function AdminNecessaryInfo() {
  const { token } = useAuth();
  const [tab, setTab] = useState<TabKey>("menu");
  const [day, setDay] = useState<string>("monday");
  const [menus, setMenus] = useState<DailyMenu[]>([]);
  const [items, setItems] = useState<NecessaryItem[]>([]);
  const [editing, setEditing] = useState<DraftItem | null>(null);
  const [adding, setAdding] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState<{
    message: string;
    variant: "success" | "error" | "info";
  } | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [m, n] = await Promise.all([
        api.adminMenuList(token),
        api.adminNecessaryInfo(token),
      ]);
      setMenus(m.days);
      setItems(n.items);
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

  const currentMenu = useMemo(
    () => menus.find((m) => m.day === day) || menus[0],
    [menus, day],
  );

  const saveMenu = async (next: DailyMenu) => {
    if (!token) return;
    try {
      await api.adminMenuUpsert(token, next.day, {
        breakfast_items: next.breakfast_items,
        lunch_items: next.lunch_items,
        dinner_items: next.dinner_items,
        breakfast_custom_question: next.breakfast_custom_question,
        lunch_custom_question: next.lunch_custom_question,
        dinner_custom_question: next.dinner_custom_question,
      });
      setToast({ message: "Saved", variant: "success" });
      await load();
    } catch (e: any) {
      setToast({ message: e?.message || "Save failed", variant: "error" });
    }
  };

  const saveItem = async (d: DraftItem) => {
    if (!token) return;
    const body = {
      item_name: d.item_name.trim(),
      meal_type: d.meal_type,
      quantity_per_person: parseFloat(d.quantity_per_person) || 0,
      unit: d.unit,
      price_per_unit: parseFloat(d.price_per_unit) || 0,
      price_unit: d.price_unit,
    };
    if (!body.item_name) {
      setToast({ message: "Item name required", variant: "error" });
      return;
    }
    try {
      if (d.id) {
        await api.adminNiUpdate(token, d.id, body);
      } else {
        await api.adminNiCreate(token, body);
      }
      setToast({ message: "Item saved", variant: "success" });
      setEditing(null);
      setAdding(false);
      await load();
    } catch (e: any) {
      setToast({ message: e?.message || "Save failed", variant: "error" });
    }
  };

  const deleteItem = async (id: string) => {
    if (!token) return;
    try {
      await api.adminNiDelete(token, id);
      setToast({ message: "Deleted", variant: "info" });
      setEditing(null);
      await load();
    } catch (e: any) {
      setToast({ message: e?.message || "Delete failed", variant: "error" });
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

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <Toast
        testID="ni-toast"
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
            <Text style={styles.title}>Necessary Info</Text>
            <Text style={styles.subtitle}>
              Powers the Dashboard cook quantity and Wastage loss math.
            </Text>
          </View>

          <Segmented<TabKey>
            testID="ni-tab"
            value={tab}
            onChange={setTab}
            options={[
              { value: "menu", label: "Menu", testID: "ni-tab-menu" },
              { value: "items", label: "Qty / Price", testID: "ni-tab-items" },
              { value: "custom", label: "Questions", testID: "ni-tab-custom" },
            ]}
            style={{ marginBottom: spacing.md }}
          />

          {tab === "menu" || tab === "custom" ? (
            <>
              <Text style={styles.subLabel}>Day</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8 }}>
                {DAYS.map((dKey) => (
                  <TouchableOpacity
                    key={dKey}
                    testID={`ni-day-${dKey}`}
                    onPress={() => setDay(dKey)}
                    style={[
                      styles.dayChip,
                      day === dKey && { backgroundColor: colors.primary },
                    ]}
                  >
                    <Text
                      style={[
                        styles.dayChipText,
                        day === dKey && { color: "#fff" },
                      ]}
                    >
                      {cap(dKey).slice(0, 3)}
                    </Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </>
          ) : null}

          {tab === "menu" && currentMenu ? (
            <MenuEditor data={currentMenu} onSave={saveMenu} />
          ) : null}
          {tab === "custom" && currentMenu ? (
            <CustomQEditor menu={currentMenu} onSave={saveMenu} />
          ) : null}

          {tab === "items" ? (
            <>
              {!adding && !editing ? (
                <TouchableOpacity
                  testID="ni-add"
                  onPress={() => {
                    setAdding(true);
                    setEditing({
                      item_name: "",
                      meal_type: "breakfast",
                      quantity_per_person: "",
                      unit: "pieces",
                      price_per_unit: "",
                      price_unit: "pieces",
                    });
                  }}
                  style={styles.addNiBtn}
                >
                  <Feather name="plus" size={16} color={colors.primary} />
                  <Text style={styles.addNiText}>Add item</Text>
                </TouchableOpacity>
              ) : null}

              {editing ? (
                <ItemEditor
                  draft={editing}
                  isNew={adding}
                  onSave={saveItem}
                  onCancel={() => {
                    setEditing(null);
                    setAdding(false);
                  }}
                  onDelete={
                    editing.id
                      ? () => deleteItem(editing.id as string)
                      : undefined
                  }
                />
              ) : null}

              {!editing ? (
                items.length === 0 ? (
                  <View style={styles.card}>
                    <Text style={styles.muted}>No items yet. Tap "Add item" above.</Text>
                  </View>
                ) : (
                  items.map((it) => (
                    <TouchableOpacity
                      key={it.id}
                      testID={`ni-item-${it.id}`}
                      activeOpacity={0.85}
                      style={styles.itemListRow}
                      onPress={() =>
                        setEditing({
                          id: it.id,
                          item_name: it.item_name,
                          meal_type: it.meal_type,
                          quantity_per_person: String(it.quantity_per_person),
                          unit: it.unit,
                          price_per_unit: String(it.price_per_unit),
                          price_unit: it.price_unit,
                        })
                      }
                    >
                      <View style={{ flex: 1 }}>
                        <Text style={styles.itemRowName}>{it.item_name}</Text>
                        <Text style={styles.itemRowSub}>
                          {cap(it.meal_type)} · {it.quantity_per_person} {it.unit}/person · ₹
                          {it.price_per_unit}/{it.price_unit}
                        </Text>
                      </View>
                      <Feather name="chevron-right" size={18} color={colors.textSecondary} />
                    </TouchableOpacity>
                  ))
                )
              ) : null}
            </>
          ) : null}
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

  card: {
    backgroundColor: colors.card,
    borderRadius: radius.xl,
    padding: spacing.md,
    marginBottom: spacing.md,
    ...shadow.card,
  },
  cardTitle: { ...typography.title2, color: colors.textPrimary, marginBottom: 8 },
  subLabel: {
    ...typography.footnote,
    color: colors.textSecondary,
    marginTop: 8,
    marginBottom: 6,
  },
  input: {
    backgroundColor: colors.inputBg,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: colors.textPrimary,
  },

  dayChip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: colors.inputBg,
    borderRadius: 999,
    marginRight: 6,
  },
  dayChipText: { ...typography.caption, color: colors.textPrimary, fontWeight: "700" },

  unitChip: {
    paddingHorizontal: 10,
    paddingVertical: 8,
    backgroundColor: colors.inputBg,
    borderRadius: 8,
    marginRight: 4,
  },
  unitChipText: { ...typography.caption, color: colors.textPrimary, fontWeight: "600" },

  addNiBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 14,
    backgroundColor: colors.primaryLight,
    borderRadius: radius.md,
    marginBottom: spacing.md,
  },
  addNiText: { ...typography.headline, color: colors.primary, fontWeight: "700" },

  itemListRow: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginBottom: 8,
    flexDirection: "row",
    alignItems: "center",
    ...shadow.card,
  },
  itemRowName: { ...typography.headline, color: colors.textPrimary },
  itemRowSub: { ...typography.caption, color: colors.textSecondary, marginTop: 2 },
  muted: { ...typography.subhead, color: colors.textSecondary, textAlign: "center" },

  deleteRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 12,
    marginTop: 6,
  },
  deleteText: { ...typography.subhead, color: colors.danger, fontWeight: "600" },
});

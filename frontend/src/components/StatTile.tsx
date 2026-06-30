// Stat tile — small card showing a number + label. Theme-reactive.

import { Feather } from "@expo/vector-icons";
import React, { useMemo } from "react";
import { StyleSheet, Text, View, ViewStyle } from "react-native";

import { radius, shadow, typography, useTheme, type ThemeColors } from "@/src/theme";

type Props = {
  label: string;
  value: string | number;
  icon?: keyof typeof Feather.glyphMap;
  tone?: "default" | "success" | "danger" | "warning";
  testID?: string;
  style?: ViewStyle;
};

export function StatTile({ label, value, icon, tone = "default", testID, style }: Props) {
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const tint =
    tone === "success" ? c.success
    : tone === "danger" ? c.danger
    : tone === "warning" ? c.warning
    : c.primary;
  return (
    <View testID={testID} style={[styles.tile, style]}>
      <View style={styles.headerRow}>
        {icon ? (
          <View style={[styles.iconBubble, { backgroundColor: tint + "22" }]}>
            <Feather name={icon} size={14} color={tint} />
          </View>
        ) : null}
        <Text style={styles.label} numberOfLines={1}>
          {label}
        </Text>
      </View>
      <Text style={styles.value}>{value}</Text>
    </View>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    tile: {
      backgroundColor: c.card,
      borderRadius: radius.lg,
      padding: 14,
      borderWidth: 1,
      borderColor: c.border,
      ...shadow.card,
      flex: 1,
      minWidth: 140,
    },
    headerRow: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 8 },
    iconBubble: { width: 24, height: 24, borderRadius: 12, alignItems: "center", justifyContent: "center" },
    label: { ...typography.caption, color: c.textSecondary, flex: 1 },
    value: { ...typography.title1, color: c.textPrimary, fontSize: 24 },
  });

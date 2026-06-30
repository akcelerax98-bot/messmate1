// Multi-select / single-select chip — theme-reactive.

import React, { useMemo } from "react";
import { StyleSheet, Text, TouchableOpacity, ViewStyle } from "react-native";

import { radius, typography, useTheme, type ThemeColors } from "@/src/theme";

type Props = {
  label: string;
  selected?: boolean;
  onPress?: () => void;
  testID?: string;
  variant?: "default" | "danger" | "success";
  style?: ViewStyle;
};

export function Chip({ label, selected, onPress, testID, variant = "default", style }: Props) {
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const bg = selected
    ? variant === "danger" ? c.danger
    : variant === "success" ? c.success
    : c.primary
    : c.inputBg;
  const text = selected ? c.textInverse : c.textPrimary;

  return (
    <TouchableOpacity
      testID={testID}
      onPress={onPress}
      activeOpacity={0.85}
      style={[styles.chip, { backgroundColor: bg }, style]}
    >
      <Text style={[styles.label, { color: text }]} numberOfLines={1}>
        {label}
      </Text>
    </TouchableOpacity>
  );
}

const makeStyles = (_c: ThemeColors) =>
  StyleSheet.create({
    chip: {
      height: 36,
      paddingHorizontal: 16,
      borderRadius: radius.pill,
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0,
    },
    label: { ...typography.subhead, fontWeight: "600" },
  });

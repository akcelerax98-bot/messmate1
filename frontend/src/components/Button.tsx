// Shared button — Apple-style filled CTA. Theme-reactive.

import React, { useMemo } from "react";
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TouchableOpacity,
  ViewStyle,
} from "react-native";

import { radius, typography, useTheme, type ThemeColors } from "@/src/theme";

type Variant = "primary" | "secondary" | "ghost" | "danger";

export function Button({
  label,
  onPress,
  variant = "primary",
  loading,
  disabled,
  style,
  testID,
}: {
  label: string;
  onPress?: () => void;
  variant?: Variant;
  loading?: boolean;
  disabled?: boolean;
  style?: ViewStyle;
  testID?: string;
}) {
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const isDisabled = disabled || loading;
  const palette =
    variant === "primary"
      ? { bg: c.primary, text: c.textInverse }
      : variant === "secondary"
        ? { bg: c.primaryLight, text: c.primary }
        : variant === "danger"
          ? { bg: c.danger, text: "#fff" }
          : { bg: "transparent", text: c.primary };

  return (
    <TouchableOpacity
      testID={testID}
      onPress={onPress}
      disabled={isDisabled}
      activeOpacity={0.85}
      style={[
        styles.btn,
        { backgroundColor: palette.bg, opacity: isDisabled ? 0.6 : 1 },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={palette.text} />
      ) : (
        <Text style={[styles.label, { color: palette.text }]}>{label}</Text>
      )}
    </TouchableOpacity>
  );
}

const makeStyles = (_c: ThemeColors) =>
  StyleSheet.create({
    btn: {
      height: 54,
      borderRadius: radius.lg,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: 20,
    },
    label: { ...typography.headline },
  });

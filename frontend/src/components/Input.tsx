// Shared text input — Apple-style soft-grey filled field. Theme-reactive.

import React, { useMemo, useState } from "react";
import { StyleSheet, Text, TextInput, TextInputProps, View } from "react-native";

import { radius, typography, useTheme, type ThemeColors } from "@/src/theme";

type Props = TextInputProps & {
  label?: string;
  error?: string | null;
  testID?: string;
};

export function Input({ label, error, style, testID, ...props }: Props) {
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const [focused, setFocused] = useState(false);
  return (
    <View style={styles.wrap}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      <TextInput
        testID={testID}
        placeholderTextColor={c.textTertiary}
        {...props}
        onFocus={(e) => {
          setFocused(true);
          props.onFocus?.(e);
        }}
        onBlur={(e) => {
          setFocused(false);
          props.onBlur?.(e);
        }}
        style={[
          styles.input,
          focused && { borderColor: c.primary },
          !!error && { borderColor: c.danger },
          style,
        ]}
      />
      {error ? <Text style={styles.errorText}>{error}</Text> : null}
    </View>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    wrap: { marginBottom: 14 },
    label: {
      ...typography.footnote,
      color: c.textSecondary,
      marginBottom: 6,
      marginLeft: 4,
    },
    input: {
      height: 54,
      backgroundColor: c.inputBg,
      borderRadius: radius.md,
      paddingHorizontal: 16,
      fontSize: 16,
      color: c.textPrimary,
      borderWidth: 1,
      borderColor: "transparent",
    },
    errorText: {
      ...typography.caption,
      color: c.danger,
      marginTop: 6,
      marginLeft: 4,
    },
  });

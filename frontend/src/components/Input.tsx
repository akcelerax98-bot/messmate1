// Shared text input — Apple-style soft-grey filled field.

import React, { useState } from "react";
import { StyleSheet, Text, TextInput, TextInputProps, View } from "react-native";

import { colors, radius, typography } from "@/src/theme";

type Props = TextInputProps & {
  label?: string;
  error?: string | null;
  testID?: string;
};

export function Input({ label, error, style, testID, ...props }: Props) {
  const [focused, setFocused] = useState(false);
  return (
    <View style={styles.wrap}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      <TextInput
        testID={testID}
        placeholderTextColor={colors.textSecondary}
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
          focused && { borderColor: colors.primary },
          !!error && { borderColor: colors.danger },
          style,
        ]}
      />
      {error ? <Text style={styles.errorText}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: 14 },
  label: {
    ...typography.footnote,
    color: colors.textSecondary,
    marginBottom: 6,
    marginLeft: 4,
  },
  input: {
    height: 54,
    backgroundColor: colors.inputBg,
    borderRadius: radius.md,
    paddingHorizontal: 16,
    fontSize: 16,
    color: colors.textPrimary,
    borderWidth: 1,
    borderColor: "transparent",
  },
  errorText: {
    ...typography.caption,
    color: colors.danger,
    marginTop: 6,
    marginLeft: 4,
  },
});

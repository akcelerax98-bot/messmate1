// 6-digit OTP input — segmented squares + a single hidden TextInput.
// Theme-reactive, auto-focuses, supports paste.

import React, { useMemo, useRef } from "react";
import {
  Keyboard,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { radius, typography, useTheme, type ThemeColors } from "@/src/theme";

type Props = {
  value: string;
  onChange: (v: string) => void;
  onComplete?: (v: string) => void;
  length?: number;
  autoFocus?: boolean;
  disabled?: boolean;
  testID?: string;
};

export function OtpInput({
  value,
  onChange,
  onComplete,
  length = 6,
  autoFocus = true,
  disabled,
  testID,
}: Props) {
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const inputRef = useRef<TextInput>(null);

  const handleChange = (text: string) => {
    const cleaned = text.replace(/\D/g, "").slice(0, length);
    onChange(cleaned);
    if (cleaned.length === length) {
      onComplete?.(cleaned);
      Keyboard.dismiss();
    }
  };

  const focus = () => {
    if (!disabled) inputRef.current?.focus();
  };

  return (
    <Pressable onPress={focus} testID={testID}>
      <View style={styles.row}>
        {Array.from({ length }).map((_, idx) => {
          const ch = value[idx] || "";
          const filled = !!ch;
          const active = value.length === idx;
          return (
            <View
              key={idx}
              style={[
                styles.box,
                filled && { borderColor: c.primary, backgroundColor: c.card },
                active && !filled && { borderColor: c.primary },
              ]}
            >
              <Text style={styles.digit}>{ch}</Text>
            </View>
          );
        })}
      </View>
      <TextInput
        ref={inputRef}
        value={value}
        onChangeText={handleChange}
        keyboardType="number-pad"
        autoComplete={Platform.OS === "ios" ? "one-time-code" : "sms-otp"}
        textContentType="oneTimeCode"
        maxLength={length}
        autoFocus={autoFocus}
        editable={!disabled}
        style={styles.hidden}
        caretHidden
        selectionColor="transparent"
      />
    </Pressable>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    row: { flexDirection: "row", gap: 8, justifyContent: "space-between" },
    box: {
      width: 48,
      height: 56,
      borderRadius: radius.md,
      borderWidth: 1.5,
      borderColor: c.divider,
      backgroundColor: c.inputBg,
      alignItems: "center",
      justifyContent: "center",
    },
    digit: { ...typography.title2, color: c.textPrimary },
    hidden: {
      position: "absolute",
      width: 1,
      height: 1,
      opacity: 0,
    },
  });

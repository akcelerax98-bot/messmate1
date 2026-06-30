// Horizontal stacked-bar showing like/dislike ratio. Theme-reactive.

import React, { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { typography, useTheme, type ThemeColors } from "@/src/theme";

type Props = {
  likePct: number | null;
  dislikePct: number | null;
  testID?: string;
};

export function LikeDislikeBar({ likePct, dislikePct, testID }: Props) {
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  if (likePct === null && dislikePct === null) {
    return (
      <Text style={styles.empty} testID={testID}>
        No reactions yet
      </Text>
    );
  }
  const lp = likePct ?? 0;
  const dp = dislikePct ?? 0;
  return (
    <View style={styles.wrap} testID={testID}>
      <View style={styles.barRow}>
        {lp > 0 ? <View style={[styles.like, { flex: lp }]} /> : null}
        {dp > 0 ? <View style={[styles.dislike, { flex: dp }]} /> : null}
        {lp + dp < 100 ? <View style={[styles.empty2, { flex: 100 - (lp + dp) }]} /> : null}
      </View>
      <View style={styles.labelRow}>
        <Text style={[styles.label, { color: c.primary }]}>
          {Math.round(lp)}% liked
        </Text>
        <Text style={[styles.label, { color: c.danger }]}>
          {Math.round(dp)}% disliked
        </Text>
      </View>
    </View>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    wrap: { gap: 6 },
    barRow: {
      height: 10,
      borderRadius: 6,
      overflow: "hidden",
      flexDirection: "row",
      backgroundColor: c.inputBg,
    },
    like: { backgroundColor: c.primary },
    dislike: { backgroundColor: c.danger },
    empty2: { backgroundColor: c.inputBg },
    labelRow: { flexDirection: "row", justifyContent: "space-between" },
    label: { ...typography.caption, fontWeight: "600" },
    empty: { ...typography.caption, color: c.textSecondary, fontStyle: "italic" },
  });

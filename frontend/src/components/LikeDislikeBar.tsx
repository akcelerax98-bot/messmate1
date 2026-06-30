// Horizontal stacked-bar showing like/dislike ratio.

import React from "react";
import { StyleSheet, Text, View } from "react-native";

import { colors, typography } from "@/src/theme";

type Props = {
  likePct: number | null;
  dislikePct: number | null;
  testID?: string;
};

export function LikeDislikeBar({ likePct, dislikePct, testID }: Props) {
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
        <Text style={[styles.label, { color: colors.primary }]}>
          {Math.round(lp)}% liked
        </Text>
        <Text style={[styles.label, { color: colors.danger }]}>
          {Math.round(dp)}% disliked
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 6 },
  barRow: {
    height: 10,
    borderRadius: 6,
    overflow: "hidden",
    flexDirection: "row",
    backgroundColor: colors.inputBg,
  },
  like: { backgroundColor: colors.primary },
  dislike: { backgroundColor: colors.danger },
  empty2: { backgroundColor: colors.inputBg },
  labelRow: { flexDirection: "row", justifyContent: "space-between" },
  label: { ...typography.caption, fontWeight: "600" },
  empty: { ...typography.caption, color: colors.textSecondary, fontStyle: "italic" },
});

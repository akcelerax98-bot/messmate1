// Simple bar chart built with View — no external chart deps. Theme-reactive.

import React, { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { typography, useTheme, type ThemeColors } from "@/src/theme";

type Point = { date: string; value: number };

type Props = {
  data: Point[];
  height?: number;
  testID?: string;
};

function shortLabel(iso: string): string {
  return iso.slice(8, 10);
}

export function BarChart({ data, height = 160, testID }: Props) {
  const { c } = useTheme();
  const styles = useMemo(() => makeStyles(c), [c]);
  const max = Math.max(1, ...data.map((d) => d.value));
  const labelEvery = Math.max(1, Math.ceil(data.length / 6));

  return (
    <View testID={testID} style={styles.wrap}>
      <View style={[styles.chart, { height }]}>
        {data.map((p, i) => {
          const h = Math.max(2, (p.value / max) * (height - 24));
          return (
            <View key={p.date + i} style={styles.col}>
              <View style={[styles.bar, { height: h }]} />
            </View>
          );
        })}
      </View>
      <View style={styles.axis}>
        {data.map((p, i) => (
          <Text key={`l-${p.date}-${i}`} style={styles.axisLabel} numberOfLines={1}>
            {i % labelEvery === 0 ? shortLabel(p.date) : ""}
          </Text>
        ))}
      </View>
      <View style={styles.legend}>
        <Text style={styles.legendText}>
          Max {max.toFixed(1)} kg · {data.length} day{data.length === 1 ? "" : "s"}
        </Text>
      </View>
    </View>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    wrap: { gap: 8 },
    chart: {
      flexDirection: "row",
      alignItems: "flex-end",
      gap: 4,
      paddingHorizontal: 4,
    },
    col: { flex: 1, alignItems: "center", justifyContent: "flex-end" },
    bar: {
      width: "100%",
      backgroundColor: c.primary,
      borderRadius: 4,
      minHeight: 3,
    },
    axis: { flexDirection: "row", paddingHorizontal: 4, gap: 4 },
    axisLabel: {
      ...typography.caption,
      color: c.textTertiary,
      flex: 1,
      textAlign: "center",
    },
    legend: { alignItems: "flex-end" },
    legendText: { ...typography.caption, color: c.textSecondary },
  });

import React from "react";
import { StyleSheet } from "react-native";
import { Card, Chip, Text, useTheme} from "react-native-paper";
import { spacing } from "../theme";

const getStatusColor = (status) => {
  switch (status?.toLowerCase()) {
    case "completed":
    case "success":
    case "active":
      return "#10B981";
    case "pending":
    case "processing":
      return "#F59E0B";
    case "failed":
    case "error":
    case "inactive":
      return "#EF4444";
    default:
      return "#6B7280";
  }
};

export default function StatusBadge({
 status, style }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const color = getStatusColor(status);

  return (
    <Chip
      mode="flat"
      style={[styles.chip, { backgroundColor: color + "20" }, style]}
      textStyle={[styles.text, { color }]}
    >
      {status?.toUpperCase()}
    </Chip>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  chip: {
    height: 24,
  },
  text: {
    fontSize: 11,
    fontWeight: "600",
  },
});

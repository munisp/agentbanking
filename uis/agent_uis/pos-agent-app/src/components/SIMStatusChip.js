import React from "react";
import { StyleSheet, TouchableOpacity, View } from "react-native";
import { Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { useSIMStatus } from "../contexts/SIMStatusContext";

function rssiQuality(rssi) {
  if (rssi == null || rssi === 99) return 0;
  return Math.round((Math.min(rssi, 31) / 31) * 100);
}

function dotColor(quality) {
  if (quality >= 60) return "#4ADE80";
  if (quality >= 30) return "#FCD34D";
  return "#F87171";
}

/**
 * Compact chip that lives in the app header.
 * Shows the active carrier (or Wi-Fi) + a coloured signal dot.
 * Tapping it navigates to the SIM Status screen.
 */
export default function SIMStatusChip({
 onPress }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const status = useSIMStatus();

  // Daemon unreachable — show a greyed-out chip so it's always visible.
  if (!status) {
    return (
      <TouchableOpacity onPress={onPress} style={styles.chip} activeOpacity={0.7}>
        <View style={[styles.dot, { backgroundColor: "#9CA3AF" }]} />
        <Icon name="sim-off" size={13} color="#FFFFFF" />
        <Text style={styles.label}>—</Text>
      </TouchableOpacity>
    );
  }

  const { isWifi, activeSlot, readings } = status;
  const active = readings?.[activeSlot];
  const carrier = isWifi ? "Wi-Fi" : (active?.carrier || "SIM");
  const icon = isWifi ? "wifi" : "sim";
  const quality = isWifi ? 80 : rssiQuality(active?.rssi);

  return (
    <TouchableOpacity onPress={onPress} style={styles.chip} activeOpacity={0.7}>
      <View style={[styles.dot, { backgroundColor: dotColor(quality) }]} />
      <Icon name={icon} size={13} color="#FFFFFF" />
      <Text style={styles.label}>{carrier}</Text>
    </TouchableOpacity>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  chip: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(255,255,255,0.18)",
    borderRadius: 12,
    paddingHorizontal: 8,
    paddingVertical: 4,
    gap: 4,
    marginLeft: 8,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  label: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "600",
  },
});

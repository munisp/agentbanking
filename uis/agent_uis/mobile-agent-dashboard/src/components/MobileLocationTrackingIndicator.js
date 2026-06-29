import React from "react";
import { StyleSheet, View } from "react-native";
import { Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

export default function MobileLocationTrackingIndicator({
 status }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  if (!status) return null;

  const getStatusColor = () => {
    if (status.permissionStatus === "granted" && status.isActive) {
      return "#10B981"; // green
    }
    if (status.permissionStatus === "denied") {
      return "#EF4444"; // red
    }
    return "#6B7280"; // gray
  };

  const getStatusText = () => {
    if (status.error) return status.error.substring(0, 12);
    if (status.permissionStatus === "granted" && status.isActive) {
      return "Tracking";
    }
    if (status.permissionStatus === "denied") {
      return "Denied";
    }
    return "Inactive";
  };

  const statusColor = getStatusColor();

  return (
    <View style={styles.container}>
      <View style={[styles.indicator, { borderColor: statusColor }]}>
        <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
        <Icon
          name="map-marker"
          size={14}
          color={statusColor}
          style={styles.icon}
        />
        <Text style={[styles.text, { color: statusColor }]}>
          {getStatusText()}
        </Text>
      </View>
    </View>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    marginHorizontal: 8,
  },
  indicator: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    borderWidth: 1,
    backgroundColor: "rgba(255, 255, 255, 0.95)",
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 4,
  },
  icon: {
    marginRight: 4,
  },
  text: {
    fontSize: 11,
    fontWeight: "600",
  },
});

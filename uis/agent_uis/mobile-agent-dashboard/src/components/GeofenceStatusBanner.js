/**
 * Geofence Status Banner Component
 * Displays a colored banner at the top of the screen showing geofence status
 */

import React from "react";
import { Image, StyleSheet, View } from "react-native";
import { Text, useTheme} from "react-native-paper";

const logo = require("../../assets/logo.png");

export default function GeofenceStatusBanner() {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  // Always show green status with logo
  return (
    <View style={styles.container}>
      <Image source={logo} style={styles.logo} resizeMode="contain" />
      <Text style={styles.text} numberOfLines={1}>
        In Service Area
      </Text>
    </View>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 8,
    paddingHorizontal: 12,
    backgroundColor: "#10B981",
    gap: 8,
  },
  logo: {
    height: 20,
    width: 60,
  },
  text: {
    fontSize: 12,
    fontWeight: "600",
    color: "#FFFFFF",
  },
});

import React from "react";
import { StyleSheet, View } from "react-native";
import { Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { spacing } from "../theme";

export default function EmptyState({

  icon = "inbox",
  title = "No data",
  message = "There is nothing to display here",
}) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  return (
    <View style={styles.container}>
      <Icon name={icon} size={64} color="#D1D5DB" />
      <Text variant="titleMedium" style={styles.title}>
        {title}
      </Text>
      <Text variant="bodyMedium" style={styles.message}>
        {message}
      </Text>
    </View>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xl,
  },
  title: {
    marginTop: spacing.lg,
    fontWeight: "600",
    textAlign: "center",
  },
  message: {
    marginTop: spacing.sm,
    color: "#6B7280",
    textAlign: "center",
  },
});

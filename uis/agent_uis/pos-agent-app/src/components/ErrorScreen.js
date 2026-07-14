import React from "react";
import { StyleSheet, View } from "react-native";
import { Button, Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { spacing } from "../theme";

export default function ErrorScreen({

  title = "Something went wrong",
  message = "Please try again later",
  onRetry,
}) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  return (
    <View style={styles.container}>
      <Icon name="alert-circle-outline" size={64} color="#EF4444" />
      <Text variant="headlineSmall" style={styles.title}>
        {title}
      </Text>
      <Text variant="bodyMedium" style={styles.message}>
        {message}
      </Text>
      {onRetry && (
        <Button mode="contained" onPress={onRetry} style={styles.button}>
          Try Again
        </Button>
      )}
    </View>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xl,
    backgroundColor: "#fff",
  },
  title: {
    marginTop: spacing.lg,
    fontWeight: "bold",
    textAlign: "center",
  },
  message: {
    marginTop: spacing.md,
    color: "#6B7280",
    textAlign: "center",
  },
  button: {
    marginTop: spacing.xl,
  },
});

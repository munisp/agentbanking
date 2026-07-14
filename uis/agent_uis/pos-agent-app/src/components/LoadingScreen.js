import React from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { Text, useTheme} from "react-native-paper";
export default function LoadingScreen({
 message = "Loading..." }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" color={colors.primary} />
      <Text variant="bodyLarge" style={styles.message}>
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
    backgroundColor: "#fff",
  },
  message: {
    marginTop: 16,
    color: "#6B7280",
  },
});

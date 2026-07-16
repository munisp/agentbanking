import React from "react";
import { useTheme } from 'react-native-paper';
import { StyleSheet, Text, View } from "react-native";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
export default function LiveChatSupportScreen() {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  return (
    <View style={styles.container}>
      <Icon
        name="chat-processing"
        size={60}
        color={colors.primary}
        style={{ marginBottom: 24 }}
      />
      <Text style={styles.title}>Live Chat Support</Text>
      <Text style={styles.subtitle}>
        Chat with our support team in real time.
      </Text>
      {/* TODO: Integrate actual chat widget/service here */}
      <View style={styles.placeholderBox}>
        <Text style={styles.placeholderText}>Live chat coming soon...</Text>
      </View>
    </View>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F3F4F6",
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  title: {
    fontSize: 26,
    fontWeight: "bold",
    color: colors.primary,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: "#374151",
    marginBottom: 32,
    textAlign: "center",
  },
  placeholderBox: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 32,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E5E7EB",
    marginTop: 16,
  },
  placeholderText: {
    color: "#9CA3AF",
    fontSize: 16,
  },
});

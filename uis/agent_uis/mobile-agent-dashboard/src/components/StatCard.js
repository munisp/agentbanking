import React from "react";
import { StyleSheet, View } from "react-native";
import { Card, Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { spacing } from "../theme";
import { theme as _appTheme } from '../theme';
const colors = _appTheme.colors;

export default function StatCard({

  icon,
  label,
  value,
  color = colors.primary,
  onPress,
}) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  return (
    <Card style={styles.card} onPress={onPress}>
      <Card.Content style={styles.content}>
        <Icon name={icon} size={24} color={color} />
        <Text variant="headlineSmall" style={styles.value}>
          {value}
        </Text>
        <Text variant="bodySmall" style={styles.label}>
          {label}
        </Text>
      </Card.Content>
    </Card>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  card: {
    flex: 1,
    marginHorizontal: spacing.xs,
  },
  content: {
    alignItems: "center",
  },
  value: {
    fontWeight: "bold",
    marginTop: spacing.sm,
  },
  label: {
    color: "#6B7280",
    marginTop: spacing.xs,
    textAlign: "center",
  },
});

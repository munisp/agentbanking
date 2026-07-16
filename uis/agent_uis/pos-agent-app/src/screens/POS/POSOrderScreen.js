import React from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { Button, Card, Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { spacing, theme } from "../../theme";
export default function POSOrderScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.contentContainer}
    >
      {/* Information Card */}
      <Card style={styles.infoCard}>
        <Card.Content>
          <View style={styles.iconContainer}>
            <Icon name="web" size={80} color={theme.colors.primary} />
          </View>

          <Text variant="headlineSmall" style={styles.title}>
            Order POS Terminal
          </Text>

          <Text variant="bodyLarge" style={styles.message}>
            To order a new POS terminal, please use the web dashboard.
          </Text>

          <View style={styles.featuresContainer}>
            <Text variant="titleSmall" style={styles.featuresTitle}>
              Available Terminal Models:
            </Text>

            <View style={styles.featureItem}>
              <Icon
                name="check-circle"
                size={20}
                color={theme.colors.success}
              />
              <Text variant="bodyMedium" style={styles.featureText}>
                Basic POS - Simple card reader
              </Text>
            </View>

            <View style={styles.featureItem}>
              <Icon
                name="check-circle"
                size={20}
                color={theme.colors.success}
              />
              <Text variant="bodyMedium" style={styles.featureText}>
                Standard POS - Card + QR code
              </Text>
            </View>

            <View style={styles.featureItem}>
              <Icon
                name="check-circle"
                size={20}
                color={theme.colors.success}
              />
              <Text variant="bodyMedium" style={styles.featureText}>
                Advanced POS - Full featured terminal
              </Text>
            </View>
          </View>

          <View style={styles.noticeContainer}>
            <Icon name="information" size={24} color={theme.colors.primary} />
            <Text variant="bodySmall" style={styles.noticeText}>
              The web dashboard provides a complete order form with delivery
              tracking and terminal management features.
            </Text>
          </View>
        </Card.Content>
      </Card>

      {/* Action Buttons */}
      <View style={styles.buttonContainer}>
        <Button
          mode="contained"
          onPress={() => navigation.goBack()}
          style={styles.button}
          icon="arrow-left"
        >
          Back to POS Management
        </Button>
      </View>
    </ScrollView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  contentContainer: {
    padding: spacing.md,
  },
  infoCard: {
    marginBottom: spacing.lg,
  },
  iconContainer: {
    alignItems: "center",
    marginVertical: spacing.lg,
  },
  title: {
    textAlign: "center",
    fontWeight: "bold",
    color: theme.colors.text,
    marginBottom: spacing.md,
  },
  message: {
    textAlign: "center",
    color: theme.colors.textSecondary,
    marginBottom: spacing.lg,
    lineHeight: 24,
  },
  featuresContainer: {
    marginVertical: spacing.lg,
    paddingVertical: spacing.md,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: theme.colors.border,
  },
  featuresTitle: {
    fontWeight: "600",
    marginBottom: spacing.md,
    color: theme.colors.text,
  },
  featureItem: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.sm,
    gap: spacing.sm,
  },
  featureText: {
    flex: 1,
    color: theme.colors.text,
  },
  noticeContainer: {
    flexDirection: "row",
    backgroundColor: theme.colors.primary + "10",
    padding: spacing.md,
    borderRadius: 8,
    marginTop: spacing.md,
    gap: spacing.sm,
  },
  noticeText: {
    flex: 1,
    color: theme.colors.textSecondary,
    lineHeight: 18,
  },
  buttonContainer: {
    gap: spacing.sm,
  },
  button: {
    paddingVertical: spacing.xs,
  },
});

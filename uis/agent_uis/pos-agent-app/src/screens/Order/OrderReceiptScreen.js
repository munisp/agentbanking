import React, { useRef } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { Button, Card, Divider, Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { spacing } from "../../theme";
import { formatCurrency } from "../../utils/formatters";
export default function OrderReceiptScreen({
 route, navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const { order } = route.params;

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString("en-NG", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const printReceipt = () => {
    // TODO: Implement print functionality
    console.log("Printing receipt...");
  };

  const shareReceipt = () => {
    // TODO: Implement share functionality
    console.log("Sharing receipt...");
  };

  return (
    <View style={styles.container}>
      <ScrollView style={styles.content}>
        {/* Success Header */}
        <View style={styles.successHeader}>
          <Icon name="check-circle" size={80} color="#10B981" />
          <Text variant="headlineMedium" style={styles.successTitle}>
            Order Created!
          </Text>
          <Text variant="bodyMedium" style={styles.successSubtitle}>
            Order #{order.id || "N/A"}
          </Text>
        </View>

        {/* Receipt Card */}
        <Card style={styles.receiptCard}>
          <Card.Content>
            {/* Store Information */}
            <View style={styles.storeInfo}>
              <Text variant="titleLarge" style={styles.storeName}>
                {order.store_name}
              </Text>
              <Text variant="bodySmall" style={styles.dateText}>
                {formatDate(order.created_at || new Date())}
              </Text>
            </View>

            <Divider style={styles.divider} />

            {/* Customer Information */}
            {order.customer_name && (
              <>
                <View style={styles.section}>
                  <Text variant="titleSmall" style={styles.sectionTitle}>
                    Customer
                  </Text>
                  <Text variant="bodyMedium">{order.customer_name}</Text>
                  {order.customer_phone && (
                    <Text variant="bodySmall" style={styles.detailText}>
                      {order.customer_phone}
                    </Text>
                  )}
                  {order.customer_email && (
                    <Text variant="bodySmall" style={styles.detailText}>
                      {order.customer_email}
                    </Text>
                  )}
                </View>
                <Divider style={styles.divider} />
              </>
            )}

            {/* Order Items */}
            <View style={styles.section}>
              <Text variant="titleSmall" style={styles.sectionTitle}>
                Items
              </Text>
              {order.items?.map((item, index) => (
                <View key={index} style={styles.itemRow}>
                  <View style={styles.itemDetails}>
                    <Text variant="bodyMedium" style={styles.itemName}>
                      {item.item_name}
                    </Text>
                    <Text variant="bodySmall" style={styles.itemMeta}>
                      {item.quantity} × {formatCurrency(item.unit_price)}
                    </Text>
                  </View>
                  <Text variant="bodyMedium" style={styles.itemTotal}>
                    {formatCurrency(item.subtotal)}
                  </Text>
                </View>
              ))}
            </View>

            <Divider style={styles.divider} />

            {/* Totals */}
            <View style={styles.totalsSection}>
              <View style={styles.totalRow}>
                <Text variant="bodyLarge">Subtotal:</Text>
                <Text variant="bodyLarge">
                  {formatCurrency(order.subtotal || 0)}
                </Text>
              </View>
              <View style={styles.totalRow}>
                <Text variant="bodyMedium">Tax (7.5%):</Text>
                <Text variant="bodyMedium">
                  {formatCurrency(order.tax || 0)}
                </Text>
              </View>
              <Divider style={styles.divider} />
              <View style={styles.totalRow}>
                <Text variant="titleLarge" style={styles.grandTotal}>
                  Total:
                </Text>
                <Text variant="titleLarge" style={styles.grandTotal}>
                  {formatCurrency(order.total || 0)}
                </Text>
              </View>
            </View>

            <Divider style={styles.divider} />

            {/* Payment Method */}
            <View style={styles.paymentInfo}>
              <Text variant="bodySmall" style={styles.paymentLabel}>
                Payment Method
              </Text>
              <Text variant="bodyMedium" style={styles.paymentMethod}>
                {order.payment_method?.toUpperCase() || "CASH"}
              </Text>
            </View>

            {/* Footer */}
            <View style={styles.footer}>
              <Text variant="bodySmall" style={styles.footerText}>
                Thank you for your business!
              </Text>
              <Text variant="bodySmall" style={styles.footerText}>
                Served by: {order.created_by || "Agent"}
              </Text>
            </View>
          </Card.Content>
        </Card>
      </ScrollView>

      {/* Action Buttons */}
      <View style={styles.actions}>
        <Button
          mode="outlined"
          onPress={shareReceipt}
          style={styles.actionButton}
          icon="share-variant"
        >
          Share
        </Button>
        <Button
          mode="outlined"
          onPress={printReceipt}
          style={styles.actionButton}
          icon="printer"
        >
          Print
        </Button>
        <Button
          mode="contained"
          onPress={() => navigation.navigate("Dashboard")}
          style={styles.actionButton}
        >
          Done
        </Button>
      </View>
    </View>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F3F4F6",
  },
  content: {
    flex: 1,
  },
  successHeader: {
    alignItems: "center",
    paddingVertical: spacing.xxl,
    backgroundColor: "#fff",
    marginBottom: spacing.lg,
  },
  successTitle: {
    fontWeight: "700",
    color: "#10B981",
    marginTop: spacing.md,
  },
  successSubtitle: {
    color: "#6B7280",
    marginTop: spacing.xs,
  },
  receiptCard: {
    margin: spacing.lg,
    marginTop: 0,
  },
  storeInfo: {
    alignItems: "center",
    paddingVertical: spacing.md,
  },
  storeName: {
    fontWeight: "700",
    marginBottom: spacing.xs,
  },
  dateText: {
    color: "#6B7280",
  },
  divider: {
    marginVertical: spacing.md,
  },
  section: {
    marginVertical: spacing.sm,
  },
  sectionTitle: {
    fontWeight: "600",
    marginBottom: spacing.sm,
    color: "#374151",
  },
  detailText: {
    color: "#6B7280",
    marginTop: 2,
  },
  itemRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: spacing.sm,
  },
  itemDetails: {
    flex: 1,
  },
  itemName: {
    fontWeight: "500",
  },
  itemMeta: {
    color: "#6B7280",
    marginTop: 2,
  },
  itemTotal: {
    fontWeight: "600",
    marginLeft: spacing.md,
  },
  totalsSection: {
    marginVertical: spacing.sm,
  },
  totalRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: spacing.sm,
  },
  grandTotal: {
    fontWeight: "700",
    color: colors.primary,
  },
  paymentInfo: {
    alignItems: "center",
    paddingVertical: spacing.sm,
  },
  paymentLabel: {
    color: "#6B7280",
    marginBottom: spacing.xs,
  },
  paymentMethod: {
    fontWeight: "600",
    color: "#374151",
  },
  footer: {
    alignItems: "center",
    paddingTop: spacing.lg,
  },
  footerText: {
    color: "#9CA3AF",
    marginBottom: 4,
  },
  actions: {
    flexDirection: "row",
    padding: spacing.lg,
    backgroundColor: "#fff",
    borderTopWidth: 1,
    borderTopColor: "#E5E7EB",
    gap: spacing.sm,
  },
  actionButton: {
    flex: 1,
  },
});

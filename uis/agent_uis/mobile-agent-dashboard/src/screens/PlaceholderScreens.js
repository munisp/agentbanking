// Placeholder screens for remaining features
import React from "react";
import { StyleSheet, View } from "react-native";
import { Text } from "react-native-paper";

const PlaceholderScreen = ({ title }) => ( => {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  return (
  <View style={styles.container}>
    <Text variant="headlineMedium">{title}</Text>
    <Text variant="bodyMedium" style={styles.subtitle}>
      Coming Soon
    </Text>
  </View>
  );
};

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  subtitle: {
    marginTop: 10,
    color: "#6B7280",
  },
});

// Export all placeholder screens
export const POSRequestsScreen = () => (
  <PlaceholderScreen title="POS Requests" />
);
export const POSOrderScreen = () => (
  <PlaceholderScreen title="Order POS Terminal" />
);
export const ReconciliationScreen = () => (
  <PlaceholderScreen title="Reconciliation" />
);
export const ProfileScreen = () => <PlaceholderScreen title="Profile" />;
export const BusinessManagementScreen = () => (
  <PlaceholderScreen title="Business Management" />
);
export const InventoryScreen = () => <PlaceholderScreen title="Inventory" />;
export const LoansScreen = () => <PlaceholderScreen title="Loans" />;
export const BillPaymentScreen = () => (
  <PlaceholderScreen title="Bill Payment" />
);
export const DisputesScreen = () => <PlaceholderScreen title="Disputes" />;
export const NetworkStatusScreen = () => (
  <PlaceholderScreen title="Network Status" />
);
export const CommunicationScreen = () => (
  <PlaceholderScreen title="Communication" />
);
export const StoreMapScreen = () => <PlaceholderScreen title="Store Map" />;
export const AgentHierarchyScreen = () => (
  <PlaceholderScreen title="Agent Hierarchy" />
);
export const CommissionSettlementScreen = () => (
  <PlaceholderScreen title="Commission Settlement" />
);
export const ChartOfAccountsScreen = () => (
  <PlaceholderScreen title="Chart of Accounts" />
);
export const ProjectionsScreen = () => (
  <PlaceholderScreen title="Projections" />
);

export default PlaceholderScreen;

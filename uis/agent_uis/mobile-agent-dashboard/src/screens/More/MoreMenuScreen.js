import React from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { Avatar, Divider, List, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { spacing } from "../../theme";
export default function MoreMenuScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const menuItems = [
    {
      title: "Profile",
      description: "Manage your account",
      icon: "account",
      screen: "Profile",
      color: colors.primary,
    },
    {
      title: "Business Management",
      description: "Manage merchant businesses",
      icon: "store",
      screen: "BusinessManagement",
      color: "#10B981",
    },
    {
      title: "Inventory",
      description: "Track and manage inventory",
      icon: "package-variant",
      screen: "Inventory",
      color: "#F59E0B",
    },
    {
      title: "Loans",
      description: "Apply for and manage loans",
      icon: "cash-multiple",
      screen: "Loans",
      color: "#8B5CF6",
    },
    {
      title: "Bill Payment",
      description: "Pay bills for customers",
      icon: "receipt",
      screen: "BillPayment",
      color: "#EC4899",
    },
    {
      title: "VAT Collections",
      description: "Collect Nigerian VAT payments",
      icon: "calculator",
      screen: "BillPayment",
      color: "#0EA5E9",
    },
    {
      title: "Disputes",
      description: "Manage transaction disputes",
      icon: "alert-circle",
      screen: "Disputes",
      color: "#EF4444",
    },
    {
      title: "Network Status",
      description: "View network performance",
      icon: "network",
      screen: "NetworkStatus",
      color: "#06B6D4",
    },
    {
      title: "Network Predictions",
      description: "View predicted success rates by channel",
      icon: "wifi-strength-4",
      screen: "NetworkPredictions",
      color: "#0EA5E9",
    },
    {
      title: "Messages",
      description: "Communication center",
      icon: "message",
      screen: "Communication",
      color: colors.primary,
    },
    {
      title: "Send Remittance",
      description: "Initiate cross-border remittance transfer",
      icon: "send",
      screen: "SendRemittance",
      color: colors.primary,
    },
    {
      title: "Remittance Verification",
      description: "Verify and disburse remittance transactions",
      icon: "shield-check",
      screen: "RemittanceVerification",
      color: "#06B6D4",
    },
    {
      title: "Store Map",
      description: "Find nearby agents",
      icon: "map-marker",
      screen: "StoreMap",
      color: "#10B981",
    },
    {
      title: "Agent Hierarchy",
      description: "View your agent network",
      icon: "account-network",
      screen: "AgentHierarchy",
      color: "#F59E0B",
    },
    {
      title: "Commission Settlement",
      description: "Track your commissions",
      icon: "cash-check",
      screen: "CommissionSettlement",
      color: "#10B981",
    },
    {
      title: "Loyalty",
      description: "Enroll, earn, spend and view point history",
      icon: "star-circle",
      screen: "Loyalty",
      color: "#F59E0B",
    },
    {
      title: "Chart of Accounts",
      description: "Financial accounts",
      icon: "chart-box",
      screen: "ChartOfAccounts",
      color: "#6366F1",
    },
    {
      title: "Projections",
      description: "Financial forecasts",
      icon: "chart-line",
      screen: "Projections",
      color: "#8B5CF6",
    },
    {
      title: "Settlement",
      description: "Daily transaction settlement",
      icon: "bank-transfer",
      screen: "Settlement",
      color: "#0EA5E9",
    },
    {
      title: "Transaction Reversal",
      description: "Reverse failed or erroneous transactions",
      icon: "undo-variant",
      screen: "Reversal",
      color: "#EF4444",
    },
  ];

  return (
    <ScrollView style={styles.container}>
      {menuItems.map((item, index) => (
        <React.Fragment key={index}>
          <List.Item
            title={item.title}
            description={item.description}
            left={(props) => (
              <Avatar.Icon
                {...props}
                icon={item.icon}
                style={[styles.icon, { backgroundColor: item.color + "20" }]}
                color={item.color}
                size={48}
              />
            )}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => navigation.navigate(item.screen)}
            style={styles.listItem}
          />
          <Divider />
        </React.Fragment>
      ))}

      <View style={styles.footer}>
        <List.Item
          title="Settings"
          left={(props) => <List.Icon {...props} icon="cog" />}
          onPress={() => {}}
        />
        <List.Item
          title="Help & Support"
          left={(props) => <List.Icon {...props} icon="help-circle" />}
          onPress={() => {}}
        />
        <List.Item
          title="Log Out"
          left={(props) => (
            <List.Icon {...props} icon="logout" color="#EF4444" />
          )}
          titleStyle={{ color: "#EF4444" }}
          onPress={() => {}}
        />
      </View>
    </ScrollView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#fff",
  },
  listItem: {
    paddingVertical: spacing.sm,
  },
  icon: {
    marginHorizontal: spacing.md,
  },
  footer: {
    marginTop: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: "#E5E7EB",
    paddingTop: spacing.md,
  },
});

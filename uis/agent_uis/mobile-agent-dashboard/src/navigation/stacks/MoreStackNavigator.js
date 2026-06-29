import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { useTheme } from 'react-native-paper';
import React from "react";
import AgentHierarchyScreen from "../../screens/AgentHierarchy/AgentHierarchyScreen";
import BillPaymentScreen from "../../screens/Bills/BillPaymentScreen";
import BusinessManagementScreen from "../../screens/Business/BusinessManagementScreen";
import ChartOfAccountsScreen from "../../screens/ChartOfAccounts/ChartOfAccountsScreen";
import CommissionSettlementScreen from "../../screens/Commission/CommissionSettlementScreen";
import CommunicationScreen from "../../screens/Communication/CommunicationScreen";
import CreateDisputeScreen from "../../screens/Disputes/CreateDisputeScreen";
import DisputeDetailScreen from "../../screens/Disputes/DisputeDetailScreen";
import DisputesScreen from "../../screens/Disputes/DisputesScreen";
import InventoryScreen from "../../screens/Inventory/InventoryScreen";
import LoansScreen from "../../screens/Loans/LoansScreen";
import MoreMenuScreen from "../../screens/More/MoreMenuScreen";
import NetworkStatusScreen from "../../screens/Network/NetworkStatusScreen";
import ProfileScreen from "../../screens/Profile/ProfileScreen";
import ProjectionsScreen from "../../screens/Projections/ProjectionsScreen";
import ReversalScreen from "../../screens/Reversal/ReversalScreen";
import SettlementScreen from "../../screens/Settlement/SettlementScreen";
import StoreMapScreen from "../../screens/StoreMap/StoreMapScreen";
const Stack = createNativeStackNavigator();

export default function MoreStackNavigator() {
  const { colors } = useTheme();

  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: {
          backgroundColor: colors.primary,
        },
        headerTintColor: "#fff",
        headerTitleStyle: {
          fontWeight: "bold",
        },
      }}
    >
      <Stack.Screen
        name="MoreMenu"
        component={MoreMenuScreen}
        options={{ title: "More" }}
      />
      <Stack.Screen
        name="Profile"
        component={ProfileScreen}
        options={{ title: "Profile" }}
      />
      <Stack.Screen
        name="BusinessManagement"
        component={BusinessManagementScreen}
        options={{ title: "Business Management" }}
      />
      <Stack.Screen
        name="Inventory"
        component={InventoryScreen}
        options={{ title: "Inventory" }}
      />
      <Stack.Screen
        name="Loans"
        component={LoansScreen}
        options={{ title: "Loans" }}
      />
      <Stack.Screen
        name="BillPayment"
        component={BillPaymentScreen}
        options={{ title: "Bill Payment" }}
      />
      <Stack.Screen
        name="Disputes"
        component={DisputesScreen}
        options={{ title: "Disputes" }}
      />
      <Stack.Screen
        name="NetworkStatus"
        component={NetworkStatusScreen}
        options={{ title: "Network Status" }}
      />
      <Stack.Screen
        name="Communication"
        component={CommunicationScreen}
        options={{ title: "Messages" }}
      />
      <Stack.Screen
        name="StoreMap"
        component={StoreMapScreen}
        options={{ title: "Store Map" }}
      />
      <Stack.Screen
        name="AgentHierarchy"
        component={AgentHierarchyScreen}
        options={{ title: "Agent Hierarchy" }}
      />
      <Stack.Screen
        name="CommissionSettlement"
        component={CommissionSettlementScreen}
        options={{ title: "Commission Settlement" }}
      />
      <Stack.Screen
        name="ChartOfAccounts"
        component={ChartOfAccountsScreen}
        options={{ title: "Chart of Accounts" }}
      />
      <Stack.Screen
        name="Projections"
        component={ProjectionsScreen}
        options={{ title: "Projections" }}
      />
      <Stack.Screen
        name="Settlement"
        component={SettlementScreen}
        options={{ title: "Settlement" }}
      />
      <Stack.Screen
        name="Reversal"
        component={ReversalScreen}
        options={{ title: "Transaction Reversal" }}
      />
      <Stack.Screen
        name="CreateDispute"
        component={CreateDisputeScreen}
        options={{ title: "File a Dispute" }}
      />
      <Stack.Screen
        name="DisputeDetail"
        component={DisputeDetailScreen}
        options={{ title: "Dispute Details" }}
      />
    </Stack.Navigator>
  );
}

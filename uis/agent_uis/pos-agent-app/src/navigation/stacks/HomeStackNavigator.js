import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { useTheme } from 'react-native-paper';
import React from "react";
import DashboardScreen from "../../screens/Dashboard/DashboardScreen";
import FloatManagementScreen from "../../screens/Float/FloatManagementScreen";
import QRScannerScreen from "../../screens/QRScanner/QRScannerScreen";
import TransferScreen from "../../screens/Transfer/TransferScreen";

// Settlement screens
import SettlementScreen from "../../screens/Settlement/SettlementScreen";
import EODWizardScreen from "../../screens/Settlement/EODWizardScreen";

// Dispute screens
import DisputesScreen from "../../screens/Disputes/DisputesScreen";
import CreateDisputeScreen from "../../screens/Disputes/CreateDisputeScreen";
import DisputeDetailScreen from "../../screens/Disputes/DisputeDetailScreen";

// Reversal screen
import ReversalScreen from "../../screens/Reversal/ReversalScreen";
const Stack = createNativeStackNavigator();

export default function HomeStackNavigator() {
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
        name="Dashboard"
        component={DashboardScreen}
        options={{ title: "Agent Dashboard" }}
      />
      <Stack.Screen
        name="FloatManagement"
        component={FloatManagementScreen}
        options={{ title: "Float Management" }}
      />
      <Stack.Screen
        name="Transfer"
        component={TransferScreen}
        options={{ title: "Transfer" }}
      />
      <Stack.Screen
        name="QRScanner"
        component={QRScannerScreen}
        options={{ title: "Scan QR Code" }}
      />
      <Stack.Screen
        name="Settlement"
        component={SettlementScreen}
        options={{ title: "Settlement" }}
      />
      <Stack.Screen
        name="EODWizard"
        component={EODWizardScreen}
        options={{ title: "End of Day Wizard" }}
      />
      <Stack.Screen
        name="Disputes"
        component={DisputesScreen}
        options={{ title: "My Disputes" }}
      />
      <Stack.Screen
        name="CreateDispute"
        component={CreateDisputeScreen}
        options={{ title: "File Dispute" }}
      />
      <Stack.Screen
        name="DisputeDetail"
        component={DisputeDetailScreen}
        options={{ title: "Dispute Details" }}
      />
      <Stack.Screen
        name="Reversal"
        component={ReversalScreen}
        options={{ title: "Transaction Reversal" }}
      />
    </Stack.Navigator>
  );
}

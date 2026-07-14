import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { useTheme } from 'react-native-paper';
import React from "react";
import DashboardScreen from "../../screens/Dashboard/DashboardScreen";
import FloatManagementScreen from "../../screens/Float/FloatManagementScreen";
import QRScannerScreen from "../../screens/QRScanner/QRScannerScreen";
import TransferScreen from "../../screens/Transfer/TransferScreen";
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
    </Stack.Navigator>
  );
}

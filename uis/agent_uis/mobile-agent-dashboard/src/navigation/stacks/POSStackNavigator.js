import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { useTheme } from 'react-native-paper';
import React from "react";
import POSDetailsScreen from "../../screens/POS/POSDetailsScreen";
import POSManagementScreen from "../../screens/POS/POSManagementScreen";
import POSOrderScreen from "../../screens/POS/POSOrderScreen";
import POSRequestsScreen from "../../screens/POS/POSRequestsScreen";
const Stack = createNativeStackNavigator();

export default function POSStackNavigator() {
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
        name="POSManagement"
        component={POSManagementScreen}
        options={{ title: "POS Management" }}
      />
      <Stack.Screen
        name="POSDetails"
        component={POSDetailsScreen}
        options={{ title: "POS Details" }}
      />
      <Stack.Screen
        name="POSRequests"
        component={POSRequestsScreen}
        options={{ title: "POS Requests" }}
      />
      <Stack.Screen
        name="POSOrder"
        component={POSOrderScreen}
        options={{ title: "Order POS Terminal" }}
      />
    </Stack.Navigator>
  );
}

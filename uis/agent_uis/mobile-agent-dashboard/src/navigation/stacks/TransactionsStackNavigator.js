import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { useTheme } from 'react-native-paper';
import React from "react";
import ReconciliationScreen from "../../screens/Reconciliation/ReconciliationScreen";
import TransactionDetailScreen from "../../screens/Transactions/TransactionDetailScreen";
import TransactionsScreen from "../../screens/Transactions/TransactionsScreen";
const Stack = createNativeStackNavigator();

export default function TransactionsStackNavigator() {
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
        name="Transactions"
        component={TransactionsScreen}
        options={{ title: "Transactions" }}
      />
      <Stack.Screen
        name="TransactionDetail"
        component={TransactionDetailScreen}
        options={{ title: "Transaction Details" }}
      />
      <Stack.Screen
        name="Reconciliation"
        component={ReconciliationScreen}
        options={{ title: "Reconciliation" }}
      />
    </Stack.Navigator>
  );
}

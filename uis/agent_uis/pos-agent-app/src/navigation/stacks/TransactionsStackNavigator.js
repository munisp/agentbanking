import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { useTheme } from 'react-native-paper';
import React from "react";
import ReconciliationScreen from "../../screens/Reconciliation/ReconciliationScreen";
import TransactionDetailScreen from "../../screens/Transactions/TransactionDetailScreen";
import TransactionsScreen from "../../screens/Transactions/TransactionsScreen";

// New transaction-related screens
import TransactionsScreenV2 from "../../screens/TransactionsScreen";
import TransactionDetailScreenV2 from "../../screens/TransactionDetailScreen";
import TransferTrackingScreen from "../../screens/TransferTrackingScreen";
import SendMoneyScreen from "../../screens/SendMoneyScreen";
import RecurringPaymentsScreen from "../../screens/RecurringPaymentsScreen";
import AddBeneficiaryScreen from "../../screens/AddBeneficiaryScreen";
import BeneficiaryListScreen from "../../screens/BeneficiaryListScreen";
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

      {/* New transaction-related screens */}
      <Stack.Screen
        name="TransactionsV2"
        component={TransactionsScreenV2}
        options={{ title: "Transaction History" }}
      />
      <Stack.Screen
        name="TransactionDetailV2"
        component={TransactionDetailScreenV2}
        options={{ title: "Transaction Details" }}
      />
      <Stack.Screen
        name="TransferTracking"
        component={TransferTrackingScreen}
        options={{ title: "Transfer Tracking" }}
      />
      <Stack.Screen
        name="SendMoney"
        component={SendMoneyScreen}
        options={{ title: "Send Money" }}
      />
      <Stack.Screen
        name="RecurringPayments"
        component={RecurringPaymentsScreen}
        options={{ title: "Recurring Payments" }}
      />
      <Stack.Screen
        name="AddBeneficiary"
        component={AddBeneficiaryScreen}
        options={{ title: "Add Beneficiary" }}
      />
      <Stack.Screen
        name="BeneficiaryList"
        component={BeneficiaryListScreen}
        options={{ title: "Beneficiaries" }}
      />
    </Stack.Navigator>
  );
}

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
import EODWizardScreen from "../../screens/Settlement/EODWizardScreen";
import InventoryScreen from "../../screens/Inventory/InventoryScreen";
import LoansScreen from "../../screens/Loans/LoansScreen";
import MoreMenuScreen from "../../screens/More/MoreMenuScreen";
import NetworkStatusScreen from "../../screens/Network/NetworkStatusScreen";
import SIMStatusScreen from "../../screens/Network/SIMStatusScreen";
import ProfileScreen from "../../screens/Profile/ProfileScreen";
import ProjectionsScreen from "../../screens/Projections/ProjectionsScreen";
import ReversalScreen from "../../screens/Reversal/ReversalScreen";
import SettlementScreen from "../../screens/Settlement/SettlementScreen";
import StoreMapScreen from "../../screens/StoreMap/StoreMapScreen";

// New screens for More stack
import ProfileScreenV2 from "../../screens/ProfileScreen";
import SettingsScreen from "../../screens/SettingsScreen";
import CardsScreen from "../../screens/CardsScreen";
import VirtualCardScreen from "../../screens/VirtualCardScreen";
import CustomerWalletScreen from "../../screens/CustomerWalletScreen";
import MultiCurrencyScreen from "../../screens/MultiCurrencyScreen";
import RateLockScreen from "../../screens/RateLockScreen";
import QRCodeScannerScreen from "../../screens/QRCodeScannerScreen";
import AgentPerformanceScreen from "../../screens/AgentPerformanceScreen";
import AuditExportScreen from "../../screens/AuditExportScreen";
import ComplianceSchedulingScreen from "../../screens/ComplianceSchedulingScreen";
// Flutter-parity screens
import JourneysScreen from "../../screens/JourneysScreen";
import SplashScreen from "../../screens/SplashScreen";
import HistoryScreen from "../../screens/HistoryScreen";
import NotificationScreen from "../../screens/NotificationScreen";
import ReceiptScreen from "../../screens/ReceiptScreen";
import ReferralScreen from "../../screens/ReferralScreen";
import FloatScreen from "../../screens/FloatScreen";
import TransactionMonitorScreen from "../../screens/TransactionMonitorScreen";
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
        name="SIMStatus"
        component={SIMStatusScreen}
        options={{ title: "SIM Status" }}
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
        name="EODWizard"
        component={EODWizardScreen}
        options={{ title: "End of Day Wizard" }}
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

      {/* New screens */}
      <Stack.Screen
        name="ProfileScreenV2"
        component={ProfileScreenV2}
        options={{ title: "Profile" }}
      />
      <Stack.Screen
        name="Settings"
        component={SettingsScreen}
        options={{ title: "Settings" }}
      />
      <Stack.Screen
        name="Cards"
        component={CardsScreen}
        options={{ title: "Cards" }}
      />
      <Stack.Screen
        name="VirtualCard"
        component={VirtualCardScreen}
        options={{ title: "Virtual Card" }}
      />
      <Stack.Screen
        name="CustomerWallet"
        component={CustomerWalletScreen}
        options={{ title: "Customer Wallet" }}
      />
      <Stack.Screen
        name="MultiCurrency"
        component={MultiCurrencyScreen}
        options={{ title: "Multi-Currency" }}
      />
      <Stack.Screen
        name="RateLock"
        component={RateLockScreen}
        options={{ title: "Rate Lock" }}
      />
      <Stack.Screen
        name="QRCodeScanner"
        component={QRCodeScannerScreen}
        options={{ title: "Scan QR Code" }}
      />
      <Stack.Screen
        name="AgentPerformance"
        component={AgentPerformanceScreen}
        options={{ title: "Agent Performance" }}
      />
      <Stack.Screen
        name="AuditExport"
        component={AuditExportScreen}
        options={{ title: "Audit Export" }}
      />
      <Stack.Screen
        name="ComplianceScheduling"
        component={ComplianceSchedulingScreen}
        options={{ title: "Compliance Scheduling" }}
      />
      {/* Flutter-parity screens */}
      <Stack.Screen name="Journeys" component={JourneysScreen} options={{ title: "My Journeys" }} />
      <Stack.Screen name="Splash" component={SplashScreen} options={{ headerShown: false }} />
      <Stack.Screen name="History" component={HistoryScreen} options={{ title: "History" }} />
      <Stack.Screen name="NotificationScreen" component={NotificationScreen} options={{ headerShown: false }} />
      <Stack.Screen name="Receipt" component={ReceiptScreen} options={{ title: "Receipt" }} />
      <Stack.Screen name="Referral" component={ReferralScreen} options={{ title: "Refer & Earn" }} />
      <Stack.Screen name="Float" component={FloatScreen} options={{ title: "Float" }} />
      <Stack.Screen name="TransactionMonitor" component={TransactionMonitorScreen} options={{ title: "Transaction Monitor" }} />
    </Stack.Navigator>
  );
}

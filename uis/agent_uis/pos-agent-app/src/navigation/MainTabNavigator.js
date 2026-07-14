import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React from "react";
import { TouchableOpacity, View } from "react-native";
import { Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { useTheme as useAppTheme } from "../contexts/ThemeContext";

// Components
import GeofenceStatusBanner from "../components/GeofenceStatusBanner";
import SIMStatusChip from "../components/SIMStatusChip";
import { SIMStatusProvider } from "../contexts/SIMStatusContext";

// Dashboard
import DashboardScreen from "../screens/Dashboard/DashboardScreen";

// Cash In and Cash Out
import CashInScreen from "../screens/CashIn/CashInScreen";
import CashOutScreen from "../screens/CashOut/CashOutScreen";

// Screens
import AgentHierarchyScreen from "../screens/AgentHierarchy/AgentHierarchyScreen";
import BillPaymentScreen from "../screens/Bills/BillPaymentScreen";
import BusinessManagementScreen from "../screens/Business/BusinessManagementScreen";
import ChartOfAccountsScreen from "../screens/ChartOfAccounts/ChartOfAccountsScreen";
import CommissionSettlementScreen from "../screens/Commission/CommissionSettlementScreen";
import CommunicationScreen from "../screens/Communication/CommunicationScreen";
import DisputesScreen from "../screens/Disputes/DisputesScreen";
import FloatManagementScreen from "../screens/Float/FloatManagementScreen";
import AddInventoryItemScreen from "../screens/Inventory/AddInventoryItemScreen";
import InventoryScreen from "../screens/Inventory/InventoryScreen";
import LoansScreen from "../screens/Loans/LoansScreen";
import LoyaltyScreen from "../screens/Loyalty/LoyaltyScreen";
import MoreMenuScreen from "../screens/More/MoreMenuScreen";
import NetworkPredictionsScreen from "../screens/Network/NetworkPredictionsScreen";
import NetworkStatusScreen from "../screens/Network/NetworkStatusScreen";
import SIMStatusScreen from "../screens/Network/SIMStatusScreen";
import CreateOrderScreen from "../screens/Order/CreateOrderScreen";
import OrderReceiptScreen from "../screens/Order/OrderReceiptScreen";
import POSDetailsScreen from "../screens/POS/POSDetailsScreen";
import POSManagementScreen from "../screens/POS/POSManagementScreen";
import POSOrderScreen from "../screens/POS/POSOrderScreen";
import POSRequestsScreen from "../screens/POS/POSRequestsScreen";
import ProfileScreen from "../screens/Profile/ProfileScreen";
import ProjectionsScreen from "../screens/Projections/ProjectionsScreen";
import QRGeneratorScreen from "../screens/QRGenerator/QRGeneratorScreen";
import QRScannerScreen from "../screens/QRScanner/QRScannerScreen";
import ReconciliationScreen from "../screens/Reconciliation/ReconciliationScreen";
import RemittanceVerificationScreen from "../screens/Remittance/RemittanceVerificationScreen";
import SettlementScreen from "../screens/Settlement/SettlementScreen";
import EODWizardScreen from "../screens/Settlement/EODWizardScreen";
import CreateDisputeScreen from "../screens/Disputes/CreateDisputeScreen";
import DisputeDetailScreen from "../screens/Disputes/DisputeDetailScreen";
import ReversalScreen from "../screens/Reversal/ReversalScreen";
import SendRemittanceScreen from "../screens/Remittance/SendRemittanceScreen";
import StoreMapScreen from "../screens/StoreMap/StoreMapScreen";
import TransactionDetailScreen from "../screens/Transactions/TransactionDetailScreen";
import TransactionsScreen from "../screens/Transactions/TransactionsScreen";
import TransferScreen from "../screens/Transfer/TransferScreen";

// ── New screens (flat-file additions) ──────────────────────────────────────────
// Auth
import LoginScreenV2 from "../screens/LoginScreen";
import LoginScreenCDP from "../screens/LoginScreen_CDP";
import OnboardingScreenV2 from "../screens/OnboardingScreen";
import RegisterScreen from "../screens/RegisterScreen";

// Dashboard / Home
import DashboardScreenV2 from "../screens/DashboardScreen";

// Profile & Settings
import ProfileScreenV2 from "../screens/ProfileScreen";
import SettingsScreen from "../screens/SettingsScreen";

// Transactions (new variants)
import TransactionsScreenV2 from "../screens/TransactionsScreen";
import TransactionDetailScreenV2 from "../screens/TransactionDetailScreen";
import TransferTrackingScreen from "../screens/TransferTrackingScreen";

// Send Money & Payments
import SendMoneyScreen from "../screens/SendMoneyScreen";
import RecurringPaymentsScreen from "../screens/RecurringPaymentsScreen";

// Beneficiaries
import AddBeneficiaryScreen from "../screens/AddBeneficiaryScreen";
import BeneficiaryListScreen from "../screens/BeneficiaryListScreen";

// Cards & Wallet
import CardsScreen from "../screens/CardsScreen";
import VirtualCardScreen from "../screens/VirtualCardScreen";
import CustomerWalletScreen from "../screens/CustomerWalletScreen";

// QR & Scanning
import QRCodeScannerScreen from "../screens/QRCodeScannerScreen";

// Currency & Rates
import MultiCurrencyScreen from "../screens/MultiCurrencyScreen";
import RateLockScreen from "../screens/RateLockScreen";

// Agent & Compliance
import AgentPerformanceScreen from "../screens/AgentPerformanceScreen";
import AuditExportScreen from "../screens/AuditExportScreen";
import ComplianceSchedulingScreen from "../screens/ComplianceSchedulingScreen";
// ──────────────────────────────────────────────────────────────────────────────

const Stack = createNativeStackNavigator();

export default function MainTabNavigator() {
  const { colors } = useTheme();
  const { tenantConfig } = useAppTheme();

  // Custom header with geofence banner
  const customHeader = ({ navigation, route, options, back }) => {
    return (
      <View>
        <View
          style={{
            backgroundColor: colors.primary,
            paddingTop: 44,
            paddingBottom: 12,
            paddingHorizontal: 16,
            flexDirection: "row",
            alignItems: "center",
          }}
        >
          {back && (
            <TouchableOpacity
              onPress={() => navigation.goBack()}
              style={{ marginRight: 12 }}
            >
              <Icon name="arrow-left" size={24} color="#fff" />
            </TouchableOpacity>
          )}
          <Text
            style={{
              color: "#fff",
              fontSize: 18,
              fontWeight: "bold",
              flex: 1,
            }}
          >
            {options.title || route.name}
          </Text>
          <SIMStatusChip onPress={() => navigation.navigate("SIMStatus")} />
        </View>
        <GeofenceStatusBanner />
      </View>
    );
  };

  return (
    <SIMStatusProvider>
    <Stack.Navigator
      screenOptions={{
        header: customHeader,
      }}
    >
      <Stack.Screen
        name="Dashboard"
        component={DashboardScreen}
        options={{ title: tenantConfig?.name ? `${tenantConfig.name} Agent Dashboard` : "Agent Dashboard" }}
      />
      <Stack.Screen
        name="CashIn"
        component={CashInScreen}
        options={{ title: "Cash In" }}
      />
      <Stack.Screen
        name="CashOut"
        component={CashOutScreen}
        options={{ title: "Cash Out" }}
      />
      <Stack.Screen
        name="Transfer"
        component={TransferScreen}
        options={{ title: "Transfer Money" }}
      />
      <Stack.Screen
        name="SendRemittance"
        component={SendRemittanceScreen}
        options={{ title: "Send Remittance" }}
      />
      <Stack.Screen
        name="RemittanceVerification"
        component={RemittanceVerificationScreen}
        options={{ title: "Remittance Verification" }}
      />
      <Stack.Screen
        name="FloatManagement"
        component={FloatManagementScreen}
        options={{ title: "Float Management" }}
      />
      <Stack.Screen
        name="QRScanner"
        component={QRScannerScreen}
        options={{ title: "Scan QR Code" }}
      />
      <Stack.Screen
        name="QRGenerator"
        component={QRGeneratorScreen}
        options={{ title: "Generate QR Code" }}
      />
      <Stack.Screen
        name="BillPayment"
        component={BillPaymentScreen}
        options={{ title: "Bill Payment" }}
      />
      <Stack.Screen
        name="Transactions"
        component={TransactionsScreen}
        options={{ title: "Transaction History" }}
      />
      <Stack.Screen
        name="TransactionDetail"
        component={TransactionDetailScreen}
        options={{ title: "Transaction Details" }}
      />
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
        name="POSOrders"
        component={POSOrderScreen}
        options={{ title: "POS Orders" }}
      />
      <Stack.Screen
        name="POSRequests"
        component={POSRequestsScreen}
        options={{ title: "POS Requests" }}
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
        name="AddInventoryItem"
        component={AddInventoryItemScreen}
        options={{ title: "Add Inventory Item" }}
      />
      <Stack.Screen
        name="CreateOrder"
        component={CreateOrderScreen}
        options={{ title: "Create Order" }}
      />
      <Stack.Screen
        name="OrderReceipt"
        component={OrderReceiptScreen}
        options={{ title: "Order Receipt" }}
      />
      <Stack.Screen
        name="Loans"
        component={LoansScreen}
        options={{ title: "Loans" }}
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
        name="NetworkPredictions"
        component={NetworkPredictionsScreen}
        options={{ title: "Network Predictions" }}
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
        name="Reconciliation"
        component={ReconciliationScreen}
        options={{ title: "Reconciliation" }}
      />
      <Stack.Screen
        name="Profile"
        component={ProfileScreen}
        options={{ title: "Profile" }}
      />
      <Stack.Screen
        name="Loyalty"
        component={LoyaltyScreen}
        options={{ title: "Loyalty" }}
      />
      <Stack.Screen
        name="More"
        component={MoreMenuScreen}
        options={{ title: "More Options" }}
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
        name="CreateDispute"
        component={CreateDisputeScreen}
        options={{ title: "File a Dispute" }}
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

      {/* ── New screens ────────────────────────────────────────────────────── */}
      {/* Auth */}
      <Stack.Screen
        name="LoginScreenV2"
        component={LoginScreenV2}
        options={{ title: "Login" }}
      />
      <Stack.Screen
        name="LoginScreenCDP"
        component={LoginScreenCDP}
        options={{ title: "Login (CDP)" }}
      />
      <Stack.Screen
        name="OnboardingScreenV2"
        component={OnboardingScreenV2}
        options={{ title: "Onboarding" }}
      />
      <Stack.Screen
        name="Register"
        component={RegisterScreen}
        options={{ title: "Register" }}
      />

      {/* Dashboard / Home */}
      <Stack.Screen
        name="DashboardScreenV2"
        component={DashboardScreenV2}
        options={{ title: "Dashboard" }}
      />

      {/* Profile & Settings */}
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

      {/* Transactions (new variants) */}
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

      {/* Send Money & Payments */}
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

      {/* Beneficiaries */}
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

      {/* Cards & Wallet */}
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

      {/* QR & Scanning */}
      <Stack.Screen
        name="QRCodeScanner"
        component={QRCodeScannerScreen}
        options={{ title: "Scan QR Code" }}
      />

      {/* Currency & Rates */}
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

      {/* Agent & Compliance */}
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
      {/* ─────────────────────────────────────────────────────────────────── */}
    </Stack.Navigator>
    </SIMStatusProvider>
  );
}

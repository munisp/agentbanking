import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React from "react";
import { TouchableOpacity, View } from "react-native";
import { Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { useTheme as useAppTheme } from "../contexts/ThemeContext";
import LiveChatSupportScreen from "../screens/Communication/LiveChatSupportScreen";

// Components
import GeofenceStatusBanner from "../components/GeofenceStatusBanner";
import MobileLocationTrackingIndicator from "../components/MobileLocationTrackingIndicator";

// Hooks
import { useLocationTrackingStatus } from "../hooks/useLocationTrackingStatus";

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
import CreateDisputeScreen from "../screens/Disputes/CreateDisputeScreen";
import DisputeDetailScreen from "../screens/Disputes/DisputeDetailScreen";
import FloatManagementScreen from "../screens/Float/FloatManagementScreen";
import AddInventoryItemScreen from "../screens/Inventory/AddInventoryItemScreen";
import InventoryScreen from "../screens/Inventory/InventoryScreen";
import LoansScreen from "../screens/Loans/LoansScreen";
import LoyaltyScreen from "../screens/Loyalty/LoyaltyScreen";
import MoreMenuScreen from "../screens/More/MoreMenuScreen";
import NetworkPredictionsScreen from "../screens/Network/NetworkPredictionsScreen";
import NetworkStatusScreen from "../screens/Network/NetworkStatusScreen";
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
import SendRemittanceScreen from "../screens/Remittance/SendRemittanceScreen";
import SettlementScreen from "../screens/Settlement/SettlementScreen";
import ReversalScreen from "../screens/Reversal/ReversalScreen";
import StoreMapScreen from "../screens/StoreMap/StoreMapScreen";
import TransactionDetailScreen from "../screens/Transactions/TransactionDetailScreen";
import TransactionsScreen from "../screens/Transactions/TransactionsScreen";
import TransferScreen from "../screens/Transfer/TransferScreen";
// Placeholder imports for new screens
// import InsuranceScreen from "../screens/Insurance/InsuranceScreen";
// import DailyReportScreen from "../screens/DailyReport/DailyReportScreen";
// import MyRewardsScreen from "../screens/MyRewards/MyRewardsScreen";
{
  /* TODO: Implement these screens and import above */
}
{
  /*
      <Stack.Screen
        name="Insurance"
        component={InsuranceScreen}
        options={{ title: "Insurance" }}
      />
      <Stack.Screen
        name="DailyReport"
        component={DailyReportScreen}
        options={{ title: "Daily Report" }}
      />
      <Stack.Screen
        name="MyRewards"
        component={MyRewardsScreen}
        options={{ title: "My Rewards" }}
      />
      */
}

const Stack = createNativeStackNavigator();

export default function MainTabNavigator() {
  const { colors } = useTheme();
  const { tenantConfig } = useAppTheme();

  const locationTrackingStatus = useLocationTrackingStatus();

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
          <MobileLocationTrackingIndicator status={locationTrackingStatus} />
        </View>
        <GeofenceStatusBanner />
      </View>
    );
  };

  return (
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
        name="More"
        component={MoreMenuScreen}
        options={{ title: "More Options" }}
      />
      <Stack.Screen
        name="Loyalty"
        component={LoyaltyScreen}
        options={{ title: "Loyalty" }}
      />
      <Stack.Screen
        name="LiveChatSupport"
        component={LiveChatSupportScreen}
        options={{ title: "Live Chat Support" }}
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
    </Stack.Navigator>
  );
}

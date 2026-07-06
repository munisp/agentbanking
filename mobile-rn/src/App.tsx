/**
 * 54Link Nigerian Remittance — React Native App Entry
 * Full navigation setup with all 191 screens registered.
 * Includes Drawer navigation with categorized groups, BottomTab navigation,
 * and role-based access control.
 */
import React, { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { createDrawerNavigator } from '@react-navigation/drawer';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { ActivityIndicator, View, StatusBar, Text } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import CustomDrawerContent from './navigation/CustomDrawerContent';

// ── Screen imports (191 screens) ──
import 2FAEnabledScreen from './screens/journeys/journey_03_2fa/2FAEnabledScreen';
import 2FAIntroScreen from './screens/journeys/journey_03_2fa/2FAIntroScreen';
import AcceptLoanScreen from './screens/journeys/journey_23_loan/AcceptLoanScreen';
import AccountCreatedScreen from './screens/journeys/journey_17_virtual_account/AccountCreatedScreen';
import AccountDetailsScreen from './screens/journeys/journey_17_virtual_account/AccountDetailsScreen';
import AccountLockedScreen from './screens/journeys/journey_29_security_incident/AccountLockedScreen';
import AccountVerificationScreen from './screens/journeys/journey_18_add_beneficiary/AccountVerificationScreen';
import AddBeneficiaryScreen from './screens/AddBeneficiaryScreen';
import AddCardScreen from './screens/journeys/journey_19_card_management/AddCardScreen';
import AgentPerformanceScreen from './screens/AgentPerformanceScreen';
import AgritechScreen from './screens/AgritechScreen';
import AiCreditScoringScreen from './screens/AiCreditScoringScreen';
import AiCreditScreen from './screens/AiCreditScreen';
import AmountEntryScreen from './screens/journeys/journey_06_nibss_transfer/AmountEntryScreen';
import AnaasScreen from './screens/AnaasScreen';
import ApplicationScreen from './screens/journeys/journey_24_insurance/ApplicationScreen';
import AuditExportScreen from './screens/AuditExportScreen';
import AutoSaveSetupScreen from './screens/journeys/journey_21_savings/AutoSaveSetupScreen';
import BackupCodesScreen from './screens/journeys/journey_03_2fa/BackupCodesScreen';
import BankInstructionsScreen from './screens/journeys/journey_16_wallet_topup/BankInstructionsScreen';
import BeneficiariesScreen from './screens/BeneficiariesScreen';
import BeneficiaryDetailsScreen from './screens/journeys/journey_11_swift/BeneficiaryDetailsScreen';
import BeneficiaryFormScreen from './screens/journeys/journey_18_add_beneficiary/BeneficiaryFormScreen';
import BeneficiaryListScreen from './screens/BeneficiaryListScreen';
import BeneficiaryManagementScreen from './screens/BeneficiaryManagementScreen';
import BeneficiarySavedScreen from './screens/journeys/journey_18_add_beneficiary/BeneficiarySavedScreen';
import BeneficiarySelectionScreen from './screens/journeys/journey_06_nibss_transfer/BeneficiarySelectionScreen';
import BillDetailsScreen from './screens/journeys/journey_08_bill_payment/BillDetailsScreen';
import BillPaymentSuccessScreen from './screens/journeys/journey_08_bill_payment/BillPaymentSuccessScreen';
import BiometricAuthScreen from './screens/BiometricAuthScreen';
import BiometricCaptureScreen from './screens/journeys/journey_02_biometric/BiometricCaptureScreen';
import BiometricIntroScreen from './screens/journeys/journey_02_biometric/BiometricIntroScreen';
import BiometricSetupScreen from './screens/BiometricSetupScreen';
import BlockchainFeesScreen from './screens/journeys/journey_15_stablecoin/BlockchainFeesScreen';
import BnplScreen from './screens/BnplScreen';
import CarbonCreditsScreen from './screens/CarbonCreditsScreen';
import CardDetailsScreen from './screens/journeys/journey_19_card_management/CardDetailsScreen';
import CardListScreen from './screens/journeys/journey_19_card_management/CardListScreen';
import CardsScreen from './screens/CardsScreen';
import ChatBankingScreen from './screens/ChatBankingScreen';
import ComplianceReviewScreen from './screens/journeys/journey_27_aml/ComplianceReviewScreen';
import ComplianceSchedulingScreen from './screens/ComplianceSchedulingScreen';
import ConfirmP2PScreen from './screens/journeys/journey_10_p2p_qr/ConfirmP2PScreen';
import ConversionPreviewScreen from './screens/journeys/journey_13_currency_conversion/ConversionPreviewScreen';
import ConversionSuccessScreen from './screens/journeys/journey_13_currency_conversion/ConversionSuccessScreen';
import CreateGoalScreen from './screens/journeys/journey_21_savings/CreateGoalScreen';
import CreateRecurringScreen from './screens/journeys/journey_07_recurring_payment/CreateRecurringScreen';
import CreditScoringScreen from './screens/journeys/journey_23_loan/CreditScoringScreen';
import CryptoConfirmScreen from './screens/journeys/journey_15_stablecoin/CryptoConfirmScreen';
import CryptoSelectScreen from './screens/journeys/journey_15_stablecoin/CryptoSelectScreen';
import CryptoTrackingScreen from './screens/journeys/journey_15_stablecoin/CryptoTrackingScreen';
import CustomerWalletScreen from './screens/CustomerWalletScreen';
import DashboardScreen from './screens/DashboardScreen';
import DigitalIdentityScreen from './screens/DigitalIdentityScreen';
import DisbursementScreen from './screens/journeys/journey_23_loan/DisbursementScreen';
import DisputeResolutionScreen from './screens/journeys/journey_20_dispute/DisputeResolutionScreen';
import DisputeTrackingScreen from './screens/journeys/journey_20_dispute/DisputeTrackingScreen';
import DocumentRequirementsScreen from './screens/journeys/journey_26_kyc_upgrade/DocumentRequirementsScreen';
import DocumentUploadScreen from './screens/journeys/journey_01_registration/DocumentUploadScreen';
import EducationPaymentsScreen from './screens/EducationPaymentsScreen';
import EnterPhoneScreen from './screens/journeys/journey_09_airtime_topup/EnterPhoneScreen';
import EvidenceScreen from './screens/journeys/journey_20_dispute/EvidenceScreen';
import ExchangeRateScreen from './screens/journeys/journey_11_swift/ExchangeRateScreen';
import ExchangeRatesScreen from './screens/ExchangeRatesScreen';
import FraudAlertScreen from './screens/journeys/journey_28_fraud/FraudAlertScreen';
import FraudResolutionScreen from './screens/journeys/journey_28_fraud/FraudResolutionScreen';
import FreezeCardScreen from './screens/journeys/journey_19_card_management/FreezeCardScreen';
import GenerateQRScreen from './screens/journeys/journey_10_p2p_qr/GenerateQRScreen';
import GetQuoteScreen from './screens/journeys/journey_24_insurance/GetQuoteScreen';
import GoalCreatedScreen from './screens/journeys/journey_21_savings/GoalCreatedScreen';
import GoalDetailsScreen from './screens/journeys/journey_21_savings/GoalDetailsScreen';
import HealthInsuranceScreen from './screens/HealthInsuranceScreen';
import HelpScreen from './screens/HelpScreen';
import IncidentDetectionScreen from './screens/journeys/journey_29_security_incident/IncidentDetectionScreen';
import IncidentInvestigationScreen from './screens/journeys/journey_29_security_incident/IncidentInvestigationScreen';
import IncidentResolvedScreen from './screens/journeys/journey_29_security_incident/IncidentResolvedScreen';
import InsuranceProductsScreen from './screens/journeys/journey_24_insurance/InsuranceProductsScreen';
import InternationalReviewScreen from './screens/journeys/journey_11_swift/InternationalReviewScreen';
import InternationalSendScreen from './screens/journeys/journey_11_swift/InternationalSendScreen';
import InvestmentConfirmScreen from './screens/journeys/journey_22_investment/InvestmentConfirmScreen';
import InvestmentOptionsScreen from './screens/journeys/journey_22_investment/InvestmentOptionsScreen';
import IotSmartPosScreen from './screens/IotSmartPosScreen';
import IotSmartScreen from './screens/IotSmartScreen';
import KYCScreen from './screens/KYCScreen';
import KYCVerificationScreen from './screens/KYCVerificationScreen';
import LinkAccountScreen from './screens/journeys/journey_05_social_login/LinkAccountScreen';
import LoanApplicationScreen from './screens/journeys/journey_23_loan/LoanApplicationScreen';
import LoanOfferScreen from './screens/journeys/journey_23_loan/LoanOfferScreen';
import LoginScreen from './screens/LoginScreen';
import LoginScreen_CDP from './screens/LoginScreen_CDP';
import LoginSuccessScreen from './screens/journeys/journey_05_social_login/LoginSuccessScreen';
import LoyaltyProgramScreen from './screens/LoyaltyProgramScreen';
import MultiCurrencyScreen from './screens/MultiCurrencyScreen';
import NewPasswordScreen from './screens/journeys/journey_04_password_reset/NewPasswordScreen';
import NfcTapScreen from './screens/NfcTapScreen';
import NfcTapToPayScreen from './screens/NfcTapToPayScreen';
import NotificationPreferencesScreen from './screens/NotificationPreferencesScreen';
import NotificationsScreen from './screens/NotificationsScreen';
import OAuthCallbackScreen from './screens/journeys/journey_05_social_login/OAuthCallbackScreen';
import OTPVerificationScreen from './screens/journeys/journey_01_registration/OTPVerificationScreen';
import OnboardingScreen from './screens/OnboardingScreen';
import OpenBankingScreen from './screens/OpenBankingScreen';
import P2PSuccessScreen from './screens/journeys/journey_10_p2p_qr/P2PSuccessScreen';
import PAPSSConfirmScreen from './screens/journeys/journey_14_papss/PAPSSConfirmScreen';
import PAPSSDestinationScreen from './screens/journeys/journey_14_papss/PAPSSDestinationScreen';
import PAPSSQuoteScreen from './screens/journeys/journey_14_papss/PAPSSQuoteScreen';
import PAPSSSuccessScreen from './screens/journeys/journey_14_papss/PAPSSSuccessScreen';
import PaymentConfirmScreen from './screens/journeys/journey_08_bill_payment/PaymentConfirmScreen';
import PaymentMethodsScreen from './screens/PaymentMethodsScreen';
import PaymentProcessingScreen from './screens/journeys/journey_16_wallet_topup/PaymentProcessingScreen';
import PaymentRetryScreen from './screens/PaymentRetryScreen';
import PayrollScreen from './screens/PayrollScreen';
import PensionScreen from './screens/PensionScreen';
import PinSetupScreen from './screens/PinSetupScreen';
import PolicyIssuedScreen from './screens/journeys/journey_24_insurance/PolicyIssuedScreen';
import PortfolioSetupScreen from './screens/journeys/journey_22_investment/PortfolioSetupScreen';
import ProcessingScreen from './screens/journeys/journey_06_nibss_transfer/ProcessingScreen';
import ProfileScreen from './screens/ProfileScreen';
import ProofUploadScreen from './screens/journeys/journey_26_kyc_upgrade/ProofUploadScreen';
import PurposeComplianceScreen from './screens/journeys/journey_11_swift/PurposeComplianceScreen';
import QRCodeScannerScreen from './screens/QRCodeScannerScreen';
import QRCodeScreen from './screens/journeys/journey_03_2fa/QRCodeScreen';
import RaiseDisputeScreen from './screens/journeys/journey_20_dispute/RaiseDisputeScreen';
import RateCalculatorScreen from './screens/RateCalculatorScreen';
import RateLockScreen from './screens/RateLockScreen';
import ReceiveMoneyScreen from './screens/ReceiveMoneyScreen';
import RecurringListScreen from './screens/journeys/journey_07_recurring_payment/RecurringListScreen';
import RecurringPaymentsScreen from './screens/RecurringPaymentsScreen';
import RedeemConfirmScreen from './screens/journeys/journey_25_rewards/RedeemConfirmScreen';
import RedemptionOptionsScreen from './screens/journeys/journey_25_rewards/RedemptionOptionsScreen';
import RedemptionSuccessScreen from './screens/journeys/journey_25_rewards/RedemptionSuccessScreen';
import ReferralProgramScreen from './screens/ReferralProgramScreen';
import RegisterScreen from './screens/RegisterScreen';
import RegistrationFormScreen from './screens/journeys/journey_01_registration/RegistrationFormScreen';
import ReportGenerationScreen from './screens/journeys/journey_30_reporting/ReportGenerationScreen';
import ReportPreviewScreen from './screens/journeys/journey_30_reporting/ReportPreviewScreen';
import ReportSubmissionScreen from './screens/journeys/journey_30_reporting/ReportSubmissionScreen';
import RequestResetScreen from './screens/journeys/journey_04_password_reset/RequestResetScreen';
import RequestVirtualAccountScreen from './screens/journeys/journey_17_virtual_account/RequestVirtualAccountScreen';
import ResetSuccessScreen from './screens/journeys/journey_04_password_reset/ResetSuccessScreen';
import ReviewConfirmScreen from './screens/journeys/journey_06_nibss_transfer/ReviewConfirmScreen';
import RewardsBalanceScreen from './screens/journeys/journey_25_rewards/RewardsBalanceScreen';
import RiskAssessmentScreen from './screens/journeys/journey_22_investment/RiskAssessmentScreen';
import SatelliteScreen from './screens/SatelliteScreen';
import SavingsGoalsScreen from './screens/SavingsGoalsScreen';
import ScanQRScreen from './screens/journeys/journey_10_p2p_qr/ScanQRScreen';
import ScheduleConfirmationScreen from './screens/journeys/journey_07_recurring_payment/ScheduleConfirmationScreen';
import SecurityChallengeScreen from './screens/journeys/journey_28_fraud/SecurityChallengeScreen';
import SecuritySettingsScreen from './screens/SecuritySettingsScreen';
import SelectBillerScreen from './screens/journeys/journey_08_bill_payment/SelectBillerScreen';
import SelectCurrenciesScreen from './screens/journeys/journey_13_currency_conversion/SelectCurrenciesScreen';
import SelectPackageScreen from './screens/journeys/journey_09_airtime_topup/SelectPackageScreen';
import SelectProviderScreen from './screens/journeys/journey_09_airtime_topup/SelectProviderScreen';
import SendMoneyHomeScreen from './screens/journeys/journey_06_nibss_transfer/SendMoneyHomeScreen';
import SendMoneyScreen from './screens/SendMoneyScreen';
import SettingsScreen from './screens/SettingsScreen';
import SetupCompleteScreen from './screens/journeys/journey_02_biometric/SetupCompleteScreen';
import SocialLoginOptionsScreen from './screens/journeys/journey_05_social_login/SocialLoginOptionsScreen';
import StablecoinScreen from './screens/StablecoinScreen';
import SuccessScreen from './screens/journeys/journey_01_registration/SuccessScreen';
import SuperAppScreen from './screens/SuperAppScreen';
import SupportScreen from './screens/SupportScreen';
import SuspiciousActivityScreen from './screens/journeys/journey_27_aml/SuspiciousActivityScreen';
import TestAuthScreen from './screens/journeys/journey_02_biometric/TestAuthScreen';
import TierOverviewScreen from './screens/journeys/journey_26_kyc_upgrade/TierOverviewScreen';
import TokenizedAssetsScreen from './screens/TokenizedAssetsScreen';
import TopupAmountScreen from './screens/journeys/journey_16_wallet_topup/TopupAmountScreen';
import TopupMethodsScreen from './screens/journeys/journey_16_wallet_topup/TopupMethodsScreen';
import TopupSuccessScreen from './screens/journeys/journey_09_airtime_topup/TopupSuccessScreen';
import TrackingScreen from './screens/journeys/journey_11_swift/TrackingScreen';
import TransactionDetailScreen from './screens/TransactionDetailScreen';
import TransactionDetailsScreen from './screens/TransactionDetailsScreen';
import TransactionHistoryScreen from './screens/TransactionHistoryScreen';
import TransactionMonitorScreen from './screens/journeys/journey_27_aml/TransactionMonitorScreen';
import TransactionSuccessScreen from './screens/journeys/journey_06_nibss_transfer/TransactionSuccessScreen';
import TransactionsScreen from './screens/TransactionsScreen';
import TransferTrackingScreen from './screens/TransferTrackingScreen';
import UnderReviewScreen from './screens/journeys/journey_26_kyc_upgrade/UnderReviewScreen';
import VerifyIdentityScreen from './screens/journeys/journey_04_password_reset/VerifyIdentityScreen';
import VerifyTOTPScreen from './screens/journeys/journey_03_2fa/VerifyTOTPScreen';
import VideoKYCScreen from './screens/journeys/journey_26_kyc_upgrade/VideoKYCScreen';
import VirtualCardScreen from './screens/VirtualCardScreen';
import WalletAddressScreen from './screens/journeys/journey_15_stablecoin/WalletAddressScreen';
import WalletScreen from './screens/WalletScreen';
import WearablePaymentsScreen from './screens/WearablePaymentsScreen';
import WearableScreen from './screens/WearableScreen';
import WelcomeScreen from './screens/journeys/journey_01_registration/WelcomeScreen';
import WiseConfirmScreen from './screens/journeys/journey_12_wise/WiseConfirmScreen';
import WiseCorridorScreen from './screens/journeys/journey_12_wise/WiseCorridorScreen';
import WiseQuoteScreen from './screens/journeys/journey_12_wise/WiseQuoteScreen';
import WiseTrackingScreen from './screens/journeys/journey_12_wise/WiseTrackingScreen';

// ── Type definitions ──
export type RootStackParamList = {
  2FAEnabledScreen: undefined;
  2FAIntroScreen: undefined;
  AcceptLoanScreen: undefined;
  AccountCreatedScreen: undefined;
  AccountDetailsScreen: undefined;
  AccountLockedScreen: undefined;
  AccountVerificationScreen: undefined;
  AddBeneficiaryScreen: undefined;
  AddCardScreen: undefined;
  AgentPerformanceScreen: undefined;
  AgritechScreen: undefined;
  AiCreditScoringScreen: undefined;
  AiCreditScreen: undefined;
  AmountEntryScreen: undefined;
  AnaasScreen: undefined;
  ApplicationScreen: undefined;
  AuditExportScreen: undefined;
  AutoSaveSetupScreen: undefined;
  BackupCodesScreen: undefined;
  BankInstructionsScreen: undefined;
  BeneficiariesScreen: undefined;
  BeneficiaryDetailsScreen: undefined;
  BeneficiaryFormScreen: undefined;
  BeneficiaryListScreen: undefined;
  BeneficiaryManagementScreen: undefined;
  BeneficiarySavedScreen: undefined;
  BeneficiarySelectionScreen: undefined;
  BillDetailsScreen: undefined;
  BillPaymentSuccessScreen: undefined;
  BiometricAuthScreen: undefined;
  BiometricCaptureScreen: undefined;
  BiometricIntroScreen: undefined;
  BiometricSetupScreen: undefined;
  BlockchainFeesScreen: undefined;
  BnplScreen: undefined;
  CarbonCreditsScreen: undefined;
  CardDetailsScreen: undefined;
  CardListScreen: undefined;
  CardsScreen: undefined;
  ChatBankingScreen: undefined;
  ComplianceReviewScreen: undefined;
  ComplianceSchedulingScreen: undefined;
  ConfirmP2PScreen: undefined;
  ConversionPreviewScreen: undefined;
  ConversionSuccessScreen: undefined;
  CreateGoalScreen: undefined;
  CreateRecurringScreen: undefined;
  CreditScoringScreen: undefined;
  CryptoConfirmScreen: undefined;
  CryptoSelectScreen: undefined;
  CryptoTrackingScreen: undefined;
  CustomerWalletScreen: undefined;
  DashboardScreen: undefined;
  DigitalIdentityScreen: undefined;
  DisbursementScreen: undefined;
  DisputeResolutionScreen: undefined;
  DisputeTrackingScreen: undefined;
  DocumentRequirementsScreen: undefined;
  DocumentUploadScreen: undefined;
  EducationPaymentsScreen: undefined;
  EnterPhoneScreen: undefined;
  EvidenceScreen: undefined;
  ExchangeRateScreen: undefined;
  ExchangeRatesScreen: undefined;
  FraudAlertScreen: undefined;
  FraudResolutionScreen: undefined;
  FreezeCardScreen: undefined;
  GenerateQRScreen: undefined;
  GetQuoteScreen: undefined;
  GoalCreatedScreen: undefined;
  GoalDetailsScreen: undefined;
  HealthInsuranceScreen: undefined;
  HelpScreen: undefined;
  IncidentDetectionScreen: undefined;
  IncidentInvestigationScreen: undefined;
  IncidentResolvedScreen: undefined;
  InsuranceProductsScreen: undefined;
  InternationalReviewScreen: undefined;
  InternationalSendScreen: undefined;
  InvestmentConfirmScreen: undefined;
  InvestmentOptionsScreen: undefined;
  IotSmartPosScreen: undefined;
  IotSmartScreen: undefined;
  KYCScreen: undefined;
  KYCVerificationScreen: undefined;
  LinkAccountScreen: undefined;
  LoanApplicationScreen: undefined;
  LoanOfferScreen: undefined;
  LoginScreen: undefined;
  LoginScreen_CDP: undefined;
  LoginSuccessScreen: undefined;
  LoyaltyProgramScreen: undefined;
  MultiCurrencyScreen: undefined;
  NewPasswordScreen: undefined;
  NfcTapScreen: undefined;
  NfcTapToPayScreen: undefined;
  NotificationPreferencesScreen: undefined;
  NotificationsScreen: undefined;
  OAuthCallbackScreen: undefined;
  OTPVerificationScreen: undefined;
  OnboardingScreen: undefined;
  OpenBankingScreen: undefined;
  P2PSuccessScreen: undefined;
  PAPSSConfirmScreen: undefined;
  PAPSSDestinationScreen: undefined;
  PAPSSQuoteScreen: undefined;
  PAPSSSuccessScreen: undefined;
  PaymentConfirmScreen: undefined;
  PaymentMethodsScreen: undefined;
  PaymentProcessingScreen: undefined;
  PaymentRetryScreen: undefined;
  PayrollScreen: undefined;
  PensionScreen: undefined;
  PinSetupScreen: undefined;
  PolicyIssuedScreen: undefined;
  PortfolioSetupScreen: undefined;
  ProcessingScreen: undefined;
  ProfileScreen: undefined;
  ProofUploadScreen: undefined;
  PurposeComplianceScreen: undefined;
  QRCodeScannerScreen: undefined;
  QRCodeScreen: undefined;
  RaiseDisputeScreen: undefined;
  RateCalculatorScreen: undefined;
  RateLockScreen: undefined;
  ReceiveMoneyScreen: undefined;
  RecurringListScreen: undefined;
  RecurringPaymentsScreen: undefined;
  RedeemConfirmScreen: undefined;
  RedemptionOptionsScreen: undefined;
  RedemptionSuccessScreen: undefined;
  ReferralProgramScreen: undefined;
  RegisterScreen: undefined;
  RegistrationFormScreen: undefined;
  ReportGenerationScreen: undefined;
  ReportPreviewScreen: undefined;
  ReportSubmissionScreen: undefined;
  RequestResetScreen: undefined;
  RequestVirtualAccountScreen: undefined;
  ResetSuccessScreen: undefined;
  ReviewConfirmScreen: undefined;
  RewardsBalanceScreen: undefined;
  RiskAssessmentScreen: undefined;
  SatelliteScreen: undefined;
  SavingsGoalsScreen: undefined;
  ScanQRScreen: undefined;
  ScheduleConfirmationScreen: undefined;
  SecurityChallengeScreen: undefined;
  SecuritySettingsScreen: undefined;
  SelectBillerScreen: undefined;
  SelectCurrenciesScreen: undefined;
  SelectPackageScreen: undefined;
  SelectProviderScreen: undefined;
  SendMoneyHomeScreen: undefined;
  SendMoneyScreen: undefined;
  SettingsScreen: undefined;
  SetupCompleteScreen: undefined;
  SocialLoginOptionsScreen: undefined;
  StablecoinScreen: undefined;
  SuccessScreen: undefined;
  SuperAppScreen: undefined;
  SupportScreen: undefined;
  SuspiciousActivityScreen: undefined;
  TestAuthScreen: undefined;
  TierOverviewScreen: undefined;
  TokenizedAssetsScreen: undefined;
  TopupAmountScreen: undefined;
  TopupMethodsScreen: undefined;
  TopupSuccessScreen: undefined;
  TrackingScreen: undefined;
  TransactionDetailScreen: undefined;
  TransactionDetailsScreen: undefined;
  TransactionHistoryScreen: undefined;
  TransactionMonitorScreen: undefined;
  TransactionSuccessScreen: undefined;
  TransactionsScreen: undefined;
  TransferTrackingScreen: undefined;
  UnderReviewScreen: undefined;
  VerifyIdentityScreen: undefined;
  VerifyTOTPScreen: undefined;
  VideoKYCScreen: undefined;
  VirtualCardScreen: undefined;
  WalletAddressScreen: undefined;
  WalletScreen: undefined;
  WearablePaymentsScreen: undefined;
  WearableScreen: undefined;
  WelcomeScreen: undefined;
  WiseConfirmScreen: undefined;
  WiseCorridorScreen: undefined;
  WiseQuoteScreen: undefined;
  WiseTrackingScreen: undefined;
  DrawerHome: undefined;
  Onboarding: undefined;
  Login: undefined;
  Register: undefined;
  PinSetup: undefined;
  BiometricSetup: undefined;
  HomeTab: undefined;
  HistoryTab: undefined;
  WalletTab: undefined;
  AlertsTab: undefined;
  ProfileTab: undefined;
  Main: undefined;
};

const Stack = createStackNavigator<RootStackParamList>();
const Drawer = createDrawerNavigator();
const BottomTab = createBottomTabNavigator();

const AUTH_TOKEN_KEY = 'jwt_token';

function BottomTabNavigator() {
  return (
    <BottomTab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarStyle: { backgroundColor: '#0f172a', borderTopColor: '#1e293b' },
        tabBarActiveTintColor: '#3b82f6',
        tabBarInactiveTintColor: '#64748b',
      }}
    >
      <BottomTab.Screen
        name="HomeTab"
        component={DashboardScreen}
        options={{ tabBarLabel: 'Home', tabBarIcon: ({color}) => <Text style={{color, fontSize: 18}}>🏠</Text> }}
      />
      <BottomTab.Screen
        name="HistoryTab"
        component={TransactionHistoryScreen}
        options={{ tabBarLabel: 'History', tabBarIcon: ({color}) => <Text style={{color, fontSize: 18}}>📋</Text> }}
      />
      <BottomTab.Screen
        name="WalletTab"
        component={WalletScreen}
        options={{ tabBarLabel: 'Wallet', tabBarIcon: ({color}) => <Text style={{color, fontSize: 18}}>💰</Text> }}
      />
      <BottomTab.Screen
        name="AlertsTab"
        component={NotificationsScreen}
        options={{ tabBarLabel: 'Alerts', tabBarIcon: ({color}) => <Text style={{color, fontSize: 18}}>🔔</Text> }}
      />
      <BottomTab.Screen
        name="ProfileTab"
        component={ProfileScreen}
        options={{ tabBarLabel: 'Profile', tabBarIcon: ({color}) => <Text style={{color, fontSize: 18}}>👤</Text> }}
      />
    </BottomTab.Navigator>
  );
}

function DrawerNavigator() {
  return (
    <Drawer.Navigator
      drawerContent={(props) => (
        <CustomDrawerContent
          {...props}
          userRole="agent"
          userName="Agent"
          userEmail=""
        />
      )}
      screenOptions={{
        headerStyle: { backgroundColor: '#0f172a' },
        headerTintColor: '#f8fafc',
        headerTitleStyle: { fontWeight: '600' },
        drawerStyle: { backgroundColor: '#0f172a', width: 300 },
      }}
    >
      <Drawer.Screen
        name="Main"
        component={BottomTabNavigator}
        options={{ title: '54Link POS' }}
      />
      <Drawer.Screen name="2FAEnabledScreen" component={2FAEnabledScreen} options={{ title: "2FAEnabled" }} />
      <Drawer.Screen name="2FAIntroScreen" component={2FAIntroScreen} options={{ title: "2FAIntro" }} />
      <Drawer.Screen name="AcceptLoanScreen" component={AcceptLoanScreen} options={{ title: "AcceptLoan" }} />
      <Drawer.Screen name="AccountCreatedScreen" component={AccountCreatedScreen} options={{ title: "AccountCreated" }} />
      <Drawer.Screen name="AccountDetailsScreen" component={AccountDetailsScreen} options={{ title: "AccountDetails" }} />
      <Drawer.Screen name="AccountLockedScreen" component={AccountLockedScreen} options={{ title: "AccountLocked" }} />
      <Drawer.Screen name="AccountVerificationScreen" component={AccountVerificationScreen} options={{ title: "AccountVerification" }} />
      <Drawer.Screen name="AddBeneficiaryScreen" component={AddBeneficiaryScreen} options={{ title: "AddBeneficiary" }} />
      <Drawer.Screen name="AddCardScreen" component={AddCardScreen} options={{ title: "AddCard" }} />
      <Drawer.Screen name="AgentPerformanceScreen" component={AgentPerformanceScreen} options={{ title: "AgentPerformance" }} />
      <Drawer.Screen name="AgritechScreen" component={AgritechScreen} options={{ title: "Agritech" }} />
      <Drawer.Screen name="AiCreditScoringScreen" component={AiCreditScoringScreen} options={{ title: "AiCreditScoring" }} />
      <Drawer.Screen name="AiCreditScreen" component={AiCreditScreen} options={{ title: "AiCredit" }} />
      <Drawer.Screen name="AmountEntryScreen" component={AmountEntryScreen} options={{ title: "AmountEntry" }} />
      <Drawer.Screen name="AnaasScreen" component={AnaasScreen} options={{ title: "Anaas" }} />
      <Drawer.Screen name="ApplicationScreen" component={ApplicationScreen} options={{ title: "Application" }} />
      <Drawer.Screen name="AuditExportScreen" component={AuditExportScreen} options={{ title: "AuditExport" }} />
      <Drawer.Screen name="AutoSaveSetupScreen" component={AutoSaveSetupScreen} options={{ title: "AutoSaveSetup" }} />
      <Drawer.Screen name="BackupCodesScreen" component={BackupCodesScreen} options={{ title: "BackupCodes" }} />
      <Drawer.Screen name="BankInstructionsScreen" component={BankInstructionsScreen} options={{ title: "BankInstructions" }} />
      <Drawer.Screen name="BeneficiariesScreen" component={BeneficiariesScreen} options={{ title: "Beneficiaries" }} />
      <Drawer.Screen name="BeneficiaryDetailsScreen" component={BeneficiaryDetailsScreen} options={{ title: "BeneficiaryDetails" }} />
      <Drawer.Screen name="BeneficiaryFormScreen" component={BeneficiaryFormScreen} options={{ title: "BeneficiaryForm" }} />
      <Drawer.Screen name="BeneficiaryListScreen" component={BeneficiaryListScreen} options={{ title: "BeneficiaryList" }} />
      <Drawer.Screen name="BeneficiaryManagementScreen" component={BeneficiaryManagementScreen} options={{ title: "BeneficiaryManagement" }} />
      <Drawer.Screen name="BeneficiarySavedScreen" component={BeneficiarySavedScreen} options={{ title: "BeneficiarySaved" }} />
      <Drawer.Screen name="BeneficiarySelectionScreen" component={BeneficiarySelectionScreen} options={{ title: "BeneficiarySelection" }} />
      <Drawer.Screen name="BillDetailsScreen" component={BillDetailsScreen} options={{ title: "BillDetails" }} />
      <Drawer.Screen name="BillPaymentSuccessScreen" component={BillPaymentSuccessScreen} options={{ title: "BillPaymentSuccess" }} />
      <Drawer.Screen name="BiometricCaptureScreen" component={BiometricCaptureScreen} options={{ title: "BiometricCapture" }} />
      <Drawer.Screen name="BiometricIntroScreen" component={BiometricIntroScreen} options={{ title: "BiometricIntro" }} />
      <Drawer.Screen name="BlockchainFeesScreen" component={BlockchainFeesScreen} options={{ title: "BlockchainFees" }} />
      <Drawer.Screen name="BnplScreen" component={BnplScreen} options={{ title: "Bnpl" }} />
      <Drawer.Screen name="CarbonCreditsScreen" component={CarbonCreditsScreen} options={{ title: "CarbonCredits" }} />
      <Drawer.Screen name="CardDetailsScreen" component={CardDetailsScreen} options={{ title: "CardDetails" }} />
      <Drawer.Screen name="CardListScreen" component={CardListScreen} options={{ title: "CardList" }} />
      <Drawer.Screen name="CardsScreen" component={CardsScreen} options={{ title: "Cards" }} />
      <Drawer.Screen name="ChatBankingScreen" component={ChatBankingScreen} options={{ title: "ChatBanking" }} />
      <Drawer.Screen name="ComplianceReviewScreen" component={ComplianceReviewScreen} options={{ title: "ComplianceReview" }} />
      <Drawer.Screen name="ComplianceSchedulingScreen" component={ComplianceSchedulingScreen} options={{ title: "ComplianceScheduling" }} />
      <Drawer.Screen name="ConfirmP2PScreen" component={ConfirmP2PScreen} options={{ title: "ConfirmP2P" }} />
      <Drawer.Screen name="ConversionPreviewScreen" component={ConversionPreviewScreen} options={{ title: "ConversionPreview" }} />
      <Drawer.Screen name="ConversionSuccessScreen" component={ConversionSuccessScreen} options={{ title: "ConversionSuccess" }} />
      <Drawer.Screen name="CreateGoalScreen" component={CreateGoalScreen} options={{ title: "CreateGoal" }} />
      <Drawer.Screen name="CreateRecurringScreen" component={CreateRecurringScreen} options={{ title: "CreateRecurring" }} />
      <Drawer.Screen name="CreditScoringScreen" component={CreditScoringScreen} options={{ title: "CreditScoring" }} />
      <Drawer.Screen name="CryptoConfirmScreen" component={CryptoConfirmScreen} options={{ title: "CryptoConfirm" }} />
      <Drawer.Screen name="CryptoSelectScreen" component={CryptoSelectScreen} options={{ title: "CryptoSelect" }} />
      <Drawer.Screen name="CryptoTrackingScreen" component={CryptoTrackingScreen} options={{ title: "CryptoTracking" }} />
      <Drawer.Screen name="CustomerWalletScreen" component={CustomerWalletScreen} options={{ title: "CustomerWallet" }} />
      <Drawer.Screen name="DigitalIdentityScreen" component={DigitalIdentityScreen} options={{ title: "DigitalIdentity" }} />
      <Drawer.Screen name="DisbursementScreen" component={DisbursementScreen} options={{ title: "Disbursement" }} />
      <Drawer.Screen name="DisputeResolutionScreen" component={DisputeResolutionScreen} options={{ title: "DisputeResolution" }} />
      <Drawer.Screen name="DisputeTrackingScreen" component={DisputeTrackingScreen} options={{ title: "DisputeTracking" }} />
      <Drawer.Screen name="DocumentRequirementsScreen" component={DocumentRequirementsScreen} options={{ title: "DocumentRequirements" }} />
      <Drawer.Screen name="DocumentUploadScreen" component={DocumentUploadScreen} options={{ title: "DocumentUpload" }} />
      <Drawer.Screen name="EducationPaymentsScreen" component={EducationPaymentsScreen} options={{ title: "EducationPayments" }} />
      <Drawer.Screen name="EnterPhoneScreen" component={EnterPhoneScreen} options={{ title: "EnterPhone" }} />
      <Drawer.Screen name="EvidenceScreen" component={EvidenceScreen} options={{ title: "Evidence" }} />
      <Drawer.Screen name="ExchangeRateScreen" component={ExchangeRateScreen} options={{ title: "ExchangeRate" }} />
      <Drawer.Screen name="ExchangeRatesScreen" component={ExchangeRatesScreen} options={{ title: "ExchangeRates" }} />
      <Drawer.Screen name="FraudAlertScreen" component={FraudAlertScreen} options={{ title: "FraudAlert" }} />
      <Drawer.Screen name="FraudResolutionScreen" component={FraudResolutionScreen} options={{ title: "FraudResolution" }} />
      <Drawer.Screen name="FreezeCardScreen" component={FreezeCardScreen} options={{ title: "FreezeCard" }} />
      <Drawer.Screen name="GenerateQRScreen" component={GenerateQRScreen} options={{ title: "GenerateQR" }} />
      <Drawer.Screen name="GetQuoteScreen" component={GetQuoteScreen} options={{ title: "GetQuote" }} />
      <Drawer.Screen name="GoalCreatedScreen" component={GoalCreatedScreen} options={{ title: "GoalCreated" }} />
      <Drawer.Screen name="GoalDetailsScreen" component={GoalDetailsScreen} options={{ title: "GoalDetails" }} />
      <Drawer.Screen name="HealthInsuranceScreen" component={HealthInsuranceScreen} options={{ title: "HealthInsurance" }} />
      <Drawer.Screen name="HelpScreen" component={HelpScreen} options={{ title: "Help" }} />
      <Drawer.Screen name="IncidentDetectionScreen" component={IncidentDetectionScreen} options={{ title: "IncidentDetection" }} />
      <Drawer.Screen name="IncidentInvestigationScreen" component={IncidentInvestigationScreen} options={{ title: "IncidentInvestigation" }} />
      <Drawer.Screen name="IncidentResolvedScreen" component={IncidentResolvedScreen} options={{ title: "IncidentResolved" }} />
      <Drawer.Screen name="InsuranceProductsScreen" component={InsuranceProductsScreen} options={{ title: "InsuranceProducts" }} />
      <Drawer.Screen name="InternationalReviewScreen" component={InternationalReviewScreen} options={{ title: "InternationalReview" }} />
      <Drawer.Screen name="InternationalSendScreen" component={InternationalSendScreen} options={{ title: "InternationalSend" }} />
      <Drawer.Screen name="InvestmentConfirmScreen" component={InvestmentConfirmScreen} options={{ title: "InvestmentConfirm" }} />
      <Drawer.Screen name="InvestmentOptionsScreen" component={InvestmentOptionsScreen} options={{ title: "InvestmentOptions" }} />
      <Drawer.Screen name="IotSmartPosScreen" component={IotSmartPosScreen} options={{ title: "IotSmartPos" }} />
      <Drawer.Screen name="IotSmartScreen" component={IotSmartScreen} options={{ title: "IotSmart" }} />
      <Drawer.Screen name="KYCScreen" component={KYCScreen} options={{ title: "KYC" }} />
      <Drawer.Screen name="KYCVerificationScreen" component={KYCVerificationScreen} options={{ title: "KYCVerification" }} />
      <Drawer.Screen name="LinkAccountScreen" component={LinkAccountScreen} options={{ title: "LinkAccount" }} />
      <Drawer.Screen name="LoanApplicationScreen" component={LoanApplicationScreen} options={{ title: "LoanApplication" }} />
      <Drawer.Screen name="LoanOfferScreen" component={LoanOfferScreen} options={{ title: "LoanOffer" }} />
      <Drawer.Screen name="LoginSuccessScreen" component={LoginSuccessScreen} options={{ title: "LoginSuccess" }} />
      <Drawer.Screen name="LoyaltyProgramScreen" component={LoyaltyProgramScreen} options={{ title: "LoyaltyProgram" }} />
      <Drawer.Screen name="MultiCurrencyScreen" component={MultiCurrencyScreen} options={{ title: "MultiCurrency" }} />
      <Drawer.Screen name="NewPasswordScreen" component={NewPasswordScreen} options={{ title: "NewPassword" }} />
      <Drawer.Screen name="NfcTapScreen" component={NfcTapScreen} options={{ title: "NfcTap" }} />
      <Drawer.Screen name="NfcTapToPayScreen" component={NfcTapToPayScreen} options={{ title: "NfcTapToPay" }} />
      <Drawer.Screen name="NotificationPreferencesScreen" component={NotificationPreferencesScreen} options={{ title: "NotificationPreferences" }} />
      <Drawer.Screen name="NotificationsScreen" component={NotificationsScreen} options={{ title: "Notifications" }} />
      <Drawer.Screen name="OAuthCallbackScreen" component={OAuthCallbackScreen} options={{ title: "OAuthCallback" }} />
      <Drawer.Screen name="OTPVerificationScreen" component={OTPVerificationScreen} options={{ title: "OTPVerification" }} />
      <Drawer.Screen name="OpenBankingScreen" component={OpenBankingScreen} options={{ title: "OpenBanking" }} />
      <Drawer.Screen name="P2PSuccessScreen" component={P2PSuccessScreen} options={{ title: "P2PSuccess" }} />
      <Drawer.Screen name="PAPSSConfirmScreen" component={PAPSSConfirmScreen} options={{ title: "PAPSSConfirm" }} />
      <Drawer.Screen name="PAPSSDestinationScreen" component={PAPSSDestinationScreen} options={{ title: "PAPSSDestination" }} />
      <Drawer.Screen name="PAPSSQuoteScreen" component={PAPSSQuoteScreen} options={{ title: "PAPSSQuote" }} />
      <Drawer.Screen name="PAPSSSuccessScreen" component={PAPSSSuccessScreen} options={{ title: "PAPSSSuccess" }} />
      <Drawer.Screen name="PaymentConfirmScreen" component={PaymentConfirmScreen} options={{ title: "PaymentConfirm" }} />
      <Drawer.Screen name="PaymentMethodsScreen" component={PaymentMethodsScreen} options={{ title: "PaymentMethods" }} />
      <Drawer.Screen name="PaymentProcessingScreen" component={PaymentProcessingScreen} options={{ title: "PaymentProcessing" }} />
      <Drawer.Screen name="PaymentRetryScreen" component={PaymentRetryScreen} options={{ title: "PaymentRetry" }} />
      <Drawer.Screen name="PayrollScreen" component={PayrollScreen} options={{ title: "Payroll" }} />
      <Drawer.Screen name="PensionScreen" component={PensionScreen} options={{ title: "Pension" }} />
      <Drawer.Screen name="PolicyIssuedScreen" component={PolicyIssuedScreen} options={{ title: "PolicyIssued" }} />
      <Drawer.Screen name="PortfolioSetupScreen" component={PortfolioSetupScreen} options={{ title: "PortfolioSetup" }} />
      <Drawer.Screen name="ProcessingScreen" component={ProcessingScreen} options={{ title: "Processing" }} />
      <Drawer.Screen name="ProfileScreen" component={ProfileScreen} options={{ title: "Profile" }} />
      <Drawer.Screen name="ProofUploadScreen" component={ProofUploadScreen} options={{ title: "ProofUpload" }} />
      <Drawer.Screen name="PurposeComplianceScreen" component={PurposeComplianceScreen} options={{ title: "PurposeCompliance" }} />
      <Drawer.Screen name="QRCodeScannerScreen" component={QRCodeScannerScreen} options={{ title: "QRCodeScanner" }} />
      <Drawer.Screen name="QRCodeScreen" component={QRCodeScreen} options={{ title: "QRCode" }} />
      <Drawer.Screen name="RaiseDisputeScreen" component={RaiseDisputeScreen} options={{ title: "RaiseDispute" }} />
      <Drawer.Screen name="RateCalculatorScreen" component={RateCalculatorScreen} options={{ title: "RateCalculator" }} />
      <Drawer.Screen name="RateLockScreen" component={RateLockScreen} options={{ title: "RateLock" }} />
      <Drawer.Screen name="ReceiveMoneyScreen" component={ReceiveMoneyScreen} options={{ title: "ReceiveMoney" }} />
      <Drawer.Screen name="RecurringListScreen" component={RecurringListScreen} options={{ title: "RecurringList" }} />
      <Drawer.Screen name="RecurringPaymentsScreen" component={RecurringPaymentsScreen} options={{ title: "RecurringPayments" }} />
      <Drawer.Screen name="RedeemConfirmScreen" component={RedeemConfirmScreen} options={{ title: "RedeemConfirm" }} />
      <Drawer.Screen name="RedemptionOptionsScreen" component={RedemptionOptionsScreen} options={{ title: "RedemptionOptions" }} />
      <Drawer.Screen name="RedemptionSuccessScreen" component={RedemptionSuccessScreen} options={{ title: "RedemptionSuccess" }} />
      <Drawer.Screen name="ReferralProgramScreen" component={ReferralProgramScreen} options={{ title: "ReferralProgram" }} />
      <Drawer.Screen name="RegistrationFormScreen" component={RegistrationFormScreen} options={{ title: "RegistrationForm" }} />
      <Drawer.Screen name="ReportGenerationScreen" component={ReportGenerationScreen} options={{ title: "ReportGeneration" }} />
      <Drawer.Screen name="ReportPreviewScreen" component={ReportPreviewScreen} options={{ title: "ReportPreview" }} />
      <Drawer.Screen name="ReportSubmissionScreen" component={ReportSubmissionScreen} options={{ title: "ReportSubmission" }} />
      <Drawer.Screen name="RequestResetScreen" component={RequestResetScreen} options={{ title: "RequestReset" }} />
      <Drawer.Screen name="RequestVirtualAccountScreen" component={RequestVirtualAccountScreen} options={{ title: "RequestVirtualAccount" }} />
      <Drawer.Screen name="ResetSuccessScreen" component={ResetSuccessScreen} options={{ title: "ResetSuccess" }} />
      <Drawer.Screen name="ReviewConfirmScreen" component={ReviewConfirmScreen} options={{ title: "ReviewConfirm" }} />
      <Drawer.Screen name="RewardsBalanceScreen" component={RewardsBalanceScreen} options={{ title: "RewardsBalance" }} />
      <Drawer.Screen name="RiskAssessmentScreen" component={RiskAssessmentScreen} options={{ title: "RiskAssessment" }} />
      <Drawer.Screen name="SatelliteScreen" component={SatelliteScreen} options={{ title: "Satellite" }} />
      <Drawer.Screen name="SavingsGoalsScreen" component={SavingsGoalsScreen} options={{ title: "SavingsGoals" }} />
      <Drawer.Screen name="ScanQRScreen" component={ScanQRScreen} options={{ title: "ScanQR" }} />
      <Drawer.Screen name="ScheduleConfirmationScreen" component={ScheduleConfirmationScreen} options={{ title: "ScheduleConfirmation" }} />
      <Drawer.Screen name="SecurityChallengeScreen" component={SecurityChallengeScreen} options={{ title: "SecurityChallenge" }} />
      <Drawer.Screen name="SecuritySettingsScreen" component={SecuritySettingsScreen} options={{ title: "SecuritySettings" }} />
      <Drawer.Screen name="SelectBillerScreen" component={SelectBillerScreen} options={{ title: "SelectBiller" }} />
      <Drawer.Screen name="SelectCurrenciesScreen" component={SelectCurrenciesScreen} options={{ title: "SelectCurrencies" }} />
      <Drawer.Screen name="SelectPackageScreen" component={SelectPackageScreen} options={{ title: "SelectPackage" }} />
      <Drawer.Screen name="SelectProviderScreen" component={SelectProviderScreen} options={{ title: "SelectProvider" }} />
      <Drawer.Screen name="SendMoneyHomeScreen" component={SendMoneyHomeScreen} options={{ title: "SendMoneyHome" }} />
      <Drawer.Screen name="SendMoneyScreen" component={SendMoneyScreen} options={{ title: "SendMoney" }} />
      <Drawer.Screen name="SettingsScreen" component={SettingsScreen} options={{ title: "Settings" }} />
      <Drawer.Screen name="SetupCompleteScreen" component={SetupCompleteScreen} options={{ title: "SetupComplete" }} />
      <Drawer.Screen name="SocialLoginOptionsScreen" component={SocialLoginOptionsScreen} options={{ title: "SocialLoginOptions" }} />
      <Drawer.Screen name="StablecoinScreen" component={StablecoinScreen} options={{ title: "Stablecoin" }} />
      <Drawer.Screen name="SuccessScreen" component={SuccessScreen} options={{ title: "Success" }} />
      <Drawer.Screen name="SuperAppScreen" component={SuperAppScreen} options={{ title: "SuperApp" }} />
      <Drawer.Screen name="SupportScreen" component={SupportScreen} options={{ title: "Support" }} />
      <Drawer.Screen name="SuspiciousActivityScreen" component={SuspiciousActivityScreen} options={{ title: "SuspiciousActivity" }} />
      <Drawer.Screen name="TestAuthScreen" component={TestAuthScreen} options={{ title: "TestAuth" }} />
      <Drawer.Screen name="TierOverviewScreen" component={TierOverviewScreen} options={{ title: "TierOverview" }} />
      <Drawer.Screen name="TokenizedAssetsScreen" component={TokenizedAssetsScreen} options={{ title: "TokenizedAssets" }} />
      <Drawer.Screen name="TopupAmountScreen" component={TopupAmountScreen} options={{ title: "TopupAmount" }} />
      <Drawer.Screen name="TopupMethodsScreen" component={TopupMethodsScreen} options={{ title: "TopupMethods" }} />
      <Drawer.Screen name="TopupSuccessScreen" component={TopupSuccessScreen} options={{ title: "TopupSuccess" }} />
      <Drawer.Screen name="TrackingScreen" component={TrackingScreen} options={{ title: "Tracking" }} />
      <Drawer.Screen name="TransactionDetailScreen" component={TransactionDetailScreen} options={{ title: "TransactionDetail" }} />
      <Drawer.Screen name="TransactionDetailsScreen" component={TransactionDetailsScreen} options={{ title: "TransactionDetails" }} />
      <Drawer.Screen name="TransactionHistoryScreen" component={TransactionHistoryScreen} options={{ title: "TransactionHistory" }} />
      <Drawer.Screen name="TransactionMonitorScreen" component={TransactionMonitorScreen} options={{ title: "TransactionMonitor" }} />
      <Drawer.Screen name="TransactionSuccessScreen" component={TransactionSuccessScreen} options={{ title: "TransactionSuccess" }} />
      <Drawer.Screen name="TransactionsScreen" component={TransactionsScreen} options={{ title: "Transactions" }} />
      <Drawer.Screen name="TransferTrackingScreen" component={TransferTrackingScreen} options={{ title: "TransferTracking" }} />
      <Drawer.Screen name="UnderReviewScreen" component={UnderReviewScreen} options={{ title: "UnderReview" }} />
      <Drawer.Screen name="VerifyIdentityScreen" component={VerifyIdentityScreen} options={{ title: "VerifyIdentity" }} />
      <Drawer.Screen name="VerifyTOTPScreen" component={VerifyTOTPScreen} options={{ title: "VerifyTOTP" }} />
      <Drawer.Screen name="VideoKYCScreen" component={VideoKYCScreen} options={{ title: "VideoKYC" }} />
      <Drawer.Screen name="VirtualCardScreen" component={VirtualCardScreen} options={{ title: "VirtualCard" }} />
      <Drawer.Screen name="WalletAddressScreen" component={WalletAddressScreen} options={{ title: "WalletAddress" }} />
      <Drawer.Screen name="WalletScreen" component={WalletScreen} options={{ title: "Wallet" }} />
      <Drawer.Screen name="WearablePaymentsScreen" component={WearablePaymentsScreen} options={{ title: "WearablePayments" }} />
      <Drawer.Screen name="WearableScreen" component={WearableScreen} options={{ title: "Wearable" }} />
      <Drawer.Screen name="WelcomeScreen" component={WelcomeScreen} options={{ title: "Welcome" }} />
      <Drawer.Screen name="WiseConfirmScreen" component={WiseConfirmScreen} options={{ title: "WiseConfirm" }} />
      <Drawer.Screen name="WiseCorridorScreen" component={WiseCorridorScreen} options={{ title: "WiseCorridor" }} />
      <Drawer.Screen name="WiseQuoteScreen" component={WiseQuoteScreen} options={{ title: "WiseQuote" }} />
      <Drawer.Screen name="WiseTrackingScreen" component={WiseTrackingScreen} options={{ title: "WiseTracking" }} />
    </Drawer.Navigator>
  );
}

function LoadingSplash() {
  return (
    <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0f172a' }}>
      <ActivityIndicator size="large" color="#3b82f6" />
    </View>
  );
}

export default function App() {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const token = await AsyncStorage.getItem(AUTH_TOKEN_KEY);
      setIsAuthenticated(!!token);
    } catch {
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) return <LoadingSplash />;

  return (
    <NavigationContainer>
      <StatusBar barStyle="light-content" backgroundColor="#0f172a" />
      <Stack.Navigator
        initialRouteName={isAuthenticated ? 'DrawerHome' : 'Onboarding'}
        screenOptions={{
          headerStyle: { backgroundColor: '#0f172a' },
          headerTintColor: '#f8fafc',
          headerTitleStyle: { fontWeight: '600' },
          cardStyle: { backgroundColor: '#0f172a' },
        }}
      >
        <Stack.Screen name="Onboarding" component={OnboardingScreen} options={{ headerShown: false }} />
        <Stack.Screen name="Login" component={LoginScreen} options={{ headerShown: false }} />
        <Stack.Screen name="Register" component={RegisterScreen} options={{ title: 'Create Account' }} />
        <Stack.Screen name="PinSetup" component={PinSetupScreen} options={{ title: 'Set PIN' }} />
        <Stack.Screen name="BiometricSetup" component={BiometricSetupScreen} options={{ title: 'Enable Biometrics' }} />
        <Stack.Screen name="BiometricAuth" component={BiometricAuthScreen} options={{ headerShown: false }} />
        <Stack.Screen
          name="DrawerHome"
          component={DrawerNavigator}
          options={{ headerShown: false }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}

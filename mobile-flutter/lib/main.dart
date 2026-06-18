import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';

// ── Screen imports (all 203 screens registered) ──
import 'screens/2_fa_enabled_screen.dart';
import 'screens/2_fa_intro_screen.dart';
import 'screens/accept_loan_screen.dart';
import 'screens/account_created_screen.dart';
import 'screens/account_details_screen.dart';
import 'screens/account_locked_screen.dart';
import 'screens/account_verification_screen.dart';
import 'screens/add_beneficiary_screen.dart';
import 'screens/add_card_screen.dart';
import 'screens/agent_performance_screen.dart';
import 'screens/agritech_screen.dart';
import 'screens/ai_credit_scoring_screen.dart';
import 'screens/ai_credit_screen.dart';
import 'screens/amount_entry_screen.dart';
import 'screens/anaas_screen.dart';
import 'screens/application_screen.dart';
import 'screens/audit_export_screen.dart';
import 'screens/auto_save_setup_screen.dart';
import 'screens/backup_codes_screen.dart';
import 'screens/bank_instructions_screen.dart';
import 'screens/beneficiaries_screen.dart';
import 'screens/beneficiary_details_screen.dart';
import 'screens/beneficiary_form_screen.dart';
import 'screens/beneficiary_list_screen.dart';
import 'screens/beneficiary_management_screen.dart';
import 'screens/beneficiary_saved_screen.dart';
import 'screens/beneficiary_selection_screen.dart';
import 'screens/bill_details_screen.dart';
import 'screens/bill_payment_screen.dart';
import 'screens/bill_payment_success_screen.dart';
import 'screens/biometric_auth_screen.dart';
import 'screens/biometric_capture_screen.dart';
import 'screens/biometric_intro_screen.dart';
import 'screens/biometric_screen.dart';
import 'screens/biometric_setup_screen.dart';
import 'screens/blockchain_fees_screen.dart';
import 'screens/bnpl_screen.dart';
import 'screens/carbon_credits_screen.dart';
import 'screens/card_details_screen.dart';
import 'screens/card_list_screen.dart';
import 'screens/cards_screen.dart';
import 'screens/cash_in_screen.dart';
import 'screens/cash_out_screen.dart';
import 'screens/chat_banking_screen.dart';
import 'screens/compliance_review_screen.dart';
import 'screens/compliance_scheduling_screen.dart';
import 'screens/confirm_p2_p_screen.dart';
import 'screens/conversion_preview_screen.dart';
import 'screens/conversion_success_screen.dart';
import 'screens/create_goal_screen.dart';
import 'screens/create_recurring_screen.dart';
import 'screens/credit_scoring_screen.dart';
import 'screens/crypto_confirm_screen.dart';
import 'screens/crypto_select_screen.dart';
import 'screens/crypto_tracking_screen.dart';
import 'screens/customer_wallet_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/digital_identity_screen.dart';
import 'screens/disbursement_screen.dart';
import 'screens/dispute_resolution_screen.dart';
import 'screens/dispute_tracking_screen.dart';
import 'screens/document_requirements_screen.dart';
import 'screens/document_upload_screen.dart';
import 'screens/education_payments_screen.dart';
import 'screens/enter_phone_screen.dart';
import 'screens/evidence_screen.dart';
import 'screens/exchange_rate_screen.dart';
import 'screens/exchange_rates_screen.dart';
import 'screens/float_screen.dart';
import 'screens/fraud_alert_screen.dart';
import 'screens/fraud_resolution_screen.dart';
import 'screens/freeze_card_screen.dart';
import 'screens/generate_qr_screen.dart';
import 'screens/get_quote_screen.dart';
import 'screens/goal_created_screen.dart';
import 'screens/goal_details_screen.dart';
import 'screens/health_insurance_screen.dart';
import 'screens/help_screen.dart';
import 'screens/history_screen.dart';
import 'screens/incident_detection_screen.dart';
import 'screens/incident_investigation_screen.dart';
import 'screens/incident_resolved_screen.dart';
import 'screens/insurance_products_screen.dart';
import 'screens/international_review_screen.dart';
import 'screens/international_send_screen.dart';
import 'screens/investment_confirm_screen.dart';
import 'screens/investment_options_screen.dart';
import 'screens/iot_smart_pos_screen.dart';
import 'screens/iot_smart_screen.dart';
import 'screens/journeys_screen.dart';
import 'screens/kyc_screen.dart';
import 'screens/kyc_verification_screen.dart';
import 'screens/link_account_screen.dart';
import 'screens/loan_application_screen.dart';
import 'screens/loan_offer_screen.dart';
import 'screens/login_screen.dart';
import 'screens/login_screen_cdp_screen.dart';
import 'screens/login_success_screen.dart';
import 'screens/loyalty_program_screen.dart';
import 'screens/multi_currency_screen.dart';
import 'screens/new_password_screen.dart';
import 'screens/nfc_screen.dart';
import 'screens/nfc_tap_to_pay_screen.dart';
import 'screens/notification_preferences_screen.dart';
import 'screens/notification_screen.dart';
import 'screens/notifications_screen.dart';
import 'screens/o_auth_callback_screen.dart';
import 'screens/onboarding_screen.dart';
import 'screens/open_banking_screen.dart';
import 'screens/otp_verification_screen.dart';
import 'screens/p2_p_success_screen.dart';
import 'screens/papss_confirm_screen.dart';
import 'screens/papss_destination_screen.dart';
import 'screens/papss_quote_screen.dart';
import 'screens/papss_success_screen.dart';
import 'screens/payment_confirm_screen.dart';
import 'screens/payment_methods_screen.dart';
import 'screens/payment_processing_screen.dart';
import 'screens/payment_retry_screen.dart';
import 'screens/payroll_screen.dart';
import 'screens/pension_screen.dart';
import 'screens/pin_setup_screen.dart';
import 'screens/policy_issued_screen.dart';
import 'screens/portfolio_setup_screen.dart';
import 'screens/processing_screen.dart';
import 'screens/profile_screen.dart';
import 'screens/proof_upload_screen.dart';
import 'screens/purpose_compliance_screen.dart';
import 'screens/qr_code_scanner_screen.dart';
import 'screens/qr_code_screen.dart';
import 'screens/qr_scanner_screen.dart';
import 'screens/raise_dispute_screen.dart';
import 'screens/rate_calculator_screen.dart';
import 'screens/rate_lock_screen.dart';
import 'screens/receipt_screen.dart';
import 'screens/receive_money_screen.dart';
import 'screens/recurring_list_screen.dart';
import 'screens/recurring_payments_screen.dart';
import 'screens/redeem_confirm_screen.dart';
import 'screens/redemption_options_screen.dart';
import 'screens/redemption_success_screen.dart';
import 'screens/referral_program_screen.dart';
import 'screens/referral_screen.dart';
import 'screens/register_screen.dart';
import 'screens/registration_form_screen.dart';
import 'screens/report_generation_screen.dart';
import 'screens/report_preview_screen.dart';
import 'screens/report_submission_screen.dart';
import 'screens/request_reset_screen.dart';
import 'screens/request_virtual_account_screen.dart';
import 'screens/reset_success_screen.dart';
import 'screens/review_confirm_screen.dart';
import 'screens/rewards_balance_screen.dart';
import 'screens/risk_assessment_screen.dart';
import 'screens/satellite_screen.dart';
import 'screens/savings_goals_screen.dart';
import 'screens/scan_qr_screen.dart';
import 'screens/schedule_confirmation_screen.dart';
import 'screens/security_challenge_screen.dart';
import 'screens/security_settings_screen.dart';
import 'screens/select_biller_screen.dart';
import 'screens/select_currencies_screen.dart';
import 'screens/select_package_screen.dart';
import 'screens/select_provider_screen.dart';
import 'screens/send_money_home_screen.dart';
import 'screens/send_money_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/setup_complete_screen.dart';
import 'screens/social_login_options_screen.dart';
import 'screens/splash_screen.dart';
import 'screens/stablecoin_screen.dart';
import 'screens/success_screen.dart';
import 'screens/super_app_screen.dart';
import 'screens/support_screen.dart';
import 'screens/suspicious_activity_screen.dart';
import 'screens/test_auth_screen.dart';
import 'screens/tier_overview_screen.dart';
import 'screens/tokenized_assets_screen.dart';
import 'screens/topup_amount_screen.dart';
import 'screens/topup_methods_screen.dart';
import 'screens/topup_success_screen.dart';
import 'screens/tracking_screen.dart';
import 'screens/transaction_detail_screen.dart';
import 'screens/transaction_details_screen.dart';
import 'screens/transaction_history_screen.dart';
import 'screens/transaction_monitor_screen.dart';
import 'screens/transaction_success_screen.dart';
import 'screens/transactions_screen.dart';
import 'screens/transfer_tracking_screen.dart';
import 'screens/under_review_screen.dart';
import 'screens/verify_identity_screen.dart';
import 'screens/verify_totp_screen.dart';
import 'screens/video_kyc_screen.dart';
import 'screens/virtual_card_screen.dart';
import 'screens/wallet_address_screen.dart';
import 'screens/wallet_screen.dart';
import 'screens/wearable_payments_screen.dart';
import 'screens/wearable_screen.dart';
import 'screens/welcome_screen.dart';
import 'screens/wise_confirm_screen.dart';
import 'screens/wise_corridor_screen.dart';
import 'screens/wise_quote_screen.dart';
import 'screens/wise_tracking_screen.dart';
import 'providers/auth_provider.dart';
import 'widgets/main_shell.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Lock to portrait on PAX A920
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // Status bar styling
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
  ));

  runApp(const ProviderScope(child: Pos54LinkApp()));
}

final _router = GoRouter(
  initialLocation: '/splash',
  routes: [
    // ── Auth & Onboarding (no shell) ─────────────────────────────────────
    GoRoute(path: '/splash', builder: (_, __) => const SplashScreen()),
    GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
    GoRoute(path: '/register', builder: (_, __) => const RegisterScreen()),
    GoRoute(path: '/onboarding', builder: (_, __) => const OnboardingScreen()),
    GoRoute(path: '/pin-setup', builder: (_, __) => const PinSetupScreen()),

    // ── Main app with ShellRoute (Drawer + BottomNav) ────────────────────
    ShellRoute(
      builder: (context, state, child) => MainShell(child: child),
      routes: [
    GoRoute(path: '/2fa-enabled', builder: (_, __) => const Screen2FAEnabledScreen()),
    GoRoute(path: '/2fa-intro', builder: (_, __) => const Screen2FAIntroScreen()),
    GoRoute(path: '/accept-loan', builder: (_, __) => const AcceptLoanScreen()),
    GoRoute(path: '/account-created', builder: (_, __) => const AccountCreatedScreen()),
    GoRoute(path: '/account-details', builder: (_, __) => const AccountDetailsScreen()),
    GoRoute(path: '/account-locked', builder: (_, __) => const AccountLockedScreen()),
    GoRoute(path: '/account-verification', builder: (_, __) => const AccountVerificationScreen()),
    GoRoute(path: '/add-beneficiary', builder: (_, __) => const AddBeneficiaryScreen()),
    GoRoute(path: '/add-card', builder: (_, __) => const AddCardScreen()),
    GoRoute(path: '/agent-performance', builder: (_, __) => const AgentPerformanceScreen()),
    GoRoute(path: '/agritech', builder: (_, __) => const AgritechScreen()),
    GoRoute(path: '/ai-credit-scoring', builder: (_, __) => const AiCreditScoringScreen()),
    GoRoute(path: '/ai-credit', builder: (_, __) => const AiCreditScreen()),
    GoRoute(path: '/amount-entry', builder: (_, __) => const AmountEntryScreen()),
    GoRoute(path: '/anaas', builder: (_, __) => const AnaasScreen()),
    GoRoute(path: '/application', builder: (_, __) => const ApplicationScreen()),
    GoRoute(path: '/audit-export', builder: (_, __) => const AuditExportScreen()),
    GoRoute(path: '/auto-save-setup', builder: (_, __) => const AutoSaveSetupScreen()),
    GoRoute(path: '/backup-codes', builder: (_, __) => const BackupCodesScreen()),
    GoRoute(path: '/bank-instructions', builder: (_, __) => const BankInstructionsScreen()),
    GoRoute(path: '/beneficiaries', builder: (_, __) => const BeneficiariesScreen()),
    GoRoute(path: '/beneficiary-details', builder: (_, __) => const BeneficiaryDetailsScreen()),
    GoRoute(path: '/beneficiary-form', builder: (_, __) => const BeneficiaryFormScreen()),
    GoRoute(path: '/beneficiary-list', builder: (_, __) => const BeneficiaryListScreen()),
    GoRoute(path: '/beneficiary-management', builder: (_, __) => const BeneficiaryManagementScreen()),
    GoRoute(path: '/beneficiary-saved', builder: (_, __) => const BeneficiarySavedScreen()),
    GoRoute(path: '/beneficiary-selection', builder: (_, __) => const BeneficiarySelectionScreen()),
    GoRoute(path: '/bill-details', builder: (_, __) => const BillDetailsScreen()),
    GoRoute(path: '/bill-payment', builder: (_, __) => const BillPaymentScreen()),
    GoRoute(path: '/bill-payment-success', builder: (_, __) => const BillPaymentSuccessScreen()),
    GoRoute(path: '/biometric-auth', builder: (_, __) => const BiometricAuthScreen()),
    GoRoute(path: '/biometric-capture', builder: (_, __) => const BiometricCaptureScreen()),
    GoRoute(path: '/biometric-intro', builder: (_, __) => const BiometricIntroScreen()),
    GoRoute(path: '/biometric', builder: (_, __) => const BiometricScreen()),
    GoRoute(path: '/biometric-setup', builder: (_, __) => const BiometricSetupScreen()),
    GoRoute(path: '/blockchain-fees', builder: (_, __) => const BlockchainFeesScreen()),
    GoRoute(path: '/bnpl', builder: (_, __) => const BnplScreen()),
    GoRoute(path: '/carbon-credits', builder: (_, __) => const CarbonCreditsScreen()),
    GoRoute(path: '/card-details', builder: (_, __) => const CardDetailsScreen()),
    GoRoute(path: '/card-list', builder: (_, __) => const CardListScreen()),
    GoRoute(path: '/cards', builder: (_, __) => const CardsScreen()),
    GoRoute(path: '/cash-in', builder: (_, __) => const CashInScreen()),
    GoRoute(path: '/cash-out', builder: (_, __) => const CashOutScreen()),
    GoRoute(path: '/chat-banking', builder: (_, __) => const ChatBankingScreen()),
    GoRoute(path: '/compliance-review', builder: (_, __) => const ComplianceReviewScreen()),
    GoRoute(path: '/compliance-scheduling', builder: (_, __) => const ComplianceSchedulingScreen()),
    GoRoute(path: '/confirm-p2p', builder: (_, __) => const ConfirmP2PScreen()),
    GoRoute(path: '/conversion-preview', builder: (_, __) => const ConversionPreviewScreen()),
    GoRoute(path: '/conversion-success', builder: (_, __) => const ConversionSuccessScreen()),
    GoRoute(path: '/create-goal', builder: (_, __) => const CreateGoalScreen()),
    GoRoute(path: '/create-recurring', builder: (_, __) => const CreateRecurringScreen()),
    GoRoute(path: '/credit-scoring', builder: (_, __) => const CreditScoringScreen()),
    GoRoute(path: '/crypto-confirm', builder: (_, __) => const CryptoConfirmScreen()),
    GoRoute(path: '/crypto-select', builder: (_, __) => const CryptoSelectScreen()),
    GoRoute(path: '/crypto-tracking', builder: (_, __) => const CryptoTrackingScreen()),
    GoRoute(path: '/customer-wallet', builder: (_, __) => const CustomerWalletScreen()),
    GoRoute(path: '/dashboard', builder: (_, state) => const DashboardScreen()),
    GoRoute(path: '/digital-identity', builder: (_, __) => const DigitalIdentityScreen()),
    GoRoute(path: '/disbursement', builder: (_, __) => const DisbursementScreen()),
    GoRoute(path: '/dispute-resolution', builder: (_, __) => const DisputeResolutionScreen()),
    GoRoute(path: '/dispute-tracking', builder: (_, __) => const DisputeTrackingScreen()),
    GoRoute(path: '/document-requirements', builder: (_, __) => const DocumentRequirementsScreen()),
    GoRoute(path: '/document-upload', builder: (_, __) => const DocumentUploadScreen()),
    GoRoute(path: '/education-payments', builder: (_, __) => const EducationPaymentsScreen()),
    GoRoute(path: '/enter-phone', builder: (_, __) => const EnterPhoneScreen()),
    GoRoute(path: '/evidence', builder: (_, __) => const EvidenceScreen()),
    GoRoute(path: '/exchange-rate', builder: (_, __) => const ExchangeRateScreen()),
    GoRoute(path: '/exchange-rates', builder: (_, __) => const ExchangeRatesScreen()),
    GoRoute(path: '/float', builder: (_, __) => const FloatScreen()),
    GoRoute(path: '/fraud-alert', builder: (_, __) => const FraudAlertScreen()),
    GoRoute(path: '/fraud-resolution', builder: (_, __) => const FraudResolutionScreen()),
    GoRoute(path: '/freeze-card', builder: (_, __) => const FreezeCardScreen()),
    GoRoute(path: '/generate-qr', builder: (_, __) => const GenerateQRScreen()),
    GoRoute(path: '/get-quote', builder: (_, __) => const GetQuoteScreen()),
    GoRoute(path: '/goal-created', builder: (_, __) => const GoalCreatedScreen()),
    GoRoute(path: '/goal-details', builder: (_, __) => const GoalDetailsScreen()),
    GoRoute(path: '/health-insurance', builder: (_, __) => const HealthInsuranceScreen()),
    GoRoute(path: '/help', builder: (_, __) => const HelpScreen()),
    GoRoute(path: '/history', builder: (_, __) => const HistoryScreen()),
    GoRoute(path: '/incident-detection', builder: (_, __) => const IncidentDetectionScreen()),
    GoRoute(path: '/incident-investigation', builder: (_, __) => const IncidentInvestigationScreen()),
    GoRoute(path: '/incident-resolved', builder: (_, __) => const IncidentResolvedScreen()),
    GoRoute(path: '/insurance-products', builder: (_, __) => const InsuranceProductsScreen()),
    GoRoute(path: '/international-review', builder: (_, __) => const InternationalReviewScreen()),
    GoRoute(path: '/international-send', builder: (_, __) => const InternationalSendScreen()),
    GoRoute(path: '/investment-confirm', builder: (_, __) => const InvestmentConfirmScreen()),
    GoRoute(path: '/investment-options', builder: (_, __) => const InvestmentOptionsScreen()),
    GoRoute(path: '/iot-smart-pos', builder: (_, __) => const IotSmartPosScreen()),
    GoRoute(path: '/iot-smart', builder: (_, __) => const IotSmartScreen()),
    GoRoute(path: '/journeys', builder: (_, __) => const JourneysScreen()),
    GoRoute(path: '/kyc', builder: (_, state) => const KycScreen()),
    GoRoute(path: '/kyc-verification', builder: (_, __) => const KycVerificationScreen()),
    GoRoute(path: '/link-account', builder: (_, __) => const LinkAccountScreen()),
    GoRoute(path: '/loan-application', builder: (_, __) => const LoanApplicationScreen()),
    GoRoute(path: '/loan-offer', builder: (_, __) => const LoanOfferScreen()),
    GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
    GoRoute(path: '/login-cdp', builder: (_, __) => const LoginScreenCDPScreen()),
    GoRoute(path: '/login-success', builder: (_, __) => const LoginSuccessScreen()),
    GoRoute(path: '/loyalty-program', builder: (_, __) => const LoyaltyProgramScreen()),
    GoRoute(path: '/multi-currency', builder: (_, __) => const MultiCurrencyScreen()),
    GoRoute(path: '/new-password', builder: (_, __) => const NewPasswordScreen()),
    GoRoute(path: '/nfc', builder: (_, __) => const NfcScreen()),
    GoRoute(path: '/nfc-tap-to-pay', builder: (_, __) => const NfcTapToPayScreen()),
    GoRoute(path: '/notification-preferences', builder: (_, __) => const NotificationPreferencesScreen()),
    GoRoute(path: '/notification', builder: (_, state) => const NotificationScreen()),
    GoRoute(path: '/notifications', builder: (_, __) => const NotificationsScreen()),
    GoRoute(path: '/oauth-callback', builder: (_, __) => const OAuthCallbackScreen()),
    GoRoute(path: '/onboarding', builder: (_, state) => const OnboardingScreen()),
    GoRoute(path: '/open-banking', builder: (_, __) => const OpenBankingScreen()),
    GoRoute(path: '/otp-verification', builder: (_, __) => const OTPVerificationScreen()),
    GoRoute(path: '/p2p-success', builder: (_, __) => const P2PSuccessScreen()),
    GoRoute(path: '/papss-confirm', builder: (_, __) => const PAPSSConfirmScreen()),
    GoRoute(path: '/papss-destination', builder: (_, __) => const PAPSSDestinationScreen()),
    GoRoute(path: '/papss-quote', builder: (_, __) => const PAPSSQuoteScreen()),
    GoRoute(path: '/papss-success', builder: (_, __) => const PAPSSSuccessScreen()),
    GoRoute(path: '/payment-confirm', builder: (_, __) => const PaymentConfirmScreen()),
    GoRoute(path: '/payment-methods', builder: (_, __) => const PaymentMethodsScreen()),
    GoRoute(path: '/payment-processing', builder: (_, __) => const PaymentProcessingScreen()),
    GoRoute(path: '/payment-retry', builder: (_, __) => const PaymentRetryScreen()),
    GoRoute(path: '/payroll', builder: (_, __) => const PayrollScreen()),
    GoRoute(path: '/pension', builder: (_, __) => const PensionScreen()),
    GoRoute(path: '/pin-setup', builder: (_, __) => const PinSetupScreen()),
    GoRoute(path: '/policy-issued', builder: (_, __) => const PolicyIssuedScreen()),
    GoRoute(path: '/portfolio-setup', builder: (_, __) => const PortfolioSetupScreen()),
    GoRoute(path: '/processing', builder: (_, __) => const ProcessingScreen()),
    GoRoute(path: '/profile', builder: (_, state) => const ProfileScreen()),
    GoRoute(path: '/proof-upload', builder: (_, __) => const ProofUploadScreen()),
    GoRoute(path: '/purpose-compliance', builder: (_, __) => const PurposeComplianceScreen()),
    GoRoute(path: '/qr-code-scanner', builder: (_, __) => const QRCodeScannerScreen()),
    GoRoute(path: '/qr-code', builder: (_, __) => const QRCodeScreen()),
    GoRoute(path: '/qr-scanner', builder: (_, __) => const QrScannerScreen()),
    GoRoute(path: '/raise-dispute', builder: (_, __) => const RaiseDisputeScreen()),
    GoRoute(path: '/rate-calculator', builder: (_, __) => const RateCalculatorScreen()),
    GoRoute(path: '/rate-lock', builder: (_, __) => const RateLockScreen()),
    GoRoute(path: '/receipt', builder: (_, __) => const ReceiptScreen()),
    GoRoute(path: '/receive-money', builder: (_, __) => const ReceiveMoneyScreen()),
    GoRoute(path: '/recurring-list', builder: (_, __) => const RecurringListScreen()),
    GoRoute(path: '/recurring-payments', builder: (_, __) => const RecurringPaymentsScreen()),
    GoRoute(path: '/redeem-confirm', builder: (_, __) => const RedeemConfirmScreen()),
    GoRoute(path: '/redemption-options', builder: (_, __) => const RedemptionOptionsScreen()),
    GoRoute(path: '/redemption-success', builder: (_, __) => const RedemptionSuccessScreen()),
    GoRoute(path: '/referral-program', builder: (_, __) => const ReferralProgramScreen()),
    GoRoute(path: '/referral', builder: (_, state) => const ReferralScreen()),
    GoRoute(path: '/register', builder: (_, __) => const RegisterScreen()),
    GoRoute(path: '/registration-form', builder: (_, __) => const RegistrationFormScreen()),
    GoRoute(path: '/report-generation', builder: (_, __) => const ReportGenerationScreen()),
    GoRoute(path: '/report-preview', builder: (_, __) => const ReportPreviewScreen()),
    GoRoute(path: '/report-submission', builder: (_, __) => const ReportSubmissionScreen()),
    GoRoute(path: '/request-reset', builder: (_, __) => const RequestResetScreen()),
    GoRoute(path: '/request-virtual-account', builder: (_, __) => const RequestVirtualAccountScreen()),
    GoRoute(path: '/reset-success', builder: (_, __) => const ResetSuccessScreen()),
    GoRoute(path: '/review-confirm', builder: (_, __) => const ReviewConfirmScreen()),
    GoRoute(path: '/rewards-balance', builder: (_, __) => const RewardsBalanceScreen()),
    GoRoute(path: '/risk-assessment', builder: (_, __) => const RiskAssessmentScreen()),
    GoRoute(path: '/satellite', builder: (_, __) => const SatelliteScreen()),
    GoRoute(path: '/savings-goals-new', builder: (_, __) => const SavingsGoalsScreen()),
    GoRoute(path: '/scan-qr', builder: (_, __) => const ScanQRScreen()),
    GoRoute(path: '/schedule-confirmation', builder: (_, __) => const ScheduleConfirmationScreen()),
    GoRoute(path: '/security-challenge', builder: (_, __) => const SecurityChallengeScreen()),
    GoRoute(path: '/security-settings', builder: (_, __) => const SecuritySettingsScreen()),
    GoRoute(path: '/select-biller', builder: (_, __) => const SelectBillerScreen()),
    GoRoute(path: '/select-currencies', builder: (_, __) => const SelectCurrenciesScreen()),
    GoRoute(path: '/select-package', builder: (_, __) => const SelectPackageScreen()),
    GoRoute(path: '/select-provider', builder: (_, __) => const SelectProviderScreen()),
    GoRoute(path: '/send-money-home', builder: (_, __) => const SendMoneyHomeScreen()),
    GoRoute(path: '/send-money', builder: (_, __) => const SendMoneyScreen()),
    GoRoute(path: '/settings', builder: (_, __) => const SettingsScreen()),
    GoRoute(path: '/setup-complete', builder: (_, __) => const SetupCompleteScreen()),
    GoRoute(path: '/social-login', builder: (_, __) => const SocialLoginOptionsScreen()),
    GoRoute(path: '/splash', builder: (_, __) => const SplashScreen()),
    GoRoute(path: '/stablecoin', builder: (_, __) => const StablecoinScreen()),
    GoRoute(path: '/success', builder: (_, __) => const SuccessScreen()),
    GoRoute(path: '/super-app', builder: (_, __) => const SuperAppScreen()),
    GoRoute(path: '/support', builder: (_, __) => const SupportScreen()),
    GoRoute(path: '/suspicious-activity', builder: (_, __) => const SuspiciousActivityScreen()),
    GoRoute(path: '/test-auth', builder: (_, __) => const TestAuthScreen()),
    GoRoute(path: '/tier-overview', builder: (_, __) => const TierOverviewScreen()),
    GoRoute(path: '/tokenized-assets', builder: (_, __) => const TokenizedAssetsScreen()),
    GoRoute(path: '/topup-amount', builder: (_, __) => const TopupAmountScreen()),
    GoRoute(path: '/topup-methods', builder: (_, __) => const TopupMethodsScreen()),
    GoRoute(path: '/topup-success', builder: (_, __) => const TopupSuccessScreen()),
    GoRoute(path: '/tracking', builder: (_, __) => const TrackingScreen()),
    GoRoute(path: '/transaction-detail/:id', builder: (_, state) => TransactionDetailScreen(transactionId: state.pathParameters['id'] ?? '')),
    GoRoute(path: '/transaction-detail', builder: (_, __) => const TransactionDetailScreen(transactionId: '')),
    GoRoute(path: '/transaction-details', builder: (_, __) => const TransactionDetailsScreen()),
    GoRoute(path: '/transaction-history', builder: (_, __) => const TransactionHistoryScreen()),
    GoRoute(path: '/transaction-monitor', builder: (_, __) => const TransactionMonitorScreen()),
    GoRoute(path: '/transaction-success', builder: (_, __) => const TransactionSuccessScreen()),
    GoRoute(path: '/transactions', builder: (_, __) => const TransactionsScreen()),
    GoRoute(path: '/transfer-tracking', builder: (_, __) => const TransferTrackingScreen()),
    GoRoute(path: '/under-review', builder: (_, __) => const UnderReviewScreen()),
    GoRoute(path: '/verify-identity', builder: (_, __) => const VerifyIdentityScreen()),
    GoRoute(path: '/verify-totp', builder: (_, __) => const VerifyTOTPScreen()),
    GoRoute(path: '/video-kyc', builder: (_, __) => const VideoKYCScreen()),
    GoRoute(path: '/virtual-card', builder: (_, __) => const VirtualCardScreen()),
    GoRoute(path: '/wallet-address', builder: (_, __) => const WalletAddressScreen()),
    GoRoute(path: '/wallet', builder: (_, state) => const WalletScreen()),
    GoRoute(path: '/wearable-payments', builder: (_, __) => const WearablePaymentsScreen()),
    GoRoute(path: '/wearable', builder: (_, __) => const WearableScreen()),
    GoRoute(path: '/welcome', builder: (_, __) => const WelcomeScreen()),
    GoRoute(path: '/wise-confirm', builder: (_, __) => const WiseConfirmScreen()),
    GoRoute(path: '/wise-corridor', builder: (_, __) => const WiseCorridorScreen()),
    GoRoute(path: '/wise-quote', builder: (_, __) => const WiseQuoteScreen()),
    GoRoute(path: '/wise-tracking', builder: (_, __) => const WiseTrackingScreen()),
      ],
    ),
  ],
  redirect: (context, state) {
    return null;
  },
);

class Pos54LinkApp extends ConsumerWidget {
  const Pos54LinkApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      title: '54Link POS',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1A56DB),
          brightness: Brightness.light,
        ),
        textTheme: GoogleFonts.interTextTheme(),
        appBarTheme: const AppBarTheme(
          centerTitle: true,
          elevation: 0,
          backgroundColor: Color(0xFF1A56DB),
          foregroundColor: Colors.white,
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFF1A56DB),
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          ),
        ),
        cardTheme: CardTheme(
          elevation: 1,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
        inputDecorationTheme: InputDecorationTheme(
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        ),
      ),
      routerConfig: _router,
    );
  }
}

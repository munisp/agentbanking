import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';

import 'screens/splash_screen.dart';
import 'screens/login_screen.dart';
import 'screens/onboarding_screen.dart';
import 'screens/pin_setup_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/cash_in_screen.dart';
import 'screens/cash_out_screen.dart';
import 'screens/send_money_screen.dart';
import 'screens/receive_money_screen.dart';
import 'screens/bill_payment_screen.dart';
import 'screens/receipt_screen.dart';
import 'screens/float_screen.dart';
import 'screens/history_screen.dart';
import 'screens/transaction_history_screen.dart';
import 'screens/transfer_tracking_screen.dart';
import 'screens/wallet_screen.dart';
import 'screens/virtual_card_screen.dart';
import 'screens/savings_goals_screen.dart';
import 'screens/qr_scanner_screen.dart';
import 'screens/exchange_rates_screen.dart';
import 'screens/kyc_screen.dart';
import 'screens/profile_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/security_settings_screen.dart';
import 'screens/notifications_screen.dart';
import 'screens/support_screen.dart';
import 'screens/referral_screen.dart';
import 'screens/biometric_screen.dart';
import 'screens/recurring_payments_screen.dart';
import 'screens/rate_calculator_screen.dart';
import 'screens/rate_lock_screen.dart';
import 'screens/payment_methods_screen.dart';
import 'screens/payment_retry_screen.dart';
import 'screens/beneficiaries_screen.dart';
import 'screens/add_beneficiary_screen.dart';
import 'screens/register_screen.dart';
import 'screens/transaction_detail_screen.dart';
import 'screens/notification_screen.dart';
import 'screens/cards_screen.dart';
import 'screens/help_screen.dart';
import 'screens/kyc_verification_screen.dart';
import 'screens/journeys_screen.dart';
import 'screens/agent_performance_screen.dart';
import 'screens/customer_wallet_screen.dart';
import 'screens/notification_preferences_screen.dart';
import 'screens/multi_currency_screen.dart';
import 'screens/compliance_scheduling_screen.dart';
import 'screens/audit_export_screen.dart';
import 'providers/auth_provider.dart';

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
    // ── Auth & Onboarding ──────────────────────────────────────────────────
    GoRoute(path: '/splash', builder: (_, __) => const SplashScreen()),
    GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
    GoRoute(path: '/onboarding', builder: (_, __) => const OnboardingScreen()),
    GoRoute(path: '/pin-setup', builder: (_, __) => const PinSetupScreen()),

    // ── Core POS ──────────────────────────────────────────────────────────
    GoRoute(path: '/dashboard', builder: (_, __) => const DashboardScreen()),
    GoRoute(path: '/cash-in', builder: (_, __) => const CashInScreen()),
    GoRoute(path: '/cash-out', builder: (_, __) => const CashOutScreen()),
    GoRoute(path: '/send-money', builder: (_, __) => const SendMoneyScreen()),
    GoRoute(path: '/receive-money', builder: (_, __) => const ReceiveMoneyScreen()),
    GoRoute(path: '/bill-payment', builder: (_, __) => const BillPaymentScreen()),
    GoRoute(
      path: '/receipt/:ref',
      builder: (_, state) => ReceiptScreen(transactionRef: state.pathParameters['ref']!),
    ),

    // ── Float & Wallet ─────────────────────────────────────────────────────
    GoRoute(path: '/float', builder: (_, __) => const FloatScreen()),
    GoRoute(path: '/wallet', builder: (_, __) => const WalletScreen()),
    GoRoute(path: '/virtual-card', builder: (_, __) => const VirtualCardScreen()),
    GoRoute(path: '/savings-goals', builder: (_, __) => const SavingsGoalsScreen()),

    // ── History & Tracking ─────────────────────────────────────────────────
    GoRoute(path: '/history', builder: (_, __) => const HistoryScreen()),
    GoRoute(path: '/transaction-history', builder: (_, __) => const TransactionHistoryScreen()),
    GoRoute(
      path: '/transfer-tracking/:ref',
      builder: (_, state) => TransferTrackingScreen(
        transactionId: state.pathParameters['ref'],
      ),
    ),

    // ── Tools ─────────────────────────────────────────────────────────────
    GoRoute(path: '/qr-scanner', builder: (_, __) => const QrScannerScreen()),
    GoRoute(path: '/exchange-rates', builder: (_, __) => const ExchangeRatesScreen()),

    // ── Account & KYC ─────────────────────────────────────────────────────
    GoRoute(path: '/kyc', builder: (_, __) => const KycScreen()),
    GoRoute(path: '/profile', builder: (_, __) => const ProfileScreen()),
    GoRoute(path: '/referral', builder: (_, __) => const ReferralScreen()),

    // ── Settings & Support ─────────────────────────────────────────────────
    GoRoute(path: '/settings', builder: (_, __) => const SettingsScreen()),
    GoRoute(path: '/security-settings', builder: (_, __) => const SecuritySettingsScreen()),
    GoRoute(path: '/notifications', builder: (_, __) => const NotificationsScreen()),
    GoRoute(path: '/support', builder: (_, __) => const SupportScreen()),

    // ── Auth Extras ────────────────────────────────────────────────────────
    GoRoute(path: '/register', builder: (_, __) => const RegisterScreen()),
    GoRoute(path: '/biometric', builder: (_, __) => const BiometricScreen()),

    // ── Payments & Beneficiaries ───────────────────────────────────────────
    GoRoute(path: '/recurring-payments', builder: (_, __) => const RecurringPaymentsScreen()),
    GoRoute(path: '/payment-methods', builder: (_, __) => const PaymentMethodsScreen()),
    GoRoute(
      path: '/payment-retry/:id',
      builder: (_, state) => PaymentRetryScreen(transactionId: state.pathParameters['id']),
    ),
    GoRoute(path: '/payment-retry', builder: (_, __) => const PaymentRetryScreen()),
    GoRoute(path: '/beneficiaries', builder: (_, __) => const BeneficiariesScreen()),
    GoRoute(path: '/add-beneficiary', builder: (_, __) => const AddBeneficiaryScreen()),

    // ── Rate Tools ─────────────────────────────────────────────────────────
    GoRoute(path: '/rate-calculator', builder: (_, __) => const RateCalculatorScreen()),
    GoRoute(path: '/rate-lock', builder: (_, __) => const RateLockScreen()),

    // ── Notification Feed ─────────────────────────────────────────────────
    GoRoute(path: '/notification-feed', builder: (_, __) => const NotificationScreen()),

    // ── Transaction Detail ─────────────────────────────────────────────────
    GoRoute(
      path: '/transaction/:id',
      builder: (_, state) => TransactionDetailScreen(transactionId: state.pathParameters['id']!),
    ),
    // ── Cards, Help, KYC Verification, Journeys (parity additions) ─────────────
    GoRoute(path: '/cards', builder: (_, __) => const CardsScreen()),
    GoRoute(path: '/help', builder: (_, __) => const HelpScreen()),
    GoRoute(path: '/kyc-verification', builder: (_, __) => const KycVerificationScreen()),
    GoRoute(path: '/journeys', builder: (_, __) => const JourneysScreen()),

    // ── Mobile Parity (6 new screens) ─────────────────────────────────────
    GoRoute(path: '/agent-performance', builder: (_, __) => const AgentPerformanceScreen()),
    GoRoute(path: '/customer-wallet', builder: (_, __) => const CustomerWalletScreen()),
    GoRoute(path: '/notification-preferences', builder: (_, __) => const NotificationPreferencesScreen()),
    GoRoute(path: '/multi-currency', builder: (_, __) => const MultiCurrencyScreen()),
    GoRoute(path: '/compliance-scheduling', builder: (_, __) => const ComplianceSchedulingScreen()),
    GoRoute(path: '/audit-export', builder: (_, __) => const AuditExportScreen()),
  ],
  redirect: (context, state) {
    // Auth guard handled in SplashScreen
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
          seedColor: const Color(0xFF1A56DB), // 54Link brand blue
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
            minimumSize: const Size(double.infinity, 56),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
          filled: true,
        ),
        cardTheme: CardTheme(
          elevation: 2,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      ),
      routerConfig: _router,
    );
  }
}

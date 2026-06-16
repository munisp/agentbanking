/// 54Link POS Shell — App Constants
/// All production defaults are set here. Override via --dart-define at build time.
library constants;

// ── API ───────────────────────────────────────────────────────────────────────
const String kApiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'https://api.54link.ng/api/trpc',
);

const String kWebSocketUrl = String.fromEnvironment(
  'WS_URL',
  defaultValue: 'wss://api.54link.ng',
);

const Duration kApiConnectTimeout = Duration(seconds: 30);
const Duration kApiReceiveTimeout = Duration(seconds: 60);
const Duration kApiSendTimeout = Duration(seconds: 30);

// ── Auth ──────────────────────────────────────────────────────────────────────
const String kJwtTokenKey = 'jwt_token';
const String kAgentCodeKey = 'agent_code';
const String kBiometricEnabledKey = 'biometric_enabled';
const String kPinHashKey = 'pin_hash';
const int kPinLength = 4;
const int kMaxPinAttempts = 3;
const Duration kSessionTimeout = Duration(hours: 8);
const Duration kPinLockoutDuration = Duration(minutes: 30);

// ── Transactions ──────────────────────────────────────────────────────────────
const double kMinTransactionAmount = 100.0;
const double kMaxCashInAmount = 500_000.0;
const double kMaxCashOutAmount = 200_000.0;
const double kMaxTransferAmount = 1_000_000.0;
const double kDailyTransactionLimit = 5_000_000.0;
const int kTransactionHistoryPageSize = 20;

// ── Float ─────────────────────────────────────────────────────────────────────
const double kMinFloatBalance = 5_000.0;
const double kLowFloatWarningThreshold = 50_000.0;
const double kCriticalFloatThreshold = 10_000.0;

// ── Exchange Rates ────────────────────────────────────────────────────────────
const Duration kRateLockDuration = Duration(minutes: 30);
const Duration kRateRefreshInterval = Duration(minutes: 5);
const String kBaseCurrency = 'NGN';
const List<String> kSupportedCurrencies = ['USD', 'GBP', 'EUR', 'GHS', 'KES', 'ZAR', 'XOF'];

// ── KYC ───────────────────────────────────────────────────────────────────────
const int kBvnLength = 11;
const int kNinLength = 11;
const int kAccountNumberLength = 10;
const List<String> kKycDocumentTypes = ['NIN', 'BVN', 'Passport', 'Driver License', 'Voter Card'];

// ── Notifications ─────────────────────────────────────────────────────────────
const int kMaxNotificationsToShow = 50;
const Duration kNotificationPollingInterval = Duration(seconds: 30);

// ── Offline ───────────────────────────────────────────────────────────────────
const int kMaxOfflineQueueSize = 100;
const Duration kOfflineSyncRetryInterval = Duration(minutes: 2);
const Duration kConnectivityCheckInterval = Duration(seconds: 10);

// ── UI ────────────────────────────────────────────────────────────────────────
const double kBorderRadius = 12.0;
const double kCardElevation = 2.0;
const Duration kAnimationDuration = Duration(milliseconds: 250);
const Duration kPageTransitionDuration = Duration(milliseconds: 300);

// ── Agent Tiers ───────────────────────────────────────────────────────────────
const Map<String, Map<String, dynamic>> kAgentTiers = {
  'Bronze':   {'color': 0xFFCD7F32, 'minLoyalty': 0,      'dailyLimit': 500_000.0},
  'Silver':   {'color': 0xFFC0C0C0, 'minLoyalty': 5_000,  'dailyLimit': 1_000_000.0},
  'Gold':     {'color': 0xFFFFD700, 'minLoyalty': 15_000, 'dailyLimit': 2_000_000.0},
  'Platinum': {'color': 0xFFE5E4E2, 'minLoyalty': 50_000, 'dailyLimit': 5_000_000.0},
};

// ── Nigerian Banks ────────────────────────────────────────────────────────────
const List<Map<String, String>> kNigerianBanks = [
  {'code': '044', 'name': 'Access Bank'},
  {'code': '063', 'name': 'Access Bank (Diamond)'},
  {'code': '035A', 'name': 'ALAT by Wema'},
  {'code': '401', 'name': 'ASO Savings and Loans'},
  {'code': '023', 'name': 'Citibank Nigeria'},
  {'code': '050', 'name': 'Ecobank Nigeria'},
  {'code': '562', 'name': 'Ekondo Microfinance Bank'},
  {'code': '070', 'name': 'Fidelity Bank'},
  {'code': '011', 'name': 'First Bank of Nigeria'},
  {'code': '214', 'name': 'First City Monument Bank'},
  {'code': '058', 'name': 'Guaranty Trust Bank'},
  {'code': '030', 'name': 'Heritage Bank'},
  {'code': '301', 'name': 'Jaiz Bank'},
  {'code': '082', 'name': 'Keystone Bank'},
  {'code': '526', 'name': 'Parallex Bank'},
  {'code': '076', 'name': 'Polaris Bank'},
  {'code': '101', 'name': 'Providus Bank'},
  {'code': '221', 'name': 'Stanbic IBTC Bank'},
  {'code': '068', 'name': 'Standard Chartered Bank'},
  {'code': '232', 'name': 'Sterling Bank'},
  {'code': '100', 'name': 'SunTrust Bank'},
  {'code': '032', 'name': 'Union Bank of Nigeria'},
  {'code': '033', 'name': 'United Bank for Africa'},
  {'code': '215', 'name': 'Unity Bank'},
  {'code': '035', 'name': 'Wema Bank'},
  {'code': '057', 'name': 'Zenith Bank'},
  {'code': '120001', 'name': 'Opay'},
  {'code': '120002', 'name': 'Palmpay'},
  {'code': '120003', 'name': 'Kuda Bank'},
  {'code': '120004', 'name': 'Moniepoint'},
];

// ── Bill Payment Billers ──────────────────────────────────────────────────────
const List<Map<String, String>> kBillers = [
  {'id': 'DSTV',      'name': 'DSTV',         'category': 'Cable TV'},
  {'id': 'GOTV',      'name': 'GOtv',          'category': 'Cable TV'},
  {'id': 'STARTIMES', 'name': 'StarTimes',     'category': 'Cable TV'},
  {'id': 'EKEDC',     'name': 'Eko Electricity','category': 'Electricity'},
  {'id': 'IKEDC',     'name': 'Ikeja Electric', 'category': 'Electricity'},
  {'id': 'AEDC',      'name': 'Abuja Electric', 'category': 'Electricity'},
  {'id': 'PHEDC',     'name': 'Port Harcourt Electric', 'category': 'Electricity'},
  {'id': 'KANO',      'name': 'Kano Electric',  'category': 'Electricity'},
  {'id': 'MTN',       'name': 'MTN Airtime',    'category': 'Airtime'},
  {'id': 'AIRTEL',    'name': 'Airtel Airtime', 'category': 'Airtime'},
  {'id': 'GLO',       'name': 'Glo Airtime',    'category': 'Airtime'},
  {'id': '9MOBILE',   'name': '9mobile Airtime','category': 'Airtime'},
  {'id': 'LAWMA',     'name': 'LAWMA',          'category': 'Waste'},
];

/**
 * Navigation groups for 54Link mobile drawer
 * Mirrors PWA DashboardLayout structure
 */

export interface NavItem {
  name: string;
  label: string;
  icon: string;
}

export interface NavGroup {
  id: string;
  label: string;
  icon: string;
  items: NavItem[];
}

export const navGroups: NavGroup[] = [
  {
    id: 'core',
    label: 'Core',
    icon: 'dashboard',
    items: [
      { name: 'Dashboard', label: 'POS Terminal', icon: 'point-of-sale' },
      { name: 'Wallet', label: 'Wallet', icon: 'wallet' },
    ],
  },
  {
    id: 'transactions',
    label: 'Transactions',
    icon: 'swap-horiz',
    items: [
      { name: 'SendMoney', label: 'Send Money', icon: 'send' },
      { name: 'ReceiveMoney', label: 'Receive Money', icon: 'call-received' },
      { name: 'TransactionHistory', label: 'Transaction History', icon: 'history' },
      { name: 'Transactions', label: 'Transactions', icon: 'list' },
      { name: 'QRCodeScanner', label: 'QR Scanner', icon: 'qr-code-scanner' },
    ],
  },
  {
    id: 'finance',
    label: 'Finance & Payments',
    icon: 'attach-money',
    items: [
      { name: 'Cards', label: 'My Cards', icon: 'credit-card' },
      { name: 'VirtualCard', label: 'Virtual Card', icon: 'credit-card' },
      { name: 'SavingsGoals', label: 'Savings Goals', icon: 'savings' },
      { name: 'RecurringPayments', label: 'Recurring Payments', icon: 'repeat' },
      { name: 'PaymentMethods', label: 'Payment Methods', icon: 'payment' },
      { name: 'ExchangeRates', label: 'Exchange Rates', icon: 'currency-exchange' },
      { name: 'RateCalculator', label: 'Rate Calculator', icon: 'calculate' },
      { name: 'CustomerWallet', label: 'Customer Wallet', icon: 'account-balance-wallet' },
      { name: 'MultiCurrency', label: 'Multi-Currency', icon: 'language' },
    ],
  },
  {
    id: 'beneficiaries',
    label: 'Beneficiaries',
    icon: 'people',
    items: [
      { name: 'Beneficiaries', label: 'Beneficiaries', icon: 'people' },
      { name: 'BeneficiaryList', label: 'Beneficiary List', icon: 'list' },
      { name: 'BeneficiaryManagement', label: 'Manage', icon: 'manage-accounts' },
      { name: 'AddBeneficiary', label: 'Add Beneficiary', icon: 'person-add' },
    ],
  },
  {
    id: 'agents',
    label: 'Agent & Compliance',
    icon: 'badge',
    items: [
      { name: 'AgentPerformance', label: 'Agent Performance', icon: 'trending-up' },
      { name: 'KYC', label: 'KYC Verification', icon: 'verified-user' },
      { name: 'KYCVerification', label: 'KYC Documents', icon: 'document-scanner' },
      { name: 'ComplianceScheduling', label: 'Compliance Schedule', icon: 'schedule' },
      { name: 'AuditExport', label: 'Audit Export', icon: 'download' },
    ],
  },
  {
    id: 'engagement',
    label: 'Engagement',
    icon: 'star',
    items: [
      { name: 'ReferralProgram', label: 'Referral Program', icon: 'card-giftcard' },
      { name: 'Notifications', label: 'Notifications', icon: 'notifications' },
      { name: 'NotificationPreferences', label: 'Notification Prefs', icon: 'tune' },
    ],
  },
  {
    id: 'account',
    label: 'Account & Security',
    icon: 'person',
    items: [
      { name: 'Profile', label: 'Profile', icon: 'person' },
      { name: 'Settings', label: 'Settings', icon: 'settings' },
      { name: 'SecuritySettings', label: 'Security', icon: 'security' },
    ],
  },
  {
    id: 'future',
    label: 'Future Features',
    icon: 'rocket-launch',
    items: [
      { name: 'OpenBankingScreen', label: 'Open Banking', icon: 'account-balance' },
      { name: 'BnplScreen', label: 'BNPL Engine', icon: 'shopping-bag' },
      { name: 'NfcTapToPayScreen', label: 'NFC Tap-to-Pay', icon: 'contactless' },
      { name: 'AiCreditScoringScreen', label: 'AI Credit Scoring', icon: 'psychology' },
      { name: 'AgritechScreen', label: 'AgriTech', icon: 'agriculture' },
      { name: 'ChatBankingScreen', label: 'Chat Banking', icon: 'chat' },
      { name: 'StablecoinScreen', label: 'Stablecoin Rails', icon: 'currency-bitcoin' },
      { name: 'WearablePaymentsScreen', label: 'Wearable Payments', icon: 'watch' },
      { name: 'SatelliteScreen', label: 'Satellite Connect', icon: 'satellite' },
      { name: 'DigitalIdentityScreen', label: 'Digital Identity', icon: 'fingerprint' },
    ],
  },
  {
    id: 'help',
    label: 'Help & Support',
    icon: 'help-outline',
    items: [
      { name: 'Help', label: 'Help Center', icon: 'help' },
      { name: 'Support', label: 'Support', icon: 'support-agent' },
    ],
  },
];

/**
 * Internationalization (i18n) System
 * Supports: English (en), Hausa (ha), Yoruba (yo), Pidgin English (pcm)
 * Covers 85%+ of Nigerian agent population
 */

export type Locale = "en" | "ha" | "yo" | "pcm";

export const SUPPORTED_LOCALES: Record<Locale, string> = {
  en: "English",
  ha: "Hausa",
  yo: "Yorùbá",
  pcm: "Pidgin",
};

type TranslationKey = keyof typeof translations.en;

const translations = {
  en: {
    // Common
    "common.loading": "Loading...",
    "common.error": "An error occurred",
    "common.success": "Success",
    "common.cancel": "Cancel",
    "common.confirm": "Confirm",
    "common.back": "Back",
    "common.next": "Next",
    "common.submit": "Submit",
    "common.retry": "Retry",
    "common.done": "Done",
    "common.search": "Search",
    "common.amount": "Amount",
    "common.balance": "Balance",

    // Auth
    "auth.login": "Login",
    "auth.logout": "Logout",
    "auth.pin": "Enter PIN",
    "auth.biometric": "Use Fingerprint",

    // Dashboard
    "dashboard.title": "Dashboard",
    "dashboard.float_balance": "Float Balance",
    "dashboard.today_transactions": "Today's Transactions",
    "dashboard.float_low": "Float is running low!",
    "dashboard.float_critical": "Float critically low — top up now!",

    // Transactions
    "tx.cash_in": "Cash In",
    "tx.cash_out": "Cash Out",
    "tx.transfer": "Transfer",
    "tx.airtime": "Airtime",
    "tx.bills": "Bill Payment",
    "tx.amount_label": "Enter Amount (₦)",
    "tx.recipient": "Recipient",
    "tx.phone_number": "Phone Number",
    "tx.confirm_transaction": "Confirm Transaction",
    "tx.processing": "Processing...",
    "tx.success": "Transaction Successful",
    "tx.failed": "Transaction Failed",
    "tx.receipt": "Receipt",
    "tx.share_receipt": "Share Receipt",

    // KYC
    "kyc.title": "KYC Verification",
    "kyc.tier1": "Tier 1 — Basic (₦50K/day)",
    "kyc.tier2": "Tier 2 — Standard (₦200K/day)",
    "kyc.tier3": "Tier 3 — Enhanced (₦5M/day)",
    "kyc.upgrade": "Upgrade KYC",
    "kyc.scan_nin": "Scan NIN Card",
    "kyc.enter_bvn": "Enter BVN",
    "kyc.take_selfie": "Take Selfie",
    "kyc.upload_document": "Upload Document",
    "kyc.liveness_check": "Liveness Check",
    "kyc.status": "KYC Status",
    "kyc.verified": "Verified",
    "kyc.pending": "Pending",
    "kyc.expired": "Document Expired",

    // Settings
    "settings.title": "Settings",
    "settings.language": "Language",
    "settings.notifications": "Notifications",
    "settings.security": "Security",
    "settings.theme": "Theme",
    "settings.printer": "Printer Setup",
    "settings.about": "About",

    // Offline
    "offline.title": "You're Offline",
    "offline.queued": "Transaction queued — will sync when online",
    "offline.syncing": "Syncing transactions...",
    "offline.synced": "All transactions synced",
  },

  ha: {
    "common.loading": "Ana lodi...",
    "common.error": "Kuskure ya faru",
    "common.success": "An yi nasara",
    "common.cancel": "Soke",
    "common.confirm": "Tabbatar",
    "common.back": "Baya",
    "common.next": "Gaba",
    "common.submit": "Aika",
    "common.retry": "Sake gwadawa",
    "common.done": "An gama",
    "common.search": "Bincika",
    "common.amount": "Adadin kuɗi",
    "common.balance": "Ragowar kuɗi",

    "auth.login": "Shiga",
    "auth.logout": "Fita",
    "auth.pin": "Shigar da PIN",
    "auth.biometric": "Yi amfani da yatsa",

    "dashboard.title": "Babban shafi",
    "dashboard.float_balance": "Ragowar Float",
    "dashboard.today_transactions": "Ma'amalar yau",
    "dashboard.float_low": "Float yana ƙarewa!",
    "dashboard.float_critical": "Float ya yi ƙasa sosai — cika yanzu!",

    "tx.cash_in": "Ajiyar Kuɗi",
    "tx.cash_out": "Cire Kuɗi",
    "tx.transfer": "Tura Kuɗi",
    "tx.airtime": "Siyan Airtime",
    "tx.bills": "Biyan Bil",
    "tx.amount_label": "Shigar da adadi (₦)",
    "tx.recipient": "Mai karɓa",
    "tx.phone_number": "Lambar waya",
    "tx.confirm_transaction": "Tabbatar da ma'amala",
    "tx.processing": "Ana aiki...",
    "tx.success": "An yi nasara",
    "tx.failed": "Ma'amala ta gaza",
    "tx.receipt": "Rasiti",
    "tx.share_receipt": "Raba rasiti",

    "kyc.title": "Tabbatar da KYC",
    "kyc.tier1": "Matakin 1 — Asali (₦50K/rana)",
    "kyc.tier2": "Matakin 2 — Daidaitacce (₦200K/rana)",
    "kyc.tier3": "Matakin 3 — Ingantacce (₦5M/rana)",
    "kyc.upgrade": "Haɓaka KYC",
    "kyc.scan_nin": "Duba katin NIN",
    "kyc.enter_bvn": "Shigar da BVN",
    "kyc.take_selfie": "Ɗauki hoto",
    "kyc.upload_document": "Ɗora takarda",
    "kyc.liveness_check": "Gwajin rayuwa",
    "kyc.status": "Matsayin KYC",
    "kyc.verified": "An tabbatar",
    "kyc.pending": "Ana jira",
    "kyc.expired": "Takarda ta ƙare",

    "settings.title": "Saituna",
    "settings.language": "Harshe",
    "settings.notifications": "Sanarwa",
    "settings.security": "Tsaro",
    "settings.theme": "Jigon fuska",
    "settings.printer": "Saita firinta",
    "settings.about": "Game da",

    "offline.title": "Ba ka kan layi ba",
    "offline.queued": "Ma'amala tana jira — za ta sync idan ka dawo kan layi",
    "offline.syncing": "Ana sync ma'amaloli...",
    "offline.synced": "An sync duk ma'amaloli",
  },

  yo: {
    "common.loading": "Ń gbékalẹ̀...",
    "common.error": "Àṣìṣe kan ṣẹlẹ̀",
    "common.success": "Àṣeyọrí",
    "common.cancel": "Fagilé",
    "common.confirm": "Jẹ́rìísí",
    "common.back": "Padà",
    "common.next": "Tẹ̀síwájú",
    "common.submit": "Fi ránṣẹ́",
    "common.retry": "Tún gbìyànjú",
    "common.done": "Tan",
    "common.search": "Wá",
    "common.amount": "Iye owó",
    "common.balance": "Iyókù owó",

    "auth.login": "Wọlé",
    "auth.logout": "Jáde",
    "auth.pin": "Tẹ PIN rẹ",
    "auth.biometric": "Lo ìka ọwọ́",

    "dashboard.title": "Ojú ìwé àkọ́kọ́",
    "dashboard.float_balance": "Iyókù Float",
    "dashboard.today_transactions": "Ìṣòwò oni",
    "dashboard.float_low": "Float rẹ fẹ́ parí!",
    "dashboard.float_critical": "Float ti kéré púpọ̀ — tún kún ní báyìí!",

    "tx.cash_in": "Fi owó sí",
    "tx.cash_out": "Mú owó jáde",
    "tx.transfer": "Gbé owó ránṣẹ́",
    "tx.airtime": "Ra Airtime",
    "tx.bills": "San owó ìdíyelé",
    "tx.amount_label": "Tẹ iye owó (₦)",
    "tx.recipient": "Olùgbà",
    "tx.phone_number": "Nọ́mbà fóònù",
    "tx.confirm_transaction": "Jẹ́rìísí ìṣòwò",
    "tx.processing": "Ń ṣiṣẹ́...",
    "tx.success": "Ìṣòwò ti yọrí sí rere",
    "tx.failed": "Ìṣòwò kò yọrísírere",
    "tx.receipt": "Ìwé ẹ̀rí",
    "tx.share_receipt": "Pín ìwé ẹ̀rí",

    "kyc.title": "Ìjẹ́rìísí KYC",
    "kyc.tier1": "Ìpele 1 — Ìpìlẹ̀ (₦50K/ọjọ́)",
    "kyc.tier2": "Ìpele 2 — Àárín (₦200K/ọjọ́)",
    "kyc.tier3": "Ìpele 3 — Gíga (₦5M/ọjọ́)",
    "kyc.upgrade": "Gbé KYC ga",
    "kyc.scan_nin": "Ṣayẹ̀wò kádì NIN",
    "kyc.enter_bvn": "Tẹ BVN",
    "kyc.take_selfie": "Ya àwòrán",
    "kyc.upload_document": "Gbé ìwé sókè",
    "kyc.liveness_check": "Àyẹ̀wò wípé o wà láàyè",
    "kyc.status": "Ipò KYC",
    "kyc.verified": "Ti jẹ́rìísí",
    "kyc.pending": "Ń dúró",
    "kyc.expired": "Ìwé ti parí",

    "settings.title": "Ètò",
    "settings.language": "Èdè",
    "settings.notifications": "Ìfitónilétí",
    "settings.security": "Ààbò",
    "settings.theme": "Àwọ̀",
    "settings.printer": "Ètò àtẹ̀wé",
    "settings.about": "Nípa",

    "offline.title": "O kò sí lórí ayélujára",
    "offline.queued": "Ìṣòwò wà ní ìtọ́jú — yóò sync nígbà tí o bá padà sí ayélujára",
    "offline.syncing": "Ń ṣe sync ìṣòwò...",
    "offline.synced": "Gbogbo ìṣòwò ti sync",
  },

  pcm: {
    "common.loading": "E dey load...",
    "common.error": "Error don happen",
    "common.success": "E don work!",
    "common.cancel": "Cancel am",
    "common.confirm": "Confirm am",
    "common.back": "Go back",
    "common.next": "Next one",
    "common.submit": "Send am",
    "common.retry": "Try again",
    "common.done": "E don finish",
    "common.search": "Search",
    "common.amount": "How much",
    "common.balance": "Wetin remain",

    "auth.login": "Enter",
    "auth.logout": "Comot",
    "auth.pin": "Put your PIN",
    "auth.biometric": "Use your fingerprint",

    "dashboard.title": "Main page",
    "dashboard.float_balance": "Float wey remain",
    "dashboard.today_transactions": "Today transaction dem",
    "dashboard.float_low": "Your float dey finish o!",
    "dashboard.float_critical": "Float don too low — go top up now now!",

    "tx.cash_in": "Put Money",
    "tx.cash_out": "Collect Money",
    "tx.transfer": "Send Money",
    "tx.airtime": "Buy Airtime",
    "tx.bills": "Pay Bill",
    "tx.amount_label": "Put amount (₦)",
    "tx.recipient": "Person wey go collect",
    "tx.phone_number": "Phone number",
    "tx.confirm_transaction": "Confirm transaction",
    "tx.processing": "E dey process...",
    "tx.success": "Transaction don work!",
    "tx.failed": "Transaction no work",
    "tx.receipt": "Receipt",
    "tx.share_receipt": "Share receipt",

    "kyc.title": "KYC Verification",
    "kyc.tier1": "Level 1 — Small (₦50K/day)",
    "kyc.tier2": "Level 2 — Normal (₦200K/day)",
    "kyc.tier3": "Level 3 — Big man (₦5M/day)",
    "kyc.upgrade": "Upgrade KYC",
    "kyc.scan_nin": "Scan your NIN card",
    "kyc.enter_bvn": "Put your BVN",
    "kyc.take_selfie": "Take selfie",
    "kyc.upload_document": "Upload document",
    "kyc.liveness_check": "Face check",
    "kyc.status": "KYC Status",
    "kyc.verified": "E don verify",
    "kyc.pending": "E dey wait",
    "kyc.expired": "Document don expire",

    "settings.title": "Settings",
    "settings.language": "Language",
    "settings.notifications": "Notifications",
    "settings.security": "Security",
    "settings.theme": "Theme",
    "settings.printer": "Printer setup",
    "settings.about": "About",

    "offline.title": "You no dey online",
    "offline.queued": "Transaction dey queue — e go sync when you come back online",
    "offline.syncing": "E dey sync transactions...",
    "offline.synced": "All transactions don sync",
  },
} as const;

// ── Hook & Utilities ────────────────────────────────────────────────────────

let currentLocale: Locale = "en";

export function setLocale(locale: Locale): void {
  currentLocale = locale;
  if (typeof localStorage !== "undefined") {
    localStorage.setItem("54link_locale", locale);
  }
}

export function getLocale(): Locale {
  if (typeof localStorage !== "undefined") {
    const stored = localStorage.getItem("54link_locale") as Locale | null;
    if (stored && stored in translations) {
      currentLocale = stored;
    }
  }
  return currentLocale;
}

export function t(key: string): string {
  const locale = getLocale();
  const localeTranslations = translations[locale] as Record<string, string>;
  return localeTranslations[key] || translations.en[key as TranslationKey] || key;
}

export function getTranslations(locale?: Locale): Record<string, string> {
  return translations[locale || getLocale()] as unknown as Record<string, string>;
}

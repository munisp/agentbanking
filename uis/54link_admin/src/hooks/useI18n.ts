/**
 * Internationalization / Localization (#26)
 * Supports: English, Hausa, Yoruba, Igbo, French, Arabic
 * Persists language preference to localStorage.
 */

import { useCallback, useState } from "react";

export type Locale = "en" | "ha" | "yo" | "ig" | "fr" | "ar";

export interface TranslationSet {
  // Navigation
  dashboard: string;
  customers: string;
  transactions: string;
  loans: string;
  cards: string;
  settings: string;
  logout: string;

  // CrudWorkspace
  totalRecords: string;
  create: string;
  edit: string;
  delete: string;
  search: string;
  export: string;
  refresh: string;
  filter: string;
  save: string;
  cancel: string;
  loading: string;
  noRecords: string;
  serviceUnavailable: string;
  retry: string;
  page: string;
  of: string;
  showing: string;
  required: string;
  actions: string;

  // Status
  active: string;
  pending: string;
  approved: string;
  rejected: string;
  completed: string;

  // Common
  yes: string;
  no: string;
  confirm: string;
  success: string;
  error: string;
  warning: string;
  online: string;
  offline: string;
  darkMode: string;
  lightMode: string;
  language: string;
}

const translations: Record<Locale, TranslationSet> = {
  en: {
    dashboard: "Dashboard", customers: "Customers", transactions: "Transactions", loans: "Loans", cards: "Cards", settings: "Settings", logout: "Logout",
    totalRecords: "Total Records", create: "Create", edit: "Edit", delete: "Delete", search: "Search", export: "Export", refresh: "Refresh", filter: "Filter", save: "Save", cancel: "Cancel", loading: "Loading...", noRecords: "No records yet", serviceUnavailable: "Service Unavailable", retry: "Retry", page: "Page", of: "of", showing: "Showing", required: "required", actions: "Actions",
    active: "Active", pending: "Pending", approved: "Approved", rejected: "Rejected", completed: "Completed",
    yes: "Yes", no: "No", confirm: "Confirm", success: "Success", error: "Error", warning: "Warning", online: "Online", offline: "Offline", darkMode: "Dark Mode", lightMode: "Light Mode", language: "Language",
  },
  ha: {
    dashboard: "Allon Dubawa", customers: "Abokan Ciniki", transactions: "Ma'amaloli", loans: "Basussuka", cards: "Katinan Banki", settings: "Saituna", logout: "Fita",
    totalRecords: "Jimillar Bayanan", create: "Kirkira", edit: "Gyara", delete: "Goge", search: "Nema", export: "Fitar da Bayanai", refresh: "Sabunta", filter: "Tace", save: "Ajiye", cancel: "Soke", loading: "Ana lodi...", noRecords: "Babu bayanan tukuna", serviceUnavailable: "Sabis ba ya samuwa", retry: "Sake gwadawa", page: "Shafi", of: "daga", showing: "Ana nuna", required: "ana bukata", actions: "Ayyuka",
    active: "Mai aiki", pending: "Ana jira", approved: "An amince", rejected: "An ki", completed: "An kammala",
    yes: "Eh", no: "A'a", confirm: "Tabbatar", success: "Nasara", error: "Kuskure", warning: "Gargadi", online: "A kan layi", offline: "Ba a kan layi", darkMode: "Yanayin Duhu", lightMode: "Yanayin Haske", language: "Harshe",
  },
  yo: {
    dashboard: "Ibi Akojopo", customers: "Onibara", transactions: "Idunadura", loans: "Awin", cards: "Kaadi Ile-ifowopamo", settings: "Eto", logout: "Jade",
    totalRecords: "Apapọ Akosile", create: "Da", edit: "Satunkọ", delete: "Pa re", search: "Wa", export: "Gbe Jade", refresh: "Tun Wo", filter: "Se", save: "Fi Pamọ", cancel: "Fagile", loading: "N sise...", noRecords: "Ko si akosile kankan", serviceUnavailable: "Iṣẹ ko si", retry: "Tun gbiyanju", page: "Oju-iwe", of: "ninu", showing: "N fihan", required: "o nilo", actions: "Ise",
    active: "N sise", pending: "N duro de", approved: "Ti fọwọ si", rejected: "Ti kọ", completed: "Ti pari",
    yes: "Bẹẹni", no: "Rara", confirm: "Jẹri", success: "Aṣeyọri", error: "Aṣiṣe", warning: "Ikilo", online: "Lori ayelujara", offline: "Ko si lori ayelujara", darkMode: "Ipo Dudu", lightMode: "Ipo Imọlẹ", language: "Ede",
  },
  ig: {
    dashboard: "Ngalaba", customers: "Ndi Ahia", transactions: "Azumahia", loans: "Ego Ibinye", cards: "Kaadi Ego", settings: "Ntọala", logout: "Pụọ",
    totalRecords: "Nchikota Ndekọ", create: "Mepụta", edit: "Dezie", delete: "Hichapụ", search: "Chọọ", export: "Bupụta", refresh: "Mee ọhụrụ", filter: "Nyocha", save: "Chekwaa", cancel: "Kagbuo", loading: "Na-ebugo...", noRecords: "Enweghị ndekọ", serviceUnavailable: "Ọrụ adịghị", retry: "Nwaa ọzọ", page: "Peeji", of: "n'ime", showing: "Na-egosi", required: "achọrọ", actions: "Omume",
    active: "Na-arụ ọrụ", pending: "Na-echere", approved: "Kwadoro", rejected: "Ajụrụ", completed: "Emechara",
    yes: "Ee", no: "Mba", confirm: "Kwado", success: "Ọganiihu", error: "Njehie", warning: "Ịdọ aka ná ntị", online: "Na intanetị", offline: "Na-enweghị intanetị", darkMode: "Ọchịchịrị", lightMode: "Ìhè", language: "Asụsụ",
  },
  fr: {
    dashboard: "Tableau de Bord", customers: "Clients", transactions: "Transactions", loans: "Prêts", cards: "Cartes", settings: "Paramètres", logout: "Déconnexion",
    totalRecords: "Total des Enregistrements", create: "Créer", edit: "Modifier", delete: "Supprimer", search: "Rechercher", export: "Exporter", refresh: "Actualiser", filter: "Filtrer", save: "Enregistrer", cancel: "Annuler", loading: "Chargement...", noRecords: "Aucun enregistrement", serviceUnavailable: "Service Indisponible", retry: "Réessayer", page: "Page", of: "sur", showing: "Affichage", required: "requis", actions: "Actions",
    active: "Actif", pending: "En attente", approved: "Approuvé", rejected: "Rejeté", completed: "Terminé",
    yes: "Oui", no: "Non", confirm: "Confirmer", success: "Succès", error: "Erreur", warning: "Avertissement", online: "En ligne", offline: "Hors ligne", darkMode: "Mode Sombre", lightMode: "Mode Clair", language: "Langue",
  },
  ar: {
    dashboard: "لوحة المعلومات", customers: "العملاء", transactions: "المعاملات", loans: "القروض", cards: "البطاقات", settings: "الإعدادات", logout: "تسجيل الخروج",
    totalRecords: "إجمالي السجلات", create: "إنشاء", edit: "تعديل", delete: "حذف", search: "بحث", export: "تصدير", refresh: "تحديث", filter: "تصفية", save: "حفظ", cancel: "إلغاء", loading: "جاري التحميل...", noRecords: "لا توجد سجلات", serviceUnavailable: "الخدمة غير متوفرة", retry: "إعادة المحاولة", page: "صفحة", of: "من", showing: "عرض", required: "مطلوب", actions: "إجراءات",
    active: "نشط", pending: "قيد الانتظار", approved: "موافق عليه", rejected: "مرفوض", completed: "مكتمل",
    yes: "نعم", no: "لا", confirm: "تأكيد", success: "نجاح", error: "خطأ", warning: "تحذير", online: "متصل", offline: "غير متصل", darkMode: "الوضع الداكن", lightMode: "الوضع الفاتح", language: "اللغة",
  },
};

const localeNames: Record<Locale, string> = {
  en: "English",
  ha: "Hausa",
  yo: "Yorùbá",
  ig: "Igbo",
  fr: "Français",
  ar: "العربية",
};

const STORAGE_KEY = "54link-dev-locale";

export function useI18n() {
  const [locale, setLocaleState] = useState<Locale>(() => {
    if (typeof window === "undefined") return "en";
    return (localStorage.getItem(STORAGE_KEY) as Locale) ?? "en";
  });

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    localStorage.setItem(STORAGE_KEY, l);
    document.documentElement.setAttribute("lang", l);
    document.documentElement.setAttribute("dir", l === "ar" ? "rtl" : "ltr");
  }, []);

  const t = translations[locale];

  return { locale, setLocale, t, locales: Object.keys(translations) as Locale[], localeNames };
}

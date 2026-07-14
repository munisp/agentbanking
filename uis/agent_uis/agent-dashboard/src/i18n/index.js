import en from "./locales/en.json";
import ha from "./locales/ha.json";
import yo from "./locales/yo.json";
import pcm from "./locales/pcm.json";

const LOCALES = { en, ha, yo, pcm };
const STORAGE_KEY = "54agent_locale";
const DEFAULT_LOCALE = "en";

export const SUPPORTED_LANGUAGES = [
  { code: "en",  label: "English" },
  { code: "ha",  label: "Hausa" },
  { code: "yo",  label: "Yorùbá" },
  { code: "pcm", label: "Pidgin" },
];

function getStoredLocale() {
  try { return localStorage.getItem(STORAGE_KEY) || DEFAULT_LOCALE; } catch { return DEFAULT_LOCALE; }
}

function setStoredLocale(code) {
  try { localStorage.setItem(STORAGE_KEY, code); } catch {}
}

// Resolve a dot-path like "nav.cash_in" against the locale object
function resolve(obj, path) {
  return path.split(".").reduce((cur, key) => (cur && cur[key] !== undefined ? cur[key] : null), obj);
}

// Singleton state (plain JS — no React dependency)
let currentLocale = getStoredLocale();
const listeners = new Set();

export function setLocale(code) {
  if (!LOCALES[code]) return;
  currentLocale = code;
  setStoredLocale(code);
  listeners.forEach(fn => fn(code));
}

export function getLocale() { return currentLocale; }

export function t(key, fallback) {
  const locale = LOCALES[currentLocale];
  const en_locale = LOCALES.en;
  return resolve(locale, key) ?? resolve(en_locale, key) ?? fallback ?? key;
}

// React hook
import { useState, useEffect } from "react";

export function useI18n() {
  const [locale, setLocaleState] = useState(currentLocale);

  useEffect(() => {
    const handler = (code) => setLocaleState(code);
    listeners.add(handler);
    return () => listeners.delete(handler);
  }, []);

  return {
    locale,
    setLocale,
    t,
    languages: SUPPORTED_LANGUAGES,
  };
}

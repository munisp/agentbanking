import { Globe } from "lucide-react";
import React, { useState } from "react";
import { SUPPORTED_LANGUAGES, useI18n } from "../i18n";

const LanguageSelector = () => {
  const { locale, setLocale } = useI18n();
  const [open, setOpen] = useState(false);
  const current = SUPPORTED_LANGUAGES.find(l => l.code === locale) || SUPPORTED_LANGUAGES[0];

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
        title="Change language"
      >
        <Globe className="w-4 h-4" />
        <span className="text-xs font-medium">{current.code.toUpperCase()}</span>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 z-20 bg-white border border-gray-200 rounded-xl shadow-lg py-1 min-w-32">
            {SUPPORTED_LANGUAGES.map(lang => (
              <button
                key={lang.code}
                onClick={() => { setLocale(lang.code); setOpen(false); }}
                className={`w-full flex items-center justify-between px-3 py-2 text-sm hover:bg-gray-50 transition-colors ${locale === lang.code ? "text-blue-600 font-medium" : "text-gray-700"}`}
              >
                <span>{lang.label}</span>
                {locale === lang.code && <span className="text-blue-600 text-xs">✓</span>}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default LanguageSelector;

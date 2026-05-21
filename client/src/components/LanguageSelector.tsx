import { useState, useRef, useEffect } from "react";
import { Globe } from "lucide-react";
import { SUPPORTED_LANGUAGES, changeLanguage } from "@/lib/i18n";
import { useTranslation } from "react-i18next";
import { haptic } from "@/lib/haptics";

export default function LanguageSelector() {
  const [open, setOpen] = useState(false);
  const { i18n } = useTranslation();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node))
        setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const handleSelect = (code: string) => {
    changeLanguage(code);
    setOpen(false);
    haptic("micro");
  };

  const currentLang = SUPPORTED_LANGUAGES.find(l => l.code === i18n.language);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2 py-1.5 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors touch-target"
        title="Select Language"
        aria-label="Select language"
      >
        <Globe className="h-4 w-4" />
        <span className="hidden sm:inline">
          {currentLang?.label || "English"}
        </span>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-48 bg-popover text-popover-foreground border border-border rounded-lg shadow-lg z-50 py-1">
          {SUPPORTED_LANGUAGES.map(lang => (
            <button
              key={lang.code}
              onClick={() => handleSelect(lang.code)}
              className={`w-full text-left px-3 py-2.5 text-sm hover:bg-accent transition-colors flex items-center justify-between touch-target ${
                i18n.language === lang.code ? "bg-accent/50 font-medium" : ""
              }`}
            >
              <span>
                {lang.flag} {lang.label}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

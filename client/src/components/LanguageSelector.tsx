import { useState, useRef, useEffect } from "react";
import { Globe } from "lucide-react";
import {
  getAvailableLocales,
  getLocale,
  setLocale,
  type Locale,
} from "@/lib/i18n";

export default function LanguageSelector() {
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState<Locale>(getLocale());
  const ref = useRef<HTMLDivElement>(null);
  const locales = getAvailableLocales();

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node))
        setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const handleSelect = (code: Locale) => {
    setLocale(code);
    setCurrent(code);
    setOpen(false);
    // Force re-render of the whole app
    window.dispatchEvent(new Event("locale-changed"));
  };

  const currentLocale = locales.find(l => l.code === current);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2 py-1.5 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
        title="Select Language"
      >
        <Globe className="h-4 w-4" />
        <span className="hidden sm:inline">
          {currentLocale?.nativeName || "English"}
        </span>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-48 bg-popover text-popover-foreground border border-border rounded-lg shadow-lg z-50 py-1">
          {locales.map(locale => (
            <button
              key={locale.code}
              onClick={() => handleSelect(locale.code)}
              className={`w-full text-left px-3 py-2 text-sm hover:bg-accent transition-colors flex items-center justify-between ${
                current === locale.code ? "bg-accent/50 font-medium" : ""
              }`}
            >
              <span>{locale.nativeName}</span>
              <span className="text-xs text-muted-foreground">
                {locale.name}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

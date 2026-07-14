// Design philosophy: restored original banking PWA shell.
// This navigation preserves the original bottom-bar behavior on handheld screens while giving
// desktop users a proper banking rail that feels integrated with the wider 54link-dev platform.

import { Link, useLocation } from "wouter";
import { CreditCard, House, QrCode, ReceiptText, Settings2 } from "lucide-react";

function navClass(active: boolean) {
  return active
    ? "text-emerald-700"
    : "text-stone-400 transition-colors hover:text-emerald-600";
}

export default function CustomerBottomNav() {
  const [location] = useLocation();

  const items = [
    { href: "/", label: "Home", icon: House, match: (value: string) => value === "/" || value === "/customer/dashboard" },
    { href: "/customer/transfers", label: "Transfers", icon: ReceiptText, match: (value: string) => value.startsWith("/customer/transfers") },
    { href: "/customer/qr", label: "Scan", icon: QrCode, match: (value: string) => value.startsWith("/customer/qr") },
    { href: "/customer/cards", label: "Cards", icon: CreditCard, match: (value: string) => value.startsWith("/customer/cards") },
    { href: "/customer/settings", label: "Settings", icon: Settings2, match: (value: string) => value.startsWith("/customer/settings") },
  ] as const;

  return (
    <>
      <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-emerald-100 bg-white/96 px-4 pb-[max(0.6rem,env(safe-area-inset-bottom))] pt-2 shadow-[0_-10px_30px_rgba(6,78,59,0.08)] backdrop-blur lg:hidden">
        <div className="mx-auto flex max-w-md items-end justify-between gap-2">
          {items.map((item) => {
            const active = item.match(location);
            const Icon = item.icon;
            const isCenter = item.label === "Scan";

            if (isCenter) {
              return (
                <Link key={item.href} href={item.href} className="-mt-6 flex min-w-0 flex-col items-center gap-1">
                  <span className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-600 text-white shadow-[0_16px_30px_rgba(5,150,105,0.34)] transition-transform hover:scale-[1.03]">
                    <Icon size={24} />
                  </span>
                  <span className="text-[11px] font-medium text-stone-500">{item.label}</span>
                </Link>
              );
            }

            return (
              <Link key={item.href} href={item.href} className={`flex min-w-0 flex-1 flex-col items-center gap-1 py-1 text-center ${navClass(active)}`}>
                <Icon size={20} strokeWidth={2} />
                <span className="text-[11px] font-medium">{item.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>

      <nav className="fixed inset-x-0 bottom-6 z-30 hidden lg:block">
        <div className="mx-auto flex w-full max-w-7xl justify-center px-6 xl:px-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-stone-200 bg-white/95 px-3 py-3 shadow-[0_20px_50px_rgba(15,23,42,0.12)] backdrop-blur">
            {items.map((item) => {
              const active = item.match(location);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-sm font-medium transition ${active ? "bg-emerald-600 text-white shadow-[0_10px_25px_rgba(5,150,105,0.22)]" : "text-stone-600 hover:bg-stone-100"}`}
                >
                  <Icon size={18} strokeWidth={2} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
            <div className="ml-2 h-8 w-px bg-stone-200" />
            <Link href="/admin" className="inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-sm font-medium text-stone-700 transition hover:bg-stone-100">
              Admin dashboard
            </Link>
          </div>
        </div>
      </nav>
    </>
  );
}

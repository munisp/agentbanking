// Design philosophy: faithful recovered main-bank administration with a desktop-first control plane.
// This shell mirrors the extracted admin architecture and avoids mixing non-admin mobile routes into the admin navigation.

import type { ReactNode } from "react";
import { Link, useLocation } from "wouter";
import {
  Activity,
  BarChart3,
  ChevronRight,
  Handshake,
  Shield,
  ToggleLeft,
  UserCog,
  Workflow,
} from "lucide-react";

interface AdminWorkspaceLayoutProps {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
  actions?: ReactNode;
}

const adminLinks = [
  { href: "/admin", label: "Overview", icon: Activity },
  { href: "/admin/feature-flags", label: "Feature flags", icon: ToggleLeft },
  { href: "/admin/security", label: "Security", icon: Shield },
  { href: "/admin/onboarding", label: "Partner onboarding", icon: Handshake },
  { href: "/admin/banking", label: "BankingOps", icon: Workflow },
  { href: "/admin/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/admin/users", label: "Users", icon: UserCog },
] as const;

export default function AdminWorkspaceLayout({
  eyebrow,
  title,
  description,
  children,
  actions,
}: AdminWorkspaceLayoutProps) {
  const [location] = useLocation();

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(5,150,105,0.12),_transparent_34%),linear-gradient(180deg,#f8fafc_0%,#f1f5f9_100%)] text-stone-900">
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <header className="overflow-hidden rounded-[2rem] bg-gradient-to-br from-stone-950 via-emerald-950 to-emerald-700 px-6 py-6 text-white shadow-[0_24px_80px_rgba(15,23,42,0.22)] sm:px-8 lg:px-10 lg:py-8">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div className="max-w-4xl">
              <p className="text-xs uppercase tracking-[0.32em] text-emerald-200/80">{eyebrow}</p>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl lg:text-[2.7rem]">{title}</h1>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-emerald-50/85 sm:text-base">{description}</p>
            </div>
            <div className="flex flex-wrap gap-3">{actions}</div>
          </div>
        </header>

        <div className="mt-6 grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="rounded-[1.8rem] bg-white p-4 shadow-[0_18px_60px_rgba(15,23,42,0.08)] sm:p-5">
            <div className="rounded-[1.4rem] bg-stone-950 px-4 py-4 text-white">
              <p className="text-xs uppercase tracking-[0.24em] text-emerald-200/80">Recovered admin navigation</p>
              <p className="mt-2 text-lg font-semibold">54link-dev dashboard modules</p>
              <p className="mt-2 text-sm leading-6 text-stone-300">
                Overview, feature governance, security, BankingOps, analytics, and users restored as bank-level admin pages from the extracted archive.
              </p>
            </div>
            <nav className="mt-4 space-y-2">
              {adminLinks.map((item) => {
                const Icon = item.icon;
                const active = location === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center justify-between rounded-[1.2rem] px-4 py-3 text-sm font-medium transition ${
                      active
                        ? "bg-emerald-50 text-emerald-800"
                        : "bg-stone-50 text-stone-600 hover:bg-stone-100 hover:text-stone-900"
                    }`}
                  >
                    <span className="flex items-center gap-3">
                      <span className={`inline-flex h-9 w-9 items-center justify-center rounded-full ${active ? "bg-emerald-100 text-emerald-700" : "bg-white text-stone-500"}`}>
                        <Icon size={16} />
                      </span>
                      {item.label}
                    </span>
                    <ChevronRight size={16} className={active ? "text-emerald-500" : "text-stone-400"} />
                  </Link>
                );
              })}
            </nav>
            <div className="mt-4 rounded-[1.4rem] border border-stone-100 bg-stone-50 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-stone-400">Customer continuity</p>
              <p className="mt-2 text-sm font-semibold text-stone-900">The customer PWA remains separate from admin.</p>
              <p className="mt-2 text-sm leading-6 text-stone-500">
                The restored retail journey remains available without being confused with the recovered main-bank administrative route set.
              </p>
              <Link href="/customer/dashboard" className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-emerald-700">
                Open customer dashboard <ChevronRight size={16} />
              </Link>
            </div>
          </aside>

          <main className="space-y-6">{children}</main>
        </div>
      </div>
    </div>
  );
}

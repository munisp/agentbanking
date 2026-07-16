import type { PropsWithChildren } from "react";
import { Link, useLocation } from "wouter";
import { Activity, ArrowUpRight, Landmark, Layers3, ShieldCheck, Workflow } from "lucide-react";

import type { ProductSurface, ServiceHealth } from "@/lib/platform";

type ProductShellProps = PropsWithChildren<{
  products: ProductSurface[];
  services: ServiceHealth[];
  title: string;
  eyebrow: string;
  summary: string;
}>;

const shellIcons = {
  retail: Landmark,
  operations: Workflow,
  treasury: Activity,
  trade: Layers3,
  partnerships: ShieldCheck,
} as const;

function statusTone(status: ServiceHealth["status"] | ProductSurface["status"]) {
  switch (status) {
    case "healthy":
      return "border-emerald-400/35 bg-emerald-500/10 text-emerald-200";
    case "degraded":
      return "border-amber-300/35 bg-amber-300/10 text-amber-100";
    case "down":
      return "border-rose-400/35 bg-rose-500/10 text-rose-100";
    default:
      return "border-white/15 bg-white/5 text-stone-100";
  }
}

export default function ProductShell({
  products,
  services,
  title,
  eyebrow,
  summary,
  children,
}: ProductShellProps) {
  const [location] = useLocation();

  return (
    <div className="min-h-screen bg-stone-950 text-stone-100">
      <div className="border-b border-white/10 bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.16),_transparent_22%),linear-gradient(180deg,#16130f_0%,#09090b_100%)]">
        <div className="container grid gap-10 px-6 py-10 lg:grid-cols-[0.27fr_0.73fr] lg:py-12">
          <aside className="rounded-[2rem] border border-white/10 bg-white/5 p-5 backdrop-blur">
            <div className="border-b border-white/10 pb-5">
              <p className="text-xs uppercase tracking-[0.34em] text-amber-300/75">54link-dev platform</p>
              <h1 className="mt-4 font-serif text-4xl text-white">A broader product surface for operations, treasury, and specialised banking.</h1>
              <p className="mt-4 text-sm leading-7 text-stone-300">
                The product shell now exposes restored banking domains through a shared navigation, service-health rail,
                and routed workspaces that remain anchored to the original core banking surface.
              </p>
            </div>

            <nav className="mt-6 space-y-2">
              {products.map((product) => {
                const Icon = shellIcons[product.category];
                const isActive = location === product.route;
                return (
                  <Link
                    key={product.key}
                    href={product.route}
                    className={`flex items-start justify-between gap-3 rounded-[1.4rem] border px-4 py-3 transition ${
                      isActive
                        ? "border-amber-300/40 bg-amber-300/12 text-white"
                        : "border-white/8 bg-white/[0.03] text-stone-300 hover:border-white/15 hover:bg-white/[0.06]"
                    }`}
                  >
                    <span className="flex gap-3">
                      <span className="mt-0.5 inline-flex h-10 w-10 items-center justify-center rounded-full bg-white/8 text-amber-200">
                        <Icon size={18} />
                      </span>
                      <span>
                        <span className="block text-sm font-semibold text-current">{product.title}</span>
                        <span className="mt-1 block text-xs leading-5 text-stone-400">{product.summary}</span>
                      </span>
                    </span>
                    <span className={`rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.24em] ${statusTone(product.status)}`}>
                      {product.status}
                    </span>
                  </Link>
                );
              })}
            </nav>
          </aside>

          <section className="space-y-6">
            <header className="rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/30 backdrop-blur">
              <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
                <div className="max-w-3xl">
                  <p className="text-xs uppercase tracking-[0.34em] text-amber-300/75">{eyebrow}</p>
                  <h2 className="mt-4 font-serif text-5xl leading-tight text-white">{title}</h2>
                  <p className="mt-4 max-w-2xl text-base leading-8 text-stone-300">{summary}</p>
                </div>
                <Link href="/" className="inline-flex items-center gap-2 rounded-full border border-white/15 px-5 py-3 text-sm font-semibold text-stone-100 transition hover:border-amber-300/45 hover:text-amber-200">
                  Return to core banking <ArrowUpRight size={16} />
                </Link>
              </div>
            </header>

            <div className="grid gap-4 xl:grid-cols-3">
              {services.map((service) => (
                <article key={service.name} className="rounded-[1.5rem] border border-white/10 bg-stone-900/80 p-4 shadow-lg shadow-black/20">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="text-base font-semibold text-white">{service.name}</h3>
                    <span className={`rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.24em] ${statusTone(service.status)}`}>
                      {service.status}
                    </span>
                  </div>
                  <p className="mt-3 text-sm leading-7 text-stone-300">{service.description}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {service.dependencies.map((dependency) => (
                      <span key={dependency} className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-stone-300">
                        {dependency}
                      </span>
                    ))}
                  </div>
                  {service.latencyMs ? <p className="mt-4 text-xs uppercase tracking-[0.22em] text-stone-500">Observed latency {service.latencyMs}ms</p> : null}
                </article>
              ))}
            </div>

            <div className="rounded-[2rem] border border-white/10 bg-stone-950/70 p-6 shadow-2xl shadow-black/30">{children}</div>
          </section>
        </div>
      </div>
    </div>
  );
}

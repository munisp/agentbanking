import { useEffect, useMemo, useState } from "react";
import { Link } from "wouter";
import { AlertTriangle, ArrowRight, Layers3, Landmark, ShieldCheck, Workflow } from "lucide-react";

import ProductShell from "@/components/ProductShell";
import {
  formatRelativeIso,
  getPlatformOverview,
  type OverviewResponse,
  type ProductSurface,
  type ServiceHealth,
} from "@/lib/platform";

const categoryIcons = {
  retail: Landmark,
  operations: Workflow,
  treasury: Layers3,
  trade: Layers3,
  partnerships: ShieldCheck,
} as const;

function toneClass(status: ProductSurface["status"]) {
  switch (status) {
    case "healthy":
      return "text-emerald-200 border-emerald-300/30 bg-emerald-500/10";
    case "degraded":
      return "text-amber-100 border-amber-300/30 bg-amber-300/10";
    case "down":
      return "text-rose-100 border-rose-400/30 bg-rose-500/10";
    default:
      return "text-stone-100 border-white/15 bg-white/5";
  }
}

function ProductCard({ product }: { product: ProductSurface }) {
  const Icon = categoryIcons[product.category];

  return (
    <article className="rounded-[1.7rem] border border-white/10 bg-white/[0.03] p-5 shadow-lg shadow-black/20 transition hover:-translate-y-0.5 hover:border-amber-300/30 hover:bg-white/[0.05]">
      <div className="flex items-start justify-between gap-4">
        <span className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-amber-300/12 text-amber-200">
          <Icon size={20} />
        </span>
        <span className={`rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.24em] ${toneClass(product.status)}`}>
          {product.status}
        </span>
      </div>
      <h3 className="mt-5 font-serif text-3xl text-white">{product.title}</h3>
      <p className="mt-3 text-sm leading-7 text-stone-300">{product.summary}</p>
      <div className="mt-5 flex flex-wrap gap-2">
        {product.services.map((service) => (
          <span key={service} className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-stone-300">
            {service}
          </span>
        ))}
      </div>
      <Link href={product.route} className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-amber-200 transition hover:text-amber-100">
        Open workspace <ArrowRight size={16} />
      </Link>
    </article>
  );
}

export default function OperationsCenter() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selectedProductKey, setSelectedProductKey] = useState<string>("");

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const data = await getPlatformOverview();
        if (active) {
          setOverview(data);
          setError(null);
        }
      } catch (issue) {
        if (active) {
          setError(issue instanceof Error ? issue.message : "Unable to load platform overview");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  const services: ServiceHealth[] = useMemo(() => overview?.serviceHealth ?? [], [overview]);
  const products: ProductSurface[] = useMemo(() => overview?.products ?? [], [overview]);

  const filteredProducts = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return products;

    return products.filter((product) => {
      const haystack = [product.title, product.summary, product.category, product.route, ...product.services]
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalized);
    });
  }, [products, query]);

  useEffect(() => {
    if (filteredProducts.length === 0) {
      setSelectedProductKey("");
      return;
    }

    setSelectedProductKey((current) => (filteredProducts.some((product) => product.key === current) ? current : filteredProducts[0]?.key ?? ""));
  }, [filteredProducts]);

  const selectedProduct = useMemo(
    () => filteredProducts.find((product) => product.key === selectedProductKey) ?? filteredProducts[0] ?? null,
    [filteredProducts, selectedProductKey],
  );

  const relatedServices = useMemo(() => {
    if (!selectedProduct) return services.slice(0, 3);
    return services.filter((service) => selectedProduct.services.includes(service.name)).slice(0, 4);
  }, [selectedProduct, services]);

  return (
    <ProductShell
      products={products}
      services={services.slice(0, 3)}
      eyebrow="Unified control center"
      title="A routed product shell that exposes restored banking domains."
      summary="Operations, treasury, specialised product teams, and integration owners now work from the same control surface. Instead of a single editorial homepage, the application exposes teller operations, Islamic banking, trade finance, agricultural insurance, dispute management, ERPNext sync, and ledger reconciliation as real destinations with shared status context."
    >
      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <section>
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-amber-300/75">Product domains</p>
              <h3 className="mt-3 font-serif text-4xl text-white">Restored banking workspaces</h3>
            </div>
            <div className="flex flex-col gap-3 xl:items-end">
              <p className="text-sm text-stone-400">Updated {formatRelativeIso(overview?.asOf)}</p>
              <label className="flex items-center gap-3 rounded-full border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-stone-300">
                <span className="uppercase tracking-[0.18em] text-stone-500">Search</span>
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="teller, ledger, trade, auth…"
                  className="min-w-[220px] bg-transparent text-white outline-none placeholder:text-stone-500"
                />
              </label>
            </div>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            {loading
              ? Array.from({ length: 4 }).map((_, index) => (
                  <div key={index} className="h-56 animate-pulse rounded-[1.7rem] border border-white/10 bg-white/[0.03]" />
                ))
              : filteredProducts.map((product) => (
                  <button key={product.key} type="button" onClick={() => setSelectedProductKey(product.key)} className="text-left">
                    <div className={selectedProduct?.key === product.key ? "rounded-[1.9rem] border border-amber-300/35 p-1" : "rounded-[1.9rem] border border-transparent p-1 transition hover:border-white/10"}>
                      <ProductCard product={product} />
                    </div>
                  </button>
                ))}

            {!loading && filteredProducts.length === 0 ? (
              <article className="rounded-[1.7rem] border border-dashed border-white/15 bg-white/[0.03] p-6 text-sm leading-7 text-stone-300">
                No routed banking workspaces match <span className="font-semibold text-white">{query}</span>. Try a module, service, or route keyword such as teller, trade, auth, or ledger.
              </article>
            ) : null}

            <article className="rounded-[1.7rem] border border-amber-300/20 bg-amber-300/10 p-5 shadow-lg shadow-black/20 transition hover:-translate-y-0.5 hover:border-amber-200/40">
              <div className="flex items-start justify-between gap-4">
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-amber-300/20 text-amber-100">
                  <ShieldCheck size={20} />
                </span>
                <span className="rounded-full border border-amber-300/30 bg-amber-300/15 px-2.5 py-1 text-[10px] uppercase tracking-[0.24em] text-amber-50">
                  shell wiring
                </span>
              </div>
              <h3 className="mt-5 font-serif text-3xl text-white">Identity and channels</h3>
              <p className="mt-3 text-sm leading-7 text-amber-50/90">
                Bring authentication context and the USSD channel into the same visible operating shell so infrastructure services stop remaining hidden from the main platform flow.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                {['auth-service', 'ussd-gateway-service'].map((service) => (
                  <span key={service} className="rounded-full border border-amber-200/20 bg-black/10 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-amber-50/90">
                    {service}
                  </span>
                ))}
              </div>
              <Link href="/identity-channels" className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-white transition hover:text-amber-100">
                Open workspace <ArrowRight size={16} />
              </Link>
            </article>
          </div>
        </section>

        <section className="space-y-4">
          <article className="rounded-[1.7rem] border border-white/10 bg-white/[0.03] p-5 shadow-lg shadow-black/20">
            <p className="text-xs uppercase tracking-[0.3em] text-amber-300/75">Selected workspace</p>
            <h3 className="mt-3 font-serif text-3xl text-white">{selectedProduct?.title ?? "Awaiting workspace selection"}</h3>
            <p className="mt-4 text-sm leading-7 text-stone-300">
              {selectedProduct?.summary ?? "Choose a routed workspace to inspect its route, service dependencies, and operational health context from the shared shell."}
            </p>
            {selectedProduct ? (
              <div className="mt-5 space-y-3">
                <div className="rounded-[1.2rem] border border-white/10 bg-stone-950/50 p-4">
                  <p className="text-xs uppercase tracking-[0.22em] text-stone-500">Route</p>
                  <strong className="mt-2 block text-2xl text-white">{selectedProduct.route}</strong>
                  <p className="mt-3 text-sm leading-7 text-stone-300">Category: {selectedProduct.category} · Status: {selectedProduct.status}</p>
                </div>
                <div className="rounded-[1.2rem] border border-white/10 bg-stone-950/50 p-4">
                  <p className="text-xs uppercase tracking-[0.22em] text-stone-500">Service dependencies</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {selectedProduct.services.map((service) => (
                      <span key={service} className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-stone-200">
                        {service}
                      </span>
                    ))}
                  </div>
                </div>
                <Link href={selectedProduct.route} className="inline-flex items-center gap-2 rounded-full border border-amber-300/35 px-4 py-2 text-sm font-semibold text-amber-100 transition hover:border-amber-200/45 hover:text-white">
                  Open selected workspace <ArrowRight size={16} />
                </Link>
              </div>
            ) : null}
          </article>

          <article className="rounded-[1.7rem] border border-amber-300/20 bg-amber-300/10 p-5 shadow-lg shadow-black/20">
            <div className="flex items-start gap-3">
              <span className="mt-1 inline-flex h-10 w-10 items-center justify-center rounded-full bg-amber-300/20 text-amber-100">
                <AlertTriangle size={18} />
              </span>
              <div className="w-full">
                <h3 className="text-lg font-semibold text-white">Current remediation focus</h3>
                <p className="mt-2 text-sm leading-7 text-amber-50/90">
                  Teller, ERPNext, Islamic banking, trade finance, agricultural insurance, and dispute management have been promoted into explicit platform workspaces because they were previously missing from the visible product surface and from the external developer review. The next implementation waves continue replacing embedded seed and mock flows with service-backed data and product-specific APIs.
                </p>
                <div className="mt-4 space-y-3">
                  {relatedServices.map((service) => (
                    <div key={service.name} className="rounded-[1.2rem] border border-white/10 bg-black/10 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-semibold text-white">{service.name}</p>
                        <span className={`rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.24em] ${toneClass(service.status)}`}>
                          {service.status}
                        </span>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-amber-50/90">{service.description}</p>
                    </div>
                  ))}
                </div>
                {error ? <p className="mt-3 text-sm text-rose-100">{error}</p> : null}
              </div>
            </div>
          </article>
        </section>
      </div>
    </ProductShell>
  );
}

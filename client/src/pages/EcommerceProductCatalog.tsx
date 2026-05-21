import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { haptic } from "@/lib/haptics";

function ProductSkeleton() {
  return (
    <div className="border rounded-xl p-4 space-y-3 animate-pulse">
      <div className="w-full h-40 bg-gray-200 rounded-lg skeleton" />
      <div className="h-4 bg-gray-200 rounded w-3/4 skeleton" />
      <div className="h-3 bg-gray-200 rounded w-1/2 skeleton" />
      <div className="h-5 bg-gray-200 rounded w-1/3 skeleton" />
    </div>
  );
}

export default function EcommerceProductCatalog() {
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState<number | undefined>();
  const [page, setPage] = useState(0);
  const limit = 20;

  const { data: products, isLoading } =
    trpc.ecommerceCatalog.listProducts.useQuery({
      limit,
      offset: page * limit,
      categoryId,
      search: search || undefined,
      active: true,
    }) as any;

  const { data: categories } =
    trpc.ecommerceCatalog.listCategories.useQuery() as any;
  const { data: lowStock } = trpc.ecommerceCatalog.lowStockAlerts.useQuery({
    limit: 10,
  }) as any;

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      {/* Sticky Header with Search (P0: mobile-first) */}
      <div className="bg-white border-b sticky top-0 z-30 safe-top">
        <div className="max-w-6xl mx-auto px-4 py-3">
          <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
            <h1 className="text-xl font-bold flex-shrink-0">Products</h1>
            <div className="flex gap-2 w-full sm:w-auto">
              <input
                type="search"
                placeholder="Search products..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                inputMode="search"
                autoComplete="off"
                className="flex-1 sm:w-64 px-4 py-2.5 border rounded-xl text-base touch-target"
              />
              <select
                value={categoryId || ""}
                onChange={e => {
                  setCategoryId(
                    e.target.value ? Number(e.target.value) : undefined
                  );
                  haptic("micro");
                }}
                className="px-3 py-2.5 border rounded-xl text-sm touch-target"
                aria-label="Filter by category"
              >
                <option value="">All</option>
                {categories?.categories?.map((cat: any) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 max-w-6xl mx-auto w-full p-4 space-y-4">
        {/* Low Stock Alerts */}
        {lowStock && lowStock.alerts?.length > 0 && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
            <h3 className="font-medium text-yellow-800 text-sm">
              ⚠ Low Stock ({lowStock.count})
            </h3>
            <div className="mt-1 text-xs text-yellow-700 space-y-0.5">
              {lowStock.alerts.slice(0, 3).map((item: any) => (
                <div key={item.id}>
                  {item.sku}: {item.quantity - item.reserved} left
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Product Grid with Skeleton Loading (P1) */}
        {isLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <ProductSkeleton key={i} />
            ))}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {products?.products?.map((product: any) => (
                <button
                  key={product.id}
                  onClick={() => haptic("micro")}
                  className="border rounded-xl p-3 hover:shadow-md transition-all text-left bg-white active:scale-98 touch-target"
                >
                  {product.imageUrl ? (
                    <img
                      src={product.imageUrl}
                      alt={product.name}
                      className="w-full h-32 sm:h-40 object-cover rounded-lg mb-2"
                      loading="lazy"
                    />
                  ) : (
                    <div className="w-full h-32 sm:h-40 bg-gray-100 rounded-lg mb-2 flex items-center justify-center text-3xl">
                      📦
                    </div>
                  )}
                  <h3 className="font-medium text-sm leading-tight line-clamp-2">
                    {product.name}
                  </h3>
                  <p className="text-xs text-gray-400 mt-0.5">{product.sku}</p>
                  <p className="text-base font-bold mt-1.5">
                    {product.currency} {Number(product.price).toLocaleString()}
                  </p>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full mt-1.5 inline-block ${
                      product.status === "active"
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {product.status}
                  </span>
                </button>
              ))}
            </div>

            {/* Pagination (P0: touch targets) */}
            <div className="flex justify-between items-center py-4">
              <span className="text-xs text-gray-500">
                {page * limit + 1}–
                {Math.min((page + 1) * limit, products?.total || 0)} of{" "}
                {products?.total || 0}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setPage(Math.max(0, page - 1));
                    haptic("micro");
                  }}
                  disabled={page === 0}
                  className="px-4 py-2.5 border rounded-xl text-sm font-medium disabled:opacity-30 transition-all active:scale-95 touch-target"
                >
                  ← Prev
                </button>
                <button
                  onClick={() => {
                    setPage(page + 1);
                    haptic("micro");
                  }}
                  disabled={(page + 1) * limit >= (products?.total || 0)}
                  className="px-4 py-2.5 border rounded-xl text-sm font-medium disabled:opacity-30 transition-all active:scale-95 touch-target"
                >
                  Next →
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

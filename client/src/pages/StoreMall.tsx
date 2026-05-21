import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { haptic } from "@/lib/haptics";

const NIGERIAN_STATES = [
  "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue",
  "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", "FCT",
  "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi",
  "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", "Oyo",
  "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara",
];

const CATEGORIES = [
  "All", "Electronics", "Phones & Accessories", "Fashion", "Groceries",
  "Health & Beauty", "Home & Garden", "Auto Parts", "Food & Beverages",
  "Computing", "Building Materials", "Farming & Agriculture",
];

function StoreSkeleton() {
  return (
    <div className="bg-white border rounded-2xl overflow-hidden animate-pulse">
      <div className="h-32 bg-gray-200 skeleton" />
      <div className="p-4 space-y-2">
        <div className="h-5 bg-gray-200 rounded w-3/4 skeleton" />
        <div className="h-3 bg-gray-200 rounded w-full skeleton" />
        <div className="h-3 bg-gray-200 rounded w-1/2 skeleton" />
      </div>
    </div>
  );
}

function StarDisplay({ rating }: { rating: number }) {
  return (
    <span className="text-yellow-500 text-xs">
      {[1, 2, 3, 4, 5].map(i => (
        <span key={i}>{i <= Math.round(rating) ? "★" : "☆"}</span>
      ))}
    </span>
  );
}

export default function StoreMall() {
  const [search, setSearch] = useState("");
  const [state, setState] = useState("");
  const [category, setCategory] = useState("");
  const [sortBy, setSortBy] = useState<"popular" | "rating" | "newest" | "name">("popular");
  const [page, setPage] = useState(0);
  const limit = 20;

  const { data, isLoading } = trpc.agentStore.discoverStores.useQuery({
    limit,
    offset: page * limit,
    search: search || undefined,
    state: state || undefined,
    category: category || undefined,
    sortBy,
  }) as any;

  const stores = data?.stores ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / limit);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Hero */}
      <div className="bg-gradient-to-br from-blue-600 to-blue-800 text-white safe-top">
        <div className="max-w-6xl mx-auto px-4 py-8 sm:py-12">
          <h1 className="text-3xl sm:text-4xl font-bold">54Link Mall</h1>
          <p className="text-blue-100 mt-2 text-sm sm:text-base">
            Discover agent stores across Nigeria. Shop from local businesses, delivered to your door.
          </p>

          {/* Search */}
          <div className="mt-5 flex gap-2">
            <input
              type="search"
              placeholder="Search stores, products, categories..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="flex-1 px-4 py-3 rounded-xl text-gray-900 text-base bg-white touch-target"
            />
            <button
              onClick={() => haptic("micro")}
              className="px-5 py-3 bg-white/20 backdrop-blur rounded-xl font-medium touch-target"
            >
              Search
            </button>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white border-b sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-4 py-3">
          <div className="flex gap-3 items-center overflow-x-auto pb-1">
            <select
              value={state}
              onChange={e => { setState(e.target.value); setPage(0); }}
              className="px-3 py-2 border rounded-lg text-sm whitespace-nowrap touch-target"
              aria-label="Filter by state"
            >
              <option value="">All States</option>
              {NIGERIAN_STATES.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>

            <div className="flex gap-1.5 overflow-x-auto flex-1">
              {CATEGORIES.map(cat => (
                <button
                  key={cat}
                  onClick={() => {
                    setCategory(cat === "All" ? "" : cat);
                    setPage(0);
                    haptic("micro");
                  }}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap border ${
                    (cat === "All" && !category) || category === cat
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-gray-600 border-gray-300"
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>

            <select
              value={sortBy}
              onChange={e => setSortBy(e.target.value as typeof sortBy)}
              className="px-3 py-2 border rounded-lg text-sm whitespace-nowrap touch-target"
              aria-label="Sort by"
            >
              <option value="popular">Most Popular</option>
              <option value="rating">Highest Rated</option>
              <option value="newest">Newest</option>
              <option value="name">A-Z</option>
            </select>
          </div>
        </div>
      </div>

      {/* Store Grid */}
      <div className="max-w-6xl mx-auto p-4">
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <StoreSkeleton key={i} />
            ))}
          </div>
        ) : stores.length === 0 ? (
          <div className="text-center py-20">
            <div className="text-6xl mb-3">🏪</div>
            <h2 className="text-xl font-bold">No Stores Found</h2>
            <p className="text-gray-500 mt-1 text-sm">
              Try adjusting your search or filters.
            </p>
          </div>
        ) : (
          <>
            <p className="text-sm text-gray-500 mb-4">
              {total} store{total !== 1 ? "s" : ""} found
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {stores.map((store: any) => (
                <a
                  key={store.id}
                  href={`/store/${store.slug}`}
                  className="bg-white border rounded-2xl overflow-hidden hover:shadow-lg transition-shadow group"
                >
                  {/* Store Banner */}
                  <div
                    className="h-32 relative"
                    style={{
                      background: store.bannerUrl
                        ? undefined
                        : `linear-gradient(135deg, ${store.themeColor || "#3b82f6"}, ${store.themeColor || "#3b82f6"}cc)`,
                    }}
                  >
                    {store.bannerUrl && (
                      <img
                        src={store.bannerUrl}
                        alt=""
                        className="w-full h-full object-cover"
                        loading="lazy"
                      />
                    )}
                    {!store.bannerUrl && (
                      <div className="w-full h-full flex items-center justify-center">
                        <span className="text-white/20 text-6xl font-bold">
                          {store.storeName.charAt(0)}
                        </span>
                      </div>
                    )}

                    {/* Logo */}
                    <div className="absolute -bottom-6 left-4">
                      {store.logoUrl ? (
                        <img
                          src={store.logoUrl}
                          alt=""
                          className="w-14 h-14 rounded-xl border-3 border-white object-cover shadow-sm"
                        />
                      ) : (
                        <div
                          className="w-14 h-14 rounded-xl border-3 border-white flex items-center justify-center text-xl font-bold text-white shadow-sm"
                          style={{ backgroundColor: store.themeColor || "#3b82f6" }}
                        >
                          {store.storeName.charAt(0)}
                        </div>
                      )}
                    </div>

                    {store.isVerified && (
                      <div className="absolute top-2 right-2 bg-blue-600 text-white text-xs px-2 py-0.5 rounded-full">
                        Verified
                      </div>
                    )}
                  </div>

                  {/* Store Info */}
                  <div className="p-4 pt-8">
                    <h3 className="font-bold text-base group-hover:text-blue-600 transition-colors line-clamp-1">
                      {store.storeName}
                    </h3>
                    {store.description && (
                      <p className="text-sm text-gray-500 mt-0.5 line-clamp-2">
                        {store.description}
                      </p>
                    )}

                    <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                      {store.city && (
                        <span className="flex items-center gap-1">
                          📍 {store.city}
                        </span>
                      )}
                      <StarDisplay rating={Number(store.averageRating || 0)} />
                      <span>{store.reviewCount} reviews</span>
                    </div>

                    <div className="flex items-center gap-2 mt-2.5">
                      {store.categories?.slice(0, 3).map((cat: string) => (
                        <span
                          key={cat}
                          className="px-2 py-0.5 bg-gray-100 rounded text-xs text-gray-600"
                        >
                          {cat}
                        </span>
                      ))}
                      {(store.categories?.length ?? 0) > 3 && (
                        <span className="text-xs text-gray-400">
                          +{store.categories.length - 3}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-3 mt-3 pt-3 border-t text-xs text-gray-500">
                      <span>{store.totalSales} sales</span>
                      {store.deliveryEnabled && <span>🚚 Delivery</span>}
                      {store.pickupEnabled && <span>📍 Pickup</span>}
                    </div>
                  </div>
                </a>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8">
                <button
                  onClick={() => { setPage(p => Math.max(0, p - 1)); haptic("micro"); }}
                  disabled={page === 0}
                  className="px-4 py-2 border rounded-lg text-sm disabled:opacity-40 touch-target"
                >
                  Previous
                </button>
                <span className="text-sm text-gray-500">
                  Page {page + 1} of {totalPages}
                </span>
                <button
                  onClick={() => { setPage(p => Math.min(totalPages - 1, p + 1)); haptic("micro"); }}
                  disabled={page >= totalPages - 1}
                  className="px-4 py-2 border rounded-lg text-sm disabled:opacity-40 touch-target"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

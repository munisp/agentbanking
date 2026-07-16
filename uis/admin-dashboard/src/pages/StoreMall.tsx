import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { haptic } from "@/lib/haptics";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const NIGERIAN_STATES = [
  "Abia",
  "Adamawa",
  "Akwa Ibom",
  "Anambra",
  "Bauchi",
  "Bayelsa",
  "Benue",
  "Borno",
  "Cross River",
  "Delta",
  "Ebonyi",
  "Edo",
  "Ekiti",
  "Enugu",
  "FCT",
  "Gombe",
  "Imo",
  "Jigawa",
  "Kaduna",
  "Kano",
  "Katsina",
  "Kebbi",
  "Kogi",
  "Kwara",
  "Lagos",
  "Nasarawa",
  "Niger",
  "Ogun",
  "Ondo",
  "Osun",
  "Oyo",
  "Plateau",
  "Rivers",
  "Sokoto",
  "Taraba",
  "Yobe",
  "Zamfara",
];

const CATEGORIES = [
  "All",
  "Electronics",
  "Phones & Accessories",
  "Fashion",
  "Groceries",
  "Health & Beauty",
  "Home & Garden",
  "Auto Parts",
  "Food & Beverages",
  "Computing",
  "Building Materials",
  "Farming & Agriculture",
];

function StoreSkeleton() {
  return (
    <Card className="overflow-hidden animate-pulse">
      <div className="h-32 bg-muted skeleton" />
      <CardContent className="p-4 space-y-2">
        <div className="h-5 bg-muted rounded w-3/4 skeleton" />
        <div className="h-3 bg-muted rounded w-full skeleton" />
        <div className="h-3 bg-muted rounded w-1/2 skeleton" />
      </CardContent>
    </Card>
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
  const [sortBy, setSortBy] = useState<
    "popular" | "rating" | "newest" | "name"
  >("popular");
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
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-foreground">54agent Mall</h1>
          <p className="text-muted-foreground">
            Discover agent stores across Nigeria. Shop from local businesses,
            delivered to your door.
          </p>
        </div>

        {/* Search & Filters */}
        <Card>
          <CardContent className="pt-6 space-y-4">
            <div className="flex gap-2">
              <Input
                type="search"
                placeholder="Search stores, products, categories..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="flex-1"
              />
              <Button onClick={() => haptic("micro")} variant="secondary">
                Search
              </Button>
            </div>

            <div className="flex gap-3 items-center overflow-x-auto pb-1">
              <select
                value={state}
                onChange={e => {
                  setState(e.target.value);
                  setPage(0);
                }}
                className="px-3 py-2 border border-input bg-background rounded-md text-sm text-foreground whitespace-nowrap"
                aria-label="Filter by state"
              >
                <option value="">All States</option>
                {NIGERIAN_STATES.map(s => (
                  <option key={s} value={s}>
                    {s}
                  </option>
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
                        ? "bg-primary text-primary-foreground border-primary"
                        : "bg-card text-foreground border-border hover:bg-accent"
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>

              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value as typeof sortBy)}
                className="px-3 py-2 border border-input bg-background rounded-md text-sm text-foreground whitespace-nowrap"
                aria-label="Sort by"
              >
                <option value="popular">Most Popular</option>
                <option value="rating">Highest Rated</option>
                <option value="newest">Newest</option>
                <option value="name">A-Z</option>
              </select>
            </div>
          </CardContent>
        </Card>

        {/* Store Grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <StoreSkeleton key={i} />
            ))}
          </div>
        ) : stores.length === 0 ? (
          <Card>
            <CardContent className="text-center py-20">
              <div className="text-6xl mb-3">🏪</div>
              <h2 className="text-xl font-bold text-foreground">
                No Stores Found
              </h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Try adjusting your search or filters.
              </p>
            </CardContent>
          </Card>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              {total} store{total !== 1 ? "s" : ""} found
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {stores.map((store: any) => (
                <a
                  key={store.id}
                  href={`/store/${store.slug}`}
                  className="block"
                >
                  <Card className="overflow-hidden hover:border-primary/50 transition-colors group h-full">
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
                            className="w-14 h-14 rounded-xl border-2 border-background object-cover shadow-sm"
                          />
                        ) : (
                          <div
                            className="w-14 h-14 rounded-xl border-2 border-background flex items-center justify-center text-xl font-bold text-white shadow-sm"
                            style={{
                              backgroundColor: store.themeColor || "#3b82f6",
                            }}
                          >
                            {store.storeName.charAt(0)}
                          </div>
                        )}
                      </div>

                      {store.isVerified && (
                        <Badge className="absolute top-2 right-2 bg-primary text-primary-foreground text-xs">
                          Verified
                        </Badge>
                      )}
                    </div>

                    {/* Store Info */}
                    <CardContent className="p-4 pt-8">
                      <h3 className="font-bold text-base text-foreground group-hover:text-primary transition-colors line-clamp-1">
                        {store.storeName}
                      </h3>
                      {store.description && (
                        <p className="text-sm text-muted-foreground mt-0.5 line-clamp-2">
                          {store.description}
                        </p>
                      )}

                      <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                        {store.city && (
                          <span className="flex items-center gap-1">
                            📍 {store.city}
                          </span>
                        )}
                        <StarDisplay
                          rating={Number(store.averageRating || 0)}
                        />
                        <span>{store.reviewCount} reviews</span>
                      </div>

                      <div className="flex items-center gap-2 mt-2.5">
                        {store.categories?.slice(0, 3).map((cat: string) => (
                          <span
                            key={cat}
                            className="px-2 py-0.5 bg-muted rounded text-xs text-muted-foreground"
                          >
                            {cat}
                          </span>
                        ))}
                        {(store.categories?.length ?? 0) > 3 && (
                          <span className="text-xs text-muted-foreground">
                            +{store.categories.length - 3}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-3 mt-3 pt-3 border-t border-border text-xs text-muted-foreground">
                        <span>{store.totalSales} sales</span>
                        {store.deliveryEnabled && <span>🚚 Delivery</span>}
                        {store.pickupEnabled && <span>📍 Pickup</span>}
                      </div>
                    </CardContent>
                  </Card>
                </a>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setPage(p => Math.max(0, p - 1));
                    haptic("micro");
                  }}
                  disabled={page === 0}
                >
                  Previous
                </Button>
                <span className="text-sm text-muted-foreground">
                  Page {page + 1} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setPage(p => Math.min(totalPages - 1, p + 1));
                    haptic("micro");
                  }}
                  disabled={page >= totalPages - 1}
                >
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

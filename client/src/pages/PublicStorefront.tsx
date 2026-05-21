import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { haptic } from "@/lib/haptics";

function ProductSkeleton() {
  return (
    <div className="border rounded-xl p-3 space-y-2 animate-pulse bg-white">
      <div className="w-full h-36 bg-gray-200 rounded-lg skeleton" />
      <div className="h-4 bg-gray-200 rounded w-3/4 skeleton" />
      <div className="h-3 bg-gray-200 rounded w-1/2 skeleton" />
    </div>
  );
}

function StarRating({ rating }: { rating: number }) {
  return (
    <span className="inline-flex items-center text-yellow-500 text-sm">
      {[1, 2, 3, 4, 5].map(i => (
        <span key={i}>{i <= Math.round(rating) ? "★" : "☆"}</span>
      ))}
      <span className="ml-1 text-xs text-gray-500">({rating.toFixed(1)})</span>
    </span>
  );
}

export default function PublicStorefront() {
  // Extract slug from URL path: /store/:slug
  const slug = window.location.pathname.split("/store/")[1]?.split("/")[0] || "";

  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState<"products" | "reviews" | "about">("products");

  const { data: store, isLoading: storeLoading } = trpc.agentStore.getStoreBySlug.useQuery(
    { slug },
    { enabled: !!slug }
  ) as any;

  const { data: products, isLoading: productsLoading } =
    trpc.agentStore.getStoreProducts.useQuery(
      { storeId: store?.id ?? 0, limit: 40, search: search || undefined },
      { enabled: !!store?.id }
    ) as any;

  const { data: reviews } = trpc.storeReviews.getStoreReviews.useQuery(
    { storeId: store?.id ?? 0, limit: 10 },
    { enabled: !!store?.id && activeTab === "reviews" }
  ) as any;

  if (storeLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="mt-3 text-gray-500 text-sm">Loading store...</p>
        </div>
      </div>
    );
  }

  if (!store) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="text-center">
          <div className="text-5xl mb-3">🔍</div>
          <h1 className="text-xl font-bold">Store Not Found</h1>
          <p className="text-gray-500 mt-1 text-sm">
            This store doesn&apos;t exist or may have been closed.
          </p>
          <a
            href="/ecommerce/mall"
            className="inline-block mt-4 px-6 py-3 bg-blue-600 text-white rounded-xl font-medium"
          >
            Browse Mall
          </a>
        </div>
      </div>
    );
  }

  const themeColor = store.themeColor || "#3b82f6";
  const isOpen = (() => {
    if (!store.businessHours) return null;
    const days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
    const today = days[new Date().getDay()];
    const todayHours = store.businessHours[today];
    if (!todayHours) return false;
    const now = new Date();
    const currentTime = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    return currentTime >= todayHours.open && currentTime <= todayHours.close;
  })();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Store Header / Banner */}
      <div
        className="relative h-48 sm:h-56"
        style={{ backgroundColor: themeColor }}
      >
        {store.bannerUrl ? (
          <img
            src={store.bannerUrl}
            alt=""
            className="w-full h-full object-cover"
          />
        ) : (
          <div
            className="w-full h-full flex items-center justify-center"
            style={{
              background: `linear-gradient(135deg, ${themeColor}, ${themeColor}dd)`,
            }}
          >
            <span className="text-white/30 text-8xl font-bold">
              {store.storeName.charAt(0)}
            </span>
          </div>
        )}

        {/* Store Info Overlay */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-4">
          <div className="max-w-5xl mx-auto flex items-end gap-4">
            {store.logoUrl ? (
              <img
                src={store.logoUrl}
                alt=""
                className="w-16 h-16 rounded-xl border-2 border-white object-cover"
              />
            ) : (
              <div
                className="w-16 h-16 rounded-xl border-2 border-white flex items-center justify-center text-2xl font-bold text-white"
                style={{ backgroundColor: themeColor }}
              >
                {store.storeName.charAt(0)}
              </div>
            )}
            <div className="flex-1 text-white pb-0.5">
              <h1 className="text-xl font-bold leading-tight flex items-center gap-2">
                {store.storeName}
                {store.isVerified && (
                  <span className="text-blue-300 text-base" title="Verified">✓</span>
                )}
              </h1>
              <div className="flex items-center gap-3 text-sm text-white/80 mt-0.5">
                {store.city && <span>{store.city}, {store.state}</span>}
                {isOpen !== null && (
                  <span className={`inline-flex items-center gap-1 ${isOpen ? "text-green-300" : "text-red-300"}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${isOpen ? "bg-green-400" : "bg-red-400"}`} />
                    {isOpen ? "Open" : "Closed"}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="bg-white border-b">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-6 text-sm text-gray-600 overflow-x-auto">
          <div className="flex items-center gap-1.5 whitespace-nowrap">
            <StarRating rating={Number(store.averageRating || 0)} />
            <span>({store.reviewCount} reviews)</span>
          </div>
          <span className="text-gray-300">|</span>
          <span className="whitespace-nowrap">{store.totalSales} sales</span>
          {store.deliveryEnabled && (
            <>
              <span className="text-gray-300">|</span>
              <span className="whitespace-nowrap">🚚 Delivery</span>
            </>
          )}
          {store.pickupEnabled && (
            <>
              <span className="text-gray-300">|</span>
              <span className="whitespace-nowrap">📍 Pickup</span>
            </>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-4 flex gap-0">
          {(["products", "reviews", "about"] as const).map(tab => (
            <button
              key={tab}
              onClick={() => { setActiveTab(tab); haptic("micro"); }}
              className={`px-4 py-3 text-sm font-medium capitalize border-b-2 transition-colors ${
                activeTab === tab
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500"
              }`}
            >
              {tab === "reviews"
                ? `Reviews (${store.reviewCount})`
                : tab}
            </button>
          ))}
        </div>
      </div>

      <div className="max-w-5xl mx-auto p-4">
        {/* Products Tab */}
        {activeTab === "products" && (
          <div className="space-y-4">
            <input
              type="search"
              placeholder="Search products in this store..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full px-4 py-3 border rounded-xl text-base touch-target"
            />

            {productsLoading ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                {Array.from({ length: 8 }).map((_, i) => (
                  <ProductSkeleton key={i} />
                ))}
              </div>
            ) : (products?.products?.length ?? 0) === 0 ? (
              <div className="text-center py-16">
                <div className="text-5xl mb-3">📦</div>
                <p className="text-gray-500">No products listed yet</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                {products.products.map((product: any) => (
                  <div
                    key={product.id}
                    className="bg-white border rounded-xl overflow-hidden hover:shadow-md transition-shadow"
                  >
                    {product.imageUrl ? (
                      <img
                        src={product.imageUrl}
                        alt={product.name}
                        className="w-full h-36 object-cover"
                        loading="lazy"
                      />
                    ) : (
                      <div className="w-full h-36 bg-gray-100 flex items-center justify-center text-4xl">
                        📦
                      </div>
                    )}
                    <div className="p-3">
                      <h3 className="font-medium text-sm leading-tight line-clamp-2">
                        {product.name}
                      </h3>
                      <p className="text-base font-bold mt-1.5">
                        ₦{Number(product.price).toLocaleString()}
                      </p>
                      <button
                        onClick={() => haptic("micro")}
                        className="mt-2 w-full py-2 text-sm font-medium text-white rounded-lg touch-target"
                        style={{ backgroundColor: themeColor }}
                      >
                        Add to Cart
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Reviews Tab */}
        {activeTab === "reviews" && (
          <div className="space-y-4">
            {(reviews?.reviews?.length ?? 0) === 0 ? (
              <div className="text-center py-16">
                <div className="text-5xl mb-3">⭐</div>
                <p className="text-gray-500">No reviews yet</p>
              </div>
            ) : (
              reviews.reviews.map((review: any) => (
                <div key={review.id} className="bg-white border rounded-xl p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">
                      {review.customerName || "Customer"}
                    </span>
                    <span className="text-xs text-gray-400">
                      {new Date(review.createdAt).toLocaleDateString()}
                    </span>
                  </div>
                  <StarRating rating={review.rating} />
                  {review.body && (
                    <p className="text-sm text-gray-700">{review.body}</p>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {/* About Tab */}
        {activeTab === "about" && (
          <div className="bg-white border rounded-xl p-5 space-y-4">
            {store.description && (
              <div>
                <h3 className="font-medium text-sm text-gray-500 mb-1">About</h3>
                <p className="text-sm">{store.description}</p>
              </div>
            )}

            {store.address && (
              <div>
                <h3 className="font-medium text-sm text-gray-500 mb-1">Address</h3>
                <p className="text-sm">
                  {store.address}
                  {store.city && `, ${store.city}`}
                  {store.state && `, ${store.state}`}
                </p>
              </div>
            )}

            {store.phone && (
              <div>
                <h3 className="font-medium text-sm text-gray-500 mb-1">Phone</h3>
                <a href={`tel:${store.phone}`} className="text-sm text-blue-600">
                  {store.phone}
                </a>
              </div>
            )}

            {store.email && (
              <div>
                <h3 className="font-medium text-sm text-gray-500 mb-1">Email</h3>
                <a href={`mailto:${store.email}`} className="text-sm text-blue-600">
                  {store.email}
                </a>
              </div>
            )}

            {store.categories?.length > 0 && (
              <div>
                <h3 className="font-medium text-sm text-gray-500 mb-1">Categories</h3>
                <div className="flex flex-wrap gap-1.5">
                  {store.categories.map((cat: string) => (
                    <span
                      key={cat}
                      className="px-2.5 py-1 bg-gray-100 rounded-full text-xs text-gray-600"
                    >
                      {cat}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {store.businessHours && (
              <div>
                <h3 className="font-medium text-sm text-gray-500 mb-1">Business Hours</h3>
                <div className="space-y-1">
                  {["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].map(
                    day => {
                      const h = store.businessHours?.[day];
                      return (
                        <div key={day} className="flex justify-between text-sm">
                          <span className="capitalize text-gray-600">{day}</span>
                          <span>
                            {h ? `${h.open} – ${h.close}` : "Closed"}
                          </span>
                        </div>
                      );
                    }
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

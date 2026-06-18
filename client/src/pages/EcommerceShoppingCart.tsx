import { useState, useRef } from "react";
import { trpc } from "@/lib/trpc";
import { haptic } from "@/lib/haptics";
import DashboardLayout from "@/components/DashboardLayout";

export default function EcommerceShoppingCart() {
  const customerId = 1;
  const [syncing, setSyncing] = useState(false);
  const [swipingId, setSwipingId] = useState<string | null>(null);
  const swipeStartX = useRef(0);
  const [swipeOffset, setSwipeOffset] = useState(0);

  const { data: cart, refetch } = trpc.ecommerceCart.getCart.useQuery({
    customerId,
  }) as any;
  const updateItem = trpc.ecommerceCart.updateItem.useMutation({
    onSuccess: () => refetch(),
  }) as any;
  const removeItem = trpc.ecommerceCart.removeItem.useMutation({
    onSuccess: () => {
      refetch();
      haptic("tap");
    },
  }) as any;
  const clearCart = trpc.ecommerceCart.clearCart.useMutation({
    onSuccess: () => refetch(),
  }) as any;
  const syncOffline = trpc.ecommerceCart.syncOfflineCart.useMutation({
    onSuccess: () => {
      setSyncing(false);
      refetch();
      haptic("success");
    },
  }) as any;

  const handleSyncOffline = () => {
    const offlineData = localStorage.getItem("offline_cart");
    if (!offlineData) return;
    setSyncing(true);
    const parsed = JSON.parse(offlineData);
    syncOffline.mutate({
      customerId,
      items: parsed.items || [],
      deviceId: parsed.deviceId || "unknown",
      checksum: parsed.checksum || "",
      strategy: "max_quantity",
    });
    localStorage.removeItem("offline_cart");
  };

  const handleSwipeStart = (id: string, x: number) => {
    setSwipingId(id);
    swipeStartX.current = x;
    setSwipeOffset(0);
  };

  const handleSwipeMove = (x: number) => {
    if (!swipingId) return;
    const delta = swipeStartX.current - x;
    setSwipeOffset(Math.max(0, Math.min(delta, 100)));
  };

  const handleSwipeEnd = (sku: string) => {
    if (swipeOffset > 60) {
      removeItem.mutate({ customerId, sku });
    }
    setSwipingId(null);
    setSwipeOffset(0);
  };

  const subTotal = cart?.subTotal || 0;
  const tax = subTotal * 0.075;
  const shipping = subTotal >= 50000 ? 0 : 500;
  const total = subTotal + tax + shipping - (cart?.discountAmount || 0);

  return (
    <DashboardLayout>
      <div className="p-6 flex flex-col">
        {/* Header */}
        <div className="bg-white border-b safe-top">
          <div className="max-w-4xl mx-auto px-4 py-4 flex justify-between items-center">
            <div>
              <h1 className="text-xl font-bold">Shopping Cart</h1>
              {cart?.itemCount > 0 && (
                <p className="text-sm text-gray-500">
                  {cart.itemCount} item{cart.itemCount > 1 ? "s" : ""}
                </p>
              )}
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleSyncOffline}
                disabled={syncing}
                className="px-4 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-all active:scale-95 touch-target"
              >
                {syncing ? "Syncing..." : "↻ Sync"}
              </button>
              {cart?.items?.length > 0 && (
                <button
                  onClick={() => {
                    clearCart.mutate({ customerId });
                    haptic("tap");
                  }}
                  className="px-4 py-2.5 border border-red-300 text-red-600 rounded-xl text-sm font-medium hover:bg-red-50 transition-all active:scale-95 touch-target"
                >
                  Clear
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto pb-40">
          {!cart?.items?.length ? (
            <div className="flex flex-col items-center justify-center py-20 px-4 text-center">
              <div className="text-6xl mb-4">🛒</div>
              <p className="text-lg font-medium text-gray-700">
                Your cart is empty
              </p>
              <p className="text-sm text-gray-500 mt-1 mb-6">
                Add products from the catalog to get started
              </p>
              <a
                href="/ecommerce/catalog"
                className="px-6 py-3 bg-blue-600 text-white rounded-xl font-medium touch-target transition-all active:scale-95"
              >
                Browse Catalog
              </a>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto p-4">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Cart Items */}
                <div className="lg:col-span-2 space-y-3">
                  <p className="text-xs text-gray-400 px-1">
                    ← Swipe left to remove
                  </p>
                  {cart.items.map((item: any) => (
                    <div
                      key={item.id}
                      className="relative overflow-hidden rounded-xl"
                    >
                      {/* Delete background */}
                      <div className="absolute inset-0 bg-red-500 flex items-center justify-end px-6 rounded-xl">
                        <span className="text-white font-bold text-sm">
                          Remove
                        </span>
                      </div>
                      {/* Item card */}
                      <div
                        className="relative bg-white border rounded-xl p-4 flex gap-4 items-center transition-transform"
                        style={{
                          transform:
                            swipingId === item.id
                              ? `translateX(-${swipeOffset}px)`
                              : "translateX(0)",
                        }}
                        onTouchStart={e =>
                          handleSwipeStart(item.id, e.touches[0].clientX)
                        }
                        onTouchMove={e => handleSwipeMove(e.touches[0].clientX)}
                        onTouchEnd={() => handleSwipeEnd(item.sku)}
                      >
                        {/* Product image placeholder */}
                        <div className="w-16 h-16 bg-gray-100 rounded-lg flex items-center justify-center text-2xl flex-shrink-0">
                          📦
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="font-medium text-sm truncate">
                            {item.name}
                          </h3>
                          <p className="text-xs text-gray-400">
                            SKU: {item.sku}
                          </p>
                          <p className="text-sm font-bold mt-1">
                            ₦
                            {(
                              Number(item.unitPrice) * item.quantity
                            ).toLocaleString()}
                          </p>
                        </div>
                        {/* Quantity stepper (P0: 44px touch targets) */}
                        <div className="flex items-center gap-0 border rounded-xl overflow-hidden">
                          <button
                            onClick={() => {
                              haptic("micro");
                              updateItem.mutate({
                                customerId,
                                sku: item.sku,
                                quantity: Math.max(0, item.quantity - 1),
                              });
                            }}
                            className="w-11 h-11 flex items-center justify-center text-lg font-bold hover:bg-gray-100 transition-colors touch-target"
                            aria-label={`Decrease quantity of ${item.name}`}
                          >
                            −
                          </button>
                          <span className="w-10 text-center font-medium text-sm">
                            {item.quantity}
                          </span>
                          <button
                            onClick={() => {
                              haptic("micro");
                              updateItem.mutate({
                                customerId,
                                sku: item.sku,
                                quantity: item.quantity + 1,
                              });
                            }}
                            className="w-11 h-11 flex items-center justify-center text-lg font-bold hover:bg-gray-100 transition-colors touch-target"
                            aria-label={`Increase quantity of ${item.name}`}
                          >
                            +
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Order Summary (desktop) */}
                <div className="hidden lg:block">
                  <div className="border rounded-xl p-5 bg-white h-fit space-y-3 sticky top-4 shadow-sm">
                    <h3 className="font-bold text-lg">Order Summary</h3>
                    <div className="flex justify-between text-sm">
                      <span>Subtotal ({cart.itemCount} items)</span>
                      <span>₦{subTotal.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span>VAT (7.5%)</span>
                      <span>₦{Math.round(tax).toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span>Shipping</span>
                      <span>{shipping === 0 ? "Free" : `₦${shipping}`}</span>
                    </div>
                    {(cart.discountAmount || 0) > 0 && (
                      <div className="flex justify-between text-sm text-green-600">
                        <span>Discount</span>
                        <span>-₦{cart.discountAmount.toLocaleString()}</span>
                      </div>
                    )}
                    <hr />
                    <div className="flex justify-between font-bold text-lg">
                      <span>Total</span>
                      <span>₦{Math.round(total).toLocaleString()}</span>
                    </div>
                    <a
                      href="/ecommerce/checkout"
                      className="block w-full text-center px-4 py-3 bg-green-600 text-white rounded-xl hover:bg-green-700 font-medium transition-all touch-target"
                    >
                      Proceed to Checkout
                    </a>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Sticky Bottom CTA (P0: mobile-first) */}
        {cart?.items?.length > 0 && (
          <div className="fixed bottom-0 left-0 right-0 bg-white border-t shadow-lg safe-bottom z-40 lg:hidden">
            <div className="max-w-lg mx-auto p-4">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm text-gray-500">
                  {cart.itemCount} items
                </span>
                <span className="text-lg font-bold">
                  ₦{Math.round(total).toLocaleString()}
                </span>
              </div>
              <a
                href="/ecommerce/checkout"
                className="block w-full text-center py-3.5 bg-green-600 text-white rounded-xl font-bold text-base hover:bg-green-700 transition-all active:scale-95 touch-target"
              >
                Checkout · ₦{Math.round(total).toLocaleString()}
              </a>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

import {
  CreditCard,
  Filter,
  Minus,
  Package,
  Plus,
  Search,
  Send,
  ShoppingCart,
  Store as StoreIcon,
  Truck,
  Wallet,
  X,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import StorefrontAdsBanner from "../components/StorefrontAdsBanner";
import useAuth from "../hooks/useAuth";
import { accountApi, inventoryApi } from "../utils/api";

const Storefront = () => {
  const [cart, setCart] = useState([]);
  const [deliveryAddress, setDeliveryAddress] = useState("");
  const [pin, setPin] = useState("");
  const [orderStatus, setOrderStatus] = useState(null);
  const [orderLoading, setOrderLoading] = useState(false);
  const { user } = useAuth();
  const [showTransferModal, setShowTransferModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [selectedStore, setSelectedStore] = useState("all");
  const [showCart, setShowCart] = useState(false);
  const [products, setProducts] = useState([]);
  const [stores, setStores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [storesLoading, setStoresLoading] = useState(true);
  const [account, setAccount] = useState(null);

  const categories = [
    { id: "all", name: "All Categories" },
    { id: "Hardware", name: "Hardware" },
    { id: "Accessories", name: "Accessories" },
    { id: "Consumables", name: "Consumables" },
    { id: "Software", name: "Software" },
  ];

  // Fetch stores (businesses) once on mount
  useEffect(() => {
    inventoryApi
      .getStores()
      .then((data) => setStores(data || []))
      .catch(() => setStores([]))
      .finally(() => setStoresLoading(false));
  }, []);

  useEffect(() => {
    loadAccount();
    console.log("User in Accounts component:", user);
  }, [user?.keycloakId]);

  const loadAccount = async () => {
    console.log("Loading account...", user);
    if (!user?.keycloakId) {
      setLoading(false);
      return;
    }
    try {
      // setLoading(true);
      // setError(null);

      console.log("Fetching account for Keycloak ID:", user.keycloakId);
      const response = await accountApi.getByKeycloakId(user.keycloakId);
      console.log("Account API response:", response);
      const accountData = response.account || response.data || response;
      console.log("Fetched account data:", accountData);
      setAccount(accountData);
    } catch (err) {
      console.error("Failed to load account:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Fetch products whenever filters change
  useEffect(() => {
    const timer = setTimeout(() => fetchProducts(), 300);
    return () => clearTimeout(timer);
  }, [searchQuery, selectedCategory, selectedStore]);

  const fetchProducts = async () => {
    setLoading(true);
    try {
      const filters = {
        search: searchQuery || undefined,
        category: selectedCategory !== "all" ? selectedCategory : undefined,
        status: "in_stock",
        limit: 200,
      };

      let items;
      if (selectedStore !== "all") {
        items = await inventoryApi.getStoreItems(selectedStore, {
          ...filters,
          status: "in_stock",
        });
      } else {
        items = await inventoryApi.getAllItems(filters);
      }
      setProducts(items || []);
    } catch (err) {
      console.error("Error fetching items:", err);
      setProducts([]);
    } finally {
      setLoading(false);
    }
  };

  // Build a store lookup map: id → name
  const storeMap = stores.reduce((acc, s) => {
    acc[s.id] = s.name;
    return acc;
  }, {});

  const addToCart = (product) => {
    if (product.quantity === 0) return;
    const existing = cart.find((i) => i.id === product.id);
    if (existing) {
      if (existing.quantity + 1 > product.quantity) return;
      setCart(
        cart.map((i) =>
          i.id === product.id ? { ...i, quantity: i.quantity + 1 } : i,
        ),
      );
    } else {
      setCart([...cart, { ...product, quantity: 1 }]);
    }
  };

  const removeFromCart = (productId) => {
    const existing = cart.find((i) => i.id === productId);
    if (existing.quantity === 1) {
      setCart(cart.filter((i) => i.id !== productId));
    } else {
      setCart(
        cart.map((i) =>
          i.id === productId ? { ...i, quantity: i.quantity - 1 } : i,
        ),
      );
    }
  };

  const cartTotal = cart.reduce((sum, i) => sum + i.unit_price * i.quantity, 0);
  const cartItemCount = cart.reduce((sum, i) => sum + i.quantity, 0);

  const formatCurrency = (amount) =>
    new Intl.NumberFormat("en-NG", {
      style: "currency",
      currency: "NGN",
    }).format(amount);

  const getStatusBadge = (item) => {
    if (item.quantity === 0)
      return (
        <span className="text-xs bg-red-100 text-red-800 px-2 py-1 rounded">
          Out of Stock
        </span>
      );
    if (item.quantity < item.reorder_level)
      return (
        <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">
          Low Stock
        </span>
      );
    return null;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Storefront</h1>
          <p className="text-gray-600 mt-1">Shop from local agent businesses</p>
        </div>
        <button
          onClick={() => setShowCart(!showCart)}
          className="relative inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
        >
          <ShoppingCart className="h-5 w-5 mr-2" />
          Cart ({cartItemCount})
          {cartItemCount > 0 && (
            <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs font-bold rounded-full h-6 w-6 flex items-center justify-center">
              {cartItemCount}
            </span>
          )}
        </button>
      </div>

      {/* Search and Category Filter */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search products..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
          />
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center space-x-2">
            <StoreIcon className="h-5 w-5 text-gray-400" />
            <select
              value={selectedStore}
              onChange={(e) => setSelectedStore(e.target.value)}
              disabled={storesLoading}
              className="px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
            >
              <option value="all">All Businesses</option>
              {stores.map((store) => (
                <option key={store.id} value={store.id}>
                  {store.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center space-x-2">
            <Filter className="h-5 w-5 text-gray-400" />
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
            >
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Active filters summary */}
      {(selectedStore !== "all" ||
        selectedCategory !== "all" ||
        searchQuery) && (
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-sm text-gray-500">Filters:</span>
          {selectedStore !== "all" && (
            <span className="flex items-center gap-1 px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm">
              <StoreIcon className="h-3 w-3" />
              {storeMap[selectedStore] || "Store"}
              <button onClick={() => setSelectedStore("all")}>
                <X className="h-3 w-3 ml-1" />
              </button>
            </span>
          )}
          {selectedCategory !== "all" && (
            <span className="flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
              {selectedCategory}
              <button onClick={() => setSelectedCategory("all")}>
                <X className="h-3 w-3 ml-1" />
              </button>
            </span>
          )}
          {searchQuery && (
            <span className="flex items-center gap-1 px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm">
              "{searchQuery}"
              <button onClick={() => setSearchQuery("")}>
                <X className="h-3 w-3 ml-1" />
              </button>
            </span>
          )}
        </div>
      )}

      {/* Shopping Cart Sidebar */}
      {showCart && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-50"
          onClick={() => setShowCart(false)}
        >
          <div
            className="absolute right-0 top-0 h-full w-full max-w-md bg-white shadow-xl p-6 overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900">Shopping Cart</h2>
              <button
                onClick={() => setShowCart(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                <X className="h-6 w-6" />
              </button>
            </div>

            {cart.length === 0 ? (
              <div className="text-center py-12">
                <ShoppingCart className="h-16 w-16 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600">Your cart is empty</p>
              </div>
            ) : (
              <>
                <div className="space-y-4 mb-6">
                  {cart.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center space-x-4 p-4 bg-gray-50 rounded-lg"
                    >
                      {item.images && item.images.length > 0 ? (
                        <img
                          src={item.images[0].url}
                          alt={item.name}
                          className="w-16 h-16 object-cover rounded"
                        />
                      ) : (
                        <div className="w-16 h-16 bg-gray-200 rounded flex items-center justify-center">
                          <Package className="h-8 w-8 text-gray-400" />
                        </div>
                      )}
                      <div className="flex-1">
                        <p className="font-medium text-gray-900">{item.name}</p>
                        {item.store_id && storeMap[item.store_id] && (
                          <p className="text-xs text-green-700 font-medium">
                            {storeMap[item.store_id]}
                          </p>
                        )}
                        <p className="text-sm text-gray-500">{item.category}</p>
                        <p className="text-green-600 font-semibold">
                          {formatCurrency(item.unit_price)}
                        </p>
                      </div>
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => removeFromCart(item.id)}
                          className="p-1 bg-gray-200 rounded hover:bg-gray-300"
                        >
                          <Minus className="h-4 w-4" />
                        </button>
                        <span className="font-medium">{item.quantity}</span>
                        <button
                          onClick={() => addToCart(item)}
                          className="p-1 bg-green-600 text-white rounded hover:bg-green-700"
                        >
                          <Plus className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="border-t border-gray-200 pt-4 space-y-4">
                  <div className="flex justify-between text-lg font-bold">
                    <span>Total:</span>
                    <span className="text-green-600">
                      {formatCurrency(cartTotal)}
                    </span>
                  </div>
                  <div className="grid grid-cols-1 gap-2">
                    <button
                      className="w-full py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium flex items-center justify-center"
                      onClick={() => alert("Pay with Wallet clicked!")}
                    >
                      <Wallet className="h-5 w-5 mr-2" />
                      Pay with Wallet
                    </button>
                    <button
                      className="w-full py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium flex items-center justify-center"
                      onClick={() => alert("Pay with Card clicked!")}
                    >
                      <CreditCard className="h-5 w-5 mr-2" />
                      Pay with Card
                    </button>
                    <button
                      className="w-full py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors font-medium flex items-center justify-center"
                      onClick={() => setShowTransferModal(true)}
                    >
                      <Send className="h-5 w-5 mr-2" />
                      Transfer
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Transfer Modal */}
      {showTransferModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-40">
          <div className="bg-white rounded-xl shadow-2xl p-8 w-full max-w-md relative">
            <button
              className="absolute top-3 right-3 text-gray-400 hover:text-gray-700"
              onClick={() => setShowTransferModal(false)}
            >
              <X className="w-6 h-6" />
            </button>
            <h2 className="text-xl font-bold mb-4 text-gray-900">
              Place Order & Transfer Payment
            </h2>
            <div className="space-y-4">
              {orderStatus && (
                <div
                  className={`p-3 rounded-lg ${orderStatus.status === "created" ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"}`}
                >
                  {orderStatus.message || "Order status unknown"}
                </div>
              )}
              <form
                className="space-y-4"
                onSubmit={async (e) => {
                  e.preventDefault();
                  setOrderLoading(true);
                  setOrderStatus(null);
                  try {
                    const orderPayload = {
                      order: cart.map((i) => ({
                        name: i.name,
                        store_id: i.store_id,
                        unit_price: i.unit_price,
                        quantity: i.quantity,
                      })),
                      account_number: account?.account_number,
                      delivery_address: deliveryAddress,
                      pin,
                    };
                    const result = await inventoryApi.placeOrder(orderPayload);
                    setOrderStatus(result);
                    setCart([]);
                  } catch (err) {
                    setOrderStatus({ status: "error", message: err.message });
                  } finally {
                    setOrderLoading(false);
                  }
                }}
              >
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Account Number
                  </label>
                  <input
                    type="text"
                    value={account?.account_number || ""}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                    disabled
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Items List
                  </label>
                  <textarea
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                    rows={4}
                    disabled
                    value={cart
                      .map((i) => `${i.name} x${i.quantity}`)
                      .join("\n")}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Total Amount
                  </label>
                  <input
                    type="text"
                    value={formatCurrency(cartTotal)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                    disabled
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Delivery Address
                  </label>
                  <input
                    type="text"
                    value={deliveryAddress}
                    onChange={(e) => setDeliveryAddress(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    PIN
                  </label>
                  <input
                    type="password"
                    value={pin}
                    onChange={(e) => setPin(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                    required
                  />
                </div>
                <div className="mt-6 flex justify-end">
                  <button
                    type="submit"
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-semibold mr-2"
                    disabled={orderLoading || cart.length === 0}
                  >
                    {orderLoading ? "Processing..." : "Pay & Place Order"}
                  </button>
                  <button
                    type="button"
                    className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-semibold"
                    onClick={() => setShowTransferModal(false)}
                  >
                    Close
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Storefront Ads Banner */}
      <StorefrontAdsBanner maxAds={5} />

      {/* Products Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading ? (
          <div className="col-span-full text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-green-600" />
            <p className="text-gray-600 mt-4">Loading products...</p>
          </div>
        ) : products.length === 0 ? (
          <div className="col-span-full text-center py-12 bg-white rounded-lg shadow">
            <Package className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">
              {searchQuery ||
              selectedCategory !== "all" ||
              selectedStore !== "all"
                ? "No products found matching your filters."
                : "No products available at the moment."}
            </p>
          </div>
        ) : (
          products.map((product) => (
            <div
              key={product.id}
              className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow"
            >
              <div className="p-6">
                {/* Product Image */}
                {product.images && product.images.length > 0 ? (
                  <div className="mb-4 h-48 bg-gray-100 rounded-lg overflow-hidden">
                    <img
                      src={product.images[0].url}
                      alt={product.name}
                      className="w-full h-full object-cover"
                    />
                  </div>
                ) : (
                  <div className="mb-4 h-48 bg-gray-100 rounded-lg flex items-center justify-center">
                    <Package className="h-16 w-16 text-gray-400" />
                  </div>
                )}

                {/* Business / store badge */}
                {product.store_id && storeMap[product.store_id] && (
                  <div className="flex items-center gap-1 mb-2">
                    <StoreIcon className="h-3 w-3 text-green-600" />
                    <span className="text-xs font-medium text-green-700 truncate">
                      {storeMap[product.store_id]}
                    </span>
                  </div>
                )}

                {/* Product Info */}
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-semibold text-gray-900 line-clamp-2">
                    {product.name}
                  </h3>
                  {getStatusBadge(product)}
                </div>

                <p className="text-sm text-gray-500 mb-1">SKU: {product.sku}</p>
                <p className="text-sm text-gray-600 mb-3">{product.category}</p>

                <div className="flex items-center justify-between">
                  <p className="text-xl font-bold text-green-600">
                    {formatCurrency(product.unit_price)}
                  </p>
                  <button
                    onClick={() => addToCart(product)}
                    disabled={product.quantity === 0}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                  >
                    <ShoppingCart className="h-4 w-4 mr-1" />
                    Add
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Delivery Info */}
      <div className="bg-green-50 border border-green-200 rounded-lg p-6">
        <div className="flex items-start">
          <Truck className="h-6 w-6 text-green-600 mt-0.5 mr-3 shrink-0" />
          <div>
            <h3 className="font-medium text-green-900 mb-1">
              Free Delivery Available
            </h3>
            <p className="text-sm text-green-700">
              Order from local agent businesses and get your items delivered to
              your doorstep. Minimum order of ₦5,000 for free delivery.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Storefront;

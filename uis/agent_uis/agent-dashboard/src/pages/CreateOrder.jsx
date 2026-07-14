import {
  Minus,
  Plus,
  RefreshCw,
  Search,
  ShoppingCart,
  Store as StoreIcon,
  Trash2,
  X,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import {
  accountApi,
  agentApi,
  authHeaders,
  inventoryApi,
  orderApi,
} from "../utils/api";

const CORE_BANKING_URL =
  import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const CreateOrder = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [stores, setStores] = useState([]);
  const [selectedStore, setSelectedStore] = useState(null);
  const [inventoryItems, setInventoryItems] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [cart, setCart] = useState([]);
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [transactionId, setTransactionId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showItemModal, setShowItemModal] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [itemQuantity, setItemQuantity] = useState(1);
  const [customPrice, setCustomPrice] = useState("");
  const [transactions, setTransactions] = useState([]);
  const [transactionsLoading, setTransactionsLoading] = useState(false);
  const [transactionsError, setTransactionsError] = useState(null);
  const [transactionSearchQuery, setTransactionSearchQuery] = useState("");

  // account numbers for the agent + all stores, used to fetch transactions
  const [allAccountNumbers, setAllAccountNumbers] = useState([]);

  useEffect(() => {
    if (user) {
      loadStores();
      loadAccountNumbers();
    }
  }, [user]);

  // Load transactions once we have account numbers
  useEffect(() => {
    if (allAccountNumbers.length > 0) {
      loadRecentTransactions();
    }
  }, [allAccountNumbers]);

  // Load inventory when a store is selected
  useEffect(() => {
    if (selectedStore) {
      loadInventoryItems();
    }
  }, [selectedStore]);

  // Reload transactions when customer phone changes (filter client-side)
  useEffect(() => {
    if (customerPhone && customerPhone.length >= 10) {
      loadRecentTransactions();
    }
  }, [customerPhone]);

  // Fetch agent account number + all store account numbers
  const loadAccountNumbers = async () => {
    try {
      const keycloakId = user?.keycloakId;
      if (!keycloakId) return;

      const nums = [];

      try {
        const accountResp = await accountApi.getAccountByKeycloakId(keycloakId);
        const account = accountResp.account ?? accountResp;
        if (account?.account_number) nums.push(account.account_number);
      } catch (err) {
        console.error("Agent account fetch error:", err);
      }

      try {
        const storesResp = await inventoryApi.getStores(keycloakId);
        const storesList = Array.isArray(storesResp.data)
          ? storesResp.data
          : Array.isArray(storesResp)
            ? storesResp
            : [];
        storesList.forEach((s) => {
          if (s.account_number) nums.push(s.account_number);
        });
      } catch (err) {
        console.error("Stores account fetch error:", err);
      }

      setAllAccountNumbers(nums);
    } catch (err) {
      console.error("loadAccountNumbers error:", err);
    }
  };

  const loadStores = async () => {
    try {
      const keycloakId = user?.keycloakId;
      const data = await inventoryApi.getStores(keycloakId);
      const storesList = Array.isArray(data.data)
        ? data.data
        : Array.isArray(data)
          ? data
          : [];
      setStores(storesList);
      if (storesList.length > 0) {
        setSelectedStore(storesList[0]);
      }
    } catch (err) {
      console.error("Error loading stores:", err);
      setError("Failed to load stores");
    }
  };

  const loadInventoryItems = async () => {
    if (!selectedStore) return;
    setLoading(true);
    setError(null);
    try {
      const items = await inventoryApi.getInventoryItems(selectedStore.id, {
        search: searchQuery || undefined,
      });
      setInventoryItems(items);
    } catch (err) {
      console.error("Error loading inventory:", err);
      setError("Failed to load inventory items");
    } finally {
      setLoading(false);
    }
  };

  // Fetch transactions from all accounts using the same ledger pattern as Dashboard
  const loadRecentTransactions = async () => {
    if (allAccountNumbers.length === 0) return;
    setTransactionsLoading(true);
    setTransactionsError(null);

    try {
      const allTxns = [];

      await Promise.all(
        allAccountNumbers.map(async (accountNumber) => {
          try {
            const res = await fetch(
              `${CORE_BANKING_URL}/ledger/txn/account-number/${accountNumber}?limit=20&page=1`,
              { headers: { ...authHeaders() } },
            );
            if (res.ok) {
              const data = await res.json();
              const txns = (data.transactions || []).map((txn) => ({
                ...txn,
                _accountNumber: accountNumber,
              }));
              allTxns.push(...txns);
            }
          } catch (err) {
            console.error(
              `Transactions fetch error for account ${accountNumber}:`,
              err,
            );
          }
        }),
      );

      // Sort newest first
      allTxns.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

      // Client-side filter by search query or customer phone
      const filterQuery = (
        transactionSearchQuery ||
        customerPhone ||
        ""
      ).toLowerCase();
      const filtered = filterQuery
        ? allTxns.filter((txn) => {
            return (
              txn.payer_account_number?.includes(filterQuery) ||
              txn.payee_account_number?.includes(filterQuery) ||
              txn.note?.toLowerCase().includes(filterQuery) ||
              txn.status?.toLowerCase().includes(filterQuery) ||
              (txn.amount || "").toString().includes(filterQuery)
            );
          })
        : allTxns;

      setTransactions(filtered.slice(0, 20));
    } catch (err) {
      console.error("Error loading transactions:", err);
      setTransactionsError("Failed to load transactions");
      setTransactions([]);
    } finally {
      setTransactionsLoading(false);
    }
  };

  const handleTransactionSearch = () => {
    loadRecentTransactions();
  };

  const openItemModal = (item) => {
    setSelectedItem(item);
    setItemQuantity(1);
    setCustomPrice(item.unit_price.toString());
    setShowItemModal(true);
  };

  const closeItemModal = () => {
    setShowItemModal(false);
    setSelectedItem(null);
    setItemQuantity(1);
    setCustomPrice("");
  };

  const addToCart = () => {
    if (!selectedItem) return;

    const quantity = parseInt(itemQuantity);
    const price = parseFloat(customPrice || selectedItem.unit_price);

    if (quantity <= 0 || quantity > selectedItem.quantity) {
      alert(`Invalid quantity. Available stock: ${selectedItem.quantity}`);
      return;
    }

    const existingIndex = cart.findIndex(
      (item) => item.inventory_item_id === selectedItem.id,
    );

    if (existingIndex >= 0) {
      const newCart = [...cart];
      newCart[existingIndex].quantity += quantity;
      newCart[existingIndex].unit_price = price;
      setCart(newCart);
    } else {
      setCart([
        ...cart,
        {
          inventory_item_id: selectedItem.id,
          name: selectedItem.name,
          quantity,
          unit_price: price,
          available_stock: selectedItem.quantity,
        },
      ]);
    }

    closeItemModal();
  };

  const removeFromCart = (inventoryItemId) => {
    setCart(cart.filter((item) => item.inventory_item_id !== inventoryItemId));
  };

  const updateCartQuantity = (inventoryItemId, delta) => {
    setCart(
      cart.map((item) => {
        if (item.inventory_item_id === inventoryItemId) {
          const newQuantity = Math.max(
            1,
            Math.min(item.quantity + delta, item.available_stock),
          );
          return { ...item, quantity: newQuantity };
        }
        return item;
      }),
    );
  };

  const calculateSubtotal = () =>
    cart.reduce((sum, item) => sum + item.quantity * item.unit_price, 0);

  const calculateTax = () => calculateSubtotal() * 0.075;

  const calculateTotal = () => calculateSubtotal() + calculateTax();

  const handleCreateOrder = async () => {
    if (!selectedStore) {
      alert("Please select a store");
      return;
    }
    if (cart.length === 0) {
      alert("Please add items to cart");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Validate inventory availability before creating order
      const validationErrors = [];
      for (const cartItem of cart) {
        try {
          const currentItem = await inventoryApi.getInventoryItem(
            cartItem.inventory_item_id,
          );

          // Check if item still exists
          if (!currentItem) {
            validationErrors.push(
              `${cartItem.name} is no longer available in inventory`,
            );
            continue;
          }

          // Check if sufficient stock is available
          if (currentItem.quantity < cartItem.quantity) {
            validationErrors.push(
              `${cartItem.name}: Only ${currentItem.quantity} units available (you have ${cartItem.quantity} in cart)`,
            );
          }
        } catch (itemError) {
          validationErrors.push(
            `${cartItem.name}: Unable to verify availability`,
          );
        }
      }

      // If validation errors exist, show them and stop
      if (validationErrors.length > 0) {
        const errorMessage =
          "Order cannot be completed:\n\n" + validationErrors.join("\n");
        alert(errorMessage);
        setError("Please review cart items and try again");
        setLoading(false);
        // Refresh inventory to show current stock levels
        loadInventoryItems();
        return;
      }

      const keycloakId = user?.keycloakId;
      const orderData = {
        store_id: selectedStore.id,
        agent_keycloak_id: keycloakId,
        customer_name: customerName || null,
        customer_phone: customerPhone || null,
        customer_email: customerEmail || null,
        payment_method: paymentMethod,
        transaction_id:
          paymentMethod === "transfer" || paymentMethod === "pos"
            ? transactionId || null
            : null,
        items: cart.map((item) => ({
          inventory_item_id: item.inventory_item_id,
          quantity: item.quantity,
          unit_price: item.unit_price,
          item_name: item.name,
          subtotal: item.quantity * item.unit_price,
        })),
        subtotal: calculateSubtotal(),
        tax: calculateTax(),
        total: calculateTotal(),
      };

      let response;
      try {
        response = await orderApi.createOrder(orderData);
      } catch (apiError) {
        console.log("Orders API not available, saving locally");
        const orderId = `local-${Date.now()}`;
        response = {
          id: orderId,
          ...orderData,
          order_number: `ORD-${orderId}`,
          status: "pending",
          created_at: new Date().toISOString(),
          store_name: selectedStore.name,
          store_location: selectedStore.location,
          is_local: true,
        };
        const localOrders = JSON.parse(
          localStorage.getItem("agent_orders") || "[]",
        );
        localOrders.push(response);
        localStorage.setItem("agent_orders", JSON.stringify(localOrders));
      }

      // Deduct items from inventory after successful order creation
      try {
        await Promise.all(
          cart.map(async (item) => {
            try {
              // Get current item data
              const currentItem = await inventoryApi.getInventoryItem(
                item.inventory_item_id,
              );

              // Calculate new quantity
              const newQuantity = currentItem.quantity - item.quantity;

              if (newQuantity < 0) {
                console.warn(
                  `Item ${item.name} quantity went negative: ${newQuantity}`,
                );
              }

              // Update inventory with new quantity
              await inventoryApi.updateInventoryItem(item.inventory_item_id, {
                quantity: Math.max(0, newQuantity), // Ensure quantity doesn't go below 0
              });
            } catch (itemError) {
              console.error(
                `Failed to update inventory for item ${item.name}:`,
                itemError,
              );
              // Don't fail the entire order if inventory update fails
              // Just log the error
            }
          }),
        );

        // Refresh inventory list to show updated quantities
        if (selectedStore) {
          loadInventoryItems();
        }
      } catch (inventoryError) {
        console.error("Error updating inventory:", inventoryError);
        // Don't fail the order, just log the error
      }

      navigate(`/orders/${response.id}/receipt`, {
        state: { order: response },
      });
    } catch (err) {
      console.error("Error creating order:", err);
      setError(err.message || "Failed to create order");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div
        className="rounded-2xl shadow-xl p-8 text-white"
        style={{
          background: "linear-gradient(to right, var(--tenant-primary-color,#004F71), #003F5A, var(--tenant-primary-color,#003047))",
        }}
      >
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-3">
              <ShoppingCart className="h-8 w-8" />
              Create Order
            </h1>
            <p className="mt-2" style={{ color: "rgba(255,255,255,0.8)" }}>
              Create a new sales order for your store
            </p>
          </div>
          <button
            onClick={() => navigate("/orders")}
            className="bg-white/20 hover:bg-white/30 backdrop-blur-sm px-4 py-2 rounded-lg transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Item Selection */}
        <div className="lg:col-span-2 space-y-6">
          {/* Store Selection */}
          <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-6">
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              <StoreIcon className="inline h-5 w-5 mr-2" />
              Select Store
            </label>
            <select
              value={selectedStore?.id || ""}
              onChange={(e) => {
                const store = stores.find((s) => s.id === e.target.value);
                setSelectedStore(store);
                setCart([]);
              }}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
            >
              {stores.map((store) => (
                <option key={store.id} value={store.id}>
                  {store.name}
                </option>
              ))}
            </select>
          </div>

          {/* Search Inventory */}
          <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search inventory items..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
                />
              </div>
              <button
                onClick={loadInventoryItems}
                className="px-6 py-3 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors font-semibold"
              >
                Search
              </button>
            </div>

            {loading ? (
              <div className="text-center py-8 text-gray-500">
                Loading inventory...
              </div>
            ) : inventoryItems.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No items found
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-96 overflow-y-auto">
                {inventoryItems.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => openItemModal(item)}
                    className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-all cursor-pointer"
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.borderColor = "rgba(0,79,113,0.3)")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.borderColor = "")
                    }
                  >
                    <h3 className="font-semibold text-gray-900">{item.name}</h3>
                    <p className="text-sm text-gray-600">{item.sku}</p>
                    <div className="flex justify-between items-center mt-2">
                      <span
                        className="text-lg font-bold"
                        style={{ color: "var(--tenant-primary-color,#004F71)" }}
                      >
                        ₦{item.unit_price.toLocaleString()}
                      </span>
                      <span
                        className={`text-sm px-2 py-1 rounded ${
                          item.quantity > 10
                            ? "bg-green-100 text-green-700"
                            : item.quantity > 0
                              ? "bg-orange-100 text-orange-700"
                              : "bg-red-100 text-red-700"
                        }`}
                      >
                        Stock: {item.quantity}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          {/* Recent Transactions */}
          <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-900">
                Recent Transactions
              </h2>
              <button
                onClick={loadRecentTransactions}
                disabled={transactionsLoading}
                className="p-2 text-[var(--tenant-primary-color,#004F71)] hover:bg-gray-100 rounded-lg transition-colors"
                title="Refresh transactions"
              >
                <RefreshCw
                  className={`h-5 w-5 ${transactionsLoading ? "animate-spin" : ""}`}
                />
              </button>
            </div>

            {/* Transaction Search */}
            <div className="flex items-center gap-2 mb-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search by account, note, amount..."
                  value={transactionSearchQuery}
                  onChange={(e) => setTransactionSearchQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleTransactionSearch();
                  }}
                  className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
                />
              </div>
              <button
                onClick={handleTransactionSearch}
                disabled={transactionsLoading}
                className="px-4 py-2 text-sm bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors font-semibold disabled:opacity-50"
              >
                Search
              </button>
            </div>

            {transactionsError && (
              <div className="text-sm text-red-600 mb-3">
                {transactionsError}
              </div>
            )}

            {transactionsLoading ? (
              <div className="text-center py-4 text-gray-500 text-sm flex items-center justify-center gap-2">
                <RefreshCw className="h-4 w-4 animate-spin" />
                Loading transactions...
              </div>
            ) : transactions.length === 0 ? (
              <div className="text-center py-4 text-gray-500 text-sm">
                No recent transactions
              </div>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {transactions.map((txn, index) => (
                  <div
                    key={txn.id || index}
                    className="border border-gray-200 rounded-lg p-3 text-sm"
                  >
                    <div className="flex justify-between items-start mb-1">
                      <div className="flex-1">
                        <p className="font-semibold text-gray-900">
                          {txn.note || txn.tag || "Transaction"}
                        </p>
                        <p className="text-xs text-gray-500">
                          {new Date(
                            txn.created_at?.replace(" ", "T"),
                          ).toLocaleString()}
                        </p>
                      </div>
                      <span
                        className={`text-xs px-2 py-1 rounded ${
                          txn.status === "completed" || txn.status === "success"
                            ? "bg-green-100 text-green-700"
                            : txn.status === "pending"
                              ? "bg-yellow-100 text-yellow-700"
                              : "bg-red-100 text-red-700"
                        }`}
                      >
                        {txn.status}
                      </span>
                    </div>
                    <div className="space-y-1">
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-gray-600 font-mono">
                          {txn.payer_account_number ||
                            txn.payee_account_number ||
                            "N/A"}
                        </span>
                        <span
                          className="font-bold"
                          style={{ color: "var(--tenant-primary-color,#004F71)" }}
                        >
                          ₦{parseFloat(txn.amount || 0).toLocaleString()}
                        </span>
                      </div>
                      {txn.transaction_id && (
                        <div className="text-xs text-gray-500">
                          <span className="font-semibold">Txn ID:</span>{" "}
                          {txn.transaction_id}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column - Cart & Checkout */}
        <div className="space-y-6">
          {/* Cart */}
          <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
              <ShoppingCart className="h-5 w-5" style={{ color: "var(--tenant-primary-color,#004F71)" }} />
              Cart ({cart.length})
            </h2>

            {cart.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <ShoppingCart className="h-12 w-12 mx-auto mb-2 text-gray-400" />
                <p>Cart is empty</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-64 overflow-y-auto mb-4">
                {cart.map((item) => (
                  <div
                    key={item.inventory_item_id}
                    className="border border-gray-200 rounded-lg p-3"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h4 className="font-semibold text-sm text-gray-900 flex-1">
                        {item.name}
                      </h4>
                      <button
                        onClick={() => removeFromCart(item.inventory_item_id)}
                        className="text-red-500 hover:text-red-700"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() =>
                            updateCartQuantity(item.inventory_item_id, -1)
                          }
                          className="p-1 bg-gray-100 hover:bg-gray-200 rounded"
                        >
                          <Minus className="h-3 w-3" />
                        </button>
                        <span className="font-semibold">{item.quantity}</span>
                        <button
                          onClick={() =>
                            updateCartQuantity(item.inventory_item_id, 1)
                          }
                          className="p-1 bg-gray-100 hover:bg-gray-200 rounded"
                        >
                          <Plus className="h-3 w-3" />
                        </button>
                      </div>
                      <span className="font-bold" style={{ color: "var(--tenant-primary-color,#004F71)" }}>
                        ₦{(item.quantity * item.unit_price).toLocaleString()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="border-t border-gray-200 pt-4 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Subtotal</span>
                <span className="font-semibold">
                  ₦{calculateSubtotal().toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Tax (7.5%)</span>
                <span className="font-semibold">
                  ₦{calculateTax().toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between text-lg font-bold pt-2 border-t border-gray-200">
                <span>Total</span>
                <span style={{ color: "var(--tenant-primary-color,#004F71)" }}>
                  ₦{calculateTotal().toLocaleString()}
                </span>
              </div>
            </div>
          </div>

          {/* Customer Details */}
          <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">
              Customer Details (Optional)
            </h2>
            <div className="space-y-3">
              <input
                type="text"
                placeholder="Customer Name"
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
              />
              <input
                type="tel"
                placeholder="Phone Number"
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
              />
              <input
                type="email"
                placeholder="Email Address"
                value={customerEmail}
                onChange={(e) => setCustomerEmail(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
              />
            </div>
          </div>

          {/* Payment Method */}
          <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">
              Payment Method
            </h2>
            <div className="space-y-2">
              {[
                { value: "cash", label: "Cash" },
                { value: "transfer", label: "Bank Transfer" },
                { value: "pos", label: "POS Terminal" },
              ].map((method) => (
                <label
                  key={method.value}
                  className="flex items-center gap-3 p-3 border border-gray-200 rounded-lg cursor-pointer transition-colors"
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.borderColor = "rgba(0,79,113,0.3)")
                  }
                  onMouseLeave={(e) => (e.currentTarget.style.borderColor = "")}
                >
                  <input
                    type="radio"
                    name="paymentMethod"
                    value={method.value}
                    checked={paymentMethod === method.value}
                    onChange={(e) => setPaymentMethod(e.target.value)}
                    className="w-4 h-4"
                    style={{ accentColor: "var(--tenant-secondary-color,#69BC5E)" }}
                  />
                  <span className="font-semibold">{method.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Transaction ID (for Bank Transfer and POS) */}
          {(paymentMethod === "transfer" || paymentMethod === "pos") && (
            <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-4">
                Transaction ID
              </h2>
              <input
                type="text"
                value={transactionId}
                onChange={(e) => setTransactionId(e.target.value)}
                placeholder={`Enter ${paymentMethod === "transfer" ? "bank transfer" : "POS"} transaction ID`}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
              />
            </div>
          )}

          {/* Create Order Button */}
          <button
            onClick={handleCreateOrder}
            disabled={loading || cart.length === 0}
            className="w-full py-4 text-white font-bold rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg"
            style={{
              background: "linear-gradient(to right, var(--tenant-primary-color,#004F71), #003F5A)",
            }}
            onMouseEnter={(e) => {
              if (!loading && cart.length > 0)
                e.currentTarget.style.background =
                  "linear-gradient(to right, var(--tenant-primary-color,#003F5A), #003047)";
            }}
            onMouseLeave={(e) => {
              if (!loading && cart.length > 0)
                e.currentTarget.style.background =
                  "linear-gradient(to right, var(--tenant-primary-color,#004F71), #003F5A)";
            }}
          >
            {loading ? "Creating Order..." : "Create Order"}
          </button>
        </div>
      </div>

      {/* Item Modal */}
      {showItemModal && selectedItem && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-bold text-gray-900">
                {selectedItem.name}
              </h3>
              <button
                onClick={closeItemModal}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-6 w-6" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <p className="text-sm text-gray-500">SKU: {selectedItem.sku}</p>
                <p className="text-sm text-gray-500">
                  Available: {selectedItem.quantity} units
                </p>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Quantity
                </label>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() =>
                      setItemQuantity(Math.max(1, itemQuantity - 1))
                    }
                    className="p-2 bg-gray-100 hover:bg-gray-200 rounded-lg"
                  >
                    <Minus className="h-5 w-5" />
                  </button>
                  <input
                    type="number"
                    value={itemQuantity}
                    onChange={(e) =>
                      setItemQuantity(
                        Math.max(
                          1,
                          Math.min(
                            parseInt(e.target.value) || 1,
                            selectedItem.quantity,
                          ),
                        ),
                      )
                    }
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-center font-semibold"
                  />
                  <button
                    onClick={() =>
                      setItemQuantity(
                        Math.min(itemQuantity + 1, selectedItem.quantity),
                      )
                    }
                    className="p-2 bg-gray-100 hover:bg-gray-200 rounded-lg"
                  >
                    <Plus className="h-5 w-5" />
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Unit Price
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500">
                    ₦
                  </span>
                  <input
                    type="number"
                    value={customPrice}
                    onChange={(e) => setCustomPrice(e.target.value)}
                    className="w-full pl-8 pr-4 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
              </div>

              <div
                className="border rounded-lg p-4"
                style={{
                  backgroundColor: "rgba(0,79,113,0.05)",
                  borderColor: "rgba(0,79,113,0.2)",
                }}
              >
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">Total:</span>
                  <span
                    className="text-2xl font-bold"
                    style={{ color: "var(--tenant-primary-color,#004F71)" }}
                  >
                    ₦
                    {(
                      itemQuantity * (parseFloat(customPrice) || 0)
                    ).toLocaleString()}
                  </span>
                </div>
              </div>

              <button
                onClick={addToCart}
                className="w-full py-3 text-white font-bold rounded-lg transition-all"
                style={{
                  background: "linear-gradient(to right, var(--tenant-primary-color,#004F71), #003F5A)",
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background =
                    "linear-gradient(to right, var(--tenant-primary-color,#003F5A), #003047)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background =
                    "linear-gradient(to right, var(--tenant-primary-color,#004F71), #003F5A)")
                }
              >
                Add to Cart
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CreateOrder;

import {
    AlertTriangle,
    BarChart3,
    CheckCircle,
    Download,
    Edit,
    Eye,
    Filter,
    Minus,
    Package,
    Plus,
    Printer,
    RefreshCw,
    Search,
    ShoppingBag,
    ShoppingCart,
    Trash2,
    TrendingUp,
    Upload,
    X,
    XCircle,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    Legend,
    Line,
    LineChart,
    Pie,
    PieChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";
import { api, InventoryItem, SaleItem, SaleRecord } from "../../utils/api";

const InventoryManagement = () => {
  const [activeTab, setActiveTab] = useState("pos");
  const [inventoryItems, setInventoryItems] = useState<InventoryItem[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterCategory, setFilterCategory] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<{
    total_items: number;
    total_value: number;
    low_stock: number;
    out_of_stock: number;
    unique_items: number;
  }>({
    total_items: 0,
    total_value: 0,
    low_stock: 0,
    out_of_stock: 0,
    unique_items: 0,
  });
  const [storeId, setStoreId] = useState(1); // TODO: Replace with dynamic store selection

  // POS State
  const [cart, setCart] = useState<
    Array<{ item: InventoryItem; quantity: number }>
  >([]);
  const [customerName, setCustomerName] = useState("");
  const [showReceipt, setShowReceipt] = useState(false);
  const [lastReceipt, setLastReceipt] = useState<SaleRecord | null>(null);
  const [salesHistory, setSalesHistory] = useState<SaleRecord[]>([]);
  const [posSearch, setPosSearch] = useState("");

  // Add Item Modal State
  const [showAddItemModal, setShowAddItemModal] = useState(false);
  const [newItem, setNewItem] = useState({
    name: "",
    sku: "",
    category: "Hardware",
    quantity: 0,
    reorder_level: 10,
    unit_price: 0,
    supplier: "",
    location: "Warehouse A",
    barcode: "",
  });

  // Load inventory items on mount and when filters change
  useEffect(() => {
    loadInventoryItems();
  }, [storeId]);

  // Load sales history
  useEffect(() => {
    loadSalesHistory();
  }, []);

  // Load metrics
  useEffect(() => {
    loadMetrics();
  }, [storeId]);

  // Reload inventory when filters change
  useEffect(() => {
    const timer = setTimeout(() => {
      loadInventoryItems();
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm, filterCategory, filterStatus, storeId]);

  const loadInventoryItems = async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await api.getInventoryItems(storeId, {
        search: searchTerm || undefined,
        category: filterCategory !== "all" ? filterCategory : undefined,
        status: filterStatus !== "all" ? filterStatus : undefined,
      });
      setInventoryItems(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load inventory");
      console.error("Error loading inventory:", err);
    } finally {
      setLoading(false);
    }
  };

  const loadSalesHistory = async () => {
    try {
      const sales = await api.getSalesHistory(50);
      setSalesHistory(sales);
    } catch (err) {
      console.error("Error loading sales history:", err);
    }
  };

  const loadMetrics = async () => {
    try {
      const data = await api.getInventoryMetrics();
      setMetrics(data);
    } catch (err) {
      console.error("Error loading metrics:", err);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-NG", {
      style: "currency",
      currency: "NGN",
    }).format(amount);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "in_stock":
        return "bg-green-100 text-green-800";
      case "low_stock":
        return "bg-yellow-100 text-yellow-800";
      case "critical":
        return "bg-orange-100 text-orange-800";
      case "out_of_stock":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "in_stock":
        return <CheckCircle className="w-4 h-4" />;
      case "low_stock":
        return <AlertTriangle className="w-4 h-4" />;
      case "critical":
        return <AlertTriangle className="w-4 h-4" />;
      case "out_of_stock":
        return <XCircle className="w-4 h-4" />;
      default:
        return null;
    }
  };

  const updateItemStatus = (quantity: number, reorderLevel: number) => {
    if (quantity === 0) return "out_of_stock";
    if (quantity < reorderLevel * 0.5) return "critical";
    if (quantity < reorderLevel) return "low_stock";
    return "in_stock";
  };

  // POS Functions
  const addToCart = (item: InventoryItem) => {
    if (item.quantity === 0) {
      alert("Item is out of stock!");
      return;
    }

    const existingItem = cart.find((c) => c.item.id === item.id);
    if (existingItem) {
      if (existingItem.quantity + 1 > item.quantity) {
        alert("Not enough stock available!");
        return;
      }
      setCart(
        cart.map((c) =>
          c.item.id === item.id ? { ...c, quantity: c.quantity + 1 } : c,
        ),
      );
    } else {
      setCart([...cart, { item, quantity: 1 }]);
    }
  };

  const removeFromCart = (itemId: number) => {
    setCart(cart.filter((c) => c.item.id !== itemId));
  };

  const updateCartQuantity = (itemId: number, delta: number) => {
    setCart(
      cart.map((c) => {
        if (c.item.id === itemId) {
          const newQuantity = c.quantity + delta;
          if (newQuantity <= 0) return c;
          if (newQuantity > c.item.quantity) {
            alert("Not enough stock available!");
            return c;
          }
          return { ...c, quantity: newQuantity };
        }
        return c;
      }),
    );
  };

  const calculateTotal = () => {
    return cart.reduce((sum, c) => sum + c.item.unit_price * c.quantity, 0);
  };

  const completeSale = async () => {
    if (cart.length === 0) {
      alert("Cart is empty!");
      return;
    }

    if (!customerName.trim()) {
      alert("Please enter customer name!");
      return;
    }

    try {
      setLoading(true);

      // Create sale items payload
      const saleItems: SaleItem[] = cart.map((c) => ({
        name: c.item.name,
        sku: c.item.sku,
        quantity: c.quantity,
        unit_price: c.item.unit_price,
        total: c.item.unit_price * c.quantity,
      }));

      // Call API to create sale
      const sale = await api.createSale({
        customer_name: customerName,
        items: saleItems,
      });

      // Update local state
      setLastReceipt(sale);
      setShowReceipt(true);
      setCart([]);
      setCustomerName("");

      // Reload inventory, sales, and metrics
      await loadInventoryItems();
      await loadSalesHistory();
      await loadMetrics();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to complete sale");
      console.error("Error completing sale:", err);
    } finally {
      setLoading(false);
    }
  };

  const printReceipt = () => {
    window.print();
  };

  const filteredItems = inventoryItems;

  const posFilteredItems = inventoryItems.filter(
    (item) =>
      item.name.toLowerCase().includes(posSearch.toLowerCase()) ||
      item.sku.toLowerCase().includes(posSearch.toLowerCase()) ||
      (item.barcode && item.barcode.includes(posSearch)),
  );

  const alertItems = inventoryItems.filter(
    (item) =>
      item.status === "low_stock" ||
      item.status === "critical" ||
      item.status === "out_of_stock",
  );

  // Parse sale items from JSON string
  const parseSaleItems = (itemsJson: string): SaleItem[] => {
    try {
      return JSON.parse(itemsJson);
    } catch {
      return [];
    }
  };

  const handleAddItem = async () => {
    if (!newItem.name || !newItem.sku || newItem.unit_price <= 0) {
      alert("Please fill in all required fields");
      return;
    }

    try {
      setLoading(true);
      await api.createInventoryItem(storeId, newItem);
      setShowAddItemModal(false);
      setNewItem({
        name: "",
        sku: "",
        category: "Hardware",
        quantity: 0,
        reorder_level: 10,
        unit_price: 0,
        supplier: "",
        location: "Warehouse A",
        barcode: "",
      });
      await loadInventoryItems();
      await loadMetrics();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to add item");
      console.error("Error adding item:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 bg-gray-50 min-h-screen">
      {/* Add Item Modal */}
      {showAddItemModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-2xl w-full max-w-2xl p-8 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold">Add New Inventory Item</h2>
              <button
                onClick={() => setShowAddItemModal(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                <X size={24} />
              </button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Item Name *
                  </label>
                  <input
                    type="text"
                    value={newItem.name}
                    onChange={(e) =>
                      setNewItem({ ...newItem, name: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
                    placeholder="POS Terminal - Model A"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    SKU *
                  </label>
                  <input
                    type="text"
                    value={newItem.sku}
                    onChange={(e) =>
                      setNewItem({ ...newItem, sku: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
                    placeholder="POS-A-001"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Category
                  </label>
                  <select
                    value={newItem.category}
                    onChange={(e) =>
                      setNewItem({ ...newItem, category: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
                  >
                    <option value="Hardware">Hardware</option>
                    <option value="Accessories">Accessories</option>
                    <option value="Consumables">Consumables</option>
                    <option value="Software">Software</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Location
                  </label>
                  <select
                    value={newItem.location}
                    onChange={(e) =>
                      setNewItem({ ...newItem, location: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
                  >
                    <option value="Warehouse A">Warehouse A</option>
                    <option value="Warehouse B">Warehouse B</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Quantity
                  </label>
                  <input
                    type="number"
                    value={newItem.quantity}
                    onChange={(e) =>
                      setNewItem({
                        ...newItem,
                        quantity: parseInt(e.target.value) || 0,
                      })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
                    min="0"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Reorder Level
                  </label>
                  <input
                    type="number"
                    value={newItem.reorder_level}
                    onChange={(e) =>
                      setNewItem({
                        ...newItem,
                        reorder_level: parseInt(e.target.value) || 0,
                      })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
                    min="0"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Unit Price (₦) *
                  </label>
                  <input
                    type="number"
                    value={newItem.unit_price}
                    onChange={(e) =>
                      setNewItem({
                        ...newItem,
                        unit_price: parseFloat(e.target.value) || 0,
                      })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
                    min="0"
                    step="0.01"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Supplier
                  </label>
                  <input
                    type="text"
                    value={newItem.supplier}
                    onChange={(e) =>
                      setNewItem({ ...newItem, supplier: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
                    placeholder="Tech Solutions Ltd"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Barcode
                  </label>
                  <input
                    type="text"
                    value={newItem.barcode}
                    onChange={(e) =>
                      setNewItem({ ...newItem, barcode: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
                    placeholder="1234567890123"
                  />
                </div>
              </div>
            </div>

            <div className="mt-6 flex gap-3">
              <button
                onClick={handleAddItem}
                disabled={loading}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:opacity-50"
              >
                <Plus size={20} />
                {loading ? "Adding..." : "Add Item"}
              </button>
              <button
                onClick={() => setShowAddItemModal(false)}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Receipt Modal */}
      {showReceipt && lastReceipt && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 print:bg-white">
          <div className="bg-white rounded-lg shadow-2xl w-full max-w-md p-8 print:shadow-none print:max-w-full">
            <div className="flex justify-between items-center mb-6 print:hidden">
              <h2 className="text-2xl font-bold">Receipt</h2>
              <button
                onClick={() => setShowReceipt(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                <X size={24} />
              </button>
            </div>

            {/* Receipt Content */}
            <div id="receipt-content" className="print:p-8">
              <div className="text-center mb-6">
                <h1 className="text-2xl font-bold">54agent Agent Banking</h1>
                <p className="text-sm text-gray-600">Agent Banking Platform</p>
                <p className="text-sm text-gray-600">Lagos, Nigeria</p>
              </div>

              <div className="border-t border-b border-gray-300 py-3 mb-4">
                <div className="flex justify-between text-sm">
                  <span>Receipt #:</span>
                  <span className="font-mono">{lastReceipt.id}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Date:</span>
                  <span>
                    {new Date(lastReceipt.created_at).toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Customer:</span>
                  <span className="font-medium">
                    {lastReceipt.customer_name}
                  </span>
                </div>
              </div>

              <table className="w-full mb-4">
                <thead>
                  <tr className="border-b border-gray-300">
                    <th className="text-left py-2 text-sm">Item</th>
                    <th className="text-right py-2 text-sm">Qty</th>
                    <th className="text-right py-2 text-sm">Price</th>
                    <th className="text-right py-2 text-sm">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {parseSaleItems(lastReceipt.items).map(
                    (item, idx: number) => (
                      <tr key={idx} className="border-b border-gray-200">
                        <td className="py-2 text-sm">
                          {item.name}
                          <br />
                          <span className="text-xs text-gray-500">
                            {item.sku}
                          </span>
                        </td>
                        <td className="text-right text-sm">{item.quantity}</td>
                        <td className="text-right text-sm">
                          {formatCurrency(item.unit_price)}
                        </td>
                        <td className="text-right text-sm font-medium">
                          {formatCurrency(item.total)}
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>

              <div className="border-t border-gray-300 pt-3 space-y-2">
                <div className="flex justify-between">
                  <span>Subtotal:</span>
                  <span>{formatCurrency(lastReceipt.subtotal)}</span>
                </div>
                <div className="flex justify-between">
                  <span>VAT (7.5%):</span>
                  <span>{formatCurrency(lastReceipt.tax)}</span>
                </div>
                <div className="flex justify-between text-xl font-bold border-t border-gray-300 pt-2">
                  <span>Total:</span>
                  <span>{formatCurrency(lastReceipt.total)}</span>
                </div>
              </div>

              <div className="text-center mt-6 text-sm text-gray-600">
                <p>Thank you for your business!</p>
                <p className="mt-2">www.54agent.com | support@54agent.com</p>
              </div>
            </div>

            {/* Print Button */}
            <div className="mt-6 flex gap-3 print:hidden">
              <button
                onClick={printReceipt}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)]"
              >
                <Printer size={20} />
                Print Receipt
              </button>
              <button
                onClick={() => setShowReceipt(false)}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-3">
          <Package className="text-[var(--tenant-primary-color,#004F71)]" />
          Inventory Management & POS
        </h1>
        <p className="text-gray-600 mt-1">
          Manage inventory and process sales with automated stock updates
        </p>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">Total Items in Stock</p>
              <p className="text-2xl font-bold text-gray-800 mt-1">
                {metrics.total_items}
              </p>
            </div>
            <Package className="text-[var(--tenant-primary-color,#004F71)]" size={40} />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">Total Inventory Value</p>
              <p className="text-2xl font-bold text-gray-800 mt-1">
                {formatCurrency(metrics.total_value)}
              </p>
            </div>
            <TrendingUp className="text-green-600" size={40} />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">Low Stock Items</p>
              <p className="text-2xl font-bold text-orange-600 mt-1">
                {metrics.low_stock}
              </p>
            </div>
            <AlertTriangle className="text-orange-600" size={40} />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">Sales Today</p>
              <p className="text-2xl font-bold text-green-600 mt-1">
                {salesHistory.length}
              </p>
            </div>
            <ShoppingBag className="text-green-600" size={40} />
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-lg shadow mb-6">
        <div className="border-b border-gray-200">
          <div className="flex gap-4 px-6">
            <button
              onClick={() => setActiveTab("pos")}
              className={`py-4 px-4 font-medium border-b-2 transition-colors flex items-center gap-2 ${
                activeTab === "pos"
                  ? "border-[var(--tenant-secondary-color,#69BC5E)] text-[var(--tenant-primary-color,#004F71)]"
                  : "border-transparent text-gray-600 hover:text-gray-800"
              }`}
            >
              <ShoppingCart size={20} />
              Point of Sale
            </button>
            <button
              onClick={() => setActiveTab("inventory")}
              className={`py-4 px-4 font-medium border-b-2 transition-colors flex items-center gap-2 ${
                activeTab === "inventory"
                  ? "border-[var(--tenant-secondary-color,#69BC5E)] text-[var(--tenant-primary-color,#004F71)]"
                  : "border-transparent text-gray-600 hover:text-gray-800"
              }`}
            >
              <Package size={20} />
              Inventory List
            </button>
            <button
              onClick={() => setActiveTab("sales")}
              className={`py-4 px-4 font-medium border-b-2 transition-colors flex items-center gap-2 ${
                activeTab === "sales"
                  ? "border-[var(--tenant-secondary-color,#69BC5E)] text-[var(--tenant-primary-color,#004F71)]"
                  : "border-transparent text-gray-600 hover:text-gray-800"
              }`}
            >
              <ShoppingBag size={20} />
              Sales History ({salesHistory.length})
            </button>
            <button
              onClick={() => setActiveTab("alerts")}
              className={`py-4 px-4 font-medium border-b-2 transition-colors flex items-center gap-2 ${
                activeTab === "alerts"
                  ? "border-[var(--tenant-secondary-color,#69BC5E)] text-[var(--tenant-primary-color,#004F71)]"
                  : "border-transparent text-gray-600 hover:text-gray-800"
              }`}
            >
              <AlertTriangle size={20} />
              Stock Alerts ({alertItems.length})
            </button>
          </div>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {/* Point of Sale Tab */}
          {activeTab === "pos" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Product Selection */}
              <div className="lg:col-span-2">
                <div className="mb-4">
                  <div className="relative">
                    <Search
                      className="absolute left-3 top-3 text-gray-400"
                      size={20}
                    />
                    <input
                      type="text"
                      placeholder="Search by name, SKU, or scan barcode..."
                      className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] text-lg"
                      value={posSearch}
                      onChange={(e) => setPosSearch(e.target.value)}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 max-h-[600px] overflow-y-auto">
                  {posFilteredItems.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => addToCart(item)}
                      disabled={item.quantity === 0}
                      className={`p-4 border-2 rounded-lg text-left transition-all ${
                        item.quantity === 0
                          ? "border-gray-200 bg-gray-50 cursor-not-allowed opacity-50"
                          : "border-[rgba(0,79,113,0.2)] hover:border-[var(--tenant-secondary-color,#69BC5E)] hover:shadow-lg"
                      }`}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <h3 className="font-semibold text-sm line-clamp-2">
                          {item.name}
                        </h3>
                        <span
                          className={`text-xs px-2 py-1 rounded font-bold ${getStatusColor(item.status)}`}
                        >
                          {item.quantity}
                        </span>
                      </div>
                      <p className="text-xs text-gray-600 mb-2">{item.sku}</p>
                      <p className="text-lg font-bold text-[var(--tenant-primary-color,#004F71)]">
                        {formatCurrency(item.unit_price)}
                      </p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Cart */}
              {/* <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-6 rounded-lg border-2 border-[rgba(0,79,113,0.2)]">
                <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                  <ShoppingCart className="text-[var(--tenant-primary-color,#004F71)]" />
                  Current Sale
                </h2>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Customer Name *
                  </label>
                  <input
                    type="text"
                    placeholder="Enter customer name"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
                    value={customerName}
                    onChange={(e) => setCustomerName(e.target.value)}
                  />
                </div>

                <div className="space-y-3 mb-4 max-h-64 overflow-y-auto">
                  {cart.map((cartItem) => (
                    <div
                      key={cartItem.item.id}
                      className="bg-white p-3 rounded-lg shadow-sm"
                    >
                      <div className="flex justify-between items-start mb-2">
                        <div className="flex-1">
                          <h4 className="font-medium text-sm">
                            {cartItem.item.name}
                          </h4>
                          <p className="text-xs text-gray-600">
                            {formatCurrency(cartItem.item.unit_price)}
                          </p>
                        </div>
                        <button
                          onClick={() => removeFromCart(cartItem.item.id)}
                          className="text-red-600 hover:bg-red-50 p-1 rounded"
                        >
                          <X size={16} />
                        </button>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() =>
                              updateCartQuantity(cartItem.item.id, -1)
                            }
                            className="p-1 bg-gray-200 hover:bg-gray-300 rounded"
                          >
                            <Minus size={16} />
                          </button>
                          <span className="font-medium w-8 text-center">
                            {cartItem.quantity}
                          </span>
                          <button
                            onClick={() =>
                              updateCartQuantity(cartItem.item.id, 1)
                            }
                            className="p-1 bg-gray-200 hover:bg-gray-300 rounded"
                          >
                            <Plus size={16} />
                          </button>
                        </div>
                        <span className="font-bold">
                          {formatCurrency(
                            cartItem.item.unit_price * cartItem.quantity,
                          )}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                {cart.length === 0 && (
                  <div className="text-center text-gray-500 py-8 bg-white rounded-lg">
                    <ShoppingCart
                      size={48}
                      className="mx-auto mb-2 opacity-50"
                    />
                    <p>Cart is empty</p>
                    <p className="text-sm">Add items to start a sale</p>
                  </div>
                )}

                <div className="bg-white rounded-lg p-4 border-t-2 border-[rgba(0,79,113,0.2)] space-y-2">
                  <div className="flex justify-between">
                    <span>Subtotal:</span>
                    <span className="font-medium">
                      {formatCurrency(calculateTotal())}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>VAT (7.5%):</span>
                    <span className="font-medium">
                      {formatCurrency(calculateTotal() * 0.075)}
                    </span>
                  </div>
                  <div className="flex justify-between text-xl font-bold border-t pt-2">
                    <span>Total:</span>
                    <span className="text-[var(--tenant-primary-color,#004F71)]">
                      {formatCurrency(calculateTotal() * 1.075)}
                    </span>
                  </div>
                </div>

                <button
                  onClick={completeSale}
                  disabled={cart.length === 0}
                  className={`w-full mt-6 py-3 rounded-lg font-bold text-white transition-colors flex items-center justify-center gap-2 ${
                    cart.length === 0
                      ? "bg-gray-400 cursor-not-allowed"
                      : "bg-green-600 hover:bg-green-700"
                  }`}
                >
                  <Printer size={20} />
                  Complete Sale & Generate Receipt
                </button>
              </div> */}
            </div>
          )}

          {/* Inventory List Tab */}
          {activeTab === "inventory" && (
            <div>
              {/* Header with Add Button */}
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-lg font-semibold">Inventory Items</h3>
                <button
                  onClick={() => setShowAddItemModal(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)]"
                >
                  <Plus size={20} />
                  Add Item
                </button>
              </div>

              {/* Filters */}
              <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
                <div className="relative md:col-span-2">
                  <Search
                    className="absolute left-3 top-3 text-gray-400"
                    size={20}
                  />
                  <input
                    type="text"
                    placeholder="Search by name or SKU..."
                    className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>

                <select
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
                  value={filterCategory}
                  onChange={(e) => setFilterCategory(e.target.value)}
                >
                  <option value="all">All Categories</option>
                  <option value="Hardware">Hardware</option>
                  <option value="Accessories">Accessories</option>
                  <option value="Consumables">Consumables</option>
                </select>

                <select
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                >
                  <option value="all">All Status</option>
                  <option value="in_stock">In Stock</option>
                  <option value="low_stock">Low Stock</option>
                  <option value="critical">Critical</option>
                  <option value="out_of_stock">Out of Stock</option>
                </select>
              </div>

              {/* Table */}
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">
                        SKU
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">
                        Item Name
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">
                        Category
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">
                        Quantity
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">
                        Unit Price
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">
                        Total Value
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {filteredItems.map((item) => (
                      <tr key={item.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-mono">
                          {item.sku}
                        </td>
                        <td className="px-4 py-3 text-sm font-medium">
                          {item.name}
                        </td>
                        <td className="px-4 py-3 text-sm">{item.category}</td>
                        <td className="px-4 py-3 text-sm font-bold">
                          {item.quantity}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {formatCurrency(item.unit_price)}
                        </td>
                        <td className="px-4 py-3 text-sm font-medium">
                          {formatCurrency(item.quantity * item.unit_price)}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(item.status)}`}
                          >
                            {getStatusIcon(item.status)}
                            {item.status.replace("_", " ")}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Sales History Tab */}
          {activeTab === "sales" && (
            <div>
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold">Recent Sales</h3>
                <div className="text-sm text-gray-600">
                  Total Revenue:{" "}
                  <span className="font-bold text-green-600">
                    {formatCurrency(
                      salesHistory.reduce((sum, sale) => sum + sale.total, 0),
                    )}
                  </span>
                </div>
              </div>
              {salesHistory.length === 0 ? (
                <div className="text-center text-gray-500 py-12 bg-gray-50 rounded-lg">
                  <ShoppingBag size={48} className="mx-auto mb-4 opacity-50" />
                  <p className="font-medium">No sales recorded yet</p>
                  <p className="text-sm">
                    Start selling to see sales history here
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {salesHistory.map((sale) => (
                    <div
                      key={sale.id}
                      className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
                    >
                      <div className="flex justify-between items-start mb-3">
                        <div>
                          <h4 className="font-semibold flex items-center gap-2">
                            Receipt #{sale.id}
                            <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">
                              Completed
                            </span>
                          </h4>
                          <p className="text-sm text-gray-600">
                            {new Date(sale.created_at).toLocaleString()}
                          </p>
                          <p className="text-sm text-gray-600">
                            Customer:{" "}
                            <span className="font-medium">
                              {sale.customer_name}
                            </span>
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-2xl font-bold text-green-600">
                            {formatCurrency(sale.total)}
                          </p>
                          <p className="text-sm text-gray-600">
                            {parseSaleItems(sale.items).length} items
                          </p>
                        </div>
                      </div>
                      <div className="border-t pt-3 bg-gray-50 rounded p-3">
                        {parseSaleItems(sale.items).map((item, idx: number) => (
                          <div
                            key={idx}
                            className="flex justify-between text-sm py-1"
                          >
                            <span>
                              {item.name}{" "}
                              <span className="text-gray-500">
                                x{item.quantity}
                              </span>
                            </span>
                            <span className="font-medium">
                              {formatCurrency(item.total)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Alerts Tab */}
          {activeTab === "alerts" && (
            <div>
              <h3 className="text-lg font-semibold mb-4">Stock Level Alerts</h3>
              {alertItems.length === 0 ? (
                <div className="text-center text-gray-500 py-12 bg-gray-50 rounded-lg">
                  <CheckCircle
                    size={48}
                    className="mx-auto mb-4 text-green-500"
                  />
                  <p className="font-medium">All items are well stocked!</p>
                  <p className="text-sm">No reorder alerts at this time</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {alertItems.map((item) => (
                    <div
                      key={item.id}
                      className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex gap-3">
                          <div
                            className={`p-3 rounded-lg ${
                              item.status === "out_of_stock"
                                ? "bg-red-100"
                                : item.status === "critical"
                                  ? "bg-orange-100"
                                  : "bg-yellow-100"
                            }`}
                          >
                            <AlertTriangle
                              className={
                                item.status === "out_of_stock"
                                  ? "text-red-600"
                                  : item.status === "critical"
                                    ? "text-orange-600"
                                    : "text-yellow-600"
                              }
                              size={24}
                            />
                          </div>
                          <div>
                            <h4 className="font-semibold text-lg">
                              {item.name}
                            </h4>
                            <p className="text-sm text-gray-600">
                              SKU: {item.sku}
                            </p>
                            <div className="mt-2 flex gap-4">
                              <p className="text-sm">
                                Current:{" "}
                                <span
                                  className={`font-bold ${
                                    item.quantity === 0
                                      ? "text-red-600"
                                      : item.quantity < item.reorder_level
                                        ? "text-orange-600"
                                        : "text-gray-800"
                                  }`}
                                >
                                  {item.quantity}
                                </span>
                              </p>
                              <p className="text-sm">
                                Reorder at:{" "}
                                <span className="font-medium">
                                  {item.reorder_level}
                                </span>
                              </p>
                              <p className="text-sm text-gray-600">
                                Location: {item.location}
                              </p>
                            </div>
                          </div>
                        </div>
                        <span
                          className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(item.status)}`}
                        >
                          {item.status === "out_of_stock"
                            ? "⚠️ Out of Stock"
                            : item.status === "critical"
                              ? "🔴 Critical"
                              : "⚡ Low Stock"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default InventoryManagement;

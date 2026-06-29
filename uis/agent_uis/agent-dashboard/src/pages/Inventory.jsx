import { BrowserMultiFormatReader } from "@zxing/browser";
import {
    AlertTriangle,
    Camera,
    Edit,
    Filter,
    MapPin,
    Package,
    Plus,
    Search,
    Store as StoreIcon,
    Trash2,
    X,
} from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import MapPicker from "../components/MapPicker";
import { documentApi, inventoryApi, storeMapApi } from "../utils/api";

const EMPTY_ITEM = {
  name: "",
  sku: "",
  category: "Hardware",
  quantity: 0,
  reorder_level: 10,
  unit_price: 0,
  supplier: "",
  location: "Warehouse A",
  barcode: "",
};

const EMPTY_STORE = {
  name: "",
  description: "",
  address: "",
  store_type: "AGENT",
  latitude: "",
  longitude: "",
};

const Inventory = () => {
  const [inventoryItems, setInventoryItems] = useState([]);
  const [metrics, setMetrics] = useState({
    total_items: 0,
    total_value: 0,
    low_stock: 0,
    out_of_stock: 0,
  });
  const [searchQuery, setSearchQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [stores, setStores] = useState([]);
  const [selectedStore, setSelectedStore] = useState(null);
  const [showCreateStoreModal, setShowCreateStoreModal] = useState(false);
  const [newStore, setNewStore] = useState(EMPTY_STORE);
  const [geocoding, setGeocoding] = useState(false);
  const [geocodeError, setGeocodeError] = useState("");

  const [showAddItemModal, setShowAddItemModal] = useState(false);
  const [newItem, setNewItem] = useState(EMPTY_ITEM);
  const [editingItem, setEditingItem] = useState(null);
  const [showBarcodeScanner, setShowBarcodeScanner] = useState(false);
  const [scannerError, setScannerError] = useState("");
  const [scannerStarting, setScannerStarting] = useState(false);
  const [scannerSession, setScannerSession] = useState(0);
  const [isMobileView, setIsMobileView] = useState(
    typeof window !== "undefined" ? window.innerWidth < 1024 : false,
  );
  const videoRef = useRef(null);
  const scannerRef = useRef(null);
  const hasScannedRef = useRef(false);

  // uploadedImages: [{ id, previewUrl, docUrl, uploading, name }]
  const [uploadedImages, setUploadedImages] = useState([]);
  const [uploadingImages, setUploadingImages] = useState(false);

  useEffect(() => {
    loadStores();
  }, []);
  useEffect(() => {
    if (selectedStore) loadInventoryItems();
  }, [selectedStore]);
  useEffect(() => {
    if (selectedStore) loadMetrics();
  }, [selectedStore]);
  useEffect(() => {
    if (!selectedStore) return;
    const t = setTimeout(() => loadInventoryItems(), 300);
    return () => clearTimeout(t);
  }, [searchQuery, filterStatus, selectedStore]);

  useEffect(() => {
    const onResize = () => setIsMobileView(window.innerWidth < 1024);
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const loadStores = async () => {
    try {
      const keycloakId = localStorage.getItem("keycloakId");
      const data = await inventoryApi.getStores(keycloakId);
      setStores(data);
      if (data.length > 0 && !selectedStore) setSelectedStore(data[0]);
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
        status:
          filterStatus !== "all" ? filterStatus.replace("-", "_") : undefined,
      });
      setInventoryItems(items);
    } catch (err) {
      setError(err.message || "Failed to load inventory items");
    } finally {
      setLoading(false);
    }
  };

  const loadMetrics = async () => {
    try {
      setMetrics(await inventoryApi.getInventoryMetrics());
    } catch (err) {
      console.error("Error loading metrics:", err);
    }
  };

  const geocodeAddress = async () => {
    if (!newStore.address.trim()) return;
    setGeocoding(true);
    setGeocodeError("");
    const parts = newStore.address
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean);
    try {
      for (let i = 0; i < parts.length; i++) {
        const q = parts.slice(i).join(", ");
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(q)}&format=json&limit=1&countrycodes=ng`,
          { headers: { "Accept-Language": "en" } },
        );
        const results = await res.json();
        if (results.length > 0) {
          const { lat, lon } = results[0];
          setNewStore((prev) => ({
            ...prev,
            latitude: parseFloat(lat).toFixed(6),
            longitude: parseFloat(lon).toFixed(6),
          }));
          return;
        }
      }
      setGeocodeError(
        "Address not found — try a more specific address or pin on the map.",
      );
    } catch {
      setGeocodeError("Geocoding failed — please pin the location manually.");
    } finally {
      setGeocoding(false);
    }
  };

  const handleCreateStore = async () => {
    if (!newStore.name.trim()) {
      alert("Please enter a store name");
      return;
    }
    try {
      setLoading(true);
      const keycloakId = localStorage.getItem("keycloakId");
      const createdStore = await inventoryApi.createStore({
        name: newStore.name,
        description: newStore.description,
        owner_keycloak_id: keycloakId,
      });
      const lat = parseFloat(newStore.latitude);
      const lng = parseFloat(newStore.longitude);
      if (!isNaN(lat) && !isNaN(lng)) {
        try {
          await storeMapApi.registerStore({
            entity_id: String(createdStore.id),
            entity_name: createdStore.name || newStore.name,
            store_type: newStore.store_type,
            latitude: lat,
            longitude: lng,
            address: newStore.address || undefined,
          });
        } catch (mapErr) {
          console.warn("Map registration failed:", mapErr);
        }
      }
      setStores((prev) => [...prev, createdStore]);
      setSelectedStore(createdStore);
      setShowCreateStoreModal(false);
      setNewStore(EMPTY_STORE);
    } catch (err) {
      alert(err.message || "Failed to create store");
    } finally {
      setLoading(false);
    }
  };

  // Upload immediately when files are chosen — no waiting for submit
  const handleImageChange = async (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;
    e.target.value = ""; // allow re-selecting the same file later
    setUploadingImages(true);

    for (const file of files) {
      const id = `${Date.now()}-${Math.random()}`;
      const previewUrl = URL.createObjectURL(file);

      // add placeholder so thumbnail shows instantly with uploading overlay
      setUploadedImages((prev) => [
        ...prev,
        { id, previewUrl, docUrl: null, uploading: true, name: file.name },
      ]);

      try {
        const resp = await documentApi.uploadFile(file, "product_image");
        console.log("Upload response:", resp);
        // Ensure URL has protocol
        let imageUrl = resp.url;
        if (imageUrl && !imageUrl.startsWith("http")) {
          imageUrl = `https://${imageUrl}`;
        }
        console.log("Stored image URL:", imageUrl);
        setUploadedImages((prev) =>
          prev.map((img) =>
            img.id === id
              ? { ...img, docUrl: imageUrl, uploading: false }
              : img,
          ),
        );
      } catch (err) {
        console.error("Upload failed:", file.name, err);
        setUploadedImages((prev) => prev.filter((img) => img.id !== id));
        alert(`Failed to upload "${file.name}": ${err.message || err}`);
      }
    }

    setUploadingImages(false);
  };

  const removeImage = (id) =>
    setUploadedImages((prev) => prev.filter((img) => img.id !== id));

  const closeAddItemModal = () => {
    setShowAddItemModal(false);
    closeBarcodeScanner();
    setNewItem(EMPTY_ITEM);
    setEditingItem(null);
    setUploadedImages([]);
  };

  const closeBarcodeScanner = () => {
    setShowBarcodeScanner(false);
    setScannerError("");
    setScannerStarting(false);
    hasScannedRef.current = false;
    if (scannerRef.current && typeof scannerRef.current.reset === "function") {
      scannerRef.current.reset();
      scannerRef.current = null;
    } else if (scannerRef.current) {
      scannerRef.current = null;
    }
  };

  const openBarcodeScanner = () => {
    setScannerError("");
    setScannerStarting(true);
    setShowBarcodeScanner(true);
    setScannerSession((current) => current + 1);
  };

  useEffect(() => {
    if (!showBarcodeScanner || !videoRef.current) return;

    if (!navigator.mediaDevices?.getUserMedia) {
      setScannerStarting(false);
      setScannerError(
        "Camera is not supported in this browser. Use manual barcode entry.",
      );
      return;
    }

    const isLocalhost =
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1";
    const isSecure = window.isSecureContext || isLocalhost;

    if (!isSecure) {
      setScannerStarting(false);
      setScannerError(
        "Camera access requires HTTPS (or localhost). Please open this dashboard via HTTPS.",
      );
      return;
    }

    hasScannedRef.current = false;
    const reader = new BrowserMultiFormatReader();
    scannerRef.current = reader;

    if (videoRef.current) {
      videoRef.current.onloadedmetadata = () => setScannerStarting(false);
    }

    reader
      .decodeFromConstraints(
        {
          audio: false,
          video: {
            facingMode: { ideal: "environment" },
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
        },
        videoRef.current,
        (result, err) => {
          if (result && !hasScannedRef.current) {
            hasScannedRef.current = true;
            setNewItem((prev) => ({ ...prev, barcode: result.getText() }));
            closeBarcodeScanner();
            return;
          }

          if (
            err &&
            !String(err?.name || "").includes("NotFoundException") &&
            !String(err?.message || "").includes("No MultiFormat Readers")
          ) {
            console.error("Barcode scan error:", err);
          }
        },
      )
      .catch((err) => {
        console.error("Unable to start barcode scanner:", err);
        setScannerStarting(false);
        setScannerError(
          "Unable to access camera. Ensure camera permission is granted and the site is served over HTTPS.",
        );
      });

    return () => {
      if (
        scannerRef.current &&
        typeof scannerRef.current.reset === "function"
      ) {
        scannerRef.current.reset();
        scannerRef.current = null;
      } else if (scannerRef.current) {
        scannerRef.current = null;
      }
      if (videoRef.current) {
        videoRef.current.onloadedmetadata = null;
      }
      hasScannedRef.current = false;
      setScannerStarting(false);
    };
  }, [showBarcodeScanner, scannerSession]);

  const handleEditItem = (item) => {
    setEditingItem(item);
    setNewItem({
      name: item.name || "",
      sku: item.sku || "",
      category: item.category || "Hardware",
      quantity: item.quantity || 0,
      reorder_level: item.reorder_level || 10,
      unit_price: item.unit_price || 0,
      supplier: item.supplier || "",
      location: item.location || "Warehouse A",
      barcode: item.barcode || "",
    });
    setShowAddItemModal(true);
  };

  const handleAddItem = async () => {
    if (!selectedStore) {
      alert("Please select a store first");
      return;
    }
    if (!newItem.name || !newItem.sku || newItem.unit_price <= 0) {
      alert("Please fill in Name, SKU and Unit Price");
      return;
    }
    if (uploadingImages) {
      alert("Please wait for images to finish uploading");
      return;
    }

    try {
      setLoading(true);

      let itemId;
      if (editingItem) {
        // Update existing item
        await inventoryApi.updateInventoryItem(editingItem.id, {
          ...newItem,
          store_id: selectedStore.id,
        });
        itemId = editingItem.id;
        console.log("Updated item:", itemId);
      } else {
        // Create new item
        const createdItem = await inventoryApi.createInventoryItem(
          selectedStore.id,
          { ...newItem, store_id: selectedStore.id },
        );
        itemId = createdItem.id;
        console.log("Created item:", createdItem);
      }

      const readyImages = uploadedImages.filter((i) => i.docUrl);
      console.log("Images to associate:", readyImages.length, readyImages);

      for (const img of readyImages) {
        try {
          console.log(
            "Associating image URL:",
            img.docUrl,
            "with item:",
            itemId,
          );
          const result = await inventoryApi.addItemImageUrl(itemId, img.docUrl);
          console.log("Image association result:", result);
        } catch (e) {
          console.error("Failed to link image:", img.docUrl, e);
          alert(`Warning: Failed to link image: ${e.message || e}`);
        }
      }
      closeAddItemModal();
      await loadInventoryItems();
      await loadMetrics();
    } catch (err) {
      console.error("Error saving item:", err);
      alert(err.message || `Failed to ${editingItem ? "update" : "add"} item`);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (s) =>
    ({
      in_stock: "bg-green-100 text-green-800",
      low_stock: "bg-yellow-100 text-yellow-800",
      critical: "bg-orange-100 text-orange-800",
      out_of_stock: "bg-red-100 text-red-800",
    })[s] || "bg-gray-100 text-gray-800";
  const formatStatus = (s) =>
    s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const formatCurrency = (n) =>
    new Intl.NumberFormat("en-NG", {
      style: "currency",
      currency: "NGN",
    }).format(n);

  return (
    <div className="w-full max-w-full min-w-0 overflow-x-hidden space-y-4 sm:space-y-6">
      {/* ─── Add Item Modal ────────────────────────────────────────────────── */}
      {showAddItemModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-2xl w-full max-w-2xl p-4 sm:p-6 lg:p-8 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold">
                {editingItem ? "Edit" : "Add New"} Inventory Item
              </h2>
              <button
                onClick={closeAddItemModal}
                className="text-gray-500 hover:text-gray-700"
              >
                <X size={24} />
              </button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
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
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="POS-A-001"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Category
                  </label>
                  <select
                    value={newItem.category}
                    onChange={(e) =>
                      setNewItem({ ...newItem, category: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option>Hardware</option>
                    <option>Accessories</option>
                    <option>Consumables</option>
                    <option>Software</option>
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
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option>Warehouse A</option>
                    <option>Warehouse B</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Quantity
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={newItem.quantity}
                    onChange={(e) =>
                      setNewItem({
                        ...newItem,
                        quantity: parseInt(e.target.value) || 0,
                      })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Reorder Level
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={newItem.reorder_level}
                    onChange={(e) =>
                      setNewItem({
                        ...newItem,
                        reorder_level: parseInt(e.target.value) || 0,
                      })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Unit Price (₦) *
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={newItem.unit_price}
                    onChange={(e) =>
                      setNewItem({
                        ...newItem,
                        unit_price: parseFloat(e.target.value) || 0,
                      })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="Tech Solutions Ltd"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Barcode
                  </label>
                  <div className="flex flex-col sm:flex-row gap-2">
                    <input
                      type="text"
                      value={newItem.barcode}
                      onChange={(e) =>
                        setNewItem({ ...newItem, barcode: e.target.value })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      placeholder="1234567890123"
                    />
                    <button
                      type="button"
                      onClick={openBarcodeScanner}
                      className="inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-gray-100 border border-gray-300 rounded-lg text-sm hover:bg-gray-200 whitespace-nowrap"
                    >
                      <Camera size={16} /> Scan
                    </button>
                  </div>
                </div>
              </div>

              {/* Image Upload — uploads to document service immediately on pick */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Product Images (Optional)
                </label>

                <input
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleImageChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 cursor-pointer"
                />

                {uploadingImages && (
                  <p className="text-sm text-blue-600 mt-1 animate-pulse">
                    Uploading images…
                  </p>
                )}

                {uploadedImages.length > 0 && (
                  <div className="mt-3 grid grid-cols-4 gap-2">
                    {uploadedImages.map((img) => (
                      <div key={img.id} className="relative aspect-square">
                        <img
                          src={img.previewUrl}
                          alt={img.name}
                          className="w-full h-full object-cover rounded-lg border border-gray-200"
                        />

                        {img.uploading ? (
                          <div className="absolute inset-0 bg-black bg-opacity-50 flex flex-col items-center justify-center rounded-lg">
                            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin mb-1" />
                            <span className="text-white text-xs">
                              Uploading
                            </span>
                          </div>
                        ) : img.docUrl ? (
                          <button
                            type="button"
                            onClick={() => removeImage(img.id)}
                            className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 hover:bg-red-600 text-white rounded-full flex items-center justify-center text-xs shadow"
                          >
                            ×
                          </button>
                        ) : (
                          <div className="absolute inset-0 bg-red-500 bg-opacity-60 flex items-center justify-center rounded-lg">
                            <span className="text-white text-xs font-medium">
                              Failed
                            </span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {uploadedImages.length > 0 && !uploadingImages && (
                  <p className="text-xs text-gray-500 mt-1">
                    {uploadedImages.filter((i) => i.docUrl).length} of{" "}
                    {uploadedImages.length} image(s) ready
                  </p>
                )}
              </div>
            </div>

            <div className="mt-6 flex gap-3">
              <button
                onClick={handleAddItem}
                disabled={loading || uploadingImages}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <Plus size={20} />
                {uploadingImages
                  ? "Waiting for images…"
                  : loading
                    ? editingItem
                      ? "Updating…"
                      : "Adding…"
                    : editingItem
                      ? "Update Item"
                      : "Add Item"}
              </button>
              <button
                onClick={closeAddItemModal}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {showBarcodeScanner && (
        <div className="fixed inset-0 bg-black/70 z-70 flex items-center justify-center p-4">
          <div className="bg-white w-full max-w-2xl rounded-xl overflow-hidden border border-gray-200">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
              <h3 className="text-white font-semibold">Scan Barcode</h3>
              <button
                onClick={closeBarcodeScanner}
                className="text-gray-600 hover:text-white"
              >
                <X size={20} />
              </button>
            </div>

            {scannerError ? (
              <div className="p-5 space-y-4">
                <p className="text-sm text-red-300">{scannerError}</p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setScannerError("");
                      setScannerSession((current) => current + 1);
                    }}
                    className="px-3 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg text-sm hover:bg-[var(--tenant-primary-color,#003F5A)]"
                  >
                    Try Again
                  </button>
                  <button
                    type="button"
                    onClick={closeBarcodeScanner}
                    className="px-3 py-2 border border-gray-300 text-gray-200 rounded-lg text-sm hover:bg-gray-800"
                  >
                    Close
                  </button>
                </div>
              </div>
            ) : (
              <>
                <video
                  ref={videoRef}
                  className="w-full aspect-video bg-black object-cover"
                  autoPlay
                  muted
                  playsInline
                />
                <div className="px-4 py-3 border-t border-gray-800">
                  {scannerStarting && (
                    <p className="text-xs text-amber-300 mb-1">
                      Starting camera...
                    </p>
                  )}
                  <p className="text-sm text-gray-600">
                    Position the barcode within the frame. It will auto-fill on
                    detection.
                  </p>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ─── Create Store Modal ────────────────────────────────────────────── */}
      {showCreateStoreModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white z-10 flex justify-between items-center px-4 sm:px-6 lg:px-8 pt-4 sm:pt-6 lg:pt-8 pb-4 border-b">
              <h2 className="text-2xl font-bold">Create New Store</h2>
              <button
                onClick={() => setShowCreateStoreModal(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                <X size={24} />
              </button>
            </div>

            <div className="px-4 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Store Name *
                </label>
                <input
                  type="text"
                  value={newStore.name}
                  onChange={(e) =>
                    setNewStore({ ...newStore, name: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="My Store"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description
                </label>
                <textarea
                  value={newStore.description}
                  onChange={(e) =>
                    setNewStore({ ...newStore, description: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  rows="2"
                  placeholder="Brief description of your store"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Address
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newStore.address}
                    onChange={(e) => {
                      setNewStore({ ...newStore, address: e.target.value });
                      setGeocodeError("");
                    }}
                    onKeyDown={(e) => e.key === "Enter" && geocodeAddress()}
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g. 12 Marina Street, Lagos Island"
                  />
                  <button
                    type="button"
                    onClick={geocodeAddress}
                    disabled={geocoding || !newStore.address.trim()}
                    className="px-3 py-2 bg-gray-100 border border-gray-300 rounded-lg text-sm hover:bg-gray-200 disabled:opacity-50 whitespace-nowrap flex items-center gap-1"
                  >
                    <MapPin size={14} />
                    {geocoding ? "Looking up…" : "Look up"}
                  </button>
                </div>
                {geocodeError && (
                  <p className="mt-1 text-xs text-red-500">{geocodeError}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Store Type
                </label>
                <select
                  value={newStore.store_type}
                  onChange={(e) =>
                    setNewStore({ ...newStore, store_type: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="AGENT">Agent</option>
                  <option value="MERCHANT">Merchant</option>
                  <option value="SUPER_AGENT">Super Agent</option>
                  <option value="AGGREGATOR">Aggregator</option>
                  <option value="POS_TERMINAL">POS Terminal</option>
                  <option value="ATM">ATM</option>
                  <option value="BANK_BRANCH">Bank Branch</option>
                </select>
              </div>
              <div className="pt-2">
                <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                  <MapPin size={14} /> Store Location
                  <span className="text-xs font-normal text-gray-500">
                    (optional — shows store on the map)
                  </span>
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Latitude
                    </label>
                    <input
                      type="number"
                      step="any"
                      value={newStore.latitude}
                      onChange={(e) =>
                        setNewStore({ ...newStore, latitude: e.target.value })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                      placeholder="e.g. 6.5244"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Longitude
                    </label>
                    <input
                      type="number"
                      step="any"
                      value={newStore.longitude}
                      onChange={(e) =>
                        setNewStore({ ...newStore, longitude: e.target.value })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                      placeholder="e.g. 3.3792"
                    />
                  </div>
                </div>
                <MapPicker
                  latitude={newStore.latitude}
                  longitude={newStore.longitude}
                  onLocationChange={(lat, lng) =>
                    setNewStore((prev) => ({
                      ...prev,
                      latitude: lat.toFixed(6),
                      longitude: lng.toFixed(6),
                    }))
                  }
                />
              </div>
            </div>

            <div className="sticky bottom-0 bg-white border-t px-4 sm:px-6 lg:px-8 py-4 flex flex-col sm:flex-row gap-3">
              {/* <button
                onClick={handleCreateStore}
                disabled={loading}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? "Creating…" : "Create Store"}
              </button> */}
              <button
                onClick={() => setShowCreateStoreModal(false)}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Page Header ──────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Package className="h-8 w-8" />
            Inventory Management
          </h1>
          <p className="text-gray-600 mt-1">
            Manage your stores and inventory items
          </p>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center gap-2 w-full sm:w-auto">
          {/* <button
            onClick={() => setShowCreateStoreModal(true)}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors w-full sm:w-auto font-medium"
          >
            <StoreIcon className="h-5 w-5 shrink-0" />
            Create Store
          </button> */}
          <button
            onClick={() => setShowAddItemModal(true)}
            disabled={!selectedStore}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed w-full sm:w-auto font-medium"
          >
            <Plus className="h-5 w-5 shrink-0" />
            Add Item
          </button>
        </div>
      </div>

      {/* ─── Store Selector ───────────────────────────────────────────────── */}
      {stores.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
            <label className="text-sm font-medium text-gray-700">
              Select Store:
            </label>
            <select
              value={selectedStore?.id || ""}
              onChange={(e) =>
                setSelectedStore(
                  stores.find((s) => s.id === parseInt(e.target.value)),
                )
              }
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              {stores.map((store) => (
                <option key={store.id} value={store.id}>
                  {store.name}
                  {store.description && ` - ${store.description}`}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {!selectedStore && stores.length === 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 text-center">
          <StoreIcon className="h-12 w-12 text-blue-600 mx-auto mb-3" />
          <h3 className="text-lg font-medium text-blue-900 mb-2">
            No Stores Yet
          </h3>
          <p className="text-blue-700 mb-4">
            Create your first store to start managing inventory
          </p>
          <button
            onClick={() => setShowCreateStoreModal(true)}
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-5 w-5 mr-2" />
            Create Your First Store
          </button>
        </div>
      )}

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          <strong>Error: </strong>
          <span>{error}</span>
        </div>
      )}

      {/* ─── Stats ────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total Items</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">
            {metrics.unique_items || inventoryItems.length}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total Value</p>
          <p className="text-2xl font-bold text-green-600 mt-1">
            {formatCurrency(metrics.total_value || 0)}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-yellow-500">
          <p className="text-sm text-gray-600">Low Stock</p>
          <p className="text-2xl font-bold text-yellow-600 mt-1">
            {metrics.low_stock || 0}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-red-500">
          <p className="text-sm text-gray-600">Out of Stock</p>
          <p className="text-2xl font-bold text-red-600 mt-1">
            {metrics.out_of_stock || 0}
          </p>
        </div>
      </div>

      {/* ─── Filters ──────────────────────────────────────────────────────── */}
      <div className="flex flex-col lg:flex-row gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name, SKU, or barcode…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="flex items-center space-x-2">
          <Filter className="h-5 w-5 text-gray-400" />
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="w-full sm:w-auto px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Status</option>
            <option value="in_stock">In Stock</option>
            <option value="low_stock">Low Stock</option>
            <option value="critical">Critical</option>
            <option value="out_of_stock">Out of Stock</option>
          </select>
        </div>
      </div>

      {loading && (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          <p className="mt-2 text-gray-600">Loading inventory…</p>
        </div>
      )}

      {/* ─── Table ────────────────────────────────────────────────────────── */}
      {!loading && inventoryItems.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          {isMobileView ? (
            <div className="divide-y divide-gray-100">
              {inventoryItems.map((item) => (
                <div key={item.id} className="p-4 space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3 min-w-0">
                      <div className="p-2 bg-blue-100 rounded-lg shrink-0">
                        <Package className="h-4 w-4 text-blue-600" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-gray-900 truncate">
                          {item.name}
                        </p>
                        <p className="text-xs text-gray-500 truncate">
                          {item.sku} · {item.category}
                        </p>
                      </div>
                    </div>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium shrink-0 ${getStatusColor(item.status)}`}
                    >
                      {(item.status === "low_stock" ||
                        item.status === "critical") && (
                        <AlertTriangle className="h-3 w-3 mr-1" />
                      )}
                      {formatStatus(item.status)}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <p className="text-gray-500">Location</p>
                      <p className="text-gray-800 truncate">
                        {item.location || "N/A"}
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-500">Quantity</p>
                      <p className="text-gray-800 font-medium">
                        {item.quantity}{" "}
                        <span className="text-gray-500">
                          (Min: {item.reorder_level})
                        </span>
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-500">Unit Price</p>
                      <p className="text-gray-800 font-medium">
                        {formatCurrency(item.unit_price)}
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-500">Total Value</p>
                      <p className="text-gray-800 font-semibold">
                        {formatCurrency(item.quantity * item.unit_price)}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-3 pt-1">
                    <button
                      onClick={() => handleEditItem(item)}
                      className="inline-flex items-center gap-1 text-sm"
                      style={{ color: "var(--tenant-primary-color,#002082)" }}
                      title="Edit item"
                    >
                      <Edit className="h-4 w-4" /> Edit
                    </button>
                    <button
                      className="inline-flex items-center gap-1 text-sm text-red-600 hover:text-red-900"
                      title="Delete item"
                    >
                      <Trash2 className="h-4 w-4" /> Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto max-h-[60vh] overflow-scroll">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    {[
                      "Item Details",
                      "Location",
                      "Quantity",
                      "Unit Price",
                      "Total Value",
                      "Status",
                      "",
                    ].map((h) => (
                      <th
                        key={h}
                        className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {inventoryItems.map((item) => (
                    <tr key={item.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <div className="flex items-center">
                          <div className="p-2 bg-blue-100 rounded-lg mr-3">
                            <Package className="h-5 w-5 text-blue-600" />
                          </div>
                          <div>
                            <p className="font-medium text-gray-900">
                              {item.name}
                            </p>
                            <p className="text-sm text-gray-500">
                              {item.sku} · {item.category}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                        {item.location || "N/A"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <p className="text-sm font-medium text-gray-900">
                          {item.quantity}
                        </p>
                        <p className="text-xs text-gray-500">
                          Min: {item.reorder_level}
                        </p>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {formatCurrency(item.unit_price)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {formatCurrency(item.quantity * item.unit_price)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(item.status)}`}
                        >
                          {(item.status === "low_stock" ||
                            item.status === "critical") && (
                            <AlertTriangle className="h-3 w-3 mr-1" />
                          )}
                          {formatStatus(item.status)}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <div className="flex justify-end space-x-2">
                          <button
                            onClick={() => handleEditItem(item)}
                            className="hover:text-gray-900"
                            style={{ color: "var(--tenant-primary-color,#002082)" }}
                            title="Edit item"
                          >
                            <Edit className="h-4 w-4" />
                          </button>
                          <button
                            className="text-red-600 hover:text-red-900"
                            title="Delete item"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {!loading && inventoryItems.length === 0 && (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <Package className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">No inventory items found.</p>
        </div>
      )}
    </div>
  );
};

export default Inventory;

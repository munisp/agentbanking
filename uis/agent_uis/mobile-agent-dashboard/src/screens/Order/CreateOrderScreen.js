import * as SecureStore from "expo-secure-store";
import React, { useEffect, useState } from "react";
import {
    Alert,
    FlatList,
    ScrollView,
    StyleSheet,
    TouchableOpacity,
    View,
} from "react-native";
import {
    Button,
    Card,
    Chip,
    Divider,
    IconButton,
    Modal,
    Portal,
    Searchbar,
    Snackbar,
    Text,
    TextInput, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { useAuth } from "../../contexts/AuthContext";
import { accountApi, inventoryApi, orderApi } from "../../services/apiService";
import { spacing } from "../../theme";
import { formatCurrency } from "../../utils/formatters";
export default function CreateOrderScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [stores, setStores] = useState([]);
  const [selectedStore, setSelectedStore] = useState(null);
  const [inventoryItems, setInventoryItems] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [cart, setCart] = useState([]);
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [showItemModal, setShowItemModal] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [quantity, setQuantity] = useState("1");
  const [customPrice, setCustomPrice] = useState("");
  const [snackbar, setSnackbar] = useState({ visible: false, message: "" });
  const [agentAccountNumber, setAgentAccountNumber] = useState(null);

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    if (selectedStore) {
      loadInventoryItems();
    }
  }, [selectedStore]);

  const loadInitialData = async () => {
    try {
      setLoading(true);
      const keycloakId = await SecureStore.getItemAsync("keycloakId");

      // Load stores
      const storesResponse = await inventoryApi.getStores(keycloakId);
      const storesData = storesResponse.data || storesResponse || [];
      setStores(storesData);

      if (storesData.length > 0) {
        setSelectedStore(storesData[0]);
      }

      // Load agent account
      const accountResponse =
        await accountApi.getAccountByKeycloakId(keycloakId);
      const account = accountResponse?.account || accountResponse;
      setAgentAccountNumber(account?.account_number);
    } catch (error) {
      console.error("Error loading initial data:", error);
      showSnackbar("Failed to load stores");
    } finally {
      setLoading(false);
    }
  };

  const loadInventoryItems = async () => {
    if (!selectedStore) return;

    try {
      const response = await inventoryApi.getInventoryItems(selectedStore.id);
      const items = response.items || response.data || response || [];
      // Only show items with stock
      setInventoryItems(items.filter((item) => item.quantity > 0));
    } catch (error) {
      console.error("Error loading inventory:", error);
      showSnackbar("Failed to load inventory items");
    }
  };

  const openItemModal = (item) => {
    setSelectedItem(item);
    setQuantity("1");
    setCustomPrice(item.price?.toString() || "");
    setShowItemModal(true);
  };

  const addToCart = () => {
    if (!selectedItem) return;

    const qty = parseInt(quantity, 10);
    const price = parseFloat(customPrice);

    if (isNaN(qty) || qty <= 0) {
      showSnackbar("Please enter a valid quantity");
      return;
    }

    if (isNaN(price) || price < 0) {
      showSnackbar("Please enter a valid price");
      return;
    }

    if (qty > selectedItem.quantity) {
      showSnackbar("Insufficient stock available");
      return;
    }

    const existingIndex = cart.findIndex((item) => item.id === selectedItem.id);

    if (existingIndex >= 0) {
      const updatedCart = [...cart];
      const newQty = updatedCart[existingIndex].orderQuantity + qty;

      if (newQty > selectedItem.quantity) {
        showSnackbar("Insufficient stock available");
        return;
      }

      updatedCart[existingIndex].orderQuantity = newQty;
      updatedCart[existingIndex].subtotal = newQty * price;
      setCart(updatedCart);
    } else {
      setCart([
        ...cart,
        {
          ...selectedItem,
          orderQuantity: qty,
          unitPrice: price,
          subtotal: qty * price,
        },
      ]);
    }

    setShowItemModal(false);
    showSnackbar(`${selectedItem.name} added to cart`);
  };

  const removeFromCart = (itemId) => {
    setCart(cart.filter((item) => item.id !== itemId));
    showSnackbar("Item removed from cart");
  };

  const updateCartItemQuantity = (itemId, newQty) => {
    if (newQty <= 0) {
      removeFromCart(itemId);
      return;
    }

    const updatedCart = cart.map((item) => {
      if (item.id === itemId) {
        const maxQty = inventoryItems.find((i) => i.id === itemId)?.quantity;
        const qty = Math.min(newQty, maxQty);
        return {
          ...item,
          orderQuantity: qty,
          subtotal: qty * item.unitPrice,
        };
      }
      return item;
    });

    setCart(updatedCart);
  };

  const calculateTotal = () => {
    return cart.reduce((sum, item) => sum + item.subtotal, 0);
  };

  const calculateTax = () => {
    // 7.5% VAT in Nigeria
    return calculateTotal() * 0.075;
  };

  const calculateGrandTotal = () => {
    return calculateTotal() + calculateTax();
  };

  const createOrder = async () => {
    if (cart.length === 0) {
      showSnackbar("Please add items to cart");
      return;
    }

    if (!agentAccountNumber) {
      showSnackbar("Agent account not found");
      return;
    }

    try {
      setLoading(true);

      const orderData = {
        store_id: selectedStore.id,
        store_name: selectedStore.name,
        agent_keycloak_id: await SecureStore.getItemAsync("keycloakId"),
        agent_account_number: agentAccountNumber,
        customer_name: customerName || "Walk-in Customer",
        customer_phone: customerPhone || null,
        customer_email: customerEmail || null,
        payment_method: paymentMethod,
        items: cart.map((item) => ({
          inventory_item_id: item.id,
          item_name: item.name,
          sku: item.sku,
          quantity: item.orderQuantity,
          unit_price: item.unitPrice,
          subtotal: item.subtotal,
          category: item.category,
        })),
        subtotal: calculateTotal(),
        tax: calculateTax(),
        total: calculateGrandTotal(),
        currency: "NGN",
        status: "completed",
        created_by: user?.name || "Agent",
      };

      let response;
      try {
        // Try to create order via API
        response = await orderApi.createOrder(orderData);
      } catch (apiError) {
        console.log("Orders API not available, saving locally");
        // If API endpoint doesn't exist, save locally
        const orderId = `local-${Date.now()}`;
        const localOrder = {
          id: orderId,
          ...orderData,
          order_number: `ORD-${orderId}`,
          created_at: new Date().toISOString(),
          is_local: true,
        };

        // Save to secure storage
        const existingOrders = await SecureStore.getItemAsync("agent_orders");
        const orders = existingOrders ? JSON.parse(existingOrders) : [];
        orders.push(localOrder);
        await SecureStore.setItemAsync("agent_orders", JSON.stringify(orders));

        response = { order: localOrder };
      }

      showSnackbar("Order created successfully!");

      // Clear cart and customer details
      setCart([]);
      setCustomerName("");
      setCustomerPhone("");
      setCustomerEmail("");

      // Navigate to receipt or order history
      setTimeout(() => {
        if (response?.order) {
          navigation.navigate("OrderReceipt", { order: response.order });
        } else {
          navigation.goBack();
        }
      }, 1500);
    } catch (error) {
      console.error("Error creating order:", error);
      showSnackbar("Failed to create order. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const showSnackbar = (message) => {
    setSnackbar({ visible: true, message });
  };

  const filteredItems = inventoryItems.filter((item) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      item.name?.toLowerCase().includes(query) ||
      item.sku?.toLowerCase().includes(query) ||
      item.category?.toLowerCase().includes(query)
    );
  });

  const renderInventoryItem = ({ item }) => (
    <Card style={styles.itemCard} onPress={() => openItemModal(item)}>
      <Card.Content>
        <View style={styles.itemRow}>
          <View style={styles.itemInfo}>
            <Text variant="titleMedium" style={styles.itemName}>
              {item.name}
            </Text>
            <Text variant="bodySmall" style={styles.itemSku}>
              SKU: {item.sku}
            </Text>
            <View style={styles.itemMeta}>
              {item.category && (
                <Chip
                  mode="outlined"
                  compact
                  style={styles.categoryChip}
                  textStyle={styles.chipText}
                >
                  {item.category}
                </Chip>
              )}
              <Chip
                compact
                style={[styles.stockChip, { backgroundColor: "#10B98115" }]}
                textStyle={[styles.chipText, { color: "#10B981" }]}
              >
                Stock: {item.quantity}
              </Chip>
            </View>
          </View>
          <View style={styles.itemPrice}>
            <Text variant="titleLarge" style={styles.priceText}>
              {formatCurrency(item.price || 0)}
            </Text>
          </View>
        </View>
      </Card.Content>
    </Card>
  );

  const renderCartItem = ({ item }) => (
    <Card style={styles.cartCard}>
      <Card.Content>
        <View style={styles.cartItemRow}>
          <View style={styles.cartItemInfo}>
            <Text variant="titleSmall" style={styles.cartItemName}>
              {item.name}
            </Text>
            <Text variant="bodySmall" style={styles.cartItemPrice}>
              {formatCurrency(item.unitPrice)} × {item.orderQuantity}
            </Text>
          </View>
          <View style={styles.cartItemActions}>
            <IconButton
              icon="minus"
              size={20}
              onPress={() =>
                updateCartItemQuantity(item.id, item.orderQuantity - 1)
              }
            />
            <Text variant="titleMedium">{item.orderQuantity}</Text>
            <IconButton
              icon="plus"
              size={20}
              onPress={() =>
                updateCartItemQuantity(item.id, item.orderQuantity + 1)
              }
            />
            <IconButton
              icon="delete"
              iconColor="#EF4444"
              size={20}
              onPress={() => removeFromCart(item.id)}
            />
          </View>
          <Text variant="titleMedium" style={styles.cartItemTotal}>
            {formatCurrency(item.subtotal)}
          </Text>
        </View>
      </Card.Content>
    </Card>
  );

  return (
    <View style={styles.container}>
      {/* Header with Store Selector */}
      <View style={styles.header}>
        <View style={styles.headerContent}>
          <Text variant="headlineSmall" style={styles.headerTitle}>
            Create Order
          </Text>
          {stores.length > 1 && (
            <View style={styles.storeSelector}>
              <Text variant="bodySmall">Store:</Text>
              <Chip
                mode="outlined"
                onPress={() => {
                  /* Show store picker modal */
                }}
              >
                {selectedStore?.name || "Select Store"}
              </Chip>
            </View>
          )}
        </View>
      </View>

      <ScrollView style={styles.content}>
        {/* Customer Information */}
        <Card style={styles.section}>
          <Card.Title
            title="Customer Information (Optional)"
            left={(props) => <Icon name="account" {...props} />}
          />
          <Card.Content>
            <TextInput
              label="Customer Name"
              value={customerName}
              onChangeText={setCustomerName}
              mode="outlined"
              style={styles.input}
            />
            <TextInput
              label="Phone Number"
              value={customerPhone}
              onChangeText={setCustomerPhone}
              mode="outlined"
              keyboardType="phone-pad"
              style={styles.input}
            />
            <TextInput
              label="Email (Optional)"
              value={customerEmail}
              onChangeText={setCustomerEmail}
              mode="outlined"
              keyboardType="email-address"
              style={styles.input}
            />
          </Card.Content>
        </Card>

        {/* Cart Summary */}
        {cart.length > 0 && (
          <Card style={styles.section}>
            <Card.Title
              title={`Cart (${cart.length} items)`}
              left={(props) => <Icon name="cart" {...props} />}
            />
            <Card.Content>
              <FlatList
                data={cart}
                renderItem={renderCartItem}
                keyExtractor={(item) => item.id.toString()}
                scrollEnabled={false}
              />
              <Divider style={styles.divider} />
              <View style={styles.totalsContainer}>
                <View style={styles.totalRow}>
                  <Text variant="bodyLarge">Subtotal:</Text>
                  <Text variant="bodyLarge">
                    {formatCurrency(calculateTotal())}
                  </Text>
                </View>
                <View style={styles.totalRow}>
                  <Text variant="bodyMedium">Tax (7.5%):</Text>
                  <Text variant="bodyMedium">
                    {formatCurrency(calculateTax())}
                  </Text>
                </View>
                <Divider style={styles.divider} />
                <View style={styles.totalRow}>
                  <Text variant="titleLarge" style={styles.grandTotal}>
                    Total:
                  </Text>
                  <Text variant="titleLarge" style={styles.grandTotal}>
                    {formatCurrency(calculateGrandTotal())}
                  </Text>
                </View>
              </View>
            </Card.Content>
          </Card>
        )}

        {/* Payment Method */}
        <Card style={styles.section}>
          <Card.Title
            title="Payment Method"
            left={(props) => <Icon name="cash" {...props} />}
          />
          <Card.Content>
            <View style={styles.paymentMethods}>
              <Chip
                selected={paymentMethod === "cash"}
                onPress={() => setPaymentMethod("cash")}
                style={styles.paymentChip}
              >
                Cash
              </Chip>
              <Chip
                selected={paymentMethod === "transfer"}
                onPress={() => setPaymentMethod("transfer")}
                style={styles.paymentChip}
              >
                Transfer
              </Chip>
              <Chip
                selected={paymentMethod === "pos"}
                onPress={() => setPaymentMethod("pos")}
                style={styles.paymentChip}
              >
                POS
              </Chip>
            </View>
          </Card.Content>
        </Card>

        {/* Add Items Section */}
        <Card style={styles.section}>
          <Card.Title
            title="Add Items"
            left={(props) => <Icon name="package-variant" {...props} />}
          />
          <Card.Content>
            <Searchbar
              placeholder="Search items..."
              onChangeText={setSearchQuery}
              value={searchQuery}
              style={styles.searchBar}
            />
            <FlatList
              data={filteredItems}
              renderItem={renderInventoryItem}
              keyExtractor={(item) => item.id.toString()}
              scrollEnabled={false}
              ListEmptyComponent={
                <Text style={styles.emptyText}>No items available</Text>
              }
            />
          </Card.Content>
        </Card>
      </ScrollView>

      {/* Bottom Action Button */}
      <View style={styles.bottomBar}>
        <Button
          mode="contained"
          onPress={createOrder}
          loading={loading}
          disabled={loading || cart.length === 0}
          style={styles.createButton}
          contentStyle={styles.createButtonContent}
        >
          Create Order - {formatCurrency(calculateGrandTotal())}
        </Button>
      </View>

      {/* Add Item Modal */}
      <Portal>
        <Modal
          visible={showItemModal}
          onDismiss={() => setShowItemModal(false)}
          contentContainerStyle={styles.modalContainer}
        >
          <Card>
            <Card.Title title="Add to Cart" />
            <Card.Content>
              {selectedItem && (
                <>
                  <Text variant="titleMedium" style={styles.modalItemName}>
                    {selectedItem.name}
                  </Text>
                  <Text variant="bodySmall" style={styles.modalItemStock}>
                    Available Stock: {selectedItem.quantity}
                  </Text>
                  <TextInput
                    label="Quantity"
                    value={quantity}
                    onChangeText={setQuantity}
                    mode="outlined"
                    keyboardType="numeric"
                    style={styles.modalInput}
                  />
                  <TextInput
                    label="Unit Price (₦)"
                    value={customPrice}
                    onChangeText={setCustomPrice}
                    mode="outlined"
                    keyboardType="numeric"
                    style={styles.modalInput}
                  />
                  <Text variant="titleMedium" style={styles.modalSubtotal}>
                    Subtotal:{" "}
                    {formatCurrency(
                      (parseFloat(quantity) || 0) *
                        (parseFloat(customPrice) || 0),
                    )}
                  </Text>
                </>
              )}
            </Card.Content>
            <Card.Actions>
              <Button onPress={() => setShowItemModal(false)}>Cancel</Button>
              <Button mode="contained" onPress={addToCart}>
                Add to Cart
              </Button>
            </Card.Actions>
          </Card>
        </Modal>
      </Portal>

      {/* Snackbar */}
      <Snackbar
        visible={snackbar.visible}
        onDismiss={() => setSnackbar({ visible: false, message: "" })}
        duration={3000}
      >
        {snackbar.message}
      </Snackbar>
    </View>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F3F4F6",
  },
  header: {
    backgroundColor: colors.primary,
    paddingTop: spacing.xl,
    paddingBottom: spacing.lg,
  },
  headerContent: {
    paddingHorizontal: spacing.lg,
  },
  headerTitle: {
    color: "#fff",
    fontWeight: "700",
    marginBottom: spacing.sm,
  },
  storeSelector: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  content: {
    flex: 1,
  },
  section: {
    margin: spacing.lg,
    marginBottom: 0,
  },
  input: {
    marginBottom: spacing.md,
  },
  searchBar: {
    marginBottom: spacing.md,
  },
  itemCard: {
    marginBottom: spacing.sm,
  },
  itemRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  itemInfo: {
    flex: 1,
  },
  itemName: {
    fontWeight: "600",
    marginBottom: spacing.xs,
  },
  itemSku: {
    color: "#6B7280",
    marginBottom: spacing.xs,
  },
  itemMeta: {
    flexDirection: "row",
    gap: spacing.xs,
  },
  categoryChip: {
    height: 24,
  },
  stockChip: {
    height: 24,
  },
  chipText: {
    fontSize: 11,
  },
  itemPrice: {
    marginLeft: spacing.md,
  },
  priceText: {
    color: colors.primary,
    fontWeight: "700",
  },
  cartCard: {
    marginBottom: spacing.sm,
  },
  cartItemRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  cartItemInfo: {
    flex: 1,
  },
  cartItemName: {
    fontWeight: "600",
  },
  cartItemPrice: {
    color: "#6B7280",
  },
  cartItemActions: {
    flexDirection: "row",
    alignItems: "center",
  },
  cartItemTotal: {
    fontWeight: "700",
    marginLeft: spacing.md,
  },
  divider: {
    marginVertical: spacing.md,
  },
  totalsContainer: {
    paddingTop: spacing.sm,
  },
  totalRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: spacing.sm,
  },
  grandTotal: {
    fontWeight: "700",
    color: colors.primary,
  },
  paymentMethods: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  paymentChip: {
    flex: 1,
  },
  emptyText: {
    textAlign: "center",
    color: "#6B7280",
    marginTop: spacing.lg,
  },
  bottomBar: {
    padding: spacing.lg,
    backgroundColor: "#fff",
    borderTopWidth: 1,
    borderTopColor: "#E5E7EB",
  },
  createButton: {
    borderRadius: 12,
  },
  createButtonContent: {
    paddingVertical: spacing.sm,
  },
  modalContainer: {
    backgroundColor: "white",
    padding: spacing.lg,
    margin: spacing.lg,
    borderRadius: 12,
  },
  modalItemName: {
    fontWeight: "600",
    marginBottom: spacing.xs,
  },
  modalItemStock: {
    color: "#10B981",
    marginBottom: spacing.lg,
  },
  modalInput: {
    marginBottom: spacing.md,
  },
  modalSubtotal: {
    marginTop: spacing.md,
    color: colors.primary,
    fontWeight: "700",
  },
});

import * as SecureStore from "expo-secure-store";
import React, { useEffect, useState } from "react";
import {
    ActivityIndicator,
    FlatList,
    RefreshControl,
    ScrollView,
    StyleSheet,
    View,
} from "react-native";
import { Card, Chip, FAB, Searchbar, Snackbar, Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { inventoryApi } from "../../services/apiService";
import { spacing } from "../../theme";
export default function InventoryScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [searchQuery, setSearchQuery] = useState("");
  const [stores, setStores] = useState([]);
  const [selectedStore, setSelectedStore] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchStores();
  }, []);

  useEffect(() => {
    if (selectedStore) {
      fetchInventoryItems();
    }
  }, [selectedStore]);

  const fetchStores = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      const response = await inventoryApi.getStores(keycloakId);
      const storesData = response.data || response || [];
      setStores(storesData);

      if (storesData.length > 0 && !selectedStore) {
        setSelectedStore(storesData[0]);
      }
    } catch (err) {
      console.error("Stores fetch error:", err);
      setError(err.message || "Failed to load stores");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const fetchInventoryItems = async () => {
    if (!selectedStore) return;

    try {
      const response = await inventoryApi.getInventoryItems(selectedStore.id);
      setItems(response.items || response.data || response || []);
    } catch (err) {
      console.error("Inventory items fetch error:", err);
      setError(err.message || "Failed to load inventory items");
    }
  };

  const onRefresh = () => {
    fetchStores(true);
  };

  const filteredItems = items.filter((item) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      item.name?.toLowerCase().includes(query) ||
      item.sku?.toLowerCase().includes(query) ||
      item.category?.toLowerCase().includes(query)
    );
  });

  const getStockStatusColor = (quantity, reorderLevel) => {
    if (quantity === 0) return "#EF4444";
    if (quantity <= reorderLevel) return "#F59E0B";
    return "#10B981";
  };

  const renderInventoryItem = ({ item }) => (
    <Card
      style={styles.itemCard}
      onPress={() => navigation.navigate("InventoryItemDetails", { item })}
    >
      <Card.Content>
        <View style={styles.itemHeader}>
          <View style={styles.itemInfo}>
            <Text variant="titleMedium" style={styles.itemName}>
              {item.name}
            </Text>
            {item.sku && (
              <Text variant="bodySmall" style={styles.itemSku}>
                SKU: {item.sku}
              </Text>
            )}
          </View>
          <Text variant="titleLarge" style={styles.itemQuantity}>
            {item.quantity}
          </Text>
        </View>

        <View style={styles.itemDetails}>
          <View style={styles.detailRow}>
            <Icon name="currency-ngn" size={16} color="#6B7280" />
            <Text variant="bodySmall" style={styles.detailLabel}>
              Price:
            </Text>
            <Text variant="bodyMedium" style={styles.detailValue}>
              ₦{parseFloat(item.unit_price || 0).toLocaleString()}
            </Text>
          </View>

          {item.category && (
            <Chip mode="flat" style={styles.categoryChip}>
              {item.category}
            </Chip>
          )}

          <View
            style={[
              styles.stockStatus,
              {
                backgroundColor:
                  getStockStatusColor(item.quantity, item.reorder_level || 10) +
                  "20",
              },
            ]}
          >
            <Text
              style={{
                color: getStockStatusColor(
                  item.quantity,
                  item.reorder_level || 10,
                ),
                fontSize: 11,
              }}
            >
              {item.quantity === 0
                ? "Out of Stock"
                : item.quantity <= (item.reorder_level || 10)
                  ? "Low Stock"
                  : "In Stock"}
            </Text>
          </View>
        </View>
      </Card.Content>
    </Card>
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Store Selector */}
      <View style={styles.storeSelector}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          {stores.map((store) => (
            <Chip
              key={store.id}
              selected={selectedStore?.id === store.id}
              onPress={() => setSelectedStore(store)}
              style={styles.storeChip}
            >
              {store.name}
            </Chip>
          ))}
        </ScrollView>
      </View>

      {/* Search Bar */}
      <View style={styles.searchContainer}>
        <Searchbar
          placeholder="Search inventory..."
          onChangeText={setSearchQuery}
          value={searchQuery}
          style={styles.searchBar}
        />
      </View>

      {/* Inventory List */}
      <FlatList
        data={filteredItems}
        renderItem={renderInventoryItem}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon name="package-variant" size={64} color="#D1D5DB" />
            <Text variant="bodyLarge" style={styles.emptyText}>
              No inventory items found
            </Text>
            <Text variant="bodySmall" style={styles.emptySubtext}>
              Add items to start managing your inventory
            </Text>
          </View>
        }
      />

      <FAB
        icon="plus"
        label="Add Item"
        style={styles.fab}
        onPress={() =>
          navigation.navigate("AddInventoryItem", {
            storeId: selectedStore?.id,
          })
        }
      />

      <Snackbar
        visible={!!error}
        onDismiss={() => setError("")}
        duration={3000}
      >
        {error}
      </Snackbar>
    </View>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F9FAFB",
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  storeSelector: {
    backgroundColor: "#fff",
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#E5E7EB",
  },
  storeChip: {
    marginRight: spacing.sm,
  },
  searchContainer: {
    backgroundColor: "#fff",
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#E5E7EB",
  },
  searchBar: {
    elevation: 0,
    backgroundColor: "#F3F4F6",
  },
  listContent: {
    padding: spacing.md,
  },
  itemCard: {
    marginBottom: spacing.md,
  },
  itemHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: spacing.sm,
  },
  itemInfo: {
    flex: 1,
  },
  itemName: {
    fontWeight: "600",
  },
  itemSku: {
    color: "#6B7280",
    marginTop: 2,
  },
  itemQuantity: {
    fontWeight: "bold",
    color: colors.primary,
  },
  itemDetails: {
    gap: spacing.sm,
  },
  detailRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  detailLabel: {
    color: "#6B7280",
  },
  detailValue: {
    fontWeight: "500",
  },
  categoryChip: {
    alignSelf: "flex-start",
  },
  stockStatus: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: 4,
    alignSelf: "flex-start",
  },
  emptyContainer: {
    padding: spacing.xl,
    alignItems: "center",
    marginTop: spacing.xxl,
  },
  emptyText: {
    marginTop: spacing.md,
    fontWeight: "600",
  },
  emptySubtext: {
    color: "#6B7280",
    marginTop: spacing.xs,
    textAlign: "center",
  },
  fab: {
    position: "absolute",
    margin: spacing.md,
    right: 0,
    bottom: 0,
  },
});

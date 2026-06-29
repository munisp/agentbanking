import * as SecureStore from "expo-secure-store";
import React, { useEffect, useState } from "react";
import {
    ActivityIndicator,
    FlatList,
    Linking,
    RefreshControl,
    StyleSheet,
    View,
} from "react-native";
import {
    Button,
    Card,
    Chip,
    Searchbar,
    Snackbar,
    Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { agentApi, inventoryApi } from "../../services/apiService";
import { spacing } from "../../theme";
export default function StoreMapScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [searchQuery, setSearchQuery] = useState("");
  const [stores, setStores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchStores();
  }, []);

  const getStoreTypeLabel = (type) => {
    const labels = {
      AGENT: "Agent",
      MERCHANT: "Merchant",
      SUPER_AGENT: "Super Agent",
      AGGREGATOR: "Aggregator",
      POS_TERMINAL: "POS Terminal",
      ATM: "ATM",
      BANK_BRANCH: "Bank Branch",
    };
    return labels[type] || type;
  };

  const getStatusColor = (status) => {
    switch (status) {
      case "OPEN":
        return "#10B98120";
      case "CLOSED":
        return "#EF444420";
      case "TEMPORARILY_CLOSED":
        return "#F59E0B20";
      case "SUSPENDED":
        return "#6B728020";
      default:
        return "#6B728020";
    }
  };

  const getStatusTextColor = (status) => {
    switch (status) {
      case "OPEN":
        return "#10B981";
      case "CLOSED":
        return "#EF4444";
      case "TEMPORARILY_CLOSED":
        return "#F59E0B";
      case "SUSPENDED":
        return "#6B7280";
      default:
        return "#6B7280";
    }
  };

  const fetchStores = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      const combined = [];

      // Fetch inventory stores
      try {
        const invRes = await inventoryApi.getStores(keycloakId);
        const invStores = Array.isArray(invRes) ? invRes : invRes?.data || invRes?.stores || [];
        invStores.forEach((s) =>
          combined.push({
            id: s.id,
            entity_name: s.name || s.store_name || s.entity_name,
            store_type: s.store_type || "AGENT",
            status: s.status || "OPEN",
            address: s.address || s.location,
            city: s.city,
            state: s.state,
            phone: s.phone || s.contact_phone,
            latitude: s.latitude,
            longitude: s.longitude,
          })
        );
      } catch (e) {
        console.log("Inventory stores unavailable:", e.message);
      }

      // Fetch agent businesses as additional storefronts
      try {
        const bizRes = await agentApi.getAgentBusinesses(keycloakId);
        const businesses = Array.isArray(bizRes) ? bizRes : bizRes?.data || bizRes?.businesses || [];
        businesses.forEach((b) =>
          combined.push({
            id: b.id,
            entity_name: b.business_name || b.name,
            store_type: b.business_type || "MERCHANT",
            status: b.status || "OPEN",
            address: b.address || b.business_address,
            city: b.city,
            state: b.state,
            phone: b.phone || b.business_phone,
            latitude: b.latitude,
            longitude: b.longitude,
          })
        );
      } catch (e) {
        console.log("Agent businesses unavailable:", e.message);
      }

      setStores(combined);
    } catch (err) {
      console.error("Stores fetch error:", err);
      setError(err.message || "Failed to load stores");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    fetchStores(true);
  };

  const filteredStores = stores.filter((store) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      store.entity_name?.toLowerCase().includes(query) ||
      store.address?.toLowerCase().includes(query) ||
      store.city?.toLowerCase().includes(query)
    );
  });

  const openMap = async (store) => {
    if (store.latitude && store.longitude) {
      const lat = parseFloat(store.latitude);
      const lng = parseFloat(store.longitude);
      const label = encodeURIComponent(store.entity_name || "Store");

      // Try different map URLs for better compatibility
      const urls = [
        `geo:${lat},${lng}?q=${lat},${lng}(${label})`, // Android native
        `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`, // Fallback
        `https://maps.google.com/?q=${lat},${lng}`, // Legacy fallback
      ];

      for (const url of urls) {
        try {
          const canOpen = await Linking.canOpenURL(url);
          if (canOpen) {
            await Linking.openURL(url);
            return;
          }
        } catch (err) {
          console.warn(`Failed to open ${url}:`, err);
        }
      }

      console.error("No suitable map app found");
    }
  };

  const calculateDistance = (lat1, lon1, lat2, lon2) => {
    // Haversine formula for calculating distance
    const R = 6371; // Earth's radius in km
    const dLat = ((lat2 - lat1) * Math.PI) / 180;
    const dLon = ((lon2 - lon1) * Math.PI) / 180;
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos((lat1 * Math.PI) / 180) *
        Math.cos((lat2 * Math.PI) / 180) *
        Math.sin(dLon / 2) *
        Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  };

  const renderStoreCard = ({ item }) => (
    <Card style={styles.storeCard}>
      <Card.Content>
        <View style={styles.storeHeader}>
          <View style={styles.iconContainer}>
            <Icon name="store" size={32} color={colors.primary} />
          </View>
          <View style={styles.storeInfo}>
            <Text variant="titleMedium" style={styles.storeName}>
              {item.entity_name}
            </Text>
            {item.store_type && (
              <Text variant="bodySmall" style={styles.storeType}>
                {getStoreTypeLabel(item.store_type)}
              </Text>
            )}
          </View>
          {item.status && (
            <Chip
              mode="flat"
              style={[
                styles.statusChip,
                {
                  backgroundColor: getStatusColor(item.status),
                },
              ]}
              textStyle={{
                color: getStatusTextColor(item.status),
                fontSize: 11,
              }}
            >
              {item.status}
            </Chip>
          )}
        </View>

        {item.address && (
          <View style={styles.addressSection}>
            <Icon name="map-marker" size={16} color="#6B7280" />
            <Text variant="bodySmall" style={styles.address}>
              {item.address}
              {item.city && `, ${item.city}`}
              {item.state && `, ${item.state}`}
            </Text>
          </View>
        )}

        {item.phone && (
          <View style={styles.contactSection}>
            <Icon name="phone" size={16} color="#6B7280" />
            <Text variant="bodySmall" style={styles.contact}>
              {item.phone}
            </Text>
          </View>
        )}

        <View style={styles.actionButtons}>
          {item.latitude && item.longitude && (
            <Button
              mode="contained"
              onPress={() => openMap(item)}
              icon="map-marker"
              style={styles.mapButton}
            >
              View on Map
            </Button>
          )}
          {item.phone && (
            <Button
              mode="outlined"
              onPress={() => Linking.openURL(`tel:${item.phone}`)}
              icon="phone"
              style={styles.callButton}
            >
              Call
            </Button>
          )}
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
      <View style={styles.searchContainer}>
        <Searchbar
          placeholder="Search stores..."
          onChangeText={setSearchQuery}
          value={searchQuery}
          style={styles.searchBar}
        />
      </View>

      <FlatList
        data={filteredStores}
        renderItem={renderStoreCard}
        keyExtractor={(item) => item.id || item.store_id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon name="store-outline" size={64} color="#D1D5DB" />
            <Text variant="bodyLarge" style={styles.emptyText}>
              No stores found
            </Text>
            <Text variant="bodySmall" style={styles.emptySubtext}>
              No stores or businesses linked to your account
            </Text>
          </View>
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
  storeCard: {
    marginBottom: spacing.md,
  },
  storeHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  iconContainer: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: "#EFF6FF",
    justifyContent: "center",
    alignItems: "center",
    marginRight: spacing.sm,
  },
  storeInfo: {
    flex: 1,
  },
  storeName: {
    fontWeight: "600",
  },
  storeType: {
    color: "#6B7280",
    marginTop: 2,
  },
  statusChip: {
    height: 28,
  },
  addressSection: {
    flexDirection: "row",
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  address: {
    flex: 1,
    color: "#374151",
  },
  contactSection: {
    flexDirection: "row",
    gap: spacing.xs,
    marginBottom: spacing.md,
  },
  contact: {
    color: "#374151",
  },
  actionButtons: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  mapButton: {
    flex: 1,
  },
  callButton: {
    flex: 1,
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

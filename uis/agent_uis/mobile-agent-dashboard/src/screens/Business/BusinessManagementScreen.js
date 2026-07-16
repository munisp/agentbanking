import * as SecureStore from "expo-secure-store";
import React, { useEffect, useState } from "react";
import {
    ActivityIndicator,
    FlatList,
    RefreshControl,
    StyleSheet,
    View,
} from "react-native";
import {
    Button,
    Card,
    Chip,
    FAB,
    Searchbar,
    Snackbar,
    Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { inventoryApi } from "../../services/apiService";
import { spacing } from "../../theme";
export default function BusinessManagementScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [searchQuery, setSearchQuery] = useState("");
  const [businesses, setBusinesses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchBusinesses();
  }, []);

  const fetchBusinesses = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      if (!keycloakId) {
        throw new Error("Keycloak ID not found. Please log in again.");
      }
      const response = await inventoryApi.getStores(keycloakId);
      setBusinesses(response || []);
    } catch (err) {
      console.error("Businesses fetch error:", err);
      setError(err.message || "Failed to load businesses");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    fetchBusinesses(true);
  };

  const filteredBusinesses = businesses.filter((business) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      business.name?.toLowerCase().includes(query) ||
      business.description?.toLowerCase().includes(query) ||
      business.account_number?.toLowerCase().includes(query)
    );
  });

  const getBusinessIcon = (description) => {
    const descLower = description?.toLowerCase() || "";
    if (descLower.includes("retail")) return "store";
    if (descLower.includes("restaurant") || descLower.includes("food"))
      return "food";
    if (descLower.includes("service")) return "account-tie";
    if (descLower.includes("agriculture")) return "sprout";
    if (descLower.includes("transport")) return "truck";
    return "store";
  };

  const renderBusinessCard = ({ item }) => (
    <Card style={styles.businessCard}>
      <Card.Content>
        <View style={styles.businessHeader}>
          <View style={styles.businessIcon}>
            <Icon
              name={getBusinessIcon(item.description)}
              size={24}
              color={colors.primary}
            />
          </View>
          <View style={styles.businessInfo}>
            <Text variant="titleMedium" style={styles.businessName}>
              {item.name}
            </Text>
            <Text variant="bodySmall" style={styles.businessType}>
              {item.description || "Store"}
            </Text>
          </View>
          {item.account_number && (
            <Chip
              mode="flat"
              style={[styles.statusChip, { backgroundColor: "#10B98120" }]}
              textStyle={{
                color: "#10B981",
                fontSize: 11,
              }}
            >
              Active
            </Chip>
          )}
        </View>

        <View style={styles.businessDetails}>
          {item.account_number && (
            <View style={styles.detailRow}>
              <Icon name="bank" size={14} color="#6B7280" />
              <Text variant="bodySmall" style={styles.detailText}>
                Account: {item.account_number}
              </Text>
            </View>
          )}
          {item.created_at && (
            <View style={styles.detailRow}>
              <Icon name="calendar" size={14} color="#6B7280" />
              <Text variant="bodySmall" style={styles.detailText}>
                Created: {new Date(item.created_at).toLocaleDateString()}
              </Text>
            </View>
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
          placeholder="Search businesses..."
          onChangeText={setSearchQuery}
          value={searchQuery}
          style={styles.searchBar}
        />
      </View>

      <FlatList
        data={filteredBusinesses}
        renderItem={renderBusinessCard}
        keyExtractor={(item) => item.id || item.business_id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon name="briefcase-outline" size={64} color="#D1D5DB" />
            <Text variant="bodyLarge" style={styles.emptyText}>
              No businesses found
            </Text>
            <Text variant="bodySmall" style={styles.emptySubtext}>
              Start by adding your first business
            </Text>
            <Button
              mode="contained"
              onPress={() =>
                setError(
                  "Please use the web dashboard to register new businesses",
                )
              }
              style={styles.emptyButton}
              icon="plus"
            >
              Add Business
            </Button>
          </View>
        }
      />

      {businesses.length > 0 && (
        <FAB
          icon="plus"
          label="Add Business"
          style={styles.fab}
          onPress={() =>
            setError("Please use the web dashboard to register new businesses")
          }
        />
      )}

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
  businessCard: {
    marginBottom: spacing.md,
  },
  businessHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  businessIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#EFF6FF",
    justifyContent: "center",
    alignItems: "center",
    marginRight: spacing.sm,
  },
  businessInfo: {
    flex: 1,
  },
  businessName: {
    fontWeight: "600",
  },
  businessType: {
    color: "#6B7280",
    marginTop: 2,
  },
  statusChip: {
    height: 28,
  },
  businessDetails: {
    gap: spacing.xs,
  },
  detailRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  detailText: {
    color: "#374151",
    flex: 1,
  },
  accountsSection: {
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: "#E5E7EB",
  },
  accountsLabel: {
    color: colors.primary,
    fontWeight: "500",
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
    marginBottom: spacing.lg,
    textAlign: "center",
  },
  emptyButton: {
    marginTop: spacing.md,
  },
  fab: {
    position: "absolute",
    margin: spacing.md,
    right: 0,
    bottom: 0,
  },
});

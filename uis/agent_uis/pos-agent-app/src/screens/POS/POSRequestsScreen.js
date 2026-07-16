import * as SecureStore from "expo-secure-store";
import React, { useEffect, useState } from "react";
import {
    ActivityIndicator,
    FlatList,
    RefreshControl,
    StyleSheet,
    View,
} from "react-native";
import { Card, Chip, FAB, Searchbar, Snackbar, Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { posRequestApi } from "../../services/apiService";
import { spacing } from "../../theme";
export default function POSRequestsScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [searchQuery, setSearchQuery] = useState("");
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchRequests();
  }, []);

  const fetchRequests = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      const response = await posRequestApi.getRequests(keycloakId);
      setRequests(response.requests || response.data || response || []);
    } catch (err) {
      console.error("POS requests fetch error:", err);
      setError(err.message || "Failed to load POS requests");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    fetchRequests(true);
  };

  const filteredRequests = requests.filter((request) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      request.request_id?.toLowerCase().includes(query) ||
      request.terminal_model?.toLowerCase().includes(query) ||
      request.status?.toLowerCase().includes(query)
    );
  });

  const getStatusColor = (status) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === "approved" || statusLower === "delivered")
      return "#10B981";
    if (statusLower === "rejected" || statusLower === "cancelled")
      return "#EF4444";
    if (statusLower === "pending") return "#F59E0B";
    if (statusLower === "processing" || statusLower === "in_transit")
      return colors.primary;
    return "#6B7280";
  };

  const getRequestIcon = (status) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === "delivered") return "check-circle";
    if (statusLower === "rejected" || statusLower === "cancelled")
      return "close-circle";
    if (statusLower === "in_transit") return "truck-delivery";
    if (statusLower === "processing") return "progress-clock";
    return "file-document";
  };

  const renderRequestCard = ({ item }) => (
    <Card
      style={styles.requestCard}
      onPress={() =>
        navigation.navigate("POSRequestDetails", { request: item })
      }
    >
      <Card.Content>
        <View style={styles.requestHeader}>
          <View style={styles.iconContainer}>
            <Icon
              name={getRequestIcon(item.status)}
              size={32}
              color={getStatusColor(item.status)}
            />
          </View>
          <View style={styles.requestInfo}>
            <Text variant="titleMedium" style={styles.requestId}>
              {item.request_id}
            </Text>
            <Text variant="bodySmall" style={styles.requestModel}>
              {item.terminal_model || "POS Terminal"}
            </Text>
          </View>
          <Chip
            mode="flat"
            style={[
              styles.statusChip,
              { backgroundColor: getStatusColor(item.status) + "20" },
            ]}
            textStyle={{ color: getStatusColor(item.status), fontSize: 11 }}
          >
            {item.status}
          </Chip>
        </View>

        <View style={styles.requestDetails}>
          <View style={styles.detailRow}>
            <Icon name="calendar" size={16} color="#6B7280" />
            <Text variant="bodySmall" style={styles.detailText}>
              Requested:{" "}
              {new Date(
                item.created_at || item.request_date,
              ).toLocaleDateString()}
            </Text>
          </View>

          {item.quantity && (
            <View style={styles.detailRow}>
              <Icon name="counter" size={16} color="#6B7280" />
              <Text variant="bodySmall" style={styles.detailText}>
                Quantity: {item.quantity}
              </Text>
            </View>
          )}

          {item.delivery_address && (
            <View style={styles.detailRow}>
              <Icon name="map-marker" size={16} color="#6B7280" />
              <Text
                variant="bodySmall"
                style={styles.detailText}
                numberOfLines={1}
              >
                {item.delivery_address}
              </Text>
            </View>
          )}

          {item.expected_delivery_date && (
            <View style={styles.detailRow}>
              <Icon name="truck-delivery" size={16} color="#6B7280" />
              <Text variant="bodySmall" style={styles.detailText}>
                Expected:{" "}
                {new Date(item.expected_delivery_date).toLocaleDateString()}
              </Text>
            </View>
          )}
        </View>

        {item.notes && (
          <Text variant="bodySmall" style={styles.notes} numberOfLines={2}>
            Notes: {item.notes}
          </Text>
        )}
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
          placeholder="Search POS requests..."
          onChangeText={setSearchQuery}
          value={searchQuery}
          style={styles.searchBar}
        />
      </View>

      <FlatList
        data={filteredRequests}
        renderItem={renderRequestCard}
        keyExtractor={(item) => item.request_id || item.id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon name="file-document-outline" size={64} color="#D1D5DB" />
            <Text variant="bodyLarge" style={styles.emptyText}>
              No POS requests found
            </Text>
            <Text variant="bodySmall" style={styles.emptySubtext}>
              Request a new POS terminal to get started
            </Text>
          </View>
        }
      />

      <FAB
        icon="plus"
        label="New Request"
        style={styles.fab}
        onPress={() => navigation.navigate("POSOrder")}
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
  requestCard: {
    marginBottom: spacing.md,
  },
  requestHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  iconContainer: {
    marginRight: spacing.sm,
  },
  requestInfo: {
    flex: 1,
  },
  requestId: {
    fontWeight: "600",
  },
  requestModel: {
    color: "#6B7280",
    marginTop: 2,
  },
  statusChip: {
    height: 28,
  },
  requestDetails: {
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
  notes: {
    color: "#6B7280",
    marginTop: spacing.sm,
    fontStyle: "italic",
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

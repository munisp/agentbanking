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
    Badge,
    Card,
    Chip,
    FAB,
    Searchbar,
    Snackbar,
    Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { messagingApi } from "../../services/apiService";
import { spacing } from "../../theme";
export default function CommunicationScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [searchQuery, setSearchQuery] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchMessages();
  }, []);

  const fetchMessages = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      const response = await messagingApi.getMessages(keycloakId, {
        page: 1,
        limit: 50,
      });
      setMessages(response.messages || response.data || response || []);
    } catch (err) {
      const errorMsg =
        err?.message ||
        (typeof err === "string" ? err : JSON.stringify(err)) ||
        "Failed to load messages";
      console.error("Messages fetch error:", errorMsg);
      setError(errorMsg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    fetchMessages(true);
  };

  const filteredMessages = messages.filter((message) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      message.subject?.toLowerCase().includes(query) ||
      message.message?.toLowerCase().includes(query) ||
      message.from?.toLowerCase().includes(query)
    );
  });

  const unreadCount = messages.filter((m) => !m.read).length;

  const getPriorityColor = (priority) => {
    const priorityLower = priority?.toLowerCase();
    if (priorityLower === "high" || priorityLower === "urgent")
      return "#EF4444";
    if (priorityLower === "medium") return "#F59E0B";
    return "#6B7280";
  };

  const getCategoryIcon = (category) => {
    const categoryLower = category?.toLowerCase();
    if (categoryLower?.includes("transaction")) return "bank-transfer";
    if (categoryLower?.includes("alert")) return "alert";
    if (categoryLower?.includes("notification")) return "bell";
    if (categoryLower?.includes("announcement")) return "bullhorn";
    return "email";
  };

  const renderMessageCard = ({ item }) => (
    <Card
      style={[styles.messageCard, !item.read && styles.unreadCard]}
      onPress={() => navigation.navigate("MessageDetails", { message: item })}
    >
      <Card.Content>
        <View style={styles.messageHeader}>
          <View style={styles.iconContainer}>
            <Icon
              name={getCategoryIcon(item.category)}
              size={24}
              color={!item.read ? colors.primary : "#6B7280"}
            />
          </View>
          <View style={styles.messageInfo}>
            <View style={styles.subjectRow}>
              <Text
                variant="titleSmall"
                style={[styles.messageSubject, !item.read && styles.unreadText]}
              >
                {item.subject || "No Subject"}
              </Text>
              {!item.read && <Badge size={8} style={styles.unreadBadge} />}
            </View>
            <Text variant="bodySmall" style={styles.messageFrom}>
              From: {item.from || "System"}
            </Text>
            <Text
              variant="bodySmall"
              style={styles.messagePreview}
              numberOfLines={2}
            >
              {item.message || item.body || ""}
            </Text>
          </View>
        </View>

        <View style={styles.messageFooter}>
          <Text variant="bodySmall" style={styles.messageDate}>
            {new Date(item.created_at || item.timestamp).toLocaleString()}
          </Text>
          {item.priority && item.priority.toLowerCase() !== "low" && (
            <Chip
              mode="flat"
              style={[
                styles.priorityChip,
                { backgroundColor: getPriorityColor(item.priority) + "20" },
              ]}
              textStyle={{
                color: getPriorityColor(item.priority),
                fontSize: 11,
              }}
              icon="flag"
            >
              {item.priority}
            </Chip>
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
      {/* Header with unread count */}
      {unreadCount > 0 && (
        <View style={styles.unreadHeader}>
          <Icon name="email-outline" size={20} color={colors.primary} />
          <Text variant="bodyMedium" style={styles.unreadHeaderText}>
            You have {unreadCount} unread message{unreadCount !== 1 ? "s" : ""}
          </Text>
        </View>
      )}

      {/* Search Bar */}
      <View style={styles.searchContainer}>
        <Searchbar
          placeholder="Search messages..."
          onChangeText={setSearchQuery}
          value={searchQuery}
          style={styles.searchBar}
        />
      </View>

      {/* Messages List */}
      <FlatList
        data={filteredMessages}
        renderItem={renderMessageCard}
        keyExtractor={(item) => item.id || item.message_id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon name="email-outline" size={64} color="#D1D5DB" />
            <Text variant="bodyLarge" style={styles.emptyText}>
              No messages found
            </Text>
            <Text variant="bodySmall" style={styles.emptySubtext}>
              Your messages and notifications will appear here
            </Text>
          </View>
        }
      />

      <FAB
        icon="email-edit"
        label="New Message"
        style={styles.fab}
        onPress={() => navigation.navigate("ComposeMessage")}
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
  unreadHeader: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#EFF6FF",
    padding: spacing.md,
    gap: spacing.sm,
  },
  unreadHeaderText: {
    color: colors.primary,
    fontWeight: "500",
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
  messageCard: {
    marginBottom: spacing.md,
  },
  unreadCard: {
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
  },
  messageHeader: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  iconContainer: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#F3F4F6",
    justifyContent: "center",
    alignItems: "center",
  },
  messageInfo: {
    flex: 1,
  },
  subjectRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  messageSubject: {
    fontWeight: "500",
  },
  unreadText: {
    fontWeight: "700",
    color: "#1F2937",
  },
  unreadBadge: {
    backgroundColor: colors.primary,
  },
  messageFrom: {
    color: "#6B7280",
    marginTop: 2,
  },
  messagePreview: {
    color: "#374151",
    marginTop: spacing.xs,
  },
  messageFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  messageDate: {
    color: "#9CA3AF",
  },
  priorityChip: {
    height: 24,
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

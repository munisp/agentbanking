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
    Card,
    Chip,
    Searchbar,
    SegmentedButtons,
    Snackbar,
    Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { agentApi } from "../../services/apiService";
import { spacing } from "../../theme";
export default function AgentHierarchyScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [hierarchy, setHierarchy] = useState(null);
  const [subAgents, setSubAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchHierarchy();
  }, []);

  const fetchHierarchy = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      const agentId = await SecureStore.getItemAsync("agentId");

      // Fetch agent's hierarchy/profile
      try {
        const profile = await agentApi.getAgent(keycloakId);
        setHierarchy(profile);
      } catch (err) {
        console.log("Hierarchy fetch error:", err.message);
      }

      // Fetch agents invited by current user (agent hierarchy)
      try {
        const invitedAgentsResponse = await agentApi.getInvitedAgents();
        const invitedAgents = Array.isArray(invitedAgentsResponse)
          ? invitedAgentsResponse
          : invitedAgentsResponse?.agents || invitedAgentsResponse?.data || [];
        setSubAgents(invitedAgents);
      } catch (err) {
        console.log("Invited agents fetch error:", err.message);
        setSubAgents([]);
      }
    } catch (err) {
      console.error("Agent hierarchy fetch error:", err);
      setError(err.message || "Failed to load agent hierarchy");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    fetchHierarchy(true);
  };

  const filteredSubAgents = subAgents.filter((agent) => {
    // Status filter
    if (statusFilter !== "all") {
      const agentStatus = agent.status?.toLowerCase();
      if (agentStatus !== statusFilter.toLowerCase()) {
        return false;
      }
    }

    // Search filter
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      agent.first_name?.toLowerCase().includes(query) ||
      agent.last_name?.toLowerCase().includes(query) ||
      agent.email?.toLowerCase().includes(query) ||
      agent.agent_id?.toLowerCase().includes(query) ||
      agent.role?.toLowerCase().includes(query) ||
      agent.inviter_type?.toLowerCase().includes(query)
    );
  });

  const getStatusColor = (status) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === "active") return "#10B981";
    if (statusLower === "suspended") return "#EF4444";
    if (statusLower === "pending_approval" || statusLower === "pending")
      return "#F59E0B";
    if (statusLower === "invited") return "#6366F1";
    if (statusLower === "inactive") return "#6B7280";
    return "#6B7280";
  };

  const renderAgentCard = ({ item }) => (
    <Card
      style={styles.agentCard}
      onPress={() => navigation.navigate("AgentDetails", { agent: item })}
    >
      <Card.Content>
        <View style={styles.agentHeader}>
          <View style={styles.avatarContainer}>
            <Icon name="account" size={32} color={colors.primary} />
          </View>
          <View style={styles.agentInfo}>
            <Text variant="titleMedium" style={styles.agentName}>
              {item.first_name} {item.last_name}
            </Text>
            <Text variant="bodySmall" style={styles.agentRole}>
              {item.role || item.inviter_type || "Agent"}
            </Text>
            <Text variant="bodySmall" style={styles.agentId}>
              ID: {item.agent_id || item.keycloak_id}
            </Text>
          </View>
          <View style={styles.statusBadges}>
            {item.status && (
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
            )}
            {item.kyc_status && (
              <Chip
                mode="flat"
                style={styles.kycChip}
                textStyle={{ fontSize: 10 }}
                icon={
                  item.kyc_status === "verified"
                    ? "check-circle"
                    : "alert-circle"
                }
              >
                KYC
              </Chip>
            )}
          </View>
        </View>

        <View style={styles.agentDetails}>
          {item.email && (
            <View style={styles.detailRow}>
              <Icon name="email" size={14} color="#6B7280" />
              <Text variant="bodySmall" style={styles.detailText}>
                {item.email}
              </Text>
            </View>
          )}
          {item.phone_number && (
            <View style={styles.detailRow}>
              <Icon name="phone" size={14} color="#6B7280" />
              <Text variant="bodySmall" style={styles.detailText}>
                {item.phone_number}
              </Text>
            </View>
          )}
          {item.invited_by && (
            <View style={styles.detailRow}>
              <Icon name="account-arrow-right" size={14} color="#6B7280" />
              <Text variant="bodySmall" style={styles.detailText}>
                Invited by: {item.inviter_type || "System"}
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
      {/* Current Agent Info */}
      {hierarchy && (
        <Card style={styles.currentAgentCard}>
          <Card.Content>
            <View style={styles.currentAgentHeader}>
              <Icon name="account-circle" size={64} color={colors.primary} />
              <View style={styles.currentAgentInfo}>
                <Text variant="titleLarge" style={styles.currentAgentName}>
                  {hierarchy.first_name} {hierarchy.last_name}
                </Text>
                <Text variant="bodyMedium" style={styles.currentAgentRole}>
                  {hierarchy.tier && `Tier ${hierarchy.tier} `}Agent
                </Text>
                <Text variant="bodySmall" style={styles.currentAgentId}>
                  ID: {hierarchy.agent_id}
                </Text>
              </View>
            </View>

            {hierarchy.parent_agent_id && (
              <View style={styles.parentSection}>
                <Text variant="bodySmall" style={styles.parentLabel}>
                  Reports to:
                </Text>
                <Text variant="bodyMedium" style={styles.parentValue}>
                  Parent Agent ID: {hierarchy.parent_agent_id}
                </Text>
              </View>
            )}

            {subAgents.length > 0 && (
              <View style={styles.subAgentsSummary}>
                <Icon name="account-multiple" size={20} color="#6B7280" />
                <Text variant="bodyMedium" style={styles.subAgentsCount}>
                  {subAgents.length} Sub-Agent
                  {subAgents.length !== 1 ? "s" : ""}
                </Text>
              </View>
            )}
          </Card.Content>
        </Card>
      )}

      {/* Sub-Agents Section */}
      {subAgents.length > 0 && (
        <>
          <View style={styles.sectionHeader}>
            <Text variant="titleMedium" style={styles.sectionTitle}>
              Invited Agents
            </Text>
          </View>

          <View style={styles.searchContainer}>
            <Searchbar
              placeholder="Search agents..."
              onChangeText={setSearchQuery}
              value={searchQuery}
              style={styles.searchBar}
            />
          </View>

          {/* Status Filter */}
          <View style={styles.filterContainer}>
            <SegmentedButtons
              value={statusFilter}
              onValueChange={setStatusFilter}
              buttons={[
                { value: "all", label: "All" },
                { value: "active", label: "Active" },
                { value: "pending", label: "Pending" },
                { value: "invited", label: "Invited" },
                { value: "suspended", label: "Suspended" },
              ]}
            />
          </View>

          <FlatList
            data={filteredSubAgents}
            renderItem={renderAgentCard}
            keyExtractor={(item) => item.agent_id || item.keycloak_id}
            contentContainerStyle={styles.listContent}
            refreshControl={
              <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
            }
          />
        </>
      )}

      {subAgents.length === 0 && (
        <View style={styles.emptyContainer}>
          <Icon name="account-group" size={64} color="#D1D5DB" />
          <Text variant="bodyLarge" style={styles.emptyText}>
            No invited agents yet
          </Text>
          <Text variant="bodySmall" style={styles.emptySubtext}>
            Agents you invite will appear here
          </Text>
        </View>
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
  currentAgentCard: {
    margin: spacing.md,
    backgroundColor: "#EFF6FF",
  },
  currentAgentHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  currentAgentInfo: {
    flex: 1,
  },
  currentAgentName: {
    fontWeight: "bold",
    color: "#1F2937",
  },
  currentAgentRole: {
    color: colors.primary,
    marginTop: 2,
  },
  currentAgentId: {
    color: "#6B7280",
    marginTop: 2,
  },
  parentSection: {
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: "#D1D5DB",
  },
  parentLabel: {
    color: "#6B7280",
  },
  parentValue: {
    color: "#374151",
    marginTop: spacing.xs,
  },
  subAgentsSummary: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    marginTop: spacing.md,
  },
  subAgentsCount: {
    color: "#6B7280",
  },
  sectionHeader: {
    paddingHorizontal: spacing.md,
    marginBottom: spacing.sm,
  },
  sectionTitle: {
    fontWeight: "600",
  },
  searchContainer: {
    backgroundColor: "#fff",
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.sm,
  },
  searchBar: {
    elevation: 0,
    backgroundColor: "#F3F4F6",
  },
  filterContainer: {
    backgroundColor: "#fff",
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "#E5E7EB",
  },
  listContent: {
    padding: spacing.md,
  },
  agentCard: {
    marginBottom: spacing.md,
  },
  agentHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  avatarContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#EFF6FF",
    justifyContent: "center",
    alignItems: "center",
    marginRight: spacing.sm,
  },
  agentInfo: {
    flex: 1,
  },
  agentName: {
    fontWeight: "600",
  },
  agentRole: {
    color: "#6366F1",
    marginTop: 2,
    textTransform: "capitalize",
  },
  agentId: {
    color: "#6B7280",
    marginTop: 2,
  },
  statusBadges: {
    gap: spacing.xs,
    alignItems: "flex-end",
  },
  statusChip: {
    height: 24,
  },
  kycChip: {
    height: 20,
    backgroundColor: "#EFF6FF",
  },
  tierChip: {
    height: 28,
  },
  agentDetails: {
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
});

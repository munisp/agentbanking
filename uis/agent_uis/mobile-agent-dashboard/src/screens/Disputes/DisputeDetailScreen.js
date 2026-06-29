import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  RefreshControl,
  StyleSheet,
  View,
} from "react-native";
import {
  ActivityIndicator,
  Card,
  Chip,
  Divider,
  Snackbar,
  Text,
  TextInput, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { disputeApi } from "../../services/apiService";
import { spacing } from "../../theme";
import { theme as _appTheme } from '../../theme';
const colors = _appTheme.colors;

const STATUS_COLORS = {
  open: "#F59E0B",
  raised: "#F59E0B",
  investigating: colors.primary,
  under_review: colors.primary,
  resolved: "#10B981",
  escalated: "#EF4444",
  closed: "#6B7280",
  rejected: "#EF4444",
};

export default function DisputeDetailScreen({
 route, navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const { dispute: initialDispute } = route.params || {};
  const [dispute, setDispute] = useState(initialDispute);
  const [messages, setMessages] = useState([]);
  const [replyText, setReplyText] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const flatListRef = useRef(null);
  const refreshIntervalRef = useRef(null);

  const disputeId = dispute?.dispute_id || dispute?.id;

  const loadData = useCallback(
    async (isRefresh = false) => {
      if (!disputeId) return;
      try {
        isRefresh ? setRefreshing(true) : setLoading(true);

        const [disputeRes, messagesRes] = await Promise.allSettled([
          disputeApi.getDispute(disputeId),
          disputeApi.getMessages(disputeId),
        ]);

        if (disputeRes.status === "fulfilled" && disputeRes.value) {
          setDispute(disputeRes.value?.dispute || disputeRes.value);
        }
        if (messagesRes.status === "fulfilled" && messagesRes.value) {
          const msgs =
            messagesRes.value?.messages ||
            messagesRes.value?.data ||
            messagesRes.value ||
            [];
          setMessages(Array.isArray(msgs) ? msgs : []);
        }
      } catch (err) {
        setError(err.message || "Failed to load dispute details");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [disputeId],
  );

  useEffect(() => {
    loadData();
    refreshIntervalRef.current = setInterval(() => loadData(), 15000);
    return () => clearInterval(refreshIntervalRef.current);
  }, [loadData]);

  const handleSendReply = async () => {
    if (!replyText.trim()) return;
    try {
      setSending(true);
      await disputeApi.addMessage(disputeId, { content: replyText.trim() });
      setReplyText("");
      await loadData();
      setTimeout(() => flatListRef.current?.scrollToEnd({ animated: true }), 200);
    } catch (err) {
      setError(err.message || "Failed to send message");
    } finally {
      setSending(false);
    }
  };

  const getStatusColor = (status) =>
    STATUS_COLORS[status?.toLowerCase()] || "#6B7280";

  if (!disputeId) {
    return (
      <View style={styles.centered}>
        <Text>Dispute not found</Text>
      </View>
    );
  }

  if (loading && !dispute) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  const renderMessage = ({ item }) => {
    const isMine = item.sender_type === "agent" || item.author_type === "agent";
    return (
      <View style={[styles.messageRow, isMine ? styles.myMessageRow : styles.theirMessageRow]}>
        {!isMine && (
          <View style={styles.avatarCircle}>
            <Icon name="shield-account" size={16} color="#fff" />
          </View>
        )}
        <View style={[styles.messageBubble, isMine ? styles.myBubble : styles.theirBubble]}>
          {!isMine && (
            <Text style={styles.messageSender}>
              {item.sender_name || item.author || "Support"}
            </Text>
          )}
          <Text style={[styles.messageText, isMine && styles.myMessageText]}>
            {item.content || item.message || item.text}
          </Text>
          <Text style={[styles.messageTime, isMine && styles.myMessageTime]}>
            {item.created_at
              ? new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
              : ""}
          </Text>
        </View>
        {isMine && (
          <View style={[styles.avatarCircle, styles.myAvatar]}>
            <Icon name="account" size={16} color="#fff" />
          </View>
        )}
      </View>
    );
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 90 : 0}
    >
      <View style={styles.infoSection}>
        <Card style={styles.infoCard}>
          <Card.Content>
            <View style={styles.infoHeader}>
              <View style={{ flex: 1 }}>
                <Text variant="titleMedium" style={{ fontWeight: "700" }}>
                  {dispute?.dispute_id || disputeId}
                </Text>
                <Text variant="bodySmall" style={{ color: "#6B7280" }}>
                  {(dispute?.dispute_type || dispute?.reason || "Dispute").replace(/_/g, " ")}
                </Text>
              </View>
              <Chip
                mode="flat"
                style={{ backgroundColor: getStatusColor(dispute?.status) + "20" }}
                textStyle={{ color: getStatusColor(dispute?.status), fontSize: 11 }}
              >
                {dispute?.status || "open"}
              </Chip>
            </View>

            {dispute?.description && (
              <>
                <Divider style={{ marginVertical: spacing.sm }} />
                <Text variant="bodySmall" style={{ color: "#374151" }}>
                  {dispute.description}
                </Text>
              </>
            )}

            <Divider style={{ marginVertical: spacing.sm }} />

            <View style={styles.metaRow}>
              {dispute?.amount && (
                <View style={styles.metaItem}>
                  <Text variant="bodySmall" style={styles.metaLabel}>Amount</Text>
                  <Text variant="bodyMedium" style={styles.metaValue}>
                    ₦{parseFloat(dispute.amount).toLocaleString()}
                  </Text>
                </View>
              )}
              <View style={styles.metaItem}>
                <Text variant="bodySmall" style={styles.metaLabel}>Filed</Text>
                <Text variant="bodyMedium" style={styles.metaValue}>
                  {dispute?.created_at ? new Date(dispute.created_at).toLocaleDateString() : "—"}
                </Text>
              </View>
              {dispute?.resolution && (
                <View style={styles.metaItem}>
                  <Text variant="bodySmall" style={styles.metaLabel}>Resolution</Text>
                  <Text variant="bodyMedium" style={[styles.metaValue, { color: "#10B981" }]}>
                    {dispute.resolution}
                  </Text>
                </View>
              )}
            </View>
          </Card.Content>
        </Card>
      </View>

      <FlatList
        ref={flatListRef}
        data={messages}
        renderItem={renderMessage}
        keyExtractor={(item, i) => item.id?.toString() || item.message_id?.toString() || i.toString()}
        contentContainerStyle={styles.messagesList}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => loadData(true)} />
        }
        onContentSizeChange={() =>
          messages.length > 0 && flatListRef.current?.scrollToEnd({ animated: false })
        }
        ListEmptyComponent={
          <View style={styles.emptyMessages}>
            <Icon name="chat-outline" size={40} color="#D1D5DB" />
            <Text variant="bodyMedium" style={{ color: "#9CA3AF", marginTop: spacing.sm }}>
              No messages yet
            </Text>
          </View>
        }
      />

      {!["closed", "resolved", "rejected"].includes(dispute?.status?.toLowerCase()) && (
        <View style={styles.replyContainer}>
          <TextInput
            mode="outlined"
            placeholder="Type a message..."
            value={replyText}
            onChangeText={setReplyText}
            style={styles.replyInput}
            dense
            right={
              <TextInput.Icon
                icon={sending ? "loading" : "send"}
                onPress={handleSendReply}
                disabled={sending || !replyText.trim()}
                color={colors.primary}
              />
            }
            onSubmitEditing={handleSendReply}
          />
        </View>
      )}

      <Snackbar visible={!!error} onDismiss={() => setError("")} duration={3000}>
        {error}
      </Snackbar>
    </KeyboardAvoidingView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F9FAFB" },
  centered: { flex: 1, justifyContent: "center", alignItems: "center" },
  infoSection: { backgroundColor: "#fff", padding: spacing.md, borderBottomWidth: 1, borderBottomColor: "#E5E7EB" },
  infoCard: { elevation: 0, borderWidth: 1, borderColor: "#E5E7EB" },
  infoHeader: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between" },
  metaRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  metaItem: {},
  metaLabel: { color: "#9CA3AF", fontSize: 11 },
  metaValue: { fontWeight: "600", color: "#111827" },
  messagesList: { padding: spacing.md, flexGrow: 1 },
  emptyMessages: { alignItems: "center", paddingTop: spacing.xxl },
  messageRow: { flexDirection: "row", marginBottom: spacing.md, alignItems: "flex-end", gap: spacing.sm },
  myMessageRow: { justifyContent: "flex-end" },
  theirMessageRow: { justifyContent: "flex-start" },
  avatarCircle: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: colors.primary,
    justifyContent: "center", alignItems: "center",
  },
  myAvatar: { backgroundColor: "#10B981" },
  messageBubble: { maxWidth: "70%", borderRadius: 16, padding: spacing.sm, paddingHorizontal: spacing.md },
  myBubble: { backgroundColor: colors.primary, borderBottomRightRadius: 4 },
  theirBubble: { backgroundColor: "#fff", borderBottomLeftRadius: 4, borderWidth: 1, borderColor: "#E5E7EB" },
  messageSender: { fontSize: 11, color: "#6B7280", fontWeight: "600", marginBottom: 2 },
  messageText: { color: "#111827", fontSize: 14, lineHeight: 20 },
  myMessageText: { color: "#fff" },
  messageTime: { fontSize: 10, color: "#9CA3AF", marginTop: 2, textAlign: "right" },
  myMessageTime: { color: "rgba(255,255,255,0.7)" },
  replyContainer: { backgroundColor: "#fff", padding: spacing.sm, borderTopWidth: 1, borderTopColor: "#E5E7EB" },
  replyInput: { backgroundColor: "#F9FAFB" },
});

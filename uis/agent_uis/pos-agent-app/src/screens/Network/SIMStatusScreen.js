import React, { useCallback, useEffect, useRef, useState } from "react";
import { theme as _appTheme } from "../../theme";
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
} from "react-native";
import { Card, Chip, ProgressBar, Text, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { simOrchestratorApi } from "../../services/apiService";
import { spacing, theme } from "../../theme";
const SLOT_LABELS = ["Phys 1", "Phys 2", "eSIM 1", "eSIM 2"];
const POLL_INTERVAL_MS = 10_000;

// Convert AT-command RSSI (0–31) → approximate dBm and a 0-100 quality %

function rssiToQuality(rssi) {
  if (rssi == null || rssi === 99) return 0; // 99 = unknown
  return Math.round((Math.min(rssi, 31) / 31) * 100);
}

function rssiToDbm(rssi) {
  if (rssi == null || rssi === 99) return null;
  return -113 + rssi * 2;
}

function scoreColor(score) {
  if (score >= 700) return "#10B981";
  if (score >= 400) return "#F59E0B";
  return "#EF4444";
}

function scoreLabel(score) {
  if (score >= 700) return "Good";
  if (score >= 400) return "Fair";
  if (score > 0)    return "Poor";
  return "Offline";
}

function reasonLabel(reason) {
  if (reason === "high_latency") return "High Latency";
  if (reason === "high_packet_loss") return "Packet Loss";
  return reason ?? "Unknown";
}

function formatTs(tsUtc) {
  if (!tsUtc) return "—";
  return new Date(tsUtc * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function timeAgo(tsUtc) {
  if (!tsUtc) return "";
  const delta = Math.floor(Date.now() / 1000 - tsUtc);
  if (delta < 60) return `${delta}s ago`;
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
  return `${Math.floor(delta / 3600)}h ago`;
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function ActiveConnectionCard({ status }) {
  const styles = makeStyles(_appTheme.colors);
  const { transactionActive, txRef, isWifi, activeSlot, readings } = status;
  const active = readings?.[activeSlot];
  const carrier = isWifi ? "Wi-Fi" : (active?.carrier || "—");
  const slotLabel = isWifi ? "Wi-Fi" : (SLOT_LABELS[activeSlot] ?? `Slot ${activeSlot}`);

  return (
    <Card style={[styles.activeCard, { backgroundColor: theme.colors.primary }]}>
      <Card.Content>
        <View style={styles.activeHeader}>
          <Icon
            name={isWifi ? "wifi" : "sim"}
            size={32}
            color="#FFFFFF"
          />
          <View style={styles.activeInfo}>
            <Text style={styles.activeSlotLabel}>{slotLabel}</Text>
            <Text style={styles.activeCarrier}>{carrier}</Text>
          </View>
          <Chip style={styles.activeBadge} textStyle={styles.activeBadgeText}>
            ACTIVE
          </Chip>
        </View>

        {transactionActive && (
          <View style={styles.txBanner}>
            <Icon name="swap-horizontal" size={14} color="#FFF7ED" />
            <Text style={styles.txBannerText}>
              Transaction in flight{txRef ? ` · ${txRef}` : ""}
            </Text>
          </View>
        )}

        {active && !isWifi && (
          <View style={styles.activeStats}>
            <View style={styles.activeStat}>
              <Icon name="signal" size={14} color="rgba(255,255,255,0.8)" />
              <Text style={styles.activeStatText}>
                {rssiToDbm(active.rssi) != null ? `${rssiToDbm(active.rssi)} dBm` : "—"}
              </Text>
            </View>
            <View style={styles.activeStat}>
              <Icon name="timer-outline" size={14} color="rgba(255,255,255,0.8)" />
              <Text style={styles.activeStatText}>{active.latencyMs} ms</Text>
            </View>
            <View style={styles.activeStat}>
              <Icon name="percent" size={14} color="rgba(255,255,255,0.8)" />
              <Text style={styles.activeStatText}>
                {((active.packetLossX10 ?? 0) / 10).toFixed(1)}% loss
              </Text>
            </View>
            <View style={styles.activeStat}>
              <Icon name="star-circle-outline" size={14} color="rgba(255,255,255,0.8)" />
              <Text style={styles.activeStatText}>
                {active.score} / 1000
              </Text>
            </View>
          </View>
        )}
      </Card.Content>
    </Card>
  );
}

function SIMSlotCard({ reading, index }) {
  const styles = makeStyles(_appTheme.colors);
  const quality = rssiToQuality(reading?.rssi);
  const dbm     = rssiToDbm(reading?.rssi);
  const score   = reading?.score ?? 0;
  const color   = scoreColor(score);
  const isSelected = reading?.selected;

  return (
    <Card style={[styles.slotCard, isSelected && styles.slotCardSelected]}>
      <Card.Content style={styles.slotContent}>
        {/* Header row */}
        <View style={styles.slotHeader}>
          <Text style={styles.slotLabel}>{SLOT_LABELS[index]}</Text>
          {isSelected && (
            <Icon name="check-circle" size={16} color={theme.colors.primary} />
          )}
        </View>

        <Text style={styles.slotCarrier} numberOfLines={1}>
          {reading?.carrier || "—"}
        </Text>

        {/* Score bar */}
        <View style={styles.scoreRow}>
          <ProgressBar
            progress={score / 1000}
            color={color}
            style={styles.scoreBar}
          />
          <Text style={[styles.scoreText, { color }]}>
            {score}
          </Text>
        </View>
        <Text style={[styles.scoreLabel, { color }]}>{scoreLabel(score)}</Text>

        {/* Stats */}
        <View style={styles.slotStats}>
          <View style={styles.slotStat}>
            <Icon name="signal" size={12} color="#6B7280" />
            <Text style={styles.slotStatText}>
              {dbm != null ? `${dbm} dBm` : "—"}
            </Text>
          </View>
          <View style={styles.slotStat}>
            <Icon name="timer-outline" size={12} color="#6B7280" />
            <Text style={styles.slotStatText}>
              {reading?.latencyMs != null ? `${reading.latencyMs} ms` : "—"}
            </Text>
          </View>
        </View>

        {/* Signal quality bar */}
        <ProgressBar
          progress={quality / 100}
          color={quality >= 60 ? "#10B981" : quality >= 30 ? "#F59E0B" : "#EF4444"}
          style={styles.signalBar}
        />
        <Text style={styles.signalLabel}>Signal {quality}%</Text>
      </Card.Content>
    </Card>
  );
}

function FailoverCard({ failover }) {
  const styles = makeStyles(_appTheme.colors);
  if (!failover) return null;

  const fromLabel = SLOT_LABELS[failover.fromSlot] ?? `Slot ${failover.fromSlot}`;
  const toLabel   = SLOT_LABELS[failover.toSlot]   ?? `Slot ${failover.toSlot}`;
  const isLatency = failover.reason === "high_latency";

  return (
    <Card style={styles.failoverCard}>
      <Card.Content>
        <View style={styles.failoverHeader}>
          <Icon name="swap-horizontal-bold" size={20} color="#EF4444" />
          <Text style={styles.failoverTitle}>Last Failover</Text>
          <Chip
            style={[
              styles.reasonChip,
              { backgroundColor: isLatency ? "#FEF3C7" : "#FEE2E2" },
            ]}
            textStyle={{ color: isLatency ? "#92400E" : "#991B1B", fontSize: 10 }}
          >
            {reasonLabel(failover.reason)}
          </Chip>
        </View>

        <View style={styles.failoverRoute}>
          <View style={styles.failoverSlot}>
            <Text style={styles.failoverSlotLabel}>{fromLabel}</Text>
            <Text style={styles.failoverSlotSub}>From</Text>
          </View>
          <Icon name="arrow-right-bold" size={24} color="#EF4444" />
          <View style={styles.failoverSlot}>
            <Text style={styles.failoverSlotLabel}>{toLabel}</Text>
            <Text style={styles.failoverSlotSub}>To</Text>
          </View>
        </View>

        <View style={styles.failoverMeta}>
          <Text style={styles.failoverMetaText}>
            {failover.latencyMs} ms latency · {((failover.lossX10 ?? 0) / 10).toFixed(1)}% loss
          </Text>
          {failover.txRef && (
            <Text style={styles.failoverMetaText}>Ref: {failover.txRef}</Text>
          )}
          <Text style={styles.failoverTime}>
            {formatTs(failover.timestampUtc)} · {timeAgo(failover.timestampUtc)}
          </Text>
        </View>
      </Card.Content>
    </Card>
  );
}

// ─── Main Screen ─────────────────────────────────────────────────────────────

export default function SIMStatusScreen() {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  const [status, setStatus]       = useState(null);
  const [loading, setLoading]     = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [unavailable, setUnavailable] = useState(false);
  const pollRef = useRef(null);

  const fetchStatus = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    const data = await simOrchestratorApi.getStatus();
    if (data) {
      setStatus(data);
      setLastUpdated(Date.now());
      setUnavailable(false);
    } else {
      setUnavailable(true);
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    fetchStatus();
    pollRef.current = setInterval(() => fetchStatus(), POLL_INTERVAL_MS);
    return () => clearInterval(pollRef.current);
  }, [fetchStatus]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={theme.colors.primary} />
        <Text style={styles.loadingText}>Connecting to SIM orchestrator…</Text>
      </View>
    );
  }

  if (unavailable) {
    return (
      <ScrollView
        contentContainerStyle={styles.center}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => fetchStatus(true)} />
        }
      >
        <Icon name="sim-off" size={64} color="#D1D5DB" />
        <Text style={styles.unavailableTitle}>Orchestrator Unavailable</Text>
        <Text style={styles.unavailableText}>
          The SIM orchestrator daemon is not reachable on localhost:9200.{"\n"}
          Pull to refresh or check the terminal service.
        </Text>
      </ScrollView>
    );
  }

  const secondsAgo = lastUpdated
    ? Math.round((Date.now() - lastUpdated) / 1000)
    : null;

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => fetchStatus(true)} />
      }
    >
      {/* Active connection */}
      <ActiveConnectionCard status={status} />

      {/* Last updated */}
      {secondsAgo != null && (
        <Text style={styles.updatedText}>
          Updated {secondsAgo}s ago · refreshes every {POLL_INTERVAL_MS / 1000}s
        </Text>
      )}

      {/* SIM slots grid */}
      <Text style={styles.sectionTitle}>SIM Slots</Text>
      <View style={styles.slotsGrid}>
        {(status.readings ?? []).map((reading, i) => (
          <SIMSlotCard key={i} reading={reading} index={i} />
        ))}
      </View>

      {/* Last failover */}
      {status.lastFailover && (
        <>
          <Text style={styles.sectionTitle}>Failover History</Text>
          <FailoverCard failover={status.lastFailover} />
        </>
      )}

      <View style={styles.bottomSpacer} />
    </ScrollView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F9FAFB",
  },
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xl,
    gap: spacing.md,
  },
  loadingText: {
    color: "#6B7280",
    marginTop: spacing.sm,
  },
  unavailableTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#374151",
    textAlign: "center",
  },
  unavailableText: {
    color: "#6B7280",
    textAlign: "center",
    lineHeight: 22,
  },

  // Active card
  activeCard: {
    margin: spacing.md,
    marginBottom: spacing.xs,
  },
  activeHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    marginBottom: spacing.sm,
  },
  activeInfo: { flex: 1 },
  activeSlotLabel: {
    color: "rgba(255,255,255,0.75)",
    fontSize: 12,
    textTransform: "uppercase",
    fontWeight: "600",
  },
  activeCarrier: {
    color: "#FFFFFF",
    fontSize: 22,
    fontWeight: "bold",
  },
  activeBadge: {
    backgroundColor: "rgba(255,255,255,0.2)",
  },
  activeBadgeText: {
    color: "#FFFFFF",
    fontSize: 10,
    fontWeight: "700",
  },
  txBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: "rgba(255,255,255,0.15)",
    borderRadius: 6,
    padding: spacing.sm,
    marginBottom: spacing.sm,
  },
  txBannerText: {
    color: "#FFF7ED",
    fontSize: 12,
    flex: 1,
  },
  activeStats: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
    marginTop: spacing.xs,
  },
  activeStat: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  activeStatText: {
    color: "rgba(255,255,255,0.9)",
    fontSize: 13,
  },

  // Updated text
  updatedText: {
    fontSize: 11,
    color: "#9CA3AF",
    textAlign: "right",
    paddingHorizontal: spacing.md,
    marginBottom: spacing.xs,
  },

  // Section title
  sectionTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#374151",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginHorizontal: spacing.md,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },

  // Slots grid
  slotsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    paddingHorizontal: spacing.sm,
    gap: spacing.sm,
  },
  slotCard: {
    width: "47%",
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E5E7EB",
  },
  slotCardSelected: {
    borderColor: theme.colors.primary,
    borderWidth: 2,
  },
  slotContent: {
    paddingVertical: spacing.sm,
  },
  slotHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 2,
  },
  slotLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: "#6B7280",
    textTransform: "uppercase",
  },
  slotCarrier: {
    fontSize: 16,
    fontWeight: "bold",
    color: "#111827",
    marginBottom: spacing.sm,
  },
  scoreRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    marginBottom: 2,
  },
  scoreBar: {
    flex: 1,
    height: 6,
    borderRadius: 3,
  },
  scoreText: {
    fontSize: 12,
    fontWeight: "700",
    minWidth: 32,
    textAlign: "right",
  },
  scoreLabel: {
    fontSize: 10,
    fontWeight: "600",
    marginBottom: spacing.sm,
  },
  slotStats: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  slotStat: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
  },
  slotStatText: {
    fontSize: 11,
    color: "#6B7280",
  },
  signalBar: {
    height: 4,
    borderRadius: 2,
    marginBottom: 2,
  },
  signalLabel: {
    fontSize: 10,
    color: "#9CA3AF",
  },

  // Failover card
  failoverCard: {
    marginHorizontal: spacing.md,
    borderLeftWidth: 4,
    borderLeftColor: "#EF4444",
  },
  failoverHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  failoverTitle: {
    fontWeight: "700",
    flex: 1,
    color: "#374151",
  },
  reasonChip: {
    height: 24,
  },
  failoverRoute: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.lg,
    marginBottom: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: "#FEF2F2",
    borderRadius: 8,
  },
  failoverSlot: {
    alignItems: "center",
  },
  failoverSlotLabel: {
    fontWeight: "700",
    fontSize: 16,
    color: "#111827",
  },
  failoverSlotSub: {
    fontSize: 11,
    color: "#6B7280",
  },
  failoverMeta: {
    gap: 4,
  },
  failoverMetaText: {
    fontSize: 12,
    color: "#6B7280",
  },
  failoverTime: {
    fontSize: 11,
    color: "#9CA3AF",
    marginTop: 2,
  },

  bottomSpacer: {
    height: spacing.xl,
  },
});

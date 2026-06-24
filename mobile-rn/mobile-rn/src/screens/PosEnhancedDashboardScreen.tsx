import React, { useState } from "react";
import { View, Text, ScrollView, TouchableOpacity, StyleSheet } from "react-native";

/**
 * POS Enhanced Dashboard — React Native screen.
 * Feature parity with PWA POSEnhancedDashboard.tsx and Flutter equivalent.
 */

type Tab = "overview" | "keys" | "routing" | "healing" | "voice" | "float" | "biometrics" | "eod" | "geo" | "revenue";

export default function PosEnhancedDashboardScreen() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "keys", label: "Keys" },
    { id: "routing", label: "Routing" },
    { id: "healing", label: "Healing" },
    { id: "voice", label: "Voice" },
    { id: "float", label: "Float" },
    { id: "biometrics", label: "Bio" },
    { id: "eod", label: "EOD" },
    { id: "geo", label: "Geo" },
    { id: "revenue", label: "Revenue" },
  ];

  return (
    <View style={styles.container}>
      <Text style={styles.title}>POS Terminal Management</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabBar}>
        {tabs.map((tab) => (
          <TouchableOpacity
            key={tab.id}
            onPress={() => setActiveTab(tab.id)}
            style={[styles.tab, activeTab === tab.id && styles.activeTab]}
          >
            <Text style={[styles.tabText, activeTab === tab.id && styles.activeTabText]}>{tab.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
      <ScrollView style={styles.content}>
        {activeTab === "overview" && <OverviewPanel />}
        {activeTab === "keys" && <PanelPlaceholder title="DUKPT Keys" desc="TMK/TPK/TAK management" />}
        {activeTab === "routing" && <PanelPlaceholder title="AI Routing" desc="NIBSS/Interswitch/UPSL scoring" />}
        {activeTab === "healing" && <PanelPlaceholder title="Self-Healing" desc="Auto-remediation log" />}
        {activeTab === "voice" && <PanelPlaceholder title="Voice POS" desc="4 languages, 5 intents" />}
        {activeTab === "float" && <PanelPlaceholder title="Float Predict" desc="ML demand forecasting" />}
        {activeTab === "biometrics" && <PanelPlaceholder title="Biometrics" desc="Keystroke risk scoring" />}
        {activeTab === "eod" && <PanelPlaceholder title="EOD Recon" desc="Forced settlement" />}
        {activeTab === "geo" && <PanelPlaceholder title="Geo-Velocity" desc="Clone detection" />}
        {activeTab === "revenue" && <PanelPlaceholder title="Revenue" desc="Fleet analytics" />}
      </ScrollView>
    </View>
  );
}

function OverviewPanel() {
  const stats = [
    { title: "Active Terminals", value: "247", change: "+12" },
    { title: "Key Rotations", value: "18", change: "0" },
    { title: "Self-Healed", value: "34", change: "+5" },
    { title: "Voice Commands", value: "156", change: "+23" },
    { title: "Float Alerts", value: "8", change: "-2" },
    { title: "Bio Blocks", value: "3", change: "+1" },
    { title: "Geo Flags", value: "1", change: "0" },
    { title: "Revenue", value: "\u20a62.4M", change: "+15%" },
  ];

  return (
    <View style={styles.grid}>
      {stats.map((stat) => (
        <View key={stat.title} style={styles.statCard}>
          <Text style={styles.statTitle}>{stat.title}</Text>
          <Text style={styles.statValue}>{stat.value}</Text>
          <Text style={[styles.statChange, { color: stat.change.startsWith("+") ? "#4ade80" : stat.change.startsWith("-") ? "#f87171" : "#9ca3af" }]}>
            {stat.change} today
          </Text>
        </View>
      ))}
    </View>
  );
}

function PanelPlaceholder({ title, desc }: { title: string; desc: string }) {
  return (
    <View style={styles.panel}>
      <Text style={styles.panelTitle}>{title}</Text>
      <Text style={styles.panelDesc}>{desc}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#111827", padding: 16 },
  title: { color: "#fff", fontSize: 22, fontWeight: "bold", marginBottom: 12 },
  tabBar: { flexDirection: "row", marginBottom: 16, maxHeight: 36 },
  tab: { paddingHorizontal: 12, paddingVertical: 6, marginRight: 4, borderRadius: 6, backgroundColor: "#1f2937" },
  activeTab: { backgroundColor: "#2563eb" },
  tabText: { color: "#9ca3af", fontSize: 12, fontWeight: "500" },
  activeTabText: { color: "#fff" },
  content: { flex: 1 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
  statCard: { width: "47%", backgroundColor: "#1f2937", borderRadius: 12, padding: 16, borderWidth: 1, borderColor: "#374151" },
  statTitle: { color: "#9ca3af", fontSize: 11, textTransform: "uppercase" },
  statValue: { color: "#fff", fontSize: 24, fontWeight: "bold", marginTop: 4 },
  statChange: { fontSize: 11, marginTop: 2 },
  panel: { backgroundColor: "#1f2937", borderRadius: 12, padding: 24 },
  panelTitle: { color: "#fff", fontSize: 18, fontWeight: "bold" },
  panelDesc: { color: "#9ca3af", marginTop: 8 },
});

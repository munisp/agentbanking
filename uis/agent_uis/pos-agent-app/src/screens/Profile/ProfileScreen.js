import * as SecureStore from "expo-secure-store";
import React, { useEffect, useState } from "react";
import {
    ActivityIndicator,
    Alert,
    RefreshControl,
    ScrollView,
    StyleSheet,
    View,
} from "react-native";
import {
    Avatar,
    Button,
    Card,
    Divider,
    Snackbar,
    Text,
    TextInput, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { useAuth } from "../../contexts/AuthContext";
import { accountApi, agentApi } from "../../services/apiService";
import { authService } from "../../services/authService";
import { spacing } from "../../theme";
export default function ProfileScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const { user, logout: authLogout } = useAuth();
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const [agentProfile, setAgentProfile] = useState(null);
  const [accountDetails, setAccountDetails] = useState(null);

  const [profileData, setProfileData] = useState({
    name: "",
    email: "",
    phone: "",
    address: "",
    agentCode: "",
    businessName: "",
    agentRole: "agent",
  });

  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      if (!keycloakId) {
        throw new Error("Not authenticated");
      }

      // Fetch agent profile
      const profileResp = await agentApi.getAgentByKeycloakId(keycloakId);
      const profile = profileResp.agent ?? profileResp;
      setAgentProfile(profile);

      // Update profile data
      setProfileData({
        name:
          profile.name ??
          `${profile.first_name ?? ""} ${profile.last_name ?? ""}`.trim(),
        email: profile.email ?? "",
        phone: profile.phone_number ?? profile.phone ?? "",
        address: profile.business_address ?? "",
        agentCode: profile.uin ?? "",
        businessName: profile.business_name ?? "",
        agentRole: profile.agent_role ?? "agent",
      });

      // Fetch account details
      try {
        const accountResp = await accountApi.getAccountByKeycloakId(keycloakId);
        setAccountDetails(accountResp.account ?? accountResp);
      } catch (accountErr) {
        console.error("Account fetch error:", accountErr);
      }
    } catch (err) {
      console.error("Profile fetch error:", err);
      setError(err.message || "Failed to load profile");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    fetchProfile(true);
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);
      setError("");

      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      if (!keycloakId) {
        throw new Error("Not authenticated");
      }

      await agentApi.updateProfile(keycloakId, {
        phone: profileData.phone,
        business_address: profileData.address,
        business_name: profileData.businessName,
      });

      setSuccessMessage("Profile updated successfully");
      setIsEditing(false);

      // Refresh profile data
      await fetchProfile(true);
    } catch (err) {
      console.error("Save profile error:", err);
      setError(err.message || "Failed to update profile");
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    fetchProfile(true);
  };

  const handleLogout = () => {
    Alert.alert(
      "Logout",
      "Are you sure you want to logout?",
      [
        {
          text: "Cancel",
          style: "cancel",
        },
        {
          text: "Logout",
          style: "destructive",
          onPress: async () => {
            try {
              setIsLoggingOut(true);
              await authService.logout();
              await authLogout();
              // Navigation will be handled by AuthContext
            } catch (err) {
              console.error("Logout error:", err);
              setError("Failed to logout. Please try again.");
            } finally {
              setIsLoggingOut(false);
            }
          },
        },
      ],
      { cancelable: true },
    );
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      <View style={styles.content}>
        {/* Profile Header */}
        <Card style={styles.headerCard}>
          <Card.Content style={styles.headerContent}>
            <Avatar.Text
              size={80}
              label={
                profileData.name
                  .split(" ")
                  .map((n) => n[0])
                  .join("")
                  .toUpperCase() || "A"
              }
              style={styles.avatar}
            />
            <View style={styles.headerText}>
              <Text variant="headlineSmall" style={styles.name}>
                {profileData.name}
              </Text>
              <Text variant="bodyMedium" style={styles.agentCode}>
                {profileData.agentCode}
              </Text>
              <Text variant="bodySmall" style={styles.role}>
                {profileData.agentRole}
              </Text>
            </View>
          </Card.Content>
        </Card>

        {/* Account Details Card */}
        {accountDetails && (
          <Card style={styles.card}>
            <Card.Content>
              <Text variant="titleMedium" style={styles.sectionTitle}>
                Account Information
              </Text>
              <Divider style={styles.divider} />

              <View style={styles.infoRow}>
                <Icon name="credit-card" size={20} color="#6B7280" />
                <View style={styles.infoContent}>
                  <Text variant="bodySmall" style={styles.infoLabel}>
                    Account Number
                  </Text>
                  <Text variant="bodyMedium" style={styles.infoValue}>
                    {accountDetails.account_number}
                  </Text>
                </View>
              </View>

              <View style={styles.infoRow}>
                <Icon name="cash" size={20} color="#6B7280" />
                <View style={styles.infoContent}>
                  <Text variant="bodySmall" style={styles.infoLabel}>
                    Balance
                  </Text>
                  <Text variant="bodyMedium" style={styles.infoValue}>
                    ₦{parseFloat(accountDetails.balance || 0).toLocaleString()}
                  </Text>
                </View>
              </View>
            </Card.Content>
          </Card>
        )}

        {/* Personal Information Card */}
        <Card style={styles.card}>
          <Card.Content>
            <View style={styles.sectionHeader}>
              <Text variant="titleMedium" style={styles.sectionTitle}>
                Personal Information
              </Text>
              {!isEditing ? (
                <Button mode="text" onPress={() => setIsEditing(true)}>
                  Edit
                </Button>
              ) : (
                <View style={styles.editButtons}>
                  <Button
                    mode="text"
                    onPress={handleCancel}
                    disabled={isSaving}
                  >
                    Cancel
                  </Button>
                  <Button
                    mode="contained"
                    onPress={handleSave}
                    loading={isSaving}
                    disabled={isSaving}
                  >
                    Save
                  </Button>
                </View>
              )}
            </View>
            <Divider style={styles.divider} />

            <TextInput
              label="Full Name"
              value={profileData.name}
              onChangeText={(text) =>
                setProfileData((prev) => ({ ...prev, name: text }))
              }
              disabled={!isEditing}
              mode="outlined"
              style={styles.input}
              left={<TextInput.Icon icon="account" />}
            />

            <TextInput
              label="Email"
              value={profileData.email}
              disabled={true}
              mode="outlined"
              style={styles.input}
              left={<TextInput.Icon icon="email" />}
            />

            <TextInput
              label="Phone Number"
              value={profileData.phone}
              onChangeText={(text) =>
                setProfileData((prev) => ({ ...prev, phone: text }))
              }
              disabled={!isEditing}
              mode="outlined"
              keyboardType="phone-pad"
              style={styles.input}
              left={<TextInput.Icon icon="phone" />}
            />

            <TextInput
              label="Business Name"
              value={profileData.businessName}
              onChangeText={(text) =>
                setProfileData((prev) => ({ ...prev, businessName: text }))
              }
              disabled={!isEditing}
              mode="outlined"
              style={styles.input}
              left={<TextInput.Icon icon="store" />}
            />

            <TextInput
              label="Business Address"
              value={profileData.address}
              onChangeText={(text) =>
                setProfileData((prev) => ({ ...prev, address: text }))
              }
              disabled={!isEditing}
              mode="outlined"
              multiline
              numberOfLines={3}
              style={styles.input}
              left={<TextInput.Icon icon="map-marker" />}
            />

            <TextInput
              label="Agent Code"
              value={profileData.agentCode}
              disabled={true}
              mode="outlined"
              style={styles.input}
              left={<TextInput.Icon icon="identifier" />}
            />
          </Card.Content>
        </Card>

        {/* Agent Details Card */}
        {agentProfile && (
          <Card style={styles.card}>
            <Card.Content>
              <Text variant="titleMedium" style={styles.sectionTitle}>
                Agent Details
              </Text>
              <Divider style={styles.divider} />

              {agentProfile.tier && (
                <View style={styles.infoRow}>
                  <Icon name="star" size={20} color="#6B7280" />
                  <View style={styles.infoContent}>
                    <Text variant="bodySmall" style={styles.infoLabel}>
                      Agent Tier
                    </Text>
                    <Text variant="bodyMedium" style={styles.infoValue}>
                      {agentProfile.tier}
                    </Text>
                  </View>
                </View>
              )}

              {agentProfile.status && (
                <View style={styles.infoRow}>
                  <Icon name="check-circle" size={20} color="#6B7280" />
                  <View style={styles.infoContent}>
                    <Text variant="bodySmall" style={styles.infoLabel}>
                      Status
                    </Text>
                    <Text variant="bodyMedium" style={styles.infoValue}>
                      {agentProfile.status}
                    </Text>
                  </View>
                </View>
              )}

              {agentProfile.created_at && (
                <View style={styles.infoRow}>
                  <Icon name="calendar" size={20} color="#6B7280" />
                  <View style={styles.infoContent}>
                    <Text variant="bodySmall" style={styles.infoLabel}>
                      Member Since
                    </Text>
                    <Text variant="bodyMedium" style={styles.infoValue}>
                      {new Date(agentProfile.created_at).toLocaleDateString()}
                    </Text>
                  </View>
                </View>
              )}
            </Card.Content>
          </Card>
        )}

        {/* Logout Button */}
        <Card style={styles.card}>
          <Card.Content>
            <Button
              mode="contained"
              buttonColor="#EF4444"
              textColor="#FFFFFF"
              onPress={handleLogout}
              loading={isLoggingOut}
              disabled={isLoggingOut}
              icon="logout"
              style={styles.logoutButton}
            >
              Logout
            </Button>
          </Card.Content>
        </Card>
      </View>

      <Snackbar
        visible={!!error}
        onDismiss={() => setError("")}
        duration={3000}
      >
        {error}
      </Snackbar>

      <Snackbar
        visible={!!successMessage}
        onDismiss={() => setSuccessMessage("")}
        duration={3000}
        style={{ backgroundColor: "#10B981" }}
      >
        {successMessage}
      </Snackbar>
    </ScrollView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F9FAFB",
  },
  content: {
    padding: spacing.md,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  headerCard: {
    marginBottom: spacing.md,
  },
  headerContent: {
    flexDirection: "row",
    alignItems: "center",
  },
  avatar: {
    backgroundColor: colors.primary,
  },
  headerText: {
    marginLeft: spacing.md,
    flex: 1,
  },
  name: {
    fontWeight: "bold",
  },
  agentCode: {
    color: "#6B7280",
    marginTop: spacing.xs,
  },
  role: {
    color: "#9CA3AF",
    textTransform: "capitalize",
    marginTop: 2,
  },
  card: {
    marginBottom: spacing.md,
  },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  sectionTitle: {
    fontWeight: "600",
  },
  editButtons: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  divider: {
    marginVertical: spacing.md,
  },
  input: {
    marginBottom: spacing.md,
  },
  infoRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  infoContent: {
    marginLeft: spacing.md,
    flex: 1,
  },
  infoLabel: {
    color: "#6B7280",
  },
  infoValue: {
    fontWeight: "500",
    marginTop: 2,
  },
  logoutButton: {
    marginVertical: spacing.xs,
  },
});

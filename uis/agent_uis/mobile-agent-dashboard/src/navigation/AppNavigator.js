import { NavigationContainer } from "@react-navigation/native";
import { useTheme } from 'react-native-paper';
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React from "react";
import {
  Linking,
  Modal,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useAuth } from "../contexts/AuthContext";

// Auth Screens
import LoginScreen from "../screens/Auth/LoginScreen";
import OnboardingScreen from "../screens/Auth/OnboardingScreen";
import SignUpScreen from "../screens/Auth/SignUpScreen";

// Main App Navigation
import MainTabNavigator from "./MainTabNavigator";

const Stack = createNativeStackNavigator();

export default function AppNavigator() {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  const { isAuthenticated, isLoading, kycStatus, user, logout } = useAuth();
  const isKycPending =
    isAuthenticated && String(kycStatus || "").trim().toLowerCase() === "pending";

  const openKycLink = async () => {
    const kycUrl = user?.kyc_verification_url || user?.kyc_url;
    if (!kycUrl) return;
    try {
      await Linking.openURL(kycUrl);
    } catch {
      // Ignore URL open errors to avoid crashing the app.
    }
  };

  if (isLoading) {
    return null; // Or a loading screen
  }

  return (
    <>
      <NavigationContainer>
        <Stack.Navigator
          screenOptions={{
            headerShown: false,
          }}
        >
          {!isAuthenticated ? (
            <>
              <Stack.Screen name="Login" component={LoginScreen} />
              <Stack.Screen name="SignUp" component={SignUpScreen} />
              <Stack.Screen name="Onboarding" component={OnboardingScreen} />
            </>
          ) : (
            <Stack.Screen name="MainApp" component={MainTabNavigator} />
          )}
        </Stack.Navigator>
      </NavigationContainer>

      <Modal
        visible={isKycPending}
        transparent
        animationType="fade"
        statusBarTranslucent
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>KYC Pending</Text>
            <Text style={styles.modalText}>
              Your account is signed in, but KYC verification is still pending.
              Complete verification to continue full access.
            </Text>

            {!!(user?.kyc_verification_url || user?.kyc_url) && (
              <TouchableOpacity style={styles.primaryButton} onPress={openKycLink}>
                <Text style={styles.primaryButtonText}>Continue KYC</Text>
              </TouchableOpacity>
            )}

            <TouchableOpacity style={styles.secondaryButton} onPress={logout}>
              <Text style={styles.secondaryButtonText}>Logout</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.6)",
    justifyContent: "center",
    padding: 20,
  },
  modalCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 20,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#111827",
    marginBottom: 8,
  },
  modalText: {
    fontSize: 14,
    lineHeight: 20,
    color: "#4B5563",
    marginBottom: 16,
  },
  primaryButton: {
    backgroundColor: "#16A34A",
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
    marginBottom: 10,
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "700",
  },
  secondaryButton: {
    borderWidth: 1,
    borderColor: "#D1D5DB",
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
  },
  secondaryButtonText: {
    color: "#374151",
    fontSize: 14,
    fontWeight: "700",
  },
});

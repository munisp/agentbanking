/**
 * Biometric Login Screen (React Native)
 * FaceID/TouchID/Fingerprint + PIN fallback.
 * Matches Flutter BiometricLoginScreen and PWA biometric prompt.
 */
import React, { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Vibration,
  Platform,
} from "react-native";

type AuthState = "idle" | "biometric" | "pin" | "authenticated" | "error";

export default function BiometricLoginScreen({ navigation }: { navigation: any }) {
  const [authState, setAuthState] = useState<AuthState>("idle");
  const [pin, setPin] = useState("");
  const [biometricType, setBiometricType] = useState<"face" | "fingerprint">("fingerprint");
  const [error, setError] = useState("");

  useEffect(() => {
    attemptBiometric();
  }, []);

  const attemptBiometric = useCallback(async () => {
    setAuthState("biometric");
    try {
      // Production: use react-native-biometrics or expo-local-authentication
      // const { biometryType } = await ReactNativeBiometrics.isSensorAvailable();
      // const { success } = await ReactNativeBiometrics.simplePrompt({ promptMessage: "Authenticate" });
      await new Promise((resolve) => setTimeout(resolve, 500));
      Vibration.vibrate([0, 50, 30, 50]); // Success haptic: double pulse
      setAuthState("authenticated");
    } catch {
      setAuthState("pin");
      setBiometricType("fingerprint");
    }
  }, []);

  const onPinDigit = useCallback((digit: string) => {
    if (pin.length >= 6) return;
    Vibration.vibrate(10);
    const newPin = pin + digit;
    setPin(newPin);
    if (newPin.length === 6) {
      verifyPin(newPin);
    }
  }, [pin]);

  const onPinDelete = useCallback(() => {
    if (pin.length === 0) return;
    Vibration.vibrate(10);
    setPin(pin.slice(0, -1));
  }, [pin]);

  const verifyPin = useCallback(async (value: string) => {
    // Production: verify against Keycloak/server
    if (value === "123456") {
      Vibration.vibrate([0, 50, 30, 50]);
      setAuthState("authenticated");
    } else {
      Vibration.vibrate(300); // Failure haptic: long buzz
      setError("Incorrect PIN");
      setPin("");
    }
  }, []);

  if (authState === "authenticated") {
    return (
      <View style={styles.container}>
        <Text style={styles.successIcon}>✓</Text>
        <Text style={styles.successText}>Authenticated</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Welcome Back</Text>
      <Text style={styles.subtitle}>
        {authState === "pin" ? "Enter your 6-digit PIN" : "Authenticate to continue"}
      </Text>

      {authState === "biometric" && (
        <View style={styles.biometricContainer}>
          <TouchableOpacity style={styles.biometricButton} onPress={attemptBiometric}>
            <Text style={styles.biometricIcon}>
              {biometricType === "face" ? "👤" : "🔒"}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => setAuthState("pin")}>
            <Text style={styles.linkText}>Use PIN instead</Text>
          </TouchableOpacity>
        </View>
      )}

      {authState === "pin" && (
        <View style={styles.pinContainer}>
          {/* PIN dots */}
          <View style={styles.dotsRow}>
            {Array.from({ length: 6 }, (_, i) => (
              <View
                key={i}
                style={[styles.dot, i < pin.length && styles.dotFilled]}
              />
            ))}
          </View>

          {error ? <Text style={styles.errorText}>{error}</Text> : null}

          {/* Numpad */}
          <View style={styles.numpad}>
            {[["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], ["bio", "0", "del"]].map(
              (row, rowIdx) => (
                <View key={rowIdx} style={styles.numRow}>
                  {row.map((key) => (
                    <TouchableOpacity
                      key={key}
                      style={styles.numButton}
                      onPress={() => {
                        if (key === "del") onPinDelete();
                        else if (key === "bio") attemptBiometric();
                        else onPinDigit(key);
                      }}
                    >
                      <Text style={styles.numText}>
                        {key === "del" ? "⌫" : key === "bio" ? "🔒" : key}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              )
            )}
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24, backgroundColor: "#fff" },
  title: { fontSize: 24, fontWeight: "600", marginBottom: 8 },
  subtitle: { fontSize: 14, color: "#666", marginBottom: 32 },
  biometricContainer: { alignItems: "center", gap: 16 },
  biometricButton: {
    width: 80, height: 80, borderRadius: 40,
    backgroundColor: "#EBF5FF", borderWidth: 2, borderColor: "#3B82F6",
    justifyContent: "center", alignItems: "center",
  },
  biometricIcon: { fontSize: 32 },
  linkText: { color: "#3B82F6", fontSize: 14 },
  pinContainer: { alignItems: "center", width: "100%" },
  dotsRow: { flexDirection: "row", gap: 12, marginBottom: 24 },
  dot: { width: 16, height: 16, borderRadius: 8, backgroundColor: "#E5E7EB" },
  dotFilled: { backgroundColor: "#3B82F6" },
  errorText: { color: "#EF4444", fontSize: 12, marginBottom: 16 },
  numpad: { width: "100%", maxWidth: 280 },
  numRow: { flexDirection: "row", justifyContent: "center", marginBottom: 8 },
  numButton: {
    width: 72, height: 72, borderRadius: 36,
    backgroundColor: "#F3F4F6", justifyContent: "center", alignItems: "center",
    marginHorizontal: 8,
  },
  numText: { fontSize: 24, fontWeight: "500" },
  successIcon: { fontSize: 80, color: "#10B981" },
  successText: { fontSize: 18, color: "#10B981", marginTop: 16 },
});

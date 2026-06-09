import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
  Alert,
} from "react-native";

export default function AccountOpeningScreen() {
  const [loading, setLoading] = useState(false);
  const [accountType, setAccountType] = useState("savings");
  const [fullName, setFullName] = useState("");
  const [bvn, setBvn] = useState("");
  const [phone, setPhone] = useState("");

  const handleSubmit = async () => {
    if (!fullName || !bvn || !phone) {
      Alert.alert("Error", "Please fill all required fields");
      return;
    }
    setLoading(true);
    // API call
    await new Promise(r => setTimeout(r, 2000));
    setLoading(false);
    Alert.alert("Success", "Account application submitted");
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Open New Account</Text>

      <Text style={styles.label}>Account Type</Text>
      <View style={styles.typeRow}>
        {["savings", "current", "fixed"].map(t => (
          <TouchableOpacity
            key={t}
            style={[styles.typeBtn, accountType === t && styles.typeBtnActive]}
            onPress={() => setAccountType(t)}
          >
            <Text
              style={accountType === t ? styles.typeTxtActive : styles.typeTxt}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={styles.label}>Full Name *</Text>
      <TextInput
        style={styles.input}
        value={fullName}
        onChangeText={setFullName}
        placeholder="Enter full name"
      />

      <Text style={styles.label}>BVN *</Text>
      <TextInput
        style={styles.input}
        value={bvn}
        onChangeText={setBvn}
        placeholder="11-digit BVN"
        keyboardType="numeric"
        maxLength={11}
      />

      <Text style={styles.label}>Phone Number *</Text>
      <TextInput
        style={styles.input}
        value={phone}
        onChangeText={setPhone}
        placeholder="Phone number"
        keyboardType="phone-pad"
      />

      <TouchableOpacity
        style={styles.submitBtn}
        onPress={handleSubmit}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.submitTxt}>Submit Application</Text>
        )}
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: "#fff" },
  title: { fontSize: 24, fontWeight: "bold", marginBottom: 24 },
  label: { fontSize: 14, fontWeight: "600", marginBottom: 8, marginTop: 16 },
  input: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
  },
  typeRow: { flexDirection: "row", gap: 8 },
  typeBtn: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#ddd",
  },
  typeBtnActive: { backgroundColor: "#0066cc", borderColor: "#0066cc" },
  typeTxt: { color: "#333" },
  typeTxtActive: { color: "#fff" },
  submitBtn: {
    backgroundColor: "#0066cc",
    padding: 16,
    borderRadius: 8,
    alignItems: "center",
    marginTop: 32,
  },
  submitTxt: { color: "#fff", fontSize: 16, fontWeight: "600" },
});

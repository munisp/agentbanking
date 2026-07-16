import * as SecureStore from "expo-secure-store";
import React, { useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import {
    Button,
    Card,
    RadioButton,
    Snackbar,
    Text,
    TextInput, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { posRequestApi } from "../../services/apiService";
import { spacing } from "../../theme";

const TERMINAL_MODELS = [
  {
    id: "pos_basic",
    label: "Basic POS",
    description: "Simple card reader",
    price: "Free",
  },
  {
    id: "pos_standard",
    label: "Standard POS",
    description: "Card + QR code",
    price: "Free",
  },
  {
    id: "pos_advanced",
    label: "Advanced POS",
    description: "Full featured terminal",
    price: "Free",
  },
];

export default function POSOrderScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [selectedModel, setSelectedModel] = useState("pos_standard");
  const [quantity, setQuantity] = useState("1");
  const [deliveryAddress, setDeliveryAddress] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleSubmitOrder = async () => {
    if (!deliveryAddress || !city || !state || !phoneNumber) {
      setError("Please fill all required fields");
      return;
    }

    try {
      setLoading(true);
      setError("");

      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      const agentId = await SecureStore.getItemAsync("agentId");

      await posRequestApi.createRequest({
        keycloak_id: keycloakId,
        agent_id: agentId,
        terminal_model: selectedModel,
        quantity: parseInt(quantity) || 1,
        delivery_address: `${deliveryAddress}, ${city}, ${state}`,
        phone_number: phoneNumber,
        notes: notes,
      });

      setSuccess("POS terminal order submitted successfully!");

      // Navigate back after successful submission
      setTimeout(() => {
        navigation.goBack();
      }, 2000);
    } catch (err) {
      console.error("POS order error:", err);
      setError(err.message || "Failed to submit POS order");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container}>
      {/* Terminal Model Selection */}
      <Card style={styles.card}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.cardTitle}>
            Select POS Terminal Model
          </Text>
          <RadioButton.Group
            onValueChange={setSelectedModel}
            value={selectedModel}
          >
            {TERMINAL_MODELS.map((model) => (
              <View key={model.id} style={styles.radioItem}>
                <RadioButton value={model.id} />
                <View style={styles.radioContent}>
                  <View style={styles.radioHeader}>
                    <Text variant="titleSmall" style={styles.modelLabel}>
                      {model.label}
                    </Text>
                    <Text variant="bodySmall" style={styles.modelPrice}>
                      {model.price}
                    </Text>
                  </View>
                  <Text variant="bodySmall" style={styles.modelDescription}>
                    {model.description}
                  </Text>
                </View>
              </View>
            ))}
          </RadioButton.Group>
        </Card.Content>
      </Card>

      {/* Quantity */}
      <Card style={styles.card}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.cardTitle}>
            Quantity
          </Text>
          <TextInput
            label="Number of Terminals"
            value={quantity}
            onChangeText={setQuantity}
            mode="outlined"
            keyboardType="numeric"
            left={<TextInput.Icon icon="counter" />}
          />
        </Card.Content>
      </Card>

      {/* Delivery Information */}
      <Card style={styles.card}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.cardTitle}>
            Delivery Information
          </Text>

          <TextInput
            label="Delivery Address *"
            value={deliveryAddress}
            onChangeText={setDeliveryAddress}
            mode="outlined"
            style={styles.input}
            multiline
            numberOfLines={2}
            left={<TextInput.Icon icon="map-marker" />}
          />

          <TextInput
            label="City *"
            value={city}
            onChangeText={setCity}
            mode="outlined"
            style={styles.input}
            left={<TextInput.Icon icon="city" />}
          />

          <TextInput
            label="State *"
            value={state}
            onChangeText={setState}
            mode="outlined"
            style={styles.input}
            left={<TextInput.Icon icon="map" />}
          />

          <TextInput
            label="Phone Number *"
            value={phoneNumber}
            onChangeText={setPhoneNumber}
            mode="outlined"
            style={styles.input}
            keyboardType="phone-pad"
            left={<TextInput.Icon icon="phone" />}
          />

          <TextInput
            label="Additional Notes (Optional)"
            value={notes}
            onChangeText={setNotes}
            mode="outlined"
            multiline
            numberOfLines={3}
            left={<TextInput.Icon icon="note-text" />}
          />
        </Card.Content>
      </Card>

      {/* Submit Button */}
      <View style={styles.buttonContainer}>
        <Button
          mode="contained"
          onPress={handleSubmitOrder}
          disabled={loading}
          loading={loading}
          style={styles.submitButton}
          icon="send"
        >
          Submit Order Request
        </Button>
      </View>

      <Snackbar
        visible={!!error}
        onDismiss={() => setError("")}
        duration={3000}
      >
        {error}
      </Snackbar>
      <Snackbar
        visible={!!success}
        onDismiss={() => setSuccess("")}
        duration={3000}
        style={{ backgroundColor: "#10B981" }}
      >
        {success}
      </Snackbar>
    </ScrollView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F9FAFB",
  },
  card: {
    margin: spacing.md,
  },
  cardTitle: {
    fontWeight: "600",
    marginBottom: spacing.md,
  },
  radioItem: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: "#E5E7EB",
  },
  radioContent: {
    flex: 1,
    marginLeft: spacing.sm,
  },
  radioHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  modelLabel: {
    fontWeight: "600",
  },
  modelPrice: {
    color: "#10B981",
    fontWeight: "600",
  },
  modelDescription: {
    color: "#6B7280",
    marginTop: 2,
  },
  input: {
    marginBottom: spacing.md,
  },
  buttonContainer: {
    padding: spacing.md,
  },
  submitButton: {
    paddingVertical: spacing.xs,
  },
});

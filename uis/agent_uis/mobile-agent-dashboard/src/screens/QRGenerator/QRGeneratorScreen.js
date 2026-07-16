import * as SecureStore from "expo-secure-store";
import React, { useEffect, useState } from "react";
import {
    Alert,
    Image,
    ScrollView,
    Share,
    StyleSheet,
    View,
} from "react-native";
import {
    ActivityIndicator,
    Button,
    Card,
    SegmentedButtons,
    Text,
    TextInput, useTheme} from "react-native-paper";
import QRCode from "react-native-qrcode-svg";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { accountApi, agentApi, qrApi } from "../../services/apiService";
import { spacing } from "../../theme";
import { formatCurrency } from "../../utils/formatters";
export default function QRGeneratorScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [qrType, setQrType] = useState("payment"); // account, payment, agent
  const [agentData, setAgentData] = useState(null);
  const [accountData, setAccountData] = useState(null);
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [qrValue, setQrValue] = useState("");
  const [paymentQRImage, setPaymentQRImage] = useState(null); // Base64 image from API
  const [loading, setLoading] = useState(false);
  const [generatingQR, setGeneratingQR] = useState(false);
  let qrCodeRef = null;

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    // Reset payment QR image when switching types or clearing amount
    if (qrType !== "payment" || !amount) {
      setPaymentQRImage(null);
    }
    generateQRValue();
  }, [qrType, agentData, accountData, amount, description]);

  const loadData = async () => {
    try {
      setLoading(true);
      const keycloakId = await SecureStore.getItemAsync("keycloakId");

      if (keycloakId) {
        // Load agent data
        try {
          const agentResponse = await agentApi.getAgentByKeycloakId(keycloakId);
          setAgentData(agentResponse?.agent || agentResponse);
        } catch (err) {
          console.log("Agent data not available:", err.message);
        }

        // Load account data
        try {
          const accountResponse =
            await accountApi.getAccountByKeycloakId(keycloakId);
          const account = accountResponse?.account || accountResponse;
          setAccountData(account);
        } catch (err) {
          console.log("Account data not available:", err.message);
        }
      }
    } catch (err) {
      console.error("Load data error:", err);
    } finally {
      setLoading(false);
    }
  };

  const generateQRValue = () => {
    let value = "";

    switch (qrType) {
      case "account":
        if (accountData) {
          value = JSON.stringify({
            type: "account",
            accountId: accountData.id,
            accountNumber: accountData.account_number,
            accountName:
              agentData?.business_name || agentData?.name || "Agent Account",
            balance: accountData.balance,
          });
        }
        break;

      case "payment":
        // For payment, we'll use the API to generate QR
        // Local QR is only for fallback display
        if (accountData && amount) {
          value = JSON.stringify({
            type: "payment",
            accountNumber: accountData.account_number,
            amount: parseFloat(amount),
            description: description || "Payment request",
            agentName: agentData?.business_name || agentData?.name || "Agent",
          });
        }
        break;

      case "agent":
        if (agentData) {
          value = JSON.stringify({
            type: "agent",
            agentId: agentData.id,
            name: agentData.business_name || agentData.name,
            phoneNumber: agentData.phone_number,
            email: agentData.email,
            location: agentData.location,
          });
        }
        break;

      default:
        value = "";
    }

    setQrValue(value);
  };

  const handleGeneratePaymentQR = async () => {
    if (!amount || parseFloat(amount) <= 0) {
      Alert.alert("Invalid Amount", "Please enter a valid amount");
      return;
    }

    if (!accountData?.account_number) {
      Alert.alert("Error", "Account information not available");
      return;
    }

    setGeneratingQR(true);
    try {
      const response = await qrApi.generateQRCode(
        accountData.account_number,
        amount,
        "NGN",
        description || "Payment request",
      );

      if (response?.qr_code_data) {
        setPaymentQRImage(response.qr_code_data);
      } else {
        Alert.alert("Error", response?.message || "Failed to generate QR code");
      }
    } catch (error) {
      console.error("QR generation error:", error);
      Alert.alert("Error", "Failed to generate QR code. Please try again.");
    } finally {
      setGeneratingQR(false);
    }
  };

  const handleShare = async () => {
    try {
      if (qrCodeRef) {
        qrCodeRef.toDataURL(async (dataURL) => {
          const message = `QR Code for ${qrType}: ${qrValue}`;
          await Share.share({
            message: message,
            // For images, you'd need expo-sharing and expo-file-system
            title: "Share QR Code",
          });
        });
      }
    } catch (error) {
      console.error("Error sharing:", error);
    }
  };

  return (
    <ScrollView style={styles.container}>
      {/* Header Card */}
      <Card style={styles.headerCard}>
        <Card.Content>
          <View style={styles.headerContent}>
            <View style={styles.headerIcon}>
              <Icon name="qrcode" size={32} color={colors.primary} />
            </View>
            <View style={styles.headerText}>
              <Text style={styles.headerTitle}>Generate QR Code</Text>
              <Text style={styles.headerSubtitle}>
                Create QR codes for payments and sharing
              </Text>
            </View>
          </View>
        </Card.Content>
      </Card>

      {/* QR Type Selector */}
      <View style={styles.selectorContainer}>
        <SegmentedButtons
          value={qrType}
          onValueChange={setQrType}
          buttons={[
            // {
            //   value: "account",
            //   label: "Account",
            //   icon: "bank",
            // },
            {
              value: "payment",
              label: "Payment",
              icon: "cash",
            },
            // {
            //   value: "agent",
            //   label: "Agent Info",
            //   icon: "account",
            // },
          ]}
        />
      </View>

      {/* Payment Form (only for payment type) */}
      {qrType === "payment" && (
        <Card style={styles.formCard}>
          <Card.Content>
            <Text style={styles.formTitle}>Payment Details</Text>
            <TextInput
              label="Amount (₦)"
              value={amount}
              onChangeText={setAmount}
              mode="outlined"
              keyboardType="numeric"
              style={styles.input}
              left={<TextInput.Icon icon="cash" />}
            />
            <TextInput
              label="Description (Optional)"
              value={description}
              onChangeText={setDescription}
              mode="outlined"
              multiline
              numberOfLines={2}
              style={styles.input}
              left={<TextInput.Icon icon="text" />}
            />
            <Button
              mode="contained"
              icon="qrcode"
              onPress={handleGeneratePaymentQR}
              disabled={generatingQR || !amount || parseFloat(amount) <= 0}
              loading={generatingQR}
              style={styles.generateButton}
            >
              {generatingQR ? "Generating..." : "Generate Payment QR Code"}
            </Button>
          </Card.Content>
        </Card>
      )}

      {/* QR Code Display */}
      {qrType === "payment" && paymentQRImage ? (
        <Card style={styles.qrCard}>
          <Card.Content>
            <View style={styles.qrContainer}>
              <Image
                source={{ uri: `data:image/png;base64,${paymentQRImage}` }}
                style={styles.qrImage}
                resizeMode="contain"
              />
            </View>

            {/* Info Display */}
            <View style={styles.infoContainer}>
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>Amount:</Text>
                <Text style={[styles.infoValue, styles.amountText]}>
                  ₦{parseFloat(amount).toLocaleString()}
                </Text>
              </View>
              {description && (
                <View style={styles.infoRow}>
                  <Text style={styles.infoLabel}>Description:</Text>
                  <Text style={styles.infoValue}>{description}</Text>
                </View>
              )}
            </View>

            {/* Action Buttons */}
            <View style={styles.actionButtons}>
              <Button
                mode="contained"
                icon="share-variant"
                onPress={handleShare}
                style={styles.actionButton}
              >
                Share QR Code
              </Button>
              <Button
                mode="outlined"
                icon="close"
                onPress={() => setPaymentQRImage(null)}
                style={styles.actionButton}
              >
                Clear
              </Button>
            </View>
          </Card.Content>
        </Card>
      ) : qrType !== "payment" && qrValue ? (
        <Card style={styles.qrCard}>
          <Card.Content>
            <View style={styles.qrContainer}>
              <QRCode
                value={qrValue}
                size={250}
                color="#000000"
                backgroundColor="#FFFFFF"
                getRef={(ref) => (qrCodeRef = ref)}
              />
            </View>

            {/* Info Display */}
            <View style={styles.infoContainer}>
              {qrType === "account" && accountData && (
                <>
                  <View style={styles.infoRow}>
                    <Text style={styles.infoLabel}>Account Number:</Text>
                    <Text style={styles.infoValue}>
                      {accountData.account_number}
                    </Text>
                  </View>
                  <View style={styles.infoRow}>
                    <Text style={styles.infoLabel}>Balance:</Text>
                    <Text style={styles.infoValue}>
                      {formatCurrency(accountData.balance)}
                    </Text>
                  </View>
                </>
              )}

              {qrType === "payment" && amount && (
                <>
                  <View style={styles.infoRow}>
                    <Text style={styles.infoLabel}>Amount:</Text>
                    <Text style={[styles.infoValue, styles.amountText]}>
                      ₦{parseFloat(amount).toLocaleString()}
                    </Text>
                  </View>
                  {description && (
                    <View style={styles.infoRow}>
                      <Text style={styles.infoLabel}>Description:</Text>
                      <Text style={styles.infoValue}>{description}</Text>
                    </View>
                  )}
                </>
              )}

              {qrType === "agent" && agentData && (
                <>
                  <View style={styles.infoRow}>
                    <Text style={styles.infoLabel}>Agent Name:</Text>
                    <Text style={styles.infoValue}>
                      {agentData.business_name || agentData.name}
                    </Text>
                  </View>
                  <View style={styles.infoRow}>
                    <Text style={styles.infoLabel}>Phone:</Text>
                    <Text style={styles.infoValue}>
                      {agentData.phone_number}
                    </Text>
                  </View>
                </>
              )}
            </View>

            {/* Action Buttons */}
            <View style={styles.actionButtons}>
              <Button
                mode="contained"
                icon="share-variant"
                onPress={handleShare}
                style={styles.actionButton}
              >
                Share QR Code
              </Button>
            </View>
          </Card.Content>
        </Card>
      ) : (
        <Card style={styles.qrCard}>
          <Card.Content>
            <View style={styles.placeholderContainer}>
              <Icon name="qrcode" size={100} color="#D1D5DB" />
              <Text style={styles.placeholderText}>
                {qrType === "payment"
                  ? "Enter amount to generate payment QR code"
                  : "Loading..."}
              </Text>
            </View>
          </Card.Content>
        </Card>
      )}

      <View style={styles.bottomPadding} />
    </ScrollView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F3F4F6",
  },
  headerCard: {
    margin: spacing.md,
    backgroundColor: "#FFFFFF",
    elevation: 4,
  },
  headerContent: {
    flexDirection: "row",
    alignItems: "center",
  },
  headerIcon: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "#DBEAFE",
    justifyContent: "center",
    alignItems: "center",
  },
  headerText: {
    flex: 1,
    marginLeft: spacing.md,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: "bold",
    color: "#111827",
  },
  headerSubtitle: {
    fontSize: 14,
    color: "#6B7280",
    marginTop: 4,
  },
  selectorContainer: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    maxWidth: "90%",
  },
  formCard: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
    backgroundColor: "#FFFFFF",
    elevation: 4,
  },
  formTitle: {
    fontSize: 18,
    fontWeight: "bold",
    color: "#111827",
    marginBottom: spacing.md,
  },
  input: {
    marginBottom: spacing.md,
  },
  generateButton: {
    marginTop: spacing.sm,
  },
  qrCard: {
    marginHorizontal: spacing.md,
    backgroundColor: "#FFFFFF",
    elevation: 4,
  },
  qrContainer: {
    alignItems: "center",
    paddingVertical: spacing.xl,
  },
  qrImage: {
    width: 250,
    height: 250,
  },
  infoContainer: {
    marginTop: spacing.lg,
    padding: spacing.md,
    backgroundColor: "#F9FAFB",
    borderRadius: 12,
  },
  infoRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: "#E5E7EB",
  },
  infoLabel: {
    fontSize: 14,
    color: "#6B7280",
    fontWeight: "600",
  },
  infoValue: {
    fontSize: 14,
    color: "#111827",
    fontWeight: "500",
  },
  amountText: {
    fontSize: 16,
    fontWeight: "bold",
    color: "#10B981",
  },
  actionButtons: {
    marginTop: spacing.lg,
  },
  actionButton: {
    marginVertical: spacing.sm,
  },
  placeholderContainer: {
    alignItems: "center",
    paddingVertical: spacing.xl * 2,
  },
  placeholderText: {
    fontSize: 14,
    color: "#6B7280",
    marginTop: spacing.md,
    textAlign: "center",
  },
  bottomPadding: {
    height: spacing.xl,
  },
});

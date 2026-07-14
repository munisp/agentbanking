import * as SecureStore from "expo-secure-store";
import React, { useCallback, useEffect, useState } from "react";
import {
    Alert,
    Animated,
    RefreshControl,
    ScrollView,
    StyleSheet,
    View,
} from "react-native";
import {
    ActivityIndicator,
    Button,
    Card,
    Chip,
    DataTable,
    SegmentedButtons,
    Snackbar,
    Text,
    TextInput, useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import {
    beep,
    onMultipleCards,
    onSwipeIncorrect,
    searchCard,
    stopCardSearch,
} from "../../lib/sunmi";
import { accountApi, agentApi, cardApi } from "../../services/apiService";
import { spacing } from "../../theme";
import { formatCurrency } from "../../utils/formatters";
// Card reading modes
const CardReadingMode = {
  NFC: "nfc",
  CHIP: "chip",
};

// Card reading states
const CardReadingState = {
  IDLE: "idle",
  WAITING: "waiting",
  READING: "reading",
  SUCCESS: "success",
  ERROR: "error",
  CANCELLED: "cancelled",
};

export default function CardTransactionsScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [transactionType, setTransactionType] = useState("withdrawal");
  const [cardNumber, setCardNumber] = useState("");
  const [cardId, setCardId] = useState("");
  const [customerAccount, setCustomerAccount] = useState("");
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const [description, setDescription] = useState("");
  const [recipientAccount, setRecipientAccount] = useState("");
  const [recipientBank, setRecipientBank] = useState("");
  const [billType, setBillType] = useState("");
  const [billerCode, setBillerCode] = useState("");

  // Card reader state
  const [cardReaderState, setCardReaderState] = useState(CardReadingState.IDLE);
  const [cardData, setCardData] = useState(null);
  const [readingMode, setReadingMode] = useState(CardReadingMode.NFC);
  const [readerSupported, setReaderSupported] = useState(false);
  const [deviceInfo, setDeviceInfo] = useState(null);
  const [useManualEntry, setUseManualEntry] = useState(false);
  const [pulseAnim] = useState(new Animated.Value(1));

  const [agentData, setAgentData] = useState(null);
  const [accountData, setAccountData] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    loadData();

    // Set device info for Nexgo N80
    setReaderSupported(true);
    setDeviceInfo({
      device: "Nexgo N80",
      nfc: true,
      chip: true,
      printer: true,
      fingerprint: false,
    });

    // Setup event listeners for card events
    const swipeListener = onSwipeIncorrect(() => {
      setError("Swipe error, please try again");
      setCardReaderState(CardReadingState.ERROR);
    });

    const multiCardListener = onMultipleCards(() => {
      setError("Multiple cards detected, please remove one");
      setCardReaderState(CardReadingState.ERROR);
    });

    return () => {
      // Cleanup event listeners
      swipeListener.remove();
      multiCardListener.remove();
      // Stop any ongoing card search
      stopCardSearch().catch(console.error);
    };
  }, []);

  useEffect(() => {
    // Start pulse animation when waiting for card
    if (
      cardReaderState === CardReadingState.WAITING ||
      cardReaderState === CardReadingState.READING
    ) {
      const animation = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.2,
            duration: 1000,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 1000,
            useNativeDriver: true,
          }),
        ]),
      );
      animation.start();
      return () => animation.stop();
    } else {
      pulseAnim.setValue(1);
    }
  }, [cardReaderState, pulseAnim]);

  const loadData = useCallback(async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      const agentId = await SecureStore.getItemAsync("agentId");

      // Load agent data
      if (keycloakId) {
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

      // Load card transactions
      if (agentId || keycloakId) {
        try {
          // Load card-based transactions from agent service
          if (cardId) {
            const response = await cardApi.getCardTransactions(cardId);
            setTransactions(response.transactions || []);
          }
        } catch (err) {
          console.log("Transactions not available:", err.message);
        }
      }
    } catch (err) {
      console.error("Load data error:", err);
      setError(err.message || "Failed to load data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const onRefresh = () => {
    loadData(true);
  };

  const handleReadCard = async () => {
    try {
      setCardReaderState(CardReadingState.WAITING);
      setError("");

      // Read card from Nexgo N80 hardware (NFC/Chip/Swipe)
      console.log(
        "[CardTransactions] Reading card from Nexgo N80 with mode:",
        readingMode,
      );
      setCardReaderState(CardReadingState.READING);

      // Use Nexgo searchCard API - waits for NFC tap, chip insert, or swipe
      const cardInfo = await searchCard(60);

      // Success - beep to confirm
      await beep(100);

      setCardReaderState(CardReadingState.SUCCESS);

      // Transform Nexgo CardInfo to our format
      const cardData = {
        cardNo: cardInfo.cardNo,
        maskCardNo: cardInfo.maskCardNo,
        cardLast4: cardInfo.maskCardNo.slice(-4),
        expiredDate: cardInfo.expiredDate,
        cardType: determineCardType(cardInfo.cardNo),
        cardholderName: "CARDHOLDER",
        bank: "BANK",
        cardSlot: cardInfo.cardSlot,
        isICC: cardInfo.isICC,
        track1: cardInfo.track1,
        track2: cardInfo.track2,
        serviceCode: cardInfo.serviceCode,
        accountNumber: extractAccountFromTrack2(cardInfo.track2),
      };

      setCardData(cardData);

      // Auto-populate form
      setCardId(cardData.cardNo);
      setCardNumber(cardData.cardLast4);
      if (transactionType === "withdrawal" && cardData.accountNumber) {
        setCustomerAccount(cardData.accountNumber);
      }

      setSuccess(`Card detected: ${cardData.cardType} ${cardInfo.maskCardNo}`);

      console.log("[CardTransactions] Card read successfully from Nexgo N80:", {
        slot: cardInfo.cardSlot,
        masked: cardInfo.maskCardNo,
        type: cardData.cardType,
      });

      // Reset to idle after success message
      setTimeout(() => {
        setCardReaderState(CardReadingState.IDLE);
      }, 2000);
    } catch (err) {
      console.error("Card reading error:", err);
      setCardReaderState(CardReadingState.ERROR);

      if (err.code === "CARD_TIMEOUT") {
        setError("No card detected. Please try again.");
      } else if (err.code === "CARD_CANCELLED") {
        setError("Card reading cancelled.");
      } else {
        setError(err.message || "Failed to read card. Please try again.");
      }

      setTimeout(() => {
        setCardReaderState(CardReadingState.IDLE);
      }, 3000);
    }
  };

  // Helper to determine card type from PAN
  const determineCardType = (cardNo) => {
    if (!cardNo) return "CARD";
    const firstDigit = cardNo.charAt(0);
    const firstTwo = cardNo.substring(0, 2);

    if (firstDigit === "4") return "VISA";
    if (["51", "52", "53", "54", "55"].includes(firstTwo)) return "MASTERCARD";
    if (["34", "37"].includes(firstTwo)) return "AMEX";
    if (firstTwo === "60") return "VERVE";
    return "CARD";
  };

  // Helper to extract account number from track2 data
  const extractAccountFromTrack2 = (track2) => {
    if (!track2) return "";
    // Track2 format: PAN=YYMM... we just return empty for now
    // Real implementation would parse this based on card issuer
    return "";
  };

  const handleCancelCardRead = async () => {
    try {
      await stopCardSearch();
      setCardReaderState(CardReadingState.CANCELLED);
      setTimeout(() => {
        setCardReaderState(CardReadingState.IDLE);
      }, 500);
    } catch (err) {
      console.error("Cancel card read error:", err);
    }
  };

  const handleClearCard = () => {
    setCardData(null);
    setCardId("");
    setCardNumber("");
    setCardReaderState(CardReadingState.IDLE);
  };

  const toggleManualEntry = () => {
    setUseManualEntry(!useManualEntry);
    if (!useManualEntry) {
      handleClearCard();
    }
  };

  const getCardTypeIcon = (cardType) => {
    switch (cardType?.toUpperCase()) {
      case "VISA":
        return "credit-card";
      case "MASTERCARD":
        return "credit-card";
      case "VERVE":
        return "credit-card";
      case "AMEX":
        return "credit-card";
      default:
        return "credit-card-outline";
    }
  };

  const validateForm = () => {
    // Check if card data is available (either from reader or manual entry)
    if (
      !useManualEntry &&
      !cardData &&
      cardReaderState !== CardReadingState.SUCCESS
    ) {
      setError("Please tap or insert your card first");
      return false;
    }

    if (!cardNumber || cardNumber.length < 4) {
      setError("Please enter valid card number (last 4 digits)");
      return false;
    }

    if (transactionType === "withdrawal") {
      if (!customerAccount) {
        setError("Please enter customer account");
        return false;
      }
    }

    if (transactionType === "transfer") {
      if (!recipientAccount) {
        setError("Please enter recipient account");
        return false;
      }
      if (!recipientBank) {
        setError("Please enter recipient bank");
        return false;
      }
    }

    if (transactionType === "bills") {
      if (!billType) {
        setError("Please select bill type");
        return false;
      }
      if (!billerCode) {
        setError("Please enter biller code");
        return false;
      }
    }

    if (!amount || parseFloat(amount) <= 0) {
      setError("Please enter a valid amount");
      return false;
    }

    // Basic validation for account balance
    if (accountData) {
      const balance = accountData.balance / 100; // Convert from kobo to naira
      if (parseFloat(amount) > balance) {
        setError(
          `Insufficient balance. Available: ₦${formatCurrency(balance)}`,
        );
        return false;
      }
    }

    return true;
  };

  const handleCardWithdrawal = async () => {
    if (!validateForm()) {
      return;
    }

    try {
      setLoading(true);
      setError("");

      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      const agentId = await SecureStore.getItemAsync("agentId");

      if (!agentId) {
        throw new Error("Agent ID not found");
      }

      // Call cash out endpoint with card payment method
      const response = await accountApi.createCashOut({
        agent_id: agentId,
        customer_account: customerAccount,
        amount: parseFloat(amount),
        currency: "NGN",
        reference: reference || undefined,
        description: description || "Card withdrawal",
        payment_method: "card",
        card_number: cardNumber,
        card_id: cardId || undefined,
      });

      setSuccess(
        `Card withdrawal successful! Transaction ID: ${response.transaction_id}`,
      );

      // Reset form
      setCustomerAccount("");
      setAmount("");
      setReference("");
      setDescription("");
      setCardNumber("");
      setCardId("");

      // Reload data
      await loadData();
    } catch (err) {
      console.error("Card withdrawal error:", err);
      setError(err.message || "Failed to process card withdrawal");
    } finally {
      setLoading(false);
    }
  };

  const handleCardTransfer = async () => {
    if (!validateForm()) {
      return;
    }

    try {
      setLoading(true);
      setError("");

      // TODO: Implement card transfer API call
      // This would use the transfer service with card as payment method

      Alert.alert(
        "Coming Soon",
        "Card transfer functionality will be available soon.",
      );

      setSuccess("Transfer initiated successfully!");

      // Reset form
      setRecipientAccount("");
      setRecipientBank("");
      setAmount("");
      setReference("");
      setDescription("");
      setCardNumber("");
      setCardId("");
    } catch (err) {
      console.error("Card transfer error:", err);
      setError(err.message || "Failed to process card transfer");
    } finally {
      setLoading(false);
    }
  };

  const handleBillPayment = async () => {
    if (!validateForm()) {
      return;
    }

    try {
      setLoading(true);
      setError("");

      // TODO: Implement bills payment with card
      // This would use the bills payment service with card as payment method

      Alert.alert(
        "Coming Soon",
        "Card bill payment functionality will be available soon.",
      );

      setSuccess("Bill payment successful!");

      // Reset form
      setBillType("");
      setBillerCode("");
      setAmount("");
      setReference("");
      setDescription("");
      setCardNumber("");
      setCardId("");
    } catch (err) {
      console.error("Bill payment error:", err);
      setError(err.message || "Failed to process bill payment");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = () => {
    switch (transactionType) {
      case "withdrawal":
        handleCardWithdrawal();
        break;
      case "transfer":
        handleCardTransfer();
        break;
      case "bills":
        handleBillPayment();
        break;
      default:
        setError("Invalid transaction type");
    }
  };

  const renderWithdrawalForm = () => (
    <>
      <TextInput
        label="Customer Account *"
        value={customerAccount}
        onChangeText={setCustomerAccount}
        mode="outlined"
        style={styles.input}
        placeholder="Enter customer account number"
        keyboardType="numeric"
        left={<TextInput.Icon icon="account" />}
      />

      <TextInput
        label="Amount (₦) *"
        value={amount}
        onChangeText={setAmount}
        mode="outlined"
        style={styles.input}
        placeholder="0.00"
        keyboardType="decimal-pad"
        left={<TextInput.Icon icon="currency-ngn" />}
      />

      {/* Quick Amount Buttons */}
      <View style={styles.quickAmountContainer}>
        {[1000, 2000, 5000, 10000].map((value) => (
          <Chip
            key={value}
            mode="outlined"
            onPress={() => setAmount(value.toString())}
            style={styles.quickAmountChip}
          >
            ₦{formatCurrency(value)}
          </Chip>
        ))}
      </View>
    </>
  );

  const renderTransferForm = () => (
    <>
      <TextInput
        label="Recipient Account *"
        value={recipientAccount}
        onChangeText={setRecipientAccount}
        mode="outlined"
        style={styles.input}
        placeholder="Enter recipient account number"
        keyboardType="numeric"
        left={<TextInput.Icon icon="account" />}
      />

      <TextInput
        label="Recipient Bank *"
        value={recipientBank}
        onChangeText={setRecipientBank}
        mode="outlined"
        style={styles.input}
        placeholder="Enter bank name"
        left={<TextInput.Icon icon="bank" />}
      />

      <TextInput
        label="Amount (₦) *"
        value={amount}
        onChangeText={setAmount}
        mode="outlined"
        style={styles.input}
        placeholder="0.00"
        keyboardType="decimal-pad"
        left={<TextInput.Icon icon="currency-ngn" />}
      />
    </>
  );

  const renderBillsForm = () => (
    <>
      <View style={styles.billTypesContainer}>
        <Text variant="labelMedium" style={styles.billTypeLabel}>
          Bill Type *
        </Text>
        <View style={styles.billTypeChips}>
          {["Electricity", "Water", "Airtime", "Data", "Cable TV"].map(
            (type) => (
              <Chip
                key={type}
                mode={billType === type ? "flat" : "outlined"}
                selected={billType === type}
                onPress={() => setBillType(type)}
                style={styles.billTypeChip}
              >
                {type}
              </Chip>
            ),
          )}
        </View>
      </View>

      <TextInput
        label="Biller Code / Meter Number *"
        value={billerCode}
        onChangeText={setBillerCode}
        mode="outlined"
        style={styles.input}
        placeholder="Enter biller code or meter number"
        left={<TextInput.Icon icon="identifier" />}
      />

      <TextInput
        label="Amount (₦) *"
        value={amount}
        onChangeText={setAmount}
        mode="outlined"
        style={styles.input}
        placeholder="0.00"
        keyboardType="decimal-pad"
        left={<TextInput.Icon icon="currency-ngn" />}
      />
    </>
  );

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Account Balance Card */}
      {accountData && (
        <Card style={styles.balanceCard}>
          <Card.Content>
            <View style={styles.balanceRow}>
              <View>
                <Text variant="bodyMedium" style={styles.balanceLabel}>
                  Available Balance
                </Text>
                <Text variant="headlineMedium" style={styles.balanceAmount}>
                  ₦{formatCurrency(accountData.balance / 100)}
                </Text>
              </View>
              <Icon name="wallet" size={40} color="#10B981" />
            </View>
          </Card.Content>
        </Card>
      )}

      {/* Transaction Type Selector */}
      <Card style={styles.card}>
        <Card.Content>
          <View style={styles.cardTitleRow}>
            <Text variant="titleMedium" style={styles.cardTitle}>
              Card Transactions
            </Text>
            {deviceInfo && (
              <Chip
                icon="cellphone-nfc"
                mode="flat"
                compact
                style={styles.deviceChip}
                textStyle={styles.deviceChipText}
              >
                {deviceInfo.device}
              </Chip>
            )}
          </View>

          <SegmentedButtons
            value={transactionType}
            onValueChange={setTransactionType}
            buttons={[
              {
                value: "withdrawal",
                label: "Withdrawal",
                icon: "cash-refund",
              },
              {
                value: "transfer",
                label: "Transfer",
                icon: "bank-transfer",
              },
              {
                value: "bills",
                label: "Bills",
                icon: "receipt",
              },
            ]}
            style={styles.segmentedButtons}
          />

          {/* Card Information Section */}
          <View style={styles.cardInfoSection}>
            <View style={styles.sectionHeader}>
              <Text variant="labelLarge" style={styles.sectionTitle}>
                Card Information
              </Text>
              {readerSupported && (
                <Chip
                  icon={useManualEntry ? "keyboard" : "nfc"}
                  mode="outlined"
                  onPress={toggleManualEntry}
                  compact
                >
                  {useManualEntry ? "Manual" : "Auto"}
                </Chip>
              )}
            </View>

            {!useManualEntry && readerSupported ? (
              <>
                {/* Card Reader UI */}
                {cardData ? (
                  <View style={styles.cardDetectedContainer}>
                    <View style={styles.cardDetectedHeader}>
                      <Icon
                        name={getCardTypeIcon(cardData.cardType)}
                        size={32}
                        color="#10B981"
                      />
                      <View style={styles.cardDetectedInfo}>
                        <Text variant="titleMedium" style={styles.cardType}>
                          {cardData.cardType}
                        </Text>
                        <Text variant="bodyMedium" style={styles.cardNumber}>
                          •••• {cardData.cardLast4}
                        </Text>
                        <Text variant="bodySmall" style={styles.cardHolder}>
                          {cardData.cardholderName}
                        </Text>
                      </View>
                      <Button
                        mode="outlined"
                        onPress={handleClearCard}
                        compact
                        icon="close"
                      >
                        Clear
                      </Button>
                    </View>
                  </View>
                ) : (
                  <View style={styles.cardReaderContainer}>
                    {cardReaderState === CardReadingState.IDLE && (
                      <Button
                        mode="contained"
                        onPress={handleReadCard}
                        icon="contactless-payment"
                        style={styles.readCardButton}
                        contentStyle={styles.readCardButtonContent}
                      >
                        Tap or Insert Card
                      </Button>
                    )}

                    {cardReaderState === CardReadingState.WAITING && (
                      <View style={styles.waitingContainer}>
                        <Animated.View
                          style={[
                            styles.nfcIconContainer,
                            { transform: [{ scale: pulseAnim }] },
                          ]}
                        >
                          <Icon
                            name="contactless-payment"
                            size={80}
                            color={colors.primary}
                          />
                        </Animated.View>
                        <Text variant="titleMedium" style={styles.waitingText}>
                          Waiting for card...
                        </Text>
                        <Text variant="bodySmall" style={styles.waitingSubtext}>
                          {readingMode === CardReadingMode.NFC
                            ? "Tap your card on the NextGo N80 reader"
                            : "Insert your card into the NextGo N80 reader"}
                        </Text>
                        {deviceInfo && (
                          <View style={styles.deviceInfoContainer}>
                            <Icon name="cellphone" size={16} color="#6B7280" />
                            <Text
                              variant="bodySmall"
                              style={styles.deviceInfoText}
                            >
                              {deviceInfo.device} • NFC{" "}
                              {deviceInfo.nfc ? "✓" : "✗"} • Chip{" "}
                              {deviceInfo.chip ? "✓" : "✗"}
                            </Text>
                          </View>
                        )}
                        <Button
                          mode="outlined"
                          onPress={handleCancelCardRead}
                          style={styles.cancelButton}
                        >
                          Cancel
                        </Button>
                      </View>
                    )}

                    {cardReaderState === CardReadingState.READING && (
                      <View style={styles.readingContainer}>
                        <ActivityIndicator size="large" color={colors.primary} />
                        <Text variant="titleMedium" style={styles.readingText}>
                          Reading card...
                        </Text>
                      </View>
                    )}

                    {cardReaderState === CardReadingState.SUCCESS && (
                      <View style={styles.successContainer}>
                        <Icon name="check-circle" size={64} color="#10B981" />
                        <Text variant="titleMedium" style={styles.successText}>
                          Card Read Successfully!
                        </Text>
                      </View>
                    )}

                    {cardReaderState === CardReadingState.ERROR && (
                      <View style={styles.errorContainer}>
                        <Icon name="alert-circle" size={64} color="#EF4444" />
                        <Text variant="titleMedium" style={styles.errorText}>
                          Card Reading Failed
                        </Text>
                        <Button
                          mode="outlined"
                          onPress={handleReadCard}
                          style={styles.retryButton}
                        >
                          Try Again
                        </Button>
                      </View>
                    )}
                  </View>
                )}
              </>
            ) : (
              <>
                {/* Manual Entry Fallback */}
                <TextInput
                  label="Card Number (Last 4 digits) *"
                  value={cardNumber}
                  onChangeText={setCardNumber}
                  mode="outlined"
                  style={styles.input}
                  placeholder="1234"
                  keyboardType="numeric"
                  maxLength={4}
                  left={<TextInput.Icon icon="credit-card" />}
                />

                <TextInput
                  label="Card ID (Optional)"
                  value={cardId}
                  onChangeText={setCardId}
                  mode="outlined"
                  style={styles.input}
                  placeholder="Enter card ID if known"
                  left={<TextInput.Icon icon="identifier" />}
                />
              </>
            )}
          </View>

          {/* Transaction-specific forms */}
          <View style={styles.transactionFormSection}>
            <Text variant="labelLarge" style={styles.sectionTitle}>
              Transaction Details
            </Text>

            {transactionType === "withdrawal" && renderWithdrawalForm()}
            {transactionType === "transfer" && renderTransferForm()}
            {transactionType === "bills" && renderBillsForm()}

            {/* Common fields */}
            <TextInput
              label="Reference (Optional)"
              value={reference}
              onChangeText={setReference}
              mode="outlined"
              style={styles.input}
              placeholder="Transaction reference"
              left={<TextInput.Icon icon="barcode" />}
            />

            <TextInput
              label="Description (Optional)"
              value={description}
              onChangeText={setDescription}
              mode="outlined"
              style={styles.input}
              placeholder="Add a note"
              multiline
              numberOfLines={2}
              left={<TextInput.Icon icon="text" />}
            />
          </View>

          <Button
            mode="contained"
            onPress={handleSubmit}
            loading={loading}
            disabled={loading}
            style={styles.submitButton}
            icon={
              transactionType === "withdrawal"
                ? "cash-refund"
                : transactionType === "transfer"
                  ? "bank-transfer"
                  : "receipt"
            }
          >
            {transactionType === "withdrawal"
              ? "Process Withdrawal"
              : transactionType === "transfer"
                ? "Transfer Money"
                : "Pay Bill"}
          </Button>
        </Card.Content>
      </Card>

      {/* Recent Transactions */}
      {transactions.length > 0 && (
        <Card style={styles.card}>
          <Card.Content>
            <View style={styles.cardHeader}>
              <Text variant="titleMedium">Recent Card Transactions</Text>
              <Chip icon="history" mode="outlined">
                {transactions.length}
              </Chip>
            </View>

            <DataTable>
              <DataTable.Header>
                <DataTable.Title>Type</DataTable.Title>
                <DataTable.Title numeric>Amount</DataTable.Title>
                <DataTable.Title>Status</DataTable.Title>
              </DataTable.Header>

              {transactions.slice(0, 5).map((txn, index) => (
                <DataTable.Row key={index}>
                  <DataTable.Cell>{txn.transaction_type}</DataTable.Cell>
                  <DataTable.Cell numeric>
                    ₦{formatCurrency(txn.amount)}
                  </DataTable.Cell>
                  <DataTable.Cell>
                    <Chip
                      mode="flat"
                      style={{
                        backgroundColor:
                          txn.status === "completed" ? "#10B981" : "#F59E0B",
                      }}
                      textStyle={{ color: "white" }}
                    >
                      {txn.status}
                    </Chip>
                  </DataTable.Cell>
                </DataTable.Row>
              ))}
            </DataTable>
          </Card.Content>
        </Card>
      )}

      {/* Snackbars */}
      <Snackbar
        visible={!!error}
        onDismiss={() => setError("")}
        duration={5000}
        action={{
          label: "Dismiss",
          onPress: () => setError(""),
        }}
        style={{ backgroundColor: "#EF4444" }}
      >
        {error}
      </Snackbar>

      <Snackbar
        visible={!!success}
        onDismiss={() => setSuccess("")}
        duration={4000}
        action={{
          label: "OK",
          onPress: () => setSuccess(""),
        }}
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
    backgroundColor: "#F5F5F7",
  },
  balanceCard: {
    margin: spacing.md,
    backgroundColor: "#FFFFFF",
    elevation: 2,
  },
  balanceRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  balanceLabel: {
    color: "#6B7280",
    marginBottom: spacing.xs,
  },
  balanceAmount: {
    fontWeight: "bold",
    color: "#10B981",
  },
  card: {
    margin: spacing.md,
    backgroundColor: "#FFFFFF",
    elevation: 2,
  },
  cardTitleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  cardTitle: {
    fontWeight: "600",
  },
  deviceChip: {
    backgroundColor: colors.primary,
    height: 28,
  },
  deviceChipText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "600",
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  segmentedButtons: {
    marginBottom: spacing.lg,
  },
  cardInfoSection: {
    marginTop: spacing.md,
    marginBottom: spacing.lg,
  },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  cardReaderContainer: {
    backgroundColor: "#F9FAFB",
    borderRadius: 12,
    padding: spacing.lg,
    alignItems: "center",
    minHeight: 200,
    justifyContent: "center",
  },
  readCardButton: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  readCardButtonContent: {
    height: 56,
  },
  waitingContainer: {
    alignItems: "center",
    gap: spacing.md,
  },
  nfcIconContainer: {
    marginBottom: spacing.md,
  },
  waitingText: {
    fontWeight: "600",
    color: "#374151",
    textAlign: "center",
  },
  waitingSubtext: {
    color: "#6B7280",
    textAlign: "center",
    marginBottom: spacing.md,
  },
  deviceInfoContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  deviceInfoText: {
    color: "#6B7280",
    fontSize: 11,
  },
  cancelButton: {
    marginTop: spacing.sm,
  },
  readingContainer: {
    alignItems: "center",
    gap: spacing.md,
  },
  readingText: {
    fontWeight: "600",
    color: "#374151",
  },
  successContainer: {
    alignItems: "center",
    gap: spacing.md,
  },
  successText: {
    fontWeight: "600",
    color: "#10B981",
  },
  errorContainer: {
    alignItems: "center",
    gap: spacing.md,
  },
  errorText: {
    fontWeight: "600",
    color: "#EF4444",
  },
  retryButton: {
    marginTop: spacing.sm,
  },
  cardDetectedContainer: {
    backgroundColor: "#F0FDF4",
    borderRadius: 12,
    padding: spacing.lg,
    borderWidth: 2,
    borderColor: "#10B981",
  },
  cardDetectedHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  cardDetectedInfo: {
    flex: 1,
  },
  cardType: {
    fontWeight: "600",
    color: "#374151",
  },
  cardNumber: {
    color: "#6B7280",
    marginTop: spacing.xs,
  },
  cardHolder: {
    color: "#9CA3AF",
    marginTop: spacing.xs,
  },
  transactionFormSection: {
    marginTop: spacing.md,
  },
  sectionTitle: {
    marginBottom: spacing.md,
    color: "#374151",
    fontWeight: "600",
  },
  input: {
    marginBottom: spacing.md,
  },
  quickAmountContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  quickAmountChip: {
    marginRight: spacing.sm,
    marginBottom: spacing.sm,
  },
  billTypesContainer: {
    marginBottom: spacing.md,
  },
  billTypeLabel: {
    marginBottom: spacing.sm,
    color: "#374151",
  },
  billTypeChips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  billTypeChip: {
    marginRight: spacing.sm,
    marginBottom: spacing.sm,
  },
  submitButton: {
    marginTop: spacing.lg,
    paddingVertical: spacing.xs,
  },
});

import * as SecureStore from "expo-secure-store";
import React, { useCallback, useEffect, useState } from "react";
import {
    ActivityIndicator,
    Alert,
    Animated,
    KeyboardAvoidingView,
    Platform,
    RefreshControl,
    ScrollView,
    StyleSheet,
    TouchableOpacity,
    View,
} from "react-native";
import {
    Button,
    Card,
    Chip,
    DataTable,
    Divider,
    Snackbar,
    Text,
    TextInput,
    useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import {
    beep,
    isSunmiAvailable,
    onMultipleCards,
    onSwipeIncorrect,
    searchCard,
    stopCardSearch,
} from "../../lib/sunmi";
import {
  accountApi,
  agentApi,
  cardApi,
  inventoryApi,
  ledgerApi,
} from "../../services/apiService";
import { spacing } from "../../theme";
import { formatCurrency } from "../../utils/formatters";
export default function CashOutScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const theme = useTheme();
  const [step, setStep] = useState(1); // 1: Amount, 2: Card Read/Manual Entry, 3: PIN Confirmation

  // Transaction details
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const [description, setDescription] = useState("");

  // Customer card details
  const [cardNumber, setCardNumber] = useState("");
  const [cardProvider, setCardProvider] = useState("");
  const [accountType, setAccountType] = useState("");
  const [expiryDate, setExpiryDate] = useState("");
  const [cvv, setCvv] = useState("");
  const [pin, setPin] = useState("");

  // PIN entry display
  const [showPin, setShowPin] = useState(false);

  // Card reader state
  const [cardReaderState, setCardReaderState] = useState("idle"); // idle, waiting, reading, success, error
  const [cardData, setCardData] = useState(null);
  const [resolvedCustomerAccount, setResolvedCustomerAccount] = useState("");
  const [resolvedCardId, setResolvedCardId] = useState("");
  const [useManualEntry, setUseManualEntry] = useState(false);
  const [pulseAnim] = useState(new Animated.Value(1));

  const [agentData, setAgentData] = useState(null);
  const [accountData, setAccountData] = useState(null);
  const [recentWithdrawals, setRecentWithdrawals] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [snackbarVisible, setSnackbarVisible] = useState(false);

  const accountTypes = [
    { value: "Savings", label: "Savings Account" },
    { value: "Current", label: "Current Account" },
    { value: "Not Sure", label: "Not Sure" },
  ];

  useEffect(() => {
    loadData();

    // If Nexgo hardware isn't available (e.g. dev build / non-Nexgo device),
    // skip the card reader UI and go straight to manual entry.
    if (!isSunmiAvailable()) {
      setUseManualEntry(true);
    }

    // Setup event listeners for card events
    const swipeListener = onSwipeIncorrect(() => {
      showError("Swipe error, please try again");
      setCardReaderState("error");
    });

    const multiCardListener = onMultipleCards(() => {
      showError("Multiple cards detected, please remove one");
      setCardReaderState("error");
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
    if (cardReaderState === "waiting" || cardReaderState === "reading") {
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

      const keycloakId = await SecureStore.getItemAsync("keycloakId");

      if (!keycloakId) {
        Alert.alert("Error", "Session expired. Please login again.");
        return;
      }

      // Load agent data
      const agentResponse = await agentApi.getAgentByKeycloakId(keycloakId);
      setAgentData(agentResponse.agent || agentResponse);

      // Load account data
      const accountResponse =
        await accountApi.getAccountByKeycloakId(keycloakId);

      const accountsData = Array.isArray(accountResponse)
        ? accountResponse
        : Array.isArray(accountResponse?.accounts)
          ? accountResponse.accounts
          : Array.isArray(accountResponse?.data)
            ? accountResponse.data
            : Array.isArray(accountResponse?.data?.accounts)
              ? accountResponse.data.accounts
              : accountResponse?.account
                ? [accountResponse.account]
                : accountResponse?.data?.account
                  ? [accountResponse.data.account]
                  : accountResponse?.account_number ||
                      accountResponse?.data?.account_number
                    ? [
                        accountResponse?.account_number
                          ? accountResponse
                          : accountResponse.data,
                      ]
                    : [];

      const primaryAccount = accountsData.find((acc) => acc?.account_number);
      setAccountData(primaryAccount || null);

      const accountNumbers = accountsData
        .map((acc) => acc?.account_number)
        .filter(Boolean);

      try {
        const storesResponse = await inventoryApi.getStores(keycloakId);
        const stores = Array.isArray(storesResponse?.data)
          ? storesResponse.data
          : Array.isArray(storesResponse)
            ? storesResponse
            : [];

        stores.forEach((store) => {
          if (store?.account_number) {
            accountNumbers.push(store.account_number);
          }
        });
      } catch (storesErr) {
        console.error("Failed to fetch store accounts:", storesErr);
      }

      const allAccountNumbers = [...new Set(accountNumbers)];

      // Load recent cash out transactions from ledger (same pattern as agent dashboard)
      if (allAccountNumbers.length === 0) {
        setRecentWithdrawals([]);
      } else {
        const responses = await Promise.all(
          allAccountNumbers.map((accountNumber) =>
            ledgerApi
              .getTransactionsByAccountNumber(accountNumber, 10, 1)
              .then((response) => ({ response }))
              .catch((err) => {
                console.error(
                  `Failed fetching transactions for ${accountNumber}:`,
                  err,
                );
                return { response: null };
              }),
          ),
        );

        const allTransactions = responses.flatMap(({ response }) =>
          Array.isArray(response?.transactions)
            ? response.transactions
            : Array.isArray(response?.data?.transactions)
              ? response.data.transactions
              : Array.isArray(response?.data)
                ? response.data
                : Array.isArray(response)
                  ? response
                  : [],
        );

        const normalizeAccount = (value) =>
          String(value ?? "")
            .trim()
            .toLowerCase();

        const normalizedAccounts = new Set(
          allAccountNumbers.map((acc) => normalizeAccount(acc)),
        );

        // Transaction screen parity: debit if payer account is one of the user's accounts.
        const withdrawals = allTransactions.filter((txn) => {
          const payerAccount = normalizeAccount(txn?.payer_account_number);
          return normalizedAccounts.has(payerAccount);
        });

        setRecentWithdrawals(withdrawals);
      }
    } catch (err) {
      console.error("Error loading cash out data:", err);
      showError(err.message || "Failed to load data. Please try again.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const onRefresh = useCallback(() => {
    loadData(true);
  }, [loadData]);

  const showError = (message) => {
    setError(message);
    setSnackbarVisible(true);
  };

  const showSuccess = (message) => {
    setSuccess(message);
    setSnackbarVisible(true);
  };

  const detectCardProvider = (number) => {
    const cleaned = number.replace(/\s/g, "");
    if (
      cleaned.startsWith("4") ||
      cleaned.startsWith("50") ||
      cleaned.startsWith("65")
    ) {
      return "Verve";
    }
    if (cleaned.startsWith("5")) {
      return "Mastercard";
    }
    if (cleaned.startsWith("6")) {
      return "Verve";
    }
    return "";
  };

  const formatCardNumber = (text) => {
    const cleaned = text.replace(/\s/g, "");
    const chunks = cleaned.match(/.{1,4}/g);
    return chunks ? chunks.join(" ") : cleaned;
  };

  const handleCardNumberChange = (text) => {
    const cleaned = text.replace(/\s/g, "");
    if (cleaned.length <= 19) {
      setCardNumber(cleaned);
      setCardProvider(detectCardProvider(cleaned));
    }
  };

  const handleExpiryChange = (text) => {
    const cleaned = text.replace(/[^\d]/g, "");
    if (cleaned.length <= 4) {
      if (cleaned.length >= 2) {
        setExpiryDate(cleaned.substring(0, 2) + " / " + cleaned.substring(2));
      } else {
        setExpiryDate(cleaned);
      }
    }
  };

  const handlePinInput = (value) => {
    if (value.length <= 4) {
      setPin(value);
    }
  };

  const getDigitsOnly = (value) => String(value ?? "").replace(/\D/g, "");

  const extractPanFromTrack2 = (track2) => {
    if (!track2) return "";
    const parts = String(track2).split("=");
    return getDigitsOnly(parts[0] || "");
  };

  const resolveCardNumberForRequest = () => {
    const fromState = getDigitsOnly(cardNumber);
    if (fromState.length >= 12) return fromState;

    const fromCardNo = getDigitsOnly(cardData?.cardNo);
    if (fromCardNo.length >= 12) return fromCardNo;

    const fromTrack2 = extractPanFromTrack2(cardData?.track2);
    if (fromTrack2.length >= 12) return fromTrack2;

    // Last resort if SDK exposes only masked PAN; backend may still reject this,
    // but it allows us to avoid false local validation failures.
    const fromMasked = getDigitsOnly(cardData?.maskCardNo);
    if (fromMasked.length >= 12) return fromMasked;

    return "";
  };

  const normalizeExpiryForDisplay = (rawExpiry) => {
    const digits = getDigitsOnly(rawExpiry);
    if (digits.length !== 4) return "";

    // Sunmi commonly returns YYMM from track2 (e.g. 2804 => 04 / 28).
    const yy = digits.substring(0, 2);
    const mm = digits.substring(2, 4);
    return `${mm} / ${yy}`;
  };

  const handleContinueToCard = () => {
    setError("");

    if (!amount || parseFloat(amount) <= 0) {
      showError("Please enter a valid withdrawal amount");
      return;
    }

    const amountInKobo = parseFloat(amount);
    if (accountData && amountInKobo > accountData.balance) {
      showError("Insufficient balance in your agent wallet");
      return;
    }

    setStep(2);
  };

  const handleReadCard = async () => {
    try {
      setCardReaderState("waiting");
      setError("");

      // Read card from Nexgo hardware (NFC/Chip/Swipe)
      console.log("[CashOut] Reading card from  device...");
      setCardReaderState("reading");
      console.log("[CashOut] Checking printer status before reading card...");

      // Use Nexgo searchCard API - waits for NFC tap, chip insert, or swipe
      console.log("[CashOut] Initiating card search with Nexgo SDK...");
      const cardInfo = await searchCard(60);
      // console.log("[CashOut] Card info received from device:", cardInfo);

      // Success - beep to confirm
      await beep(100);

      setCardReaderState("success");

      // Extract account number from track2 data
      const extractAccountFromTrack2 = (track2) => {
        if (!track2) return "";
        // Track 2 format: PAN=expiry_date_service_code_discretionary_data
        const parts = track2.split("=");
        return parts[0] || "";
      };

      // Determine card type from card number
      const determineCardType = (cardNo = "") => {
  if (!cardNo) return "Unknown";

  const first = cardNo.charAt(0);

  if (first === "4") return "Visa";
  if (first === "5") return "Mastercard";
  if (first === "6") return "Verve";

  return "Unknown";
};

      // Transform Nexgo CardInfo to our format
      const cardDataObj = {
  cardNo: cardInfo.cardNo,
  maskCardNo: cardInfo.maskCardNo,

  track1: cardInfo.track1,
  track2: cardInfo.track2,
  track3: cardInfo.track3,

  // derived safely in JS
  cardLast4: cardInfo.maskCardNo?.slice(-4) || "",

  cardType: determineCardType(cardInfo.cardNo || ""),
};

      setCardData(cardDataObj);

      try {
        const lookup = await cardApi.lookupCardByNumber(cardInfo.cardNo);
        const foundCard = lookup?.card || lookup;
        setResolvedCardId(foundCard?.card_id || foundCard?.cardId || "");
        setResolvedCustomerAccount(foundCard?.account_id || "");
      } catch (lookupErr) {
        console.warn("[CashOut] Card lookup failed:", lookupErr?.message || lookupErr);
        setResolvedCardId("");
        setResolvedCustomerAccount("");
      }

      // Auto-populate form
      setCardNumber(cardInfo.cardNo);
      setExpiryDate(
        normalizeExpiryForDisplay(cardInfo.expiredDate || cardInfo.expireDate),
      );
      setCardProvider(cardDataObj.cardType);
      setAccountType((prev) => prev || "Savings");

      showSuccess(
        `Card detected: ${cardDataObj.cardType} ${cardInfo.maskCardNo}`,
      );

      // Card-present flow: jump directly to PIN-only step.
      setUseManualEntry(false);
      setStep(3);

      console.log("[CashOut] Card read successfully:", {
        slot: cardInfo.cardSlot,
        masked: cardInfo.maskCardNo,
        type: cardDataObj.cardType,
      });
    } catch (err) {
      console.error("[CashOut] Card reading error:", err);
      setCardReaderState("error");
      showError(err.message || "Failed to read card. Please try manual entry.");
    }
  };

  const handleCancelCardReading = async () => {
    try {
      await stopCardSearch();
      setCardReaderState("idle");
    } catch (err) {
      console.error("Error stopping card search:", err);
    }
  };

  const handleSubmitWithdrawal = async () => {
    setError("");

    const isManualFlow = useManualEntry;
    const isCardReadFlow = !useManualEntry && !!cardData;
    const resolvedCardNumber = resolveCardNumberForRequest();

    // Validate card details
    if (!resolvedCardNumber || resolvedCardNumber.length < 12) {
      showError("Please enter a valid card number");
      return;
    }

    if (isManualFlow && (!expiryDate || expiryDate.length < 7)) {
      showError("Please enter card expiry date (MM / YY)");
      return;
    }

    if (isManualFlow && (!cvv || cvv.length < 3)) {
      showError("Please enter CVV");
      return;
    }

    if (isManualFlow && !accountType) {
      showError("Please select account type");
      return;
    }

    if (!isManualFlow && !isCardReadFlow) {
      showError("Read card or switch to manual entry to continue");
      return;
    }

    if (!isManualFlow && (!resolvedCardId || !resolvedCustomerAccount)) {
      showError(
        "Card details could not be resolved. Please use manual entry or try another card.",
      );
      return;
    }

    if (!pin || pin.length !== 4) {
      showError("Please enter 4-digit PIN");
      return;
    }

    setSubmitting(true);

    try {
      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      const storedAgentId = await SecureStore.getItemAsync("agentId");

      if (!keycloakId) {
        throw new Error("Session expired. Please login again.");
      }

      const candidateAgentIds = [
        agentData?.agent_id,
        agentData?.id,
        agentData?.keycloak_id,
        agentData?.keycloakId,
        storedAgentId,
        keycloakId,
      ]
        .map((id) => (id == null ? "" : String(id).trim()))
        .filter(Boolean);

      const uniqueAgentIds = [...new Set(candidateAgentIds)];

      const payloadBase = {
        customer_account: resolvedCustomerAccount,
        customer_card_number: resolvedCardNumber,
        card_number: resolvedCardNumber,
        amount: parseFloat(amount),
        currency: "NGN",
        reference: reference || `CASHOUT-${Date.now()}`,
        description: description || "Cash withdrawal",
        payment_method: "card",
        card_details: {
          card_number: resolvedCardNumber,
          expiry: expiryDate || "",
          cvv: isManualFlow ? cvv : "",
          account_type: isManualFlow ? accountType : accountType || "Savings",
          pin: pin,
        },
      };

      let lastCashOutError = null;
      let submitted = false;

      for (const agentIdCandidate of uniqueAgentIds) {
        try {
          await accountApi.createCashOut({
            ...payloadBase,
            agent_id: agentIdCandidate,
            card_id: isManualFlow ? undefined : resolvedCardId,
          });
          submitted = true;
          break;
        } catch (submitErr) {
          lastCashOutError = submitErr;
          const message = String(submitErr?.message || "").toLowerCase();
          const isNotFound = message.includes("not found") || message.includes("404");

          if (!isNotFound) {
            throw submitErr;
          }
        }
      }

      if (!submitted) {
        throw lastCashOutError || new Error("Failed to process withdrawal");
      }

      showSuccess("Cash withdrawal successful!");

      // Reset form
      setTimeout(() => {
        setStep(1);
        setAmount("");
        setReference("");
        setDescription("");
        setCardNumber("");
        setCardProvider("");
        setAccountType("");
        setExpiryDate("");
        setCvv("");
        setPin("");
        setCardData(null);
        setCardReaderState("idle");
        setUseManualEntry(false);
        loadData();
      }, 2000);
    } catch (err) {
      console.error("Cash out error:", err);
      showError(
        err.message || "Failed to process withdrawal. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case "completed":
      case "success":
        return "#10B981";
      case "pending":
        return "#F59E0B";
      case "failed":
        return theme.colors.error;
      default:
        return "#6B7280";
    }
  };

  const getStatusIcon = (status) => {
    switch (status?.toLowerCase()) {
      case "completed":
      case "success":
        return "check-circle";
      case "pending":
        return "clock-outline";
      case "failed":
        return "close-circle";
      default:
        return "help-circle";
    }
  };

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={theme.colors.primary} />
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : null}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {/* Header Card */}
        <Card style={styles.headerCard}>
          <Card.Content>
            <View style={styles.headerContent}>
              <Icon name="cash-minus" size={40} color={theme.colors.primary} />
              <View style={styles.headerText}>
                <Text style={styles.headerTitle}>Cash Withdrawal</Text>
                <Text style={styles.headerSubtitle}>
                  Process customer cash withdrawal
                </Text>
              </View>
            </View>
          </Card.Content>
        </Card>

        {/* Balance Card */}
        <Card style={styles.balanceCard}>
          <Card.Content>
            <View style={styles.balanceRow}>
              <View>
                <Text style={styles.balanceLabel}>Your Agent Balance</Text>
                <Text style={styles.balanceAmount}>
                  {formatCurrency(accountData?.balance || 0)}
                </Text>
              </View>
              <Icon name="wallet" size={32} color={theme.colors.primary} />
            </View>
          </Card.Content>
        </Card>

        {/* Step 1: Amount */}
        {step === 1 && (
          <Card style={styles.formCard}>
            <Card.Content>
              <Text style={styles.cardTitle}>Enter Withdrawal Amount</Text>
              <Divider style={styles.divider} />

              <View style={styles.inputGroup}>
                <Text style={styles.label}>Amount *</Text>
                <TextInput
                  mode="outlined"
                  value={amount}
                  onChangeText={setAmount}
                  placeholder="0.00"
                  keyboardType="numeric"
                  left={<TextInput.Icon icon="currency-ngn" />}
                  style={styles.input}
                  outlineColor="#D1D5DB"
                  activeOutlineColor={theme.colors.primary}
                />
              </View>

              {/*<View style={styles.inputGroup}>
                <Text style={styles.label}>Reference (Optional)</Text>
                <TextInput
                  mode="outlined"
                  value={reference}
                  onChangeText={setReference}
                  placeholder="Transaction reference"
                  left={<TextInput.Icon icon="pound" />}
                  style={styles.input}
                  outlineColor="#D1D5DB"
                  activeOutlineColor={theme.colors.primary}
                />
              </View>*/}

              <View style={styles.inputGroup}>
                <Text style={styles.label}>Description (Optional)</Text>
                <TextInput
                  mode="outlined"
                  value={description}
                  onChangeText={setDescription}
                  placeholder="Add a note"
                  multiline
                  numberOfLines={3}
                  left={<TextInput.Icon icon="note-text" />}
                  style={styles.input}
                  outlineColor="#D1D5DB"
                  activeOutlineColor={theme.colors.primary}
                />
              </View>

              <Button
                mode="contained"
                onPress={handleContinueToCard}
                style={styles.continueButton}
                icon="arrow-right"
                contentStyle={styles.buttonContent}
              >
                Continue to Card Details
              </Button>
            </Card.Content>
          </Card>
        )}

        {/* Step 2: Card Details */}
        {step === 2 && (
          <Card style={styles.formCard}>
            <Card.Content>
              <View style={styles.cardHeader}>
                <TouchableOpacity onPress={() => setStep(1)}>
                  <Icon name="arrow-left" size={24} color="#374151" />
                </TouchableOpacity>
                <Text style={styles.cardTitle}>Customer Card Details</Text>
                <View style={{ width: 24 }} />
              </View>

              <View style={styles.amountDisplay}>
                <Text style={styles.amountDisplayLabel}>Withdrawal Amount</Text>
                <Text style={styles.amountDisplayValue}>
                  {formatCurrency(parseFloat(amount))}
                </Text>
              </View>

              <Divider style={styles.divider} />

              {/* Card Reader Section */}
              {!useManualEntry && (
                <View style={styles.cardReaderSection}>
                  <View style={styles.cardReaderHeader}>
                    <Icon
                      name="contactless-payment"
                      size={32}
                      color={theme.colors.primary}
                    />
                    <Text style={styles.cardReaderTitle}>
                      Insert or Tap Customer Card
                    </Text>
                  </View>

                  {cardReaderState === "idle" && (
                    <View>
                      <Button
                        mode="contained"
                        onPress={handleReadCard}
                        style={styles.readCardButton}
                        icon="credit-card-scan"
                        contentStyle={styles.buttonContent}
                      >
                        Read Card (NFC/Chip)
                      </Button>
                      <Button
                        mode="text"
                        onPress={() => setUseManualEntry(true)}
                        style={{ marginTop: spacing.sm }}
                      >
                        Enter Card Details Manually
                      </Button>
                    </View>
                  )}

                  {(cardReaderState === "waiting" ||
                    cardReaderState === "reading") && (
                    <View style={styles.cardReadingContainer}>
                      <Animated.View
                        style={{
                          transform: [{ scale: pulseAnim }],
                        }}
                      >
                        <Icon
                          name="contactless-payment"
                          size={64}
                          color={theme.colors.primary}
                        />
                      </Animated.View>
                      <Text style={styles.cardReadingText}>
                        {cardReaderState === "waiting"
                          ? "Waiting for card..."
                          : "Reading card..."}
                      </Text>
                      <ActivityIndicator
                        size="large"
                        color={theme.colors.primary}
                      />
                      <Button
                        mode="outlined"
                        onPress={handleCancelCardReading}
                        style={{ marginTop: spacing.md }}
                        icon="close"
                      >
                        Cancel
                      </Button>
                    </View>
                  )}

                  {cardReaderState === "success" && cardData && (
                    <View style={styles.cardSuccessContainer}>
                      <Icon name="check-circle" size={48} color="#10B981" />
                      <Text style={styles.cardSuccessText}>
                        Card Read Successfully!
                      </Text>
                      <View style={styles.cardInfoBox}>
                        <Text style={styles.cardInfoLabel}>Card Type:</Text>
                        <Text style={styles.cardInfoValue}>
                          {cardData.cardType}
                        </Text>
                      </View>
                      <View style={styles.cardInfoBox}>
                        <Text style={styles.cardInfoLabel}>Card Number:</Text>
                        <Text style={styles.cardInfoValue}>
                          {cardData.maskCardNo}
                        </Text>
                      </View>
                      <View style={styles.cardInfoBox}>
                        <Text style={styles.cardInfoLabel}>Read Method:</Text>
                        <Text style={styles.cardInfoValue}>
                          {cardData.cardSlot === "ICC1"
                            ? "Chip"
                            : cardData.cardSlot}
                        </Text>
                      </View>
                    </View>
                  )}

                  {cardReaderState === "error" && (
                    <View style={styles.cardErrorContainer}>
                      <Icon name="alert-circle" size={48} color="#EF4444" />
                      <Text style={styles.cardErrorText}>
                        Failed to read card
                      </Text>
                      <Button
                        mode="contained"
                        onPress={handleReadCard}
                        style={{ marginTop: spacing.md }}
                        icon="refresh"
                      >
                        Try Again
                      </Button>
                      <Button
                        mode="text"
                        onPress={() => setUseManualEntry(true)}
                        style={{ marginTop: spacing.sm }}
                      >
                        Enter Manually Instead
                      </Button>
                    </View>
                  )}

                  {cardReaderState === "success" && (
                    <Divider style={styles.divider} />
                  )}
                </View>
              )}

              {/* Manual Card Entry Fields */}
              {useManualEntry && (
                <View>
                  {useManualEntry && (
                    <View style={styles.manualEntryHeader}>
                      <Text style={styles.manualEntryTitle}>
                        Manual Card Entry
                      </Text>
                      <Button
                        mode="text"
                        onPress={() => {
                          setUseManualEntry(false);
                          setCardReaderState("idle");
                        }}
                      >
                        Use Card Reader
                      </Button>
                    </View>
                  )}

                  {/* Card Number */}
                  <View style={styles.inputGroup}>
                    <Text style={styles.label}>Card Number *</Text>
                    <TextInput
                      mode="outlined"
                      value={formatCardNumber(cardNumber)}
                      onChangeText={handleCardNumberChange}
                      placeholder="0000 0000 0000 0000"
                      keyboardType="numeric"
                      left={<TextInput.Icon icon="credit-card" />}
                      right={
                        cardProvider ? (
                          <TextInput.Affix text={cardProvider} />
                        ) : null
                      }
                      style={styles.input}
                      outlineColor="#D1D5DB"
                      activeOutlineColor={theme.colors.primary}
                    />
                  </View>

                  {/* Account Type */}
                  <View style={styles.inputGroup}>
                    <Text style={styles.label}>Account Type *</Text>
                    <View style={styles.accountTypeContainer}>
                      {accountTypes.map((type) => (
                        <Chip
                          key={type.value}
                          selected={accountType === type.value}
                          onPress={() => setAccountType(type.value)}
                          style={[
                            styles.accountTypeChip,
                            accountType === type.value &&
                              styles.accountTypeChipSelected,
                          ]}
                          textStyle={[
                            styles.accountTypeChipText,
                            accountType === type.value &&
                              styles.accountTypeChipTextSelected,
                          ]}
                        >
                          {type.label}
                        </Chip>
                      ))}
                    </View>
                  </View>

                  {/* Expiry and CVV */}
                  <View style={styles.row}>
                    <View
                      style={[
                        styles.inputGroup,
                        { flex: 1, marginRight: spacing.sm },
                      ]}
                    >
                      <Text style={styles.label}>Expiry Date *</Text>
                      <TextInput
                        mode="outlined"
                        value={expiryDate}
                        onChangeText={handleExpiryChange}
                        placeholder="MM / YY"
                        keyboardType="numeric"
                        style={styles.input}
                        outlineColor="#D1D5DB"
                        activeOutlineColor={theme.colors.primary}
                      />
                    </View>

                    <View style={[styles.inputGroup, { flex: 1 }]}>
                      <Text style={styles.label}>CVV *</Text>
                      <TextInput
                        mode="outlined"
                        value={cvv}
                        onChangeText={(text) =>
                          text.length <= 3 && setCvv(text)
                        }
                        placeholder="123"
                        keyboardType="numeric"
                        secureTextEntry
                        maxLength={3}
                        style={styles.input}
                        outlineColor="#D1D5DB"
                        activeOutlineColor={theme.colors.primary}
                      />
                    </View>
                  </View>

                  {/* PIN */}
                  <View style={styles.inputGroup}>
                    <Text style={styles.label}>PIN *</Text>
                    <TextInput
                      mode="outlined"
                      value={pin}
                      onChangeText={handlePinInput}
                      placeholder="Enter 4-digit PIN"
                      keyboardType="numeric"
                      secureTextEntry={!showPin}
                      maxLength={4}
                      left={<TextInput.Icon icon="lock" />}
                      right={
                        <TextInput.Icon
                          icon={showPin ? "eye-off" : "eye"}
                          onPress={() => setShowPin(!showPin)}
                        />
                      }
                      style={styles.input}
                      outlineColor="#D1D5DB"
                      activeOutlineColor={theme.colors.primary}
                    />
                  </View>

                  <View style={styles.securityInfo}>
                    <Icon name="shield-check" size={20} color="#10B981" />
                    <Text style={styles.securityInfoText}>
                      All card details are encrypted and secure
                    </Text>
                  </View>
                </View>
              )}

              {/* Submit Button - shown only for manual entry in Step 2 */}
              {useManualEntry && (
                <View>
                  <Button
                    mode="contained"
                    onPress={handleSubmitWithdrawal}
                    loading={submitting}
                    disabled={submitting}
                    style={styles.submitButton}
                    icon="check"
                    contentStyle={styles.buttonContent}
                  >
                    {submitting ? "Processing..." : "Process Withdrawal"}
                  </Button>

                  <Button
                    mode="text"
                    onPress={() => setStep(1)}
                    style={styles.cancelButton}
                  >
                    Cancel
                  </Button>
                </View>
              )}
            </Card.Content>
          </Card>
        )}

        {/* Step 3: PIN Confirmation (card-read flow) */}
        {step === 3 && (
          <Card style={styles.formCard}>
            <Card.Content>
              <View style={styles.cardHeader}>
                <TouchableOpacity onPress={() => setStep(2)}>
                  <Icon name="arrow-left" size={24} color="#374151" />
                </TouchableOpacity>
                <Text style={styles.cardTitle}>Enter PIN</Text>
                <View style={{ width: 24 }} />
              </View>

              <View style={styles.amountDisplay}>
                <Text style={styles.amountDisplayLabel}>Withdrawal Amount</Text>
                <Text style={styles.amountDisplayValue}>
                  {formatCurrency(parseFloat(amount))}
                </Text>
              </View>

              <View style={styles.cardSuccessContainer}>
                <Icon name="check-circle" size={48} color="#10B981" />
                <Text style={styles.cardSuccessText}>Card Read Successfully</Text>
                <View style={styles.cardInfoBox}>
                  <Text style={styles.cardInfoLabel}>Card:</Text>
                  <Text style={styles.cardInfoValue}>
                    {cardData?.maskCardNo || formatCardNumber(cardNumber)}
                  </Text>
                </View>
              </View>

              <Divider style={styles.divider} />

              <View style={styles.inputGroup}>
                <Text style={styles.label}>PIN *</Text>
                <TextInput
                  mode="outlined"
                  value={pin}
                  onChangeText={handlePinInput}
                  placeholder="Enter 4-digit PIN"
                  keyboardType="numeric"
                  secureTextEntry={!showPin}
                  maxLength={4}
                  left={<TextInput.Icon icon="lock" />}
                  right={
                    <TextInput.Icon
                      icon={showPin ? "eye-off" : "eye"}
                      onPress={() => setShowPin(!showPin)}
                    />
                  }
                  style={styles.input}
                  outlineColor="#D1D5DB"
                  activeOutlineColor={theme.colors.primary}
                />
              </View>

              <Button
                mode="contained"
                onPress={handleSubmitWithdrawal}
                loading={submitting}
                disabled={submitting}
                style={styles.submitButton}
                icon="check"
                contentStyle={styles.buttonContent}
              >
                {submitting ? "Processing..." : "Process Withdrawal"}
              </Button>

              <Button
                mode="text"
                onPress={() => {
                  setStep(1);
                  setCardReaderState("idle");
                  setCardData(null);
                  setPin("");
                }}
                style={styles.cancelButton}
              >
                Cancel
              </Button>
            </Card.Content>
          </Card>
        )}

        {/* Recent Withdrawals */}
        <Card style={styles.transactionsCard}>
          <Card.Content>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>Recent Withdrawals</Text>
              <Chip style={styles.countChip} textStyle={styles.countChipText}>
                {recentWithdrawals.length}
              </Chip>
            </View>

            {recentWithdrawals.length === 0 ? (
              <View style={styles.emptyState}>
                <Icon name="inbox" size={48} color="#D1D5DB" />
                <Text style={styles.emptyText}>No withdrawals yet</Text>
                <Text style={styles.emptySubtext}>
                  Recent withdrawals will appear here
                </Text>
              </View>
            ) : (
              <DataTable>
                <DataTable.Header>
                  <DataTable.Title style={{ flex: 2 }}>Date</DataTable.Title>
                  <DataTable.Title style={{ flex: 2 }}>Amount</DataTable.Title>
                  <DataTable.Title style={{ flex: 1.5 }}>
                    Status
                  </DataTable.Title>
                </DataTable.Header>

                {recentWithdrawals.map((transaction, index) => (
                  <DataTable.Row key={index}>
                    <DataTable.Cell style={{ flex: 2 }}>
                      <Text style={styles.dateText}>
                        {new Date(
                          transaction.created_at || transaction.timestamp,
                        ).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                        })}
                      </Text>
                    </DataTable.Cell>
                    <DataTable.Cell style={{ flex: 2 }}>
                      <Text style={styles.amountText}>
                        {formatCurrency(transaction.amount || 0)}
                      </Text>
                    </DataTable.Cell>
                    <DataTable.Cell style={{ flex: 1.5 }}>
                      <View style={styles.statusContainer}>
                        <Icon
                          name={getStatusIcon(transaction.status)}
                          size={16}
                          color={getStatusColor(transaction.status)}
                        />
                        <Text
                          style={[
                            styles.statusText,
                            { color: getStatusColor(transaction.status) },
                          ]}
                        >
                          {transaction.status}
                        </Text>
                      </View>
                    </DataTable.Cell>
                  </DataTable.Row>
                ))}
              </DataTable>
            )}

            {recentWithdrawals.length > 0 && (
              <Button
                mode="text"
                onPress={() => navigation.navigate("Transactions")}
                style={styles.viewAllButton}
              >
                View All Transactions
              </Button>
            )}
          </Card.Content>
        </Card>
      </ScrollView>

      <Snackbar
        visible={snackbarVisible}
        onDismiss={() => setSnackbarVisible(false)}
        duration={3000}
        style={[
          styles.snackbar,
          error ? styles.snackbarError : styles.snackbarSuccess,
        ]}
      >
        {error || success}
      </Snackbar>
    </KeyboardAvoidingView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F9FAFB",
  },
  centerContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#F9FAFB",
  },
  loadingText: {
    marginTop: spacing.md,
    fontSize: 16,
    color: "#6B7280",
  },
  scrollContent: {
    padding: spacing.md,
  },
  headerCard: {
    marginBottom: spacing.md,
    borderRadius: 12,
    elevation: 2,
    backgroundColor: "#E8F4F8",
    borderWidth: 1,
    borderColor: "#B3D9E8",
  },
  headerContent: {
    flexDirection: "row",
    alignItems: "center",
  },
  headerText: {
    marginLeft: spacing.md,
    flex: 1,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: "bold",
    color: colors.primary,
    marginBottom: 4,
  },
  headerSubtitle: {
    fontSize: 14,
    color: colors.primary,
  },
  balanceCard: {
    marginBottom: spacing.md,
    borderRadius: 12,
    elevation: 2,
    backgroundColor: "#FFFFFF",
  },
  balanceRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  balanceLabel: {
    fontSize: 14,
    color: "#6B7280",
    marginBottom: 4,
  },
  balanceAmount: {
    fontSize: 28,
    fontWeight: "bold",
    color: "#111827",
  },
  formCard: {
    marginBottom: spacing.md,
    borderRadius: 12,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: "bold",
    color: "#111827",
  },
  divider: {
    marginVertical: spacing.md,
  },
  inputGroup: {
    marginBottom: spacing.md,
  },
  label: {
    fontSize: 14,
    fontWeight: "600",
    color: "#374151",
    marginBottom: spacing.xs,
  },
  input: {
    backgroundColor: "#FFFFFF",
  },
  row: {
    flexDirection: "row",
  },
  amountDisplay: {
    backgroundColor: "#E8F4F8",
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#B3D9E8",
  },
  amountDisplayLabel: {
    fontSize: 12,
    color: colors.primary,
    marginBottom: 4,
    fontWeight: "600",
  },
  amountDisplayValue: {
    fontSize: 32,
    fontWeight: "bold",
    color: colors.primary,
  },
  accountTypeContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  accountTypeChip: {
    backgroundColor: "#F3F4F6",
    marginRight: spacing.xs,
    marginBottom: spacing.xs,
  },
  accountTypeChipSelected: {
    backgroundColor: colors.primary,
  },
  accountTypeChipText: {
    color: "#6B7280",
  },
  accountTypeChipTextSelected: {
    color: "#FFFFFF",
  },
  securityInfo: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#ECFDF5",
    padding: spacing.sm,
    borderRadius: 8,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: "#A7F3D0",
  },
  securityInfoText: {
    fontSize: 12,
    color: "#047857",
    marginLeft: spacing.xs,
    flex: 1,
    fontWeight: "500",
  },
  continueButton: {
    backgroundColor: colors.primary,
    marginTop: spacing.sm,
  },
  submitButton: {
    backgroundColor: colors.primary,
  },
  cancelButton: {
    marginTop: spacing.sm,
  },
  buttonContent: {
    height: 48,
  },
  transactionsCard: {
    marginBottom: spacing.xl,
    borderRadius: 12,
    elevation: 2,
  },
  countChip: {
    backgroundColor: "#E8F4F8",
  },
  countChipText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "bold",
  },
  emptyState: {
    alignItems: "center",
    paddingVertical: spacing.xl * 2,
  },
  emptyText: {
    fontSize: 16,
    fontWeight: "600",
    color: "#6B7280",
    marginTop: spacing.md,
  },
  emptySubtext: {
    fontSize: 14,
    color: "#9CA3AF",
    marginTop: spacing.xs,
  },
  dateText: {
    fontSize: 13,
    color: "#374151",
  },
  amountText: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.primary,
  },
  statusContainer: {
    flexDirection: "row",
    alignItems: "center",
  },
  statusText: {
    fontSize: 11,
    fontWeight: "500",
    marginLeft: 4,
    textTransform: "capitalize",
  },
  viewAllButton: {
    marginTop: spacing.sm,
  },
  snackbar: {
    marginBottom: spacing.md,
  },
  snackbarSuccess: {
    backgroundColor: "#10B981",
  },
  snackbarError: {
    backgroundColor: "#B91C1C",
  },
  cardReaderSection: {
    marginBottom: spacing.lg,
  },
  cardReaderHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  cardReaderTitle: {
    fontSize: 16,
    fontWeight: "600",
    color: "#374151",
    marginLeft: spacing.sm,
  },
  readCardButton: {
    backgroundColor: colors.primary,
    marginTop: spacing.sm,
  },
  cardReadingContainer: {
    alignItems: "center",
    paddingVertical: spacing.xl,
  },
  cardReadingText: {
    fontSize: 16,
    fontWeight: "600",
    color: "#374151",
    marginTop: spacing.md,
    marginBottom: spacing.md,
  },
  cardSuccessContainer: {
    alignItems: "center",
    paddingVertical: spacing.lg,
    backgroundColor: "#ECFDF5",
    borderRadius: 12,
    marginTop: spacing.md,
  },
  cardSuccessText: {
    fontSize: 16,
    fontWeight: "600",
    color: "#047857",
    marginTop: spacing.md,
    marginBottom: spacing.md,
  },
  cardInfoBox: {
    flexDirection: "row",
    justifyContent: "space-between",
    width: "100%",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xs,
  },
  cardInfoLabel: {
    fontSize: 14,
    color: "#6B7280",
  },
  cardInfoValue: {
    fontSize: 14,
    fontWeight: "600",
    color: "#374151",
  },
  cardErrorContainer: {
    alignItems: "center",
    paddingVertical: spacing.lg,
    backgroundColor: "#FEF2F2",
    borderRadius: 12,
    marginTop: spacing.md,
  },
  cardErrorText: {
    fontSize: 16,
    fontWeight: "600",
    color: "#DC2626",
    marginTop: spacing.md,
  },
  manualEntryHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  manualEntryTitle: {
    fontSize: 16,
    fontWeight: "600",
    color: "#374151",
  },
});

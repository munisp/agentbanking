import * as SecureStore from "expo-secure-store";
import React, { useEffect, useState } from "react";
import {
    ActivityIndicator,
    FlatList,
    RefreshControl,
    ScrollView,
    StyleSheet,
    View,
} from "react-native";
import {
    Button,
    Card,
    Chip,
    SegmentedButtons,
    Snackbar,
    Text,
    TextInput,
    useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { networkOperationsApi } from "../../services/apiService";
import { spacing } from "../../theme";
const BILL_CATEGORIES = [
  { id: "electricity", label: "Electricity", icon: "lightning-bolt" },
  { id: "water", label: "Water", icon: "water" },
  { id: "airtime", label: "Airtime", icon: "phone" },
  { id: "data", label: "Data", icon: "wifi" },
  { id: "cable", label: "Cable TV", icon: "television" },
  { id: "internet", label: "Internet", icon: "web" },
  { id: "giving", label: "Giving/Donate", icon: "hand-heart" },
  { id: "vat", label: "Nigerian VAT", icon: "calculator" },
];

const VAT_RATE = 0.075;

export default function BillPaymentScreen() {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  const theme = useTheme();
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [billerCode, setBillerCode] = useState("");
  const [customerNumber, setCustomerNumber] = useState("");
  const [amount, setAmount] = useState("");
  const [taxpayerName, setTaxpayerName] = useState("");
  const [tin, setTin] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [taxPeriod, setTaxPeriod] = useState("");
  const [description, setDescription] = useState("");
  const [selectedOrganization, setSelectedOrganization] = useState(null);
  const [organizationFilter, setOrganizationFilter] = useState("all");
  const [organizations, setOrganizations] = useState([]);
  const [loadingOrgs, setLoadingOrgs] = useState(false);
  const [recentPayments, setRecentPayments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const taxableAmount = Number(amount || 0);
  const vatAmount =
    selectedCategory === "vat"
      ? Number((taxableAmount * VAT_RATE).toFixed(2))
      : 0;
  const vatTotalAmount = Number((taxableAmount + vatAmount).toFixed(2));

  useEffect(() => {
    fetchRecentPayments();
  }, []);

  useEffect(() => {
    if (selectedCategory === "giving") {
      fetchOrganizations();
    }
  }, [selectedCategory]);

  const fetchOrganizations = async () => {
    setLoadingOrgs(true);
    try {
      const response = await networkOperationsApi.getBillers("giving");
      const data = response?.data || response || [];
      setOrganizations(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Failed to fetch organizations:", err);
      setOrganizations([]); // Show empty list, NOT fake data
    } finally {
      setLoadingOrgs(false);
    }
  };

  const fetchBillers = async (category) => {
    try {
      const response = await networkOperationsApi.getBillers(category);
      const data = response?.data || response || [];
      return Array.isArray(data) ? data : [];
    } catch (err) {
      console.error("Failed to fetch billers:", err);
      return [];
    }
  };

  const fetchRecentPayments = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      }

      const agentId = await SecureStore.getItemAsync("agentId");
      const response = await networkOperationsApi.listTransactions({
        agent_id: agentId,
        transaction_type: "BILL_PAYMENT",
        page: 1,
        limit: 10,
      });
      setRecentPayments(response.transactions || response.data || []);
    } catch (err) {
      console.log("Recent payments fetch error:", err.message);
    } finally {
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    fetchRecentPayments(true);
  };

  const handlePayBill = async () => {
    // For giving/donations, check organization selection
    if (selectedCategory === "giving") {
      if (!selectedOrganization || !amount) {
        setError("Please select an organization and enter amount");
        return;
      }
    } else if (selectedCategory === "vat") {
      if (!taxpayerName || !tin || !invoiceNumber || !taxPeriod || !amount) {
        setError("Please complete all VAT fields");
        return;
      }
    } else {
      // For regular bills
      if (!selectedCategory || !customerNumber || !amount) {
        setError("Please fill all required fields");
        return;
      }
    }

    try {
      setLoading(true);
      setError("");

      const agentId = await SecureStore.getItemAsync("agentId");

      const transactionData = {
        agent_id: agentId,
        transaction_type:
          selectedCategory === "giving" ? "DONATION" : "BILL_PAYMENT",
        amount:
          selectedCategory === "vat" ? vatTotalAmount : parseFloat(amount),
        category: selectedCategory,
      };

      // Add appropriate fields based on transaction type
      if (selectedCategory === "giving") {
        const org = organizations.find(
          (o) => o.id === selectedOrganization,
        );
        transactionData.organization_name = org.name;
        transactionData.organization_type = org.type;
        transactionData.customer_number = org.account;
        transactionData.biller_code = org.bank;
      } else if (selectedCategory === "vat") {
        transactionData.taxpayer_name = taxpayerName;
        transactionData.tin = tin;
        transactionData.invoice_number = invoiceNumber;
        transactionData.tax_period = taxPeriod;
        transactionData.description = description;
        transactionData.tax_rate = VAT_RATE;
        transactionData.taxable_amount = taxableAmount;
        transactionData.vat_amount = vatAmount;
        transactionData.total_amount = vatTotalAmount;
        transactionData.biller_code = "FIRS";
      } else {
        transactionData.customer_number = customerNumber;
        transactionData.biller_code = billerCode;
      }

      await networkOperationsApi.createTransaction(transactionData);

      setSuccess(
        selectedCategory === "giving"
          ? "Donation successful! Thank you for your generosity"
          : selectedCategory === "vat"
            ? "VAT payment successful"
            : "Bill payment successful",
      );
      setBillerCode("");
      setCustomerNumber("");
      setAmount("");
      setTaxpayerName("");
      setTin("");
      setInvoiceNumber("");
      setTaxPeriod("");
      setDescription("");
      setSelectedCategory(null);
      setSelectedOrganization(null);
      fetchRecentPayments();
    } catch (err) {
      console.error("Payment error:", err);
      setError(
        err.message ||
          (selectedCategory === "giving"
            ? "Failed to process donation"
            : selectedCategory === "vat"
              ? "Failed to process VAT payment"
              : "Failed to process bill payment"),
      );
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === "completed" || statusLower === "success")
      return "#10B981";
    if (statusLower === "failed" || statusLower === "rejected")
      return theme.colors.error;
    if (statusLower === "pending") return "#F59E0B";
    return "#6B7280";
  };

  const getFilteredOrganizations = () => {
    if (organizationFilter === "all") return organizations;
    return organizations.filter(
      (org) => org.type.toLowerCase() === organizationFilter,
    );
  };

  const renderOrganizationCard = (org) => (
    <Card
      key={org.id}
      style={[
        styles.orgCard,
        selectedOrganization === org.id && styles.selectedOrgCard,
      ]}
      onPress={() => setSelectedOrganization(org.id)}
    >
      <Card.Content>
        <View style={styles.orgHeader}>
          <Icon
            name={
              org.type === "Religious"
                ? org.religion === "Muslim"
                  ? "mosque"
                  : "church"
                : "hand-heart"
            }
            size={24}
            color={
              selectedOrganization === org.id ? theme.colors.primary : "#6B7280"
            }
          />
          <Chip
            mode="flat"
            style={styles.orgTypeChip}
            textStyle={{ fontSize: 10 }}
          >
            {org.type === "Religious" ? org.religion : org.type}
          </Chip>
        </View>
        <Text
          variant="bodyMedium"
          style={[
            styles.orgName,
            selectedOrganization === org.id && styles.selectedOrgName,
          ]}
        >
          {org.name}
        </Text>
        <Text variant="bodySmall" style={styles.orgBank}>
          {org.bank} • {org.account}
        </Text>
      </Card.Content>
    </Card>
  );

  const renderCategoryCard = (category) => (
    <Card
      key={category.id}
      style={[
        styles.categoryCard,
        selectedCategory === category.id && styles.selectedCategoryCard,
      ]}
      onPress={() => setSelectedCategory(category.id)}
    >
      <Card.Content style={styles.categoryContent}>
        <Icon
          name={category.icon}
          size={32}
          color={
            selectedCategory === category.id ? theme.colors.primary : "#6B7280"
          }
        />
        <Text
          variant="bodyMedium"
          style={[
            styles.categoryLabel,
            selectedCategory === category.id && styles.selectedCategoryLabel,
          ]}
        >
          {category.label}
        </Text>
      </Card.Content>
    </Card>
  );

  const renderPaymentItem = ({ item }) => (
    <View style={styles.paymentItem}>
      <View style={styles.paymentLeft}>
        <Text variant="bodyMedium" style={styles.paymentCategory}>
          {item.category === "vat"
            ? "VAT Payment"
            : item.category || "Bill Payment"}
        </Text>
        <Text variant="bodySmall" style={styles.paymentDate}>
          {new Date(item.created_at || item.timestamp).toLocaleDateString()}
        </Text>
        {item.customer_number && (
          <Text variant="bodySmall" style={styles.paymentCustomer}>
            {item.customer_number}
          </Text>
        )}
      </View>
      <View style={styles.paymentRight}>
        <Text variant="bodyMedium" style={styles.paymentAmount}>
          ₦{parseFloat(item.amount).toLocaleString()}
        </Text>
        <Chip
          mode="flat"
          style={[
            styles.statusChip,
            { backgroundColor: getStatusColor(item.status) + "20" },
          ]}
          textStyle={{ color: getStatusColor(item.status), fontSize: 10 }}
        >
          {item.status}
        </Chip>
      </View>
    </View>
  );

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Category Selection */}
      <View style={styles.section}>
        <Text variant="titleMedium" style={styles.sectionTitle}>
          Select Bill Category
        </Text>
        <View style={styles.categoriesGrid}>
          {BILL_CATEGORIES.map(renderCategoryCard)}
        </View>
      </View>

      {/* Giving/Donation Form */}
      {selectedCategory === "giving" && (
        <View>
          <View style={styles.section}>
            <Text variant="titleMedium" style={styles.sectionTitle}>
              Select Organization Type
            </Text>
            <SegmentedButtons
              value={organizationFilter}
              onValueChange={setOrganizationFilter}
              buttons={[
                { value: "all", label: "All" },
                { value: "religious", label: "Religious" },
                { value: "ngo", label: "NGOs" },
              ]}
              style={styles.segmentedButtons}
            />
          </View>

          <View style={styles.section}>
            <Text variant="titleMedium" style={styles.sectionTitle}>
              Choose Where to Give
            </Text>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              style={styles.orgScrollView}
            >
              {getFilteredOrganizations().map(renderOrganizationCard)}
            </ScrollView>
          </View>

          <Card style={styles.formCard}>
            <Card.Content>
              <Text variant="titleMedium" style={styles.formTitle}>
                Donation Amount
              </Text>

              <TextInput
                label="Amount to Give *"
                value={amount}
                onChangeText={setAmount}
                mode="outlined"
                style={styles.input}
                keyboardType="numeric"
                left={<TextInput.Icon icon="currency-ngn" />}
                placeholder="Enter donation amount"
              />

              <Button
                mode="contained"
                onPress={handlePayBill}
                disabled={loading || !selectedOrganization || !amount}
                loading={loading}
                style={styles.payButton}
                icon="hand-heart"
              >
                Complete Donation
              </Button>
            </Card.Content>
          </Card>
        </View>
      )}

      {/* VAT Form */}
      {selectedCategory === "vat" && (
        <Card style={styles.formCard}>
          <Card.Content>
            <Text variant="titleMedium" style={styles.formTitle}>
              Nigerian VAT Details
            </Text>

            <TextInput
              label="Taxpayer Name *"
              value={taxpayerName}
              onChangeText={setTaxpayerName}
              mode="outlined"
              style={styles.input}
              left={<TextInput.Icon icon="account" />}
              placeholder="Company or individual name"
            />

            <TextInput
              label="TIN *"
              value={tin}
              onChangeText={setTin}
              mode="outlined"
              style={styles.input}
              left={<TextInput.Icon icon="identifier" />}
              placeholder="Tax Identification Number"
            />

            <TextInput
              label="Invoice / Assessment Number *"
              value={invoiceNumber}
              onChangeText={setInvoiceNumber}
              mode="outlined"
              style={styles.input}
              left={<TextInput.Icon icon="receipt" />}
              placeholder="VAT invoice reference"
            />

            <TextInput
              label="Tax Period *"
              value={taxPeriod}
              onChangeText={setTaxPeriod}
              mode="outlined"
              style={styles.input}
              left={<TextInput.Icon icon="calendar-month" />}
              placeholder="e.g. Q1 2026"
            />

            <TextInput
              label="Taxable Amount *"
              value={amount}
              onChangeText={setAmount}
              mode="outlined"
              style={styles.input}
              keyboardType="numeric"
              left={<TextInput.Icon icon="currency-ngn" />}
              placeholder="Enter amount before VAT"
            />

            <View style={styles.vatSummaryGrid}>
              <View style={styles.vatSummaryCard}>
                <Text variant="labelSmall" style={styles.vatSummaryLabel}>
                  VAT rate
                </Text>
                <Text variant="bodyMedium" style={styles.vatSummaryValue}>
                  7.5%
                </Text>
              </View>
              <View style={styles.vatSummaryCard}>
                <Text variant="labelSmall" style={styles.vatSummaryLabel}>
                  VAT amount
                </Text>
                <Text variant="bodyMedium" style={styles.vatSummaryValue}>
                  ₦{vatAmount.toLocaleString()}
                </Text>
              </View>
              <View style={styles.vatSummaryCard}>
                <Text variant="labelSmall" style={styles.vatSummaryLabel}>
                  Total payable
                </Text>
                <Text variant="bodyMedium" style={styles.vatSummaryValue}>
                  ₦{vatTotalAmount.toLocaleString()}
                </Text>
              </View>
            </View>

            <TextInput
              label="Description / Notes"
              value={description}
              onChangeText={setDescription}
              mode="outlined"
              style={styles.input}
              left={<TextInput.Icon icon="text" />}
              placeholder="Optional VAT notes"
              multiline
            />

            <Button
              mode="contained"
              onPress={handlePayBill}
              disabled={
                loading ||
                !taxpayerName ||
                !tin ||
                !invoiceNumber ||
                !taxPeriod ||
                !amount
              }
              loading={loading}
              style={styles.payButton}
              icon="calculator"
            >
              Pay VAT
            </Button>
          </Card.Content>
        </Card>
      )}

      {/* Regular Bill Payment Form */}
      {selectedCategory &&
        selectedCategory !== "giving" &&
        selectedCategory !== "vat" && (
          <Card style={styles.formCard}>
            <Card.Content>
              <Text variant="titleMedium" style={styles.formTitle}>
                Bill Payment Details
              </Text>

              <TextInput
                label="Biller Code (Optional)"
                value={billerCode}
                onChangeText={setBillerCode}
                mode="outlined"
                style={styles.input}
                left={<TextInput.Icon icon="barcode" />}
              />

              <TextInput
                label="Customer Number *"
                value={customerNumber}
                onChangeText={setCustomerNumber}
                mode="outlined"
                style={styles.input}
                keyboardType="numeric"
                left={<TextInput.Icon icon="account" />}
              />

              <TextInput
                label="Amount *"
                value={amount}
                onChangeText={setAmount}
                mode="outlined"
                style={styles.input}
                keyboardType="numeric"
                left={<TextInput.Icon icon="currency-ngn" />}
              />

              <Button
                mode="contained"
                onPress={handlePayBill}
                disabled={loading || !customerNumber || !amount}
                loading={loading}
                style={styles.payButton}
                icon="check"
              >
                Pay Bill
              </Button>
            </Card.Content>
          </Card>
        )}

      {/* Recent Payments */}
      {recentPayments.length > 0 && (
        <Card style={styles.recentCard}>
          <Card.Content>
            <Text variant="titleMedium" style={styles.sectionTitle}>
              Recent Payments
            </Text>
            <FlatList
              data={recentPayments}
              renderItem={renderPaymentItem}
              keyExtractor={(item, index) =>
                item.id || item.reference || index.toString()
              }
              scrollEnabled={false}
            />
          </Card.Content>
        </Card>
      )}

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
  section: {
    padding: spacing.md,
  },
  sectionTitle: {
    fontWeight: "600",
    marginBottom: spacing.md,
  },
  categoriesGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  categoryCard: {
    width: "31%",
    marginBottom: spacing.sm,
  },
  selectedCategoryCard: {
    borderWidth: 2,
    borderColor: colors.primary,
  },
  categoryContent: {
    alignItems: "center",
    padding: spacing.sm,
  },
  categoryLabel: {
    marginTop: spacing.xs,
    textAlign: "center",
  },
  selectedCategoryLabel: {
    color: colors.primary,
    fontWeight: "600",
  },
  formCard: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  formTitle: {
    fontWeight: "600",
    marginBottom: spacing.md,
  },
  input: {
    marginBottom: spacing.md,
  },
  payButton: {
    marginTop: spacing.sm,
  },
  recentCard: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  paymentItem: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: "#E5E7EB",
  },
  paymentLeft: {
    flex: 1,
  },
  paymentCategory: {
    fontWeight: "500",
    textTransform: "capitalize",
  },
  paymentDate: {
    color: "#6B7280",
    marginTop: 2,
  },
  paymentCustomer: {
    color: "#9CA3AF",
    fontSize: 11,
    marginTop: 2,
  },
  paymentRight: {
    alignItems: "flex-end",
    gap: 4,
  },
  paymentAmount: {
    fontWeight: "600",
  },
  statusChip: {
    height: 20,
  },
  vatSummaryGrid: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.md,
    flexWrap: "wrap",
  },
  vatSummaryCard: {
    flexGrow: 1,
    minWidth: 100,
    padding: spacing.sm,
    borderRadius: 12,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E5E7EB",
  },
  vatSummaryLabel: {
    color: "#6B7280",
  },
  vatSummaryValue: {
    fontWeight: "600",
    marginTop: 4,
  },
  segmentedButtons: {
    marginBottom: spacing.sm,
  },
  orgScrollView: {
    marginHorizontal: -spacing.md,
    paddingHorizontal: spacing.md,
  },
  orgCard: {
    width: 280,
    marginRight: spacing.sm,
    marginBottom: spacing.sm,
  },
  selectedOrgCard: {
    borderWidth: 2,
    borderColor: colors.primary,
  },
  orgHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  orgTypeChip: {
    height: 34,
  },
  orgName: {
    fontWeight: "500",
    marginBottom: spacing.xs,
  },
  selectedOrgName: {
    color: colors.primary,
    fontWeight: "600",
  },
  orgBank: {
    color: "#6B7280",
  },
});

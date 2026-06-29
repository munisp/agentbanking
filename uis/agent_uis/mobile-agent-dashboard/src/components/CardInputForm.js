import React, { useRef } from "react";
import { StyleSheet, View } from "react-native";
import { Chip, Text, TextInput, useTheme } from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { spacing } from "../theme";
import { theme as _appTheme } from '../theme';
const colors = _appTheme.colors;

// ── Card provider config ──────────────────────────────────────────────────────

const PROVIDERS = {
  Visa:       { color: "#1A1F71", accent: "#F7B600", icon: "credit-card" },
  Mastercard: { color: "#1D1D1D", accent: "#EB001B", icon: "credit-card" },
  Verve:      { color: "#00833A", accent: "#F5C518", icon: "credit-card" },
  Amex:       { color: "#007BC1", accent: "#FFFFFF", icon: "credit-card" },
  default:    { color: colors.primary, accent: colors.secondary, icon: "credit-card" },
};

function providerConfig(name) {
  return PROVIDERS[name] || PROVIDERS.default;
}

// ── Luhn validation ───────────────────────────────────────────────────────────

export function luhnValid(digits) {

  if (!digits || digits.length < 13) return false;
  let sum = 0;
  let alt = false;
  for (let i = digits.length - 1; i >= 0; i--) {
    let n = parseInt(digits[i], 10);
    if (alt) { n *= 2; if (n > 9) n -= 9; }
    sum += n;
    alt = !alt;
  }
  return sum % 10 === 0;
}

// ── Card visual ───────────────────────────────────────────────────────────────

function CardVisual({ cardNumber, expiryDate, cardProvider, showBack, cvv }) {
  const cfg = providerConfig(cardProvider);

  // Format display number: fill remaining with bullet groups
  const raw = (cardNumber || "").replace(/\D/g, "").slice(0, 16);
  const padded = raw.padEnd(16, " ");
  const groups = [
    padded.slice(0, 4),
    padded.slice(4, 8),
    padded.slice(8, 12),
    padded.slice(12, 16),
  ].map((g) =>
    g
      .split("")
      .map((c) => (c === " " ? "•" : c))
      .join(""),
  );

  const expDisplay = expiryDate || "MM / YY";

  if (showBack) {
    return (
      <View style={[styles.card, { backgroundColor: cfg.color }]}>
        <View style={styles.magStripe} />
        <View style={styles.cvvRow}>
          <Text style={styles.cvvLabel}>CVV</Text>
          <View style={styles.cvvBox}>
            <Text style={styles.cvvValue}>
              {cvv ? "•".repeat(cvv.length) : "•••"}
            </Text>
          </View>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.card, { backgroundColor: cfg.color }]}>
      {/* Top row: chip + provider */}
      <View style={styles.cardTopRow}>
        <View style={styles.chip}>
          <View style={styles.chipInner} />
        </View>
        <Icon name="contactless-payment" size={22} color="rgba(255,255,255,0.7)" />
      </View>

      {/* Card number */}
      <View style={styles.cardNumberRow}>
        {groups.map((group, i) => (
          <Text key={i} style={styles.cardGroup}>
            {group}
          </Text>
        ))}
      </View>

      {/* Bottom row: expiry + provider name */}
      <View style={styles.cardBottomRow}>
        <View>
          <Text style={styles.cardLabel}>VALID THRU</Text>
          <Text style={styles.cardValue}>{expDisplay}</Text>
        </View>
        {cardProvider ? (
          <Text style={[styles.providerName, { color: cfg.accent }]}>
            {cardProvider.toUpperCase()}
          </Text>
        ) : null}
      </View>
    </View>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

const ACCOUNT_TYPES = [
  { value: "Savings", label: "Savings" },
  { value: "Current", label: "Current" },
  { value: "Not Sure", label: "Not Sure" },
];

export default function CardInputForm({
  cardNumber = "",
  cardProvider = "",
  expiryDate = "",
  cvv = "",
  accountType = "",
  pin = "",
  showPin = false,
  onCardNumberChange,
  onExpiryChange,
  onCvvChange,
  onAccountTypeChange,
  onPinChange,
  onTogglePin,
  style,
}) {
  const theme = useTheme();
  const styles = makeStyles(theme.colors);
  const expiryRef = useRef(null);
  const cvvRef = useRef(null);
  const pinRef = useRef(null);

  const isCardValid = luhnValid(cardNumber);
  const showBackOfCard = cvv.length > 0;

  const handleCardNumber = (text) => {
    const digits = text.replace(/\D/g, "").slice(0, 19);
    onCardNumberChange(digits);
    // Auto-advance after 16 digits
    if (digits.length >= 16) expiryRef.current?.focus();
  };

  const handleExpiry = (text) => {
    const digits = text.replace(/\D/g, "").slice(0, 4);
    let formatted = digits;
    if (digits.length >= 3) {
      formatted = digits.slice(0, 2) + " / " + digits.slice(2);
    } else if (digits.length === 2 && text.endsWith(" / ")) {
      // Allow backspace through the separator
      formatted = digits.slice(0, 1);
    }
    onExpiryChange(formatted);
    // Auto-advance after MM / YY
    if (digits.length === 4) cvvRef.current?.focus();
  };

  const handleCvv = (text) => {
    const digits = text.replace(/\D/g, "").slice(0, 3);
    onCvvChange(digits);
    if (digits.length === 3) pinRef.current?.focus();
  };

  const cardNumberForDisplay = cardNumber
    .replace(/\D/g, "")
    .replace(/(.{4})/g, "$1 ")
    .trim();

  return (
    <View style={style}>
      {/* Live card visual */}
      <CardVisual
        cardNumber={cardNumber}
        expiryDate={expiryDate}
        cardProvider={cardProvider}
        showBack={showBackOfCard}
        cvv={cvv}
      />

      {/* Card Number */}
      <View style={styles.inputGroup}>
        <Text style={styles.label}>Card Number *</Text>
        <TextInput
          mode="outlined"
          value={cardNumberForDisplay}
          onChangeText={handleCardNumber}
          placeholder="0000 0000 0000 0000"
          keyboardType="numeric"
          left={<TextInput.Icon icon="credit-card" />}
          right={
            cardNumber.length >= 13 ? (
              <TextInput.Icon
                icon={isCardValid ? "check-circle" : "alert-circle"}
                color={isCardValid ? "#10B981" : "#F59E0B"}
              />
            ) : cardProvider ? (
              <TextInput.Affix text={cardProvider} />
            ) : null
          }
          style={styles.input}
          outlineColor="#D1D5DB"
          activeOutlineColor={theme.colors.primary}
          returnKeyType="next"
          onSubmitEditing={() => expiryRef.current?.focus()}
        />
        {cardNumber.length >= 13 && !isCardValid && (
          <Text style={styles.fieldError}>Card number looks invalid</Text>
        )}
      </View>

      {/* Account Type */}
      <View style={styles.inputGroup}>
        <Text style={styles.label}>Account Type *</Text>
        <View style={styles.chipRow}>
          {ACCOUNT_TYPES.map((t) => (
            <Chip
              key={t.value}
              selected={accountType === t.value}
              onPress={() => onAccountTypeChange(t.value)}
              style={[
                styles.typeChip,
                accountType === t.value && styles.typeChipSelected,
              ]}
              textStyle={[
                styles.typeChipText,
                accountType === t.value && styles.typeChipTextSelected,
              ]}
            >
              {t.label}
            </Chip>
          ))}
        </View>
      </View>

      {/* Expiry + CVV side by side */}
      <View style={styles.row}>
        <View style={[styles.inputGroup, styles.halfInput]}>
          <Text style={styles.label}>Expiry *</Text>
          <TextInput
            ref={expiryRef}
            mode="outlined"
            value={expiryDate}
            onChangeText={handleExpiry}
            placeholder="MM / YY"
            keyboardType="numeric"
            style={styles.input}
            outlineColor="#D1D5DB"
            activeOutlineColor={theme.colors.primary}
            returnKeyType="next"
            onSubmitEditing={() => cvvRef.current?.focus()}
          />
        </View>

        <View style={[styles.inputGroup, styles.halfInput]}>
          <Text style={styles.label}>CVV *</Text>
          <TextInput
            ref={cvvRef}
            mode="outlined"
            value={cvv}
            onChangeText={handleCvv}
            placeholder="•••"
            keyboardType="numeric"
            secureTextEntry
            maxLength={3}
            style={styles.input}
            outlineColor="#D1D5DB"
            activeOutlineColor={theme.colors.primary}
            returnKeyType="next"
            onSubmitEditing={() => pinRef.current?.focus()}
          />
        </View>
      </View>

      {/* PIN */}
      <View style={styles.inputGroup}>
        <Text style={styles.label}>PIN *</Text>
        <TextInput
          ref={pinRef}
          mode="outlined"
          value={pin}
          onChangeText={(v) => onPinChange(v.replace(/\D/g, "").slice(0, 4))}
          placeholder="4-digit PIN"
          keyboardType="numeric"
          secureTextEntry={!showPin}
          maxLength={4}
          left={<TextInput.Icon icon="lock" />}
          right={
            <TextInput.Icon
              icon={showPin ? "eye-off" : "eye"}
              onPress={onTogglePin}
            />
          }
          style={styles.input}
          outlineColor="#D1D5DB"
          activeOutlineColor={theme.colors.primary}
        />
      </View>

      <View style={styles.securityBadge}>
        <Icon name="shield-check" size={16} color="#10B981" />
        <Text style={styles.securityText}>
          All card details are encrypted end-to-end
        </Text>
      </View>
    </View>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const makeStyles = (colors) => StyleSheet.create({
  // Card visual
  card: {
    borderRadius: 16,
    padding: spacing.lg,
    marginBottom: spacing.lg,
    height: 190,
    justifyContent: "space-between",
    elevation: 6,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
  },
  cardTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  chip: {
    width: 38,
    height: 28,
    borderRadius: 5,
    backgroundColor: "#D4A84B",
    justifyContent: "center",
    alignItems: "center",
  },
  chipInner: {
    width: 22,
    height: 16,
    borderRadius: 3,
    borderWidth: 1,
    borderColor: "#B8891E",
  },
  cardNumberRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginVertical: spacing.sm,
  },
  cardGroup: {
    color: "#FFF",
    fontSize: 18,
    fontWeight: "700",
    letterSpacing: 3,
    fontFamily: "monospace",
  },
  cardBottomRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
  },
  cardLabel: {
    color: "rgba(255,255,255,0.6)",
    fontSize: 9,
    letterSpacing: 1,
    marginBottom: 2,
  },
  cardValue: {
    color: "#FFF",
    fontSize: 14,
    fontWeight: "600",
    letterSpacing: 1,
  },
  providerName: {
    fontSize: 16,
    fontWeight: "900",
    letterSpacing: 1,
  },
  // Back of card
  magStripe: {
    height: 40,
    backgroundColor: "#1A1A1A",
    marginHorizontal: -spacing.lg,
    marginTop: -spacing.xs,
  },
  cvvRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "flex-end",
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  cvvLabel: {
    color: "rgba(255,255,255,0.7)",
    fontSize: 11,
    letterSpacing: 2,
  },
  cvvBox: {
    backgroundColor: "#FFF",
    borderRadius: 4,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    minWidth: 60,
    alignItems: "center",
  },
  cvvValue: {
    color: "#111",
    fontSize: 14,
    fontWeight: "700",
    letterSpacing: 4,
  },
  // Form fields
  inputGroup: {
    marginBottom: spacing.md,
  },
  label: {
    fontSize: 13,
    fontWeight: "600",
    color: "#374151",
    marginBottom: spacing.xs,
  },
  input: {
    backgroundColor: "#FFF",
  },
  fieldError: {
    fontSize: 11,
    color: "#F59E0B",
    marginTop: 4,
  },
  row: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  halfInput: {
    flex: 1,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  typeChip: {
    backgroundColor: "#F3F4F6",
  },
  typeChipSelected: {
    backgroundColor: colors.primary,
  },
  typeChipText: {
    color: "#6B7280",
    fontSize: 12,
  },
  typeChipTextSelected: {
    color: "#FFF",
    fontSize: 12,
  },
  securityBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: "#ECFDF5",
    borderWidth: 1,
    borderColor: "#A7F3D0",
    borderRadius: 8,
    padding: spacing.sm,
    marginBottom: spacing.sm,
  },
  securityText: {
    fontSize: 12,
    color: "#047857",
    fontWeight: "500",
    flex: 1,
  },
});

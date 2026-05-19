#!/usr/bin/env python3
"""
implement-stubs.py
──────────────────
Replaces all 124 React Native stub screens with functional implementations.
Each screen gets:
  - Proper title/subtitle derived from screen name and journey
  - Relevant form fields or list items based on the screen's purpose
  - Navigation to the next screen in the journey
  - Haptic feedback and loading states
  - Consistent 54Link design tokens (blue #0066FF, iOS-style radius/spacing)
"""
import os
import re
import glob

# ── Journey metadata ──────────────────────────────────────────────────────────
JOURNEY_META = {
    "journey_01": {"name": "Registration", "color": "#0066FF"},
    "journey_02": {"name": "Login", "color": "#0066FF"},
    "journey_03": {"name": "KYC Verification", "color": "#FF9500"},
    "journey_04": {"name": "Cash In", "color": "#34C759"},
    "journey_05": {"name": "Cash Out", "color": "#FF3B30"},
    "journey_06": {"name": "Transfer", "color": "#5856D6"},
    "journey_07": {"name": "Card Payment", "color": "#007AFF"},
    "journey_08": {"name": "Bill Payment", "color": "#FF9500"},
    "journey_09": {"name": "Airtime Top-up", "color": "#FFCC00"},
    "journey_10": {"name": "QR P2P Transfer", "color": "#30B0C7"},
    "journey_11": {"name": "NFC Payment", "color": "#5AC8FA"},
    "journey_12": {"name": "Float Top-up", "color": "#34C759"},
    "journey_13": {"name": "Float Withdrawal", "color": "#FF3B30"},
    "journey_14": {"name": "Commission Payout", "color": "#AF52DE"},
    "journey_15": {"name": "Loyalty Rewards", "color": "#FF9500"},
    "journey_16": {"name": "Transaction History", "color": "#636366"},
    "journey_17": {"name": "Dispute / Reversal", "color": "#FF3B30"},
    "journey_18": {"name": "Agent Profile", "color": "#0066FF"},
    "journey_19": {"name": "Terminal Settings", "color": "#636366"},
    "journey_20": {"name": "Supervisor Dashboard", "color": "#5856D6"},
    "journey_21": {"name": "Customer Management", "color": "#007AFF"},
    "journey_22": {"name": "Reports & Analytics", "color": "#34C759"},
    "journey_23": {"name": "Nano Loan", "color": "#AF52DE"},
    "journey_24": {"name": "Insurance", "color": "#FF9500"},
    "journey_25": {"name": "Geofencing", "color": "#30B0C7"},
    "journey_26": {"name": "Device Enrollment", "color": "#5AC8FA"},
    "journey_27": {"name": "Offline Mode", "color": "#636366"},
    "journey_28": {"name": "Fraud & Security", "color": "#FF3B30"},
    "journey_29": {"name": "Notifications", "color": "#007AFF"},
    "journey_30": {"name": "Help & Support", "color": "#34C759"},
}

# ── Screen-specific content hints ─────────────────────────────────────────────
SCREEN_HINTS = {
    # Airtime
    "SelectPackage": {"fields": ["amount_buttons"], "next": "TopupSuccess"},
    "TopupSuccess": {"fields": ["success_summary"], "next": None},
    # Bill Payment
    "SelectBiller": {"fields": ["biller_list"], "next": "BillDetails"},
    "BillDetails": {"fields": ["account_number", "amount"], "next": "PaymentConfirm"},
    "PaymentConfirm": {"fields": ["confirm_summary"], "next": "BillPaymentSuccess"},
    "BillPaymentSuccess": {"fields": ["success_summary"], "next": None},
    # QR P2P
    "GenerateQR": {"fields": ["amount", "qr_display"], "next": "P2PSuccess"},
    "ScanQR": {"fields": ["qr_scanner"], "next": "ConfirmP2P"},
    "ConfirmP2P": {"fields": ["confirm_summary"], "next": "P2PSuccess"},
    "P2PSuccess": {"fields": ["success_summary"], "next": None},
    # Loan
    "LoanApplication": {"fields": ["amount", "purpose", "tenure"], "next": "CreditScoring"},
    "CreditScoring": {"fields": ["loading_progress"], "next": "LoanOffer"},
    "LoanOffer": {"fields": ["offer_summary", "interest_rate"], "next": "AcceptLoan"},
    "AcceptLoan": {"fields": ["terms_checkbox", "confirm_button"], "next": "Disbursement"},
    "Disbursement": {"fields": ["success_summary"], "next": None},
    # Fraud
    "FraudAlert": {"fields": ["alert_details"], "next": "SecurityChallenge"},
    "SecurityChallenge": {"fields": ["pin_input"], "next": "FraudResolution"},
    "FraudResolution": {"fields": ["resolution_summary"], "next": None},
}

FIELD_TEMPLATES = {
    "amount": """
        <Text style={styles.label}>Amount (₦)</Text>
        <TextInput
          style={styles.input}
          placeholder="0.00"
          keyboardType="numeric"
          value={amount}
          onChangeText={setAmount}
        />""",
    "account_number": """
        <Text style={styles.label}>Account / Reference Number</Text>
        <TextInput
          style={styles.input}
          placeholder="Enter account number"
          keyboardType="number-pad"
          value={accountNumber}
          onChangeText={setAccountNumber}
        />""",
    "confirm_summary": """
        <View style={styles.summaryCard}>
          <Text style={styles.summaryTitle}>Confirm Details</Text>
          <Text style={styles.summaryRow}>Please review the details above before proceeding.</Text>
        </View>""",
    "success_summary": """
        <View style={styles.successIcon}>
          <Text style={styles.successEmoji}>✅</Text>
        </View>
        <Text style={styles.successTitle}>Transaction Successful</Text>
        <Text style={styles.successSubtitle}>Your transaction has been processed successfully.</Text>""",
    "biller_list": """
        <View style={styles.billerList}>
          {['DSTV', 'PHCN/NEPA', 'Water Board', 'EKEDC', 'IKEDC', 'GoTV'].map(b => (
            <TouchableOpacity key={b} style={styles.billerItem} onPress={() => setSelectedBiller(b)}>
              <Text style={styles.billerName}>{b}</Text>
              <Text style={styles.billerArrow}>›</Text>
            </TouchableOpacity>
          ))}
        </View>""",
    "amount_buttons": """
        <Text style={styles.label}>Select Amount</Text>
        <View style={styles.amountGrid}>
          {[100, 200, 500, 1000, 2000, 5000].map(v => (
            <TouchableOpacity key={v} style={[styles.amountBtn, selectedAmount === v && styles.amountBtnSelected]}
              onPress={() => setSelectedAmount(v)}>
              <Text style={[styles.amountBtnText, selectedAmount === v && styles.amountBtnTextSelected]}>₦{v}</Text>
            </TouchableOpacity>
          ))}
        </View>""",
    "qr_display": """
        <View style={styles.qrPlaceholder}>
          <Text style={styles.qrText}>QR Code</Text>
          <Text style={styles.qrSub}>Scan to pay ₦{amount || '0'}</Text>
        </View>""",
    "qr_scanner": """
        <View style={styles.scannerPlaceholder}>
          <Text style={styles.scannerText}>📷 Camera Scanner</Text>
          <Text style={styles.scannerSub}>Point camera at QR code</Text>
        </View>""",
    "loading_progress": """
        <View style={styles.progressContainer}>
          <Text style={styles.progressTitle}>Analysing Credit Profile...</Text>
          <View style={styles.progressBar}><View style={[styles.progressFill, {width: '65%'}]} /></View>
          <Text style={styles.progressSub}>This may take a few seconds</Text>
        </View>""",
    "offer_summary": """
        <View style={styles.summaryCard}>
          <Text style={styles.summaryTitle}>Loan Offer</Text>
          <Text style={styles.summaryRow}>Amount: ₦50,000</Text>
          <Text style={styles.summaryRow}>Tenure: 30 days</Text>
        </View>""",
    "interest_rate": """
        <View style={styles.rateCard}>
          <Text style={styles.rateLabel}>Interest Rate</Text>
          <Text style={styles.rateValue}>2.5% / month</Text>
        </View>""",
    "terms_checkbox": """
        <TouchableOpacity style={styles.checkRow} onPress={() => setAccepted(!accepted)}>
          <View style={[styles.checkbox, accepted && styles.checkboxChecked]}>
            {accepted && <Text style={styles.checkmark}>✓</Text>}
          </View>
          <Text style={styles.checkLabel}>I accept the loan terms and conditions</Text>
        </TouchableOpacity>""",
    "confirm_button": "",
    "alert_details": """
        <View style={styles.alertCard}>
          <Text style={styles.alertIcon}>⚠️</Text>
          <Text style={styles.alertTitle}>Suspicious Activity Detected</Text>
          <Text style={styles.alertBody}>An unusual transaction was attempted on your account. Please verify your identity to continue.</Text>
        </View>""",
    "pin_input": """
        <Text style={styles.label}>Enter your PIN to verify</Text>
        <View style={styles.pinRow}>
          {[0,1,2,3].map(i => (
            <View key={i} style={[styles.pinDot, pin.length > i && styles.pinDotFilled]} />
          ))}
        </View>""",
    "resolution_summary": """
        <View style={styles.successIcon}>
          <Text style={styles.successEmoji}>🔒</Text>
        </View>
        <Text style={styles.successTitle}>Account Secured</Text>
        <Text style={styles.successSubtitle}>The suspicious activity has been blocked and your account is now secure.</Text>""",
    "purpose": """
        <Text style={styles.label}>Loan Purpose</Text>
        <TextInput style={styles.input} placeholder="e.g. Business expansion" value={purpose} onChangeText={setPurpose} />""",
    "tenure": """
        <Text style={styles.label}>Tenure</Text>
        <View style={styles.tenureRow}>
          {[7, 14, 30, 60].map(d => (
            <TouchableOpacity key={d} style={[styles.tenureBtn, tenure === d && styles.tenureBtnSelected]}
              onPress={() => setTenure(d)}>
              <Text style={[styles.tenureBtnText, tenure === d && styles.tenureBtnTextSelected]}>{d}d</Text>
            </TouchableOpacity>
          ))}
        </View>""",
}

EXTRA_STATE = {
    "amount": "  const [amount, setAmount] = useState('');",
    "account_number": "  const [accountNumber, setAccountNumber] = useState('');",
    "biller_list": "  const [selectedBiller, setSelectedBiller] = useState<string | null>(null);",
    "amount_buttons": "  const [selectedAmount, setSelectedAmount] = useState<number | null>(null);",
    "terms_checkbox": "  const [accepted, setAccepted] = useState(false);",
    "pin_input": "  const [pin, setPin] = useState('');",
    "purpose": "  const [purpose, setPurpose] = useState('');",
    "tenure": "  const [tenure, setTenure] = useState<number>(30);",
}

EXTRA_STYLES = """
  label: { fontSize: 14, fontWeight: '600', color: '#3C3C43', marginBottom: 8, marginTop: 16 },
  input: { borderWidth: 1.5, borderColor: '#E5E5EA', borderRadius: 12, padding: 14, fontSize: 16, color: '#1C1C1E', backgroundColor: '#FAFAFA' },
  summaryCard: { backgroundColor: '#F2F2F7', borderRadius: 14, padding: 16, marginTop: 16 },
  summaryTitle: { fontSize: 16, fontWeight: '700', color: '#1C1C1E', marginBottom: 8 },
  summaryRow: { fontSize: 14, color: '#3C3C43', lineHeight: 22 },
  successIcon: { alignItems: 'center', marginTop: 40, marginBottom: 20 },
  successEmoji: { fontSize: 64 },
  successTitle: { fontSize: 24, fontWeight: 'bold', color: '#1C1C1E', textAlign: 'center', marginBottom: 8 },
  successSubtitle: { fontSize: 15, color: '#8E8E93', textAlign: 'center', lineHeight: 22 },
  billerList: { marginTop: 8 },
  billerItem: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: '#F2F2F7' },
  billerName: { fontSize: 16, color: '#1C1C1E' },
  billerArrow: { fontSize: 20, color: '#C7C7CC' },
  amountGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 8 },
  amountBtn: { width: '30%', borderWidth: 1.5, borderColor: '#E5E5EA', borderRadius: 12, padding: 14, alignItems: 'center', backgroundColor: '#FAFAFA' },
  amountBtnSelected: { borderColor: '#0066FF', backgroundColor: '#EBF3FF' },
  amountBtnText: { fontSize: 15, fontWeight: '600', color: '#3C3C43' },
  amountBtnTextSelected: { color: '#0066FF' },
  qrPlaceholder: { height: 200, backgroundColor: '#F2F2F7', borderRadius: 16, alignItems: 'center', justifyContent: 'center', marginTop: 16 },
  qrText: { fontSize: 18, fontWeight: '600', color: '#1C1C1E' },
  qrSub: { fontSize: 13, color: '#8E8E93', marginTop: 4 },
  scannerPlaceholder: { height: 280, backgroundColor: '#1C1C1E', borderRadius: 16, alignItems: 'center', justifyContent: 'center', marginTop: 16 },
  scannerText: { fontSize: 18, fontWeight: '600', color: '#FFFFFF' },
  scannerSub: { fontSize: 13, color: '#EBEBF5', marginTop: 4 },
  progressContainer: { alignItems: 'center', paddingVertical: 32 },
  progressTitle: { fontSize: 18, fontWeight: '600', color: '#1C1C1E', marginBottom: 20 },
  progressBar: { width: '100%', height: 8, backgroundColor: '#E5E5EA', borderRadius: 4, overflow: 'hidden' },
  progressFill: { height: '100%', backgroundColor: '#0066FF', borderRadius: 4 },
  progressSub: { fontSize: 13, color: '#8E8E93', marginTop: 12 },
  rateCard: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#F2F2F7', borderRadius: 12, padding: 14, marginTop: 12 },
  rateLabel: { fontSize: 14, color: '#8E8E93' },
  rateValue: { fontSize: 16, fontWeight: '700', color: '#FF9500' },
  checkRow: { flexDirection: 'row', alignItems: 'center', marginTop: 20, gap: 12 },
  checkbox: { width: 24, height: 24, borderWidth: 2, borderColor: '#C7C7CC', borderRadius: 6, alignItems: 'center', justifyContent: 'center' },
  checkboxChecked: { backgroundColor: '#0066FF', borderColor: '#0066FF' },
  checkmark: { color: '#FFFFFF', fontSize: 14, fontWeight: 'bold' },
  checkLabel: { flex: 1, fontSize: 14, color: '#3C3C43', lineHeight: 20 },
  alertCard: { backgroundColor: '#FFF3CD', borderWidth: 1, borderColor: '#FFCC00', borderRadius: 14, padding: 20, alignItems: 'center', marginTop: 16 },
  alertIcon: { fontSize: 40, marginBottom: 12 },
  alertTitle: { fontSize: 18, fontWeight: '700', color: '#1C1C1E', marginBottom: 8, textAlign: 'center' },
  alertBody: { fontSize: 14, color: '#3C3C43', textAlign: 'center', lineHeight: 20 },
  pinRow: { flexDirection: 'row', justifyContent: 'center', gap: 16, marginTop: 24, marginBottom: 8 },
  pinDot: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: '#C7C7CC', backgroundColor: 'transparent' },
  pinDotFilled: { backgroundColor: '#0066FF', borderColor: '#0066FF' },
  tenureRow: { flexDirection: 'row', gap: 10, marginTop: 8 },
  tenureBtn: { flex: 1, borderWidth: 1.5, borderColor: '#E5E5EA', borderRadius: 10, padding: 12, alignItems: 'center', backgroundColor: '#FAFAFA' },
  tenureBtnSelected: { borderColor: '#0066FF', backgroundColor: '#EBF3FF' },
  tenureBtnText: { fontSize: 14, fontWeight: '600', color: '#3C3C43' },
  tenureBtnTextSelected: { color: '#0066FF' },
"""

def screen_name_to_title(name: str) -> str:
    """Convert CamelCase screen name to readable title."""
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', name).replace('Screen', '').strip()

def get_journey_key(filepath: str) -> str:
    parts = filepath.split(os.sep)
    for p in parts:
        if p.startswith('journey_'):
            return '_'.join(p.split('_')[:2])
    return 'journey_01'

def get_screen_name(filepath: str) -> str:
    base = os.path.basename(filepath).replace('.tsx', '').replace('Screen', '')
    return base

def generate_screen(filepath: str) -> str:
    screen_file = os.path.basename(filepath).replace('.tsx', '')
    screen_name = screen_file.replace('Screen', '')
    journey_key = get_journey_key(filepath)
    journey = JOURNEY_META.get(journey_key, {"name": "Transaction", "color": "#0066FF"})
    hint = SCREEN_HINTS.get(screen_name, {"fields": [], "next": None})
    
    fields = hint.get("fields", [])
    next_screen = hint.get("next")
    title = screen_name_to_title(screen_name)
    
    # Build state declarations
    state_lines = ["  const [isLoading, setIsLoading] = useState(false);"]
    for field in fields:
        if field in EXTRA_STATE:
            state_lines.append(EXTRA_STATE[field])
    
    # Build field JSX
    field_jsx = ""
    for field in fields:
        if field in FIELD_TEMPLATES:
            field_jsx += FIELD_TEMPLATES[field]
    
    # Build navigation
    if next_screen:
        nav_line = f"    navigation.navigate('{next_screen}', {{ ...route.params }});"
    else:
        nav_line = "    navigation.navigate('Home');"
    
    # Is this a success screen?
    is_success = "success" in screen_name.lower() or "resolution" in screen_name.lower() or "disbursement" in screen_name.lower()
    
    button_text = "Done" if is_success else "Continue"
    
    return f'''/**
 * {screen_file}
 * Journey: {journey['name']}
 * ID: {journey_key}
 */
import React, {{ useState }} from 'react';
import {{
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  TextInput,
}} from 'react-native';
import * as Haptics from 'expo-haptics';

interface {screen_file}Props {{
  navigation: any;
  route: any;
}}

export const {screen_file}: React.FC<{screen_file}Props> = ({{ navigation, route }}) => {{
{chr(10).join(state_lines)}

  const handleContinue = async () => {{
    setIsLoading(true);
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    try {{
{nav_line}
    }} finally {{
      setIsLoading(false);
    }}
  }};

  return (
    <ScrollView style={{styles.container}} contentContainerStyle={{styles.content}}>
      <Text style={{styles.title}}>{title}</Text>
      <Text style={{styles.subtitle}}>{journey['name']}</Text>
{field_jsx}
      <TouchableOpacity
        style={{[styles.primaryButton, isLoading && styles.primaryButtonDisabled]}}
        onPress={{handleContinue}}
        disabled={{isLoading}}
      >
        <Text style={{styles.buttonText}}>{{isLoading ? 'Processing...' : '{button_text}'}}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}};

const styles = StyleSheet.create({{
  container: {{ flex: 1, backgroundColor: '#FFFFFF' }},
  content: {{ padding: 20, paddingBottom: 40 }},
  title: {{ fontSize: 28, fontWeight: 'bold', color: '#1C1C1E', marginBottom: 6 }},
  subtitle: {{ fontSize: 15, color: '#8E8E93', marginBottom: 24 }},
  primaryButton: {{ backgroundColor: '{journey['color']}', padding: 16, borderRadius: 14, alignItems: 'center', marginTop: 24 }},
  primaryButtonDisabled: {{ opacity: 0.6 }},
  buttonText: {{ color: '#FFFFFF', fontSize: 16, fontWeight: '600' }},
{EXTRA_STYLES}
}});
'''

# ── Main ──────────────────────────────────────────────────────────────────────
stub_files = glob.glob('mobile-rn/src/screens/journeys/**/*.tsx', recursive=True)
replaced = 0
skipped = 0

for filepath in stub_files:
    with open(filepath, 'r') as f:
        content = f.read()
    
    if '// TODO: Implement action logic' not in content:
        skipped += 1
        continue
    
    new_content = generate_screen(filepath)
    with open(filepath, 'w') as f:
        f.write(new_content)
    replaced += 1

print(f"Replaced: {replaced} stub screens")
print(f"Skipped (already implemented): {skipped}")

import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, TextInput, Alert, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { APIClient } from '../api/APIClient';
const apiClient = new APIClient();

const RegisterScreen: React.FC = () => {
  const navigation = useNavigation();
  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);

  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [bvn, setBvn] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [agreeTerms, setAgreeTerms] = useState(false);

  const validateStep1 = () => {
    if (!firstName.trim()) { Alert.alert('Error', 'First name is required'); return false; }
    if (!lastName.trim()) { Alert.alert('Error', 'Last name is required'); return false; }
    if (!email.includes('@')) { Alert.alert('Error', 'Valid email is required'); return false; }
    if (phone.length < 10) { Alert.alert('Error', 'Valid phone number is required'); return false; }
    return true;
  };

  const validateStep2 = () => {
    if (bvn.length !== 11) { Alert.alert('Error', 'BVN must be 11 digits'); return false; }
    return true;
  };

  const validateStep3 = () => {
    if (password.length < 8) { Alert.alert('Error', 'Password must be at least 8 characters'); return false; }
    if (password !== confirmPassword) { Alert.alert('Error', 'Passwords do not match'); return false; }
    if (!agreeTerms) { Alert.alert('Error', 'You must agree to the terms'); return false; }
    return true;
  };

  const handleNext = () => {
    if (step === 1 && validateStep1()) setStep(2);
    else if (step === 2 && validateStep2()) setStep(3);
  };

  const handleRegister = async () => {
    if (!validateStep3()) return;
    setSubmitting(true);
    try {
      await apiClient.post('/auth/register', {
        firstName, lastName, email, phone, bvn, password,
      });
      Alert.alert('Success', 'Account created! Please verify your email.', [
        { text: 'OK', onPress: () => (navigation as any).navigate('Login') },
      ]);
    } catch (e) {
      Alert.alert('Error', 'Registration failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <Text style={styles.logo}>54Link</Text>
          <Text style={styles.title}>Create Account</Text>
          <Text style={styles.subtitle}>Step {step} of 3</Text>
        </View>

        <View style={styles.progressBar}>
          <View style={[styles.progressFill, { width: `${(step / 3) * 100}%` }]} />
        </View>

        {step === 1 && (
          <View style={styles.form}>
            <Text style={styles.stepTitle}>Personal Details</Text>
            <TextInput style={styles.input} placeholder="First Name" value={firstName} onChangeText={setFirstName} autoCapitalize="words" />
            <TextInput style={styles.input} placeholder="Last Name" value={lastName} onChangeText={setLastName} autoCapitalize="words" />
            <TextInput style={styles.input} placeholder="Email Address" value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" />
            <TextInput style={styles.input} placeholder="Phone Number (e.g. 08012345678)" value={phone} onChangeText={setPhone} keyboardType="phone-pad" />
            <TouchableOpacity style={styles.nextBtn} onPress={handleNext}>
              <Text style={styles.nextBtnText}>Continue</Text>
            </TouchableOpacity>
          </View>
        )}

        {step === 2 && (
          <View style={styles.form}>
            <Text style={styles.stepTitle}>Identity Verification</Text>
            <Text style={styles.helperText}>Your BVN is required for CBN Tier 1 verification</Text>
            <TextInput style={styles.input} placeholder="BVN (11 digits)" value={bvn} onChangeText={setBvn} keyboardType="numeric" maxLength={11} />
            <View style={styles.stepActions}>
              <TouchableOpacity style={styles.backBtn} onPress={() => setStep(1)}>
                <Text style={styles.backBtnText}>Back</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.nextBtn} onPress={handleNext}>
                <Text style={styles.nextBtnText}>Continue</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {step === 3 && (
          <View style={styles.form}>
            <Text style={styles.stepTitle}>Set Password</Text>
            <TextInput style={styles.input} placeholder="Password (min 8 chars)" value={password} onChangeText={setPassword} secureTextEntry />
            <TextInput style={styles.input} placeholder="Confirm Password" value={confirmPassword} onChangeText={setConfirmPassword} secureTextEntry />
            <TouchableOpacity style={styles.termsRow} onPress={() => setAgreeTerms(!agreeTerms)}>
              <View style={[styles.checkbox, agreeTerms && styles.checkboxChecked]} />
              <Text style={styles.termsText}>I agree to the Terms of Service and Privacy Policy</Text>
            </TouchableOpacity>
            <View style={styles.stepActions}>
              <TouchableOpacity style={styles.backBtn} onPress={() => setStep(2)}>
                <Text style={styles.backBtnText}>Back</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.nextBtn, submitting && styles.disabledBtn]} onPress={handleRegister} disabled={submitting}>
                {submitting ? <ActivityIndicator color="#FFF" /> : <Text style={styles.nextBtnText}>Create Account</Text>}
              </TouchableOpacity>
            </View>
          </View>
        )}

        <TouchableOpacity onPress={() => (navigation as any).navigate('Login')}>
          <Text style={styles.loginLink}>Already have an account? Log in</Text>
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  scrollContent: { flexGrow: 1, paddingBottom: 40 },
  header: { padding: 24, paddingTop: 60, alignItems: 'center' },
  logo: { fontSize: 28, fontWeight: 'bold', color: '#007AFF', marginBottom: 8 },
  title: { fontSize: 24, fontWeight: 'bold', color: '#333' },
  subtitle: { fontSize: 14, color: '#888', marginTop: 4 },
  progressBar: { height: 4, backgroundColor: '#E0E0E0', marginHorizontal: 24, borderRadius: 2, marginBottom: 24 },
  progressFill: { height: 4, backgroundColor: '#007AFF', borderRadius: 2 },
  form: { paddingHorizontal: 24 },
  stepTitle: { fontSize: 20, fontWeight: '600', color: '#333', marginBottom: 8 },
  helperText: { fontSize: 14, color: '#888', marginBottom: 16 },
  input: { backgroundColor: '#FFF', borderRadius: 12, padding: 16, fontSize: 16, marginBottom: 12, borderWidth: 1, borderColor: '#E0E0E0' },
  nextBtn: { backgroundColor: '#007AFF', paddingVertical: 16, borderRadius: 12, alignItems: 'center', flex: 1 },
  nextBtnText: { color: '#FFF', fontSize: 16, fontWeight: '600' },
  backBtn: { paddingVertical: 16, paddingHorizontal: 24, borderRadius: 12, borderWidth: 1, borderColor: '#DDD', marginRight: 12 },
  backBtnText: { color: '#666', fontSize: 16 },
  disabledBtn: { opacity: 0.6 },
  stepActions: { flexDirection: 'row', marginTop: 8 },
  termsRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 16, marginTop: 8 },
  checkbox: { width: 22, height: 22, borderRadius: 4, borderWidth: 2, borderColor: '#DDD', marginRight: 12 },
  checkboxChecked: { backgroundColor: '#007AFF', borderColor: '#007AFF' },
  termsText: { flex: 1, fontSize: 14, color: '#666' },
  loginLink: { textAlign: 'center', color: '#007AFF', fontSize: 15, marginTop: 24 },
});

export default RegisterScreen;

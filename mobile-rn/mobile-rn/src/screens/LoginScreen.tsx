import React, { useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity,
  ActivityIndicator, TextInput, Alert, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { APIClient } from '../api/APIClient';
const apiClient = new APIClient();

const LoginScreen: React.FC = () => {
  const navigation = useNavigation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleLogin = async () => {
    if (!email.trim()) { Alert.alert('Error', 'Email is required'); return; }
    if (!password.trim()) { Alert.alert('Error', 'Password is required'); return; }
    setLoading(true);
    try {
      const response = await apiClient.post('/auth/login', { email, password });
      const token = (response as any)?.token ?? (response as any)?.accessToken;
      if (token) {
        (navigation as any).reset({ index: 0, routes: [{ name: 'Dashboard' }] });
      } else {
        Alert.alert('Error', 'Invalid credentials');
      }
    } catch (e) {
      Alert.alert('Login Failed', 'Please check your credentials and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={styles.content}>
        <View style={styles.header}>
          <Text style={styles.logo}>54Link</Text>
          <Text style={styles.title}>Welcome Back</Text>
          <Text style={styles.subtitle}>Sign in to your agent account</Text>
        </View>

        <View style={styles.form}>
          <TextInput
            style={styles.input}
            placeholder="Email or Phone"
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
          />
          <View style={styles.passwordRow}>
            <TextInput
              style={[styles.input, styles.passwordInput]}
              placeholder="Password"
              value={password}
              onChangeText={setPassword}
              secureTextEntry={!showPassword}
              autoCapitalize="none"
            />
            <TouchableOpacity style={styles.showBtn} onPress={() => setShowPassword(!showPassword)}>
              <Text style={styles.showBtnText}>{showPassword ? 'Hide' : 'Show'}</Text>
            </TouchableOpacity>
          </View>

          <TouchableOpacity onPress={() => (navigation as any).navigate('ForgotPassword')}>
            <Text style={styles.forgotText}>Forgot password?</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.loginBtn, loading && styles.disabledBtn]}
            onPress={handleLogin}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color="#FFF" />
            ) : (
              <Text style={styles.loginBtnText}>Sign In</Text>
            )}
          </TouchableOpacity>
        </View>

        <View style={styles.footer}>
          <TouchableOpacity onPress={() => (navigation as any).navigate('Register')}>
            <Text style={styles.registerLink}>
              Don't have an account? <Text style={styles.registerLinkBold}>Sign Up</Text>
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFF' },
  content: { flex: 1, justifyContent: 'center', paddingHorizontal: 24 },
  header: { alignItems: 'center', marginBottom: 40 },
  logo: { fontSize: 32, fontWeight: 'bold', color: '#007AFF', marginBottom: 12 },
  title: { fontSize: 26, fontWeight: 'bold', color: '#333' },
  subtitle: { fontSize: 15, color: '#888', marginTop: 4 },
  form: { marginBottom: 24 },
  input: { backgroundColor: '#F5F5F5', borderRadius: 12, padding: 16, fontSize: 16, marginBottom: 12, borderWidth: 1, borderColor: '#E8E8E8' },
  passwordRow: { position: 'relative' },
  passwordInput: { paddingRight: 60 },
  showBtn: { position: 'absolute', right: 16, top: 16 },
  showBtnText: { color: '#007AFF', fontSize: 14, fontWeight: '600' },
  forgotText: { color: '#007AFF', fontSize: 14, textAlign: 'right', marginBottom: 20 },
  loginBtn: { backgroundColor: '#007AFF', paddingVertical: 16, borderRadius: 12, alignItems: 'center' },
  loginBtnText: { color: '#FFF', fontSize: 17, fontWeight: '600' },
  disabledBtn: { opacity: 0.6 },
  footer: { alignItems: 'center' },
  registerLink: { fontSize: 15, color: '#888' },
  registerLinkBold: { color: '#007AFF', fontWeight: '600' },
});

export default LoginScreen;

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { cdpAuthService } from '../services/CDPAuthService';
import { APIClient } from '../api/APIClient';
const apiClient = new APIClient();


interface LoginScreenProps {
  onLoginSuccess: () => void;
}

export const LoginScreen_CDP: React.FC<LoginScreenProps> = ({
  onLoginSuccess,
}) => {
  const [email, setEmail] = useState('');
  const [otp, setOTP] = useState('');
  const [flowId, setFlowId] = useState<string | null>(null);
  const [showOTPField, setShowOTPField] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [resendCooldown, setResendCooldown] = useState(0);

  // Cooldown timer
  useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setTimeout(() => {
        setResendCooldown(resendCooldown - 1);
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [resendCooldown]);

  const handleSendOTP = async () => {
    if (!email) return;

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const newFlowId = await cdpAuthService.sendOTP(email);
      setFlowId(newFlowId);
      setShowOTPField(true);
      setResendCooldown(60);
    } catch (error: any) {
      setErrorMessage(error.message || 'Failed to send OTP');
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyOTP = async () => {
    if (!flowId || otp.length !== 6) return;

    setIsLoading(true);
    setErrorMessage(null);

    try {
      await cdpAuthService.verifyOTP(flowId, otp, email);
      onLoginSuccess();
    } catch (error: any) {
      setErrorMessage(error.message || 'Invalid OTP');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendOTP = async () => {
    if (resendCooldown > 0) return;

    setIsLoading(true);
    setErrorMessage(null);
    setOTP('');

    try {
      const newFlowId = await cdpAuthService.sendOTP(email);
      setFlowId(newFlowId);
      setResendCooldown(60);
    } catch (error: any) {
      setErrorMessage(error.message || 'Failed to resend OTP');
    } finally {
      setIsLoading(false);
    }
  };

  const handleBack = () => {
    setShowOTPField(false);
    setOTP('');
    setFlowId(null);
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={styles.container}
    >
      <LinearGradient
        colors={['#E3F2FD', '#C5CAE9']}
        style={styles.gradient}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          {/* Logo */}
          <View style={styles.logoContainer}>
            <LinearGradient
              colors={['#2196F3', '#3F51B5']}
              style={styles.logoCircle}
            >
              <Ionicons name="mail" size={36} color="#FFFFFF" />
            </LinearGradient>
          </View>

          {/* Title */}
          <Text style={styles.title}>Welcome Back</Text>
          <Text style={styles.subtitle}>
            {showOTPField
              ? 'Enter the code sent to your email'
              : 'Sign in with your email'}
          </Text>

          {/* Error Message */}
          {errorMessage && (
            <View style={styles.errorContainer}>
              <Ionicons name="alert-circle" size={20} color="#D32F2F" />
              <Text style={styles.errorText}>{errorMessage}</Text>
            </View>
          )}

          {/* Form */}
          {!showOTPField ? (
            <EmailInputForm
              email={email}
              onEmailChange={setEmail}
              isLoading={isLoading}
              onSendOTP={handleSendOTP}
            />
          ) : (
            <OTPVerificationForm
              email={email}
              otp={otp}
              onOTPChange={setOTP}
              isLoading={isLoading}
              resendCooldown={resendCooldown}
              onVerifyOTP={handleVerifyOTP}
              onBack={handleBack}
              onResendOTP={handleResendOTP}
            />
          )}

          {/* Info Banner */}
          <View style={styles.infoBanner}>
            <Ionicons name="shield-checkmark" size={20} color="#2196F3" />
            <Text style={styles.infoText}>
              Secure email authentication powered by Coinbase. Your wallet is
              created automatically.
            </Text>
          </View>
        </ScrollView>
      </LinearGradient>
    </KeyboardAvoidingView>
  );
};

// Email Input Form Component
const EmailInputForm: React.FC<{
  email: string;
  onEmailChange: (email: string) => void;
  isLoading: boolean;
  onSendOTP: () => void;
}> = ({ email, onEmailChange, isLoading, onSendOTP }) => {
  return (
    <View style={styles.formContainer}>
      <Text style={styles.label}>Email Address</Text>
      <View style={styles.inputContainer}>
        <Ionicons name="mail-outline" size={20} color="#666" />
        <TextInput
          style={styles.input}
          placeholder="you@example.com"
          value={email}
          onChangeText={onEmailChange}
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
          editable={!isLoading}
        />
      </View>

      <TouchableOpacity
        style={[
          styles.button,
          (!email || isLoading) && styles.buttonDisabled,
        ]}
        onPress={onSendOTP}
        disabled={!email || isLoading}
      >
        <LinearGradient
          colors={['#2196F3', '#3F51B5']}
          style={styles.buttonGradient}
        >
          {isLoading ? (
            <>
              <ActivityIndicator color="#FFFFFF" size="small" />
              <Text style={styles.buttonText}>Sending...</Text>
            </>
          ) : (
            <>
              <Text style={styles.buttonText}>Send Code</Text>
              <Ionicons name="arrow-forward" size={20} color="#FFFFFF" />
            </>
          )}
        </LinearGradient>
      </TouchableOpacity>

      <View style={styles.signupContainer}>
        <Text style={styles.signupText}>Don't have an account? </Text>
        <TouchableOpacity>
          <Text style={styles.signupLink}>Sign up</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

// OTP Verification Form Component
const OTPVerificationForm: React.FC<{
  email: string;
  otp: string;
  onOTPChange: (otp: string) => void;
  isLoading: boolean;
  resendCooldown: number;
  onVerifyOTP: () => void;
  onBack: () => void;
  onResendOTP: () => void;
}> = ({
  email,
  otp,
  onOTPChange,
  isLoading,
  resendCooldown,
  onVerifyOTP,
  onBack,
  onResendOTP,
}) => {
  return (
    <View style={styles.formContainer}>
      <Text style={styles.label}>Verification Code</Text>
      <TextInput
        style={styles.otpInput}
        placeholder="000000"
        value={otp}
        onChangeText={(text) => {
          if (text.length <= 6 && /^\d*$/.test(text)) {
            onOTPChange(text);
          }
        }}
        keyboardType="number-pad"
        maxLength={6}
        editable={!isLoading}
      />
      <Text style={styles.helperText}>Code sent to {email}</Text>

      <TouchableOpacity
        style={[
          styles.button,
          (otp.length !== 6 || isLoading) && styles.buttonDisabled,
        ]}
        onPress={onVerifyOTP}
        disabled={otp.length !== 6 || isLoading}
      >
        <LinearGradient
          colors={['#2196F3', '#3F51B5']}
          style={styles.buttonGradient}
        >
          {isLoading ? (
            <>
              <ActivityIndicator color="#FFFFFF" size="small" />
              <Text style={styles.buttonText}>Verifying...</Text>
            </>
          ) : (
            <>
              <Text style={styles.buttonText}>Verify & Sign In</Text>
              <Ionicons name="arrow-forward" size={20} color="#FFFFFF" />
            </>
          )}
        </LinearGradient>
      </TouchableOpacity>

      <View style={styles.actionsRow}>
        <TouchableOpacity onPress={onBack} style={styles.actionButton}>
          <Ionicons name="arrow-back" size={16} color="#666" />
          <Text style={styles.actionText}>Change email</Text>
        </TouchableOpacity>

        <TouchableOpacity
          onPress={onResendOTP}
          disabled={resendCooldown > 0}
          style={styles.actionButton}
        >
          <Text
            style={[
              styles.actionText,
              styles.actionTextPrimary,
              resendCooldown > 0 && styles.actionTextDisabled,
            ]}
          >
            {resendCooldown > 0
              ? `Resend in ${resendCooldown}s`
              : 'Resend code'}
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  gradient: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    padding: 24,
    paddingTop: 60,
  },
  logoContainer: {
    alignItems: 'center',
    marginBottom: 24,
  },
  logoCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#1A237E',
    textAlign: 'center',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    marginBottom: 24,
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFEBEE',
    padding: 16,
    borderRadius: 12,
    marginBottom: 16,
  },
  errorText: {
    fontSize: 14,
    color: '#D32F2F',
    marginLeft: 12,
    flex: 1,
  },
  formContainer: {
    marginBottom: 32,
  },
  label: {
    fontSize: 14,
    fontWeight: '500',
    color: '#666',
    marginBottom: 8,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E0E0E0',
    paddingHorizontal: 16,
    marginBottom: 24,
  },
  input: {
    flex: 1,
    height: 56,
    fontSize: 16,
    marginLeft: 12,
  },
  otpInput: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E0E0E0',
    padding: 16,
    fontSize: 24,
    fontWeight: '500',
    textAlign: 'center',
    letterSpacing: 8,
    marginBottom: 8,
  },
  helperText: {
    fontSize: 12,
    color: '#666',
    marginBottom: 24,
  },
  button: {
    borderRadius: 12,
    overflow: 'hidden',
    marginBottom: 16,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonGradient: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    height: 56,
    paddingHorizontal: 24,
  },
  buttonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
    marginHorizontal: 8,
  },
  signupContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
  },
  signupText: {
    fontSize: 14,
    color: '#666',
  },
  signupLink: {
    fontSize: 14,
    fontWeight: '500',
    color: '#2196F3',
  },
  actionsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  actionButton: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  actionText: {
    fontSize: 14,
    color: '#666',
    marginLeft: 4,
  },
  actionTextPrimary: {
    fontWeight: '500',
    color: '#2196F3',
  },
  actionTextDisabled: {
    color: '#999',
  },
  infoBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#E3F2FD',
    padding: 16,
    borderRadius: 12,
  },
  infoText: {
    fontSize: 12,
    color: '#666',
    marginLeft: 12,
    flex: 1,
    lineHeight: 16,
  },
});

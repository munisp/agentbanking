// React Native Security Service
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Crypto from 'expo-crypto';
import * as LocalAuthentication from 'expo-local-authentication';
import * as SecureStore from 'expo-secure-store';

export class SecurityService {
  private static readonly SECURE_KEY_PREFIX = 'secure_';
  private static readonly DEVICE_ID_KEY = 'device_id';
  private static readonly SESSION_TOKEN_KEY = 'session_token';

  // Biometric Authentication
  static async isBiometricAvailable(): Promise<boolean> {
    const compatible = await LocalAuthentication.hasHardwareAsync();
    const enrolled = await LocalAuthentication.isEnrolledAsync();
    return compatible && enrolled;
  }

  static async authenticateWithBiometrics(reason: string = 'Authenticate to continue'): Promise<boolean> {
    try {
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: reason,
        fallbackLabel: 'Use Passcode',
        disableDeviceFallback: false,
      });
      return result.success;
    } catch (error) {
      console.error('Biometric authentication failed:', error);
      return false;
    }
  }

  // Secure Storage
  static async securelyStore(key: string, value: string): Promise<void> {
    try {
      await SecureStore.setItemAsync(this.SECURE_KEY_PREFIX + key, value);
    } catch (error) {
      console.error('Secure storage failed:', error);
      // Fallback to encrypted AsyncStorage
      const encrypted = await this.encrypt(value);
      await AsyncStorage.setItem(this.SECURE_KEY_PREFIX + key, encrypted);
    }
  }

  static async securelyRetrieve(key: string): Promise<string | null> {
    try {
      return await SecureStore.getItemAsync(this.SECURE_KEY_PREFIX + key);
    } catch (error) {
      console.error('Secure retrieval failed:', error);
      // Fallback to encrypted AsyncStorage
      const encrypted = await AsyncStorage.getItem(this.SECURE_KEY_PREFIX + key);
      if (encrypted) {
        return await this.decrypt(encrypted);
      }
      return null;
    }
  }

  static async securelyDelete(key: string): Promise<void> {
    try {
      await SecureStore.deleteItemAsync(this.SECURE_KEY_PREFIX + key);
    } catch (error) {
      await AsyncStorage.removeItem(this.SECURE_KEY_PREFIX + key);
    }
  }

  // Encryption
  static async encrypt(data: string): Promise<string> {
    const deviceId = await this.getDeviceId();
    const key = await Crypto.digestStringAsync(
      Crypto.CryptoDigestAlgorithm.SHA256,
      deviceId
    );
    
    // Simple XOR encryption (in production, use proper encryption library)
    const encrypted = Buffer.from(data)
      .map((byte, i) => byte ^ key.charCodeAt(i % key.length))
      .toString('base64');
    
    return encrypted;
  }

  static async decrypt(encrypted: string): Promise<string> {
    const deviceId = await this.getDeviceId();
    const key = await Crypto.digestStringAsync(
      Crypto.CryptoDigestAlgorithm.SHA256,
      deviceId
    );
    
    const decrypted = Buffer.from(encrypted, 'base64')
      .map((byte, i) => byte ^ key.charCodeAt(i % key.length))
      .toString();
    
    return decrypted;
  }

  // Device ID
  static async getDeviceId(): Promise<string> {
    let deviceId = await AsyncStorage.getItem(this.DEVICE_ID_KEY);
    
    if (!deviceId) {
      deviceId = await Crypto.digestStringAsync(
        Crypto.CryptoDigestAlgorithm.SHA256,
        `${Date.now()}_${Math.random()}`
      );
      await AsyncStorage.setItem(this.DEVICE_ID_KEY, deviceId);
    }
    
    return deviceId;
  }

  // Session Management
  static async createSession(token: string): Promise<void> {
    await this.securelyStore(this.SESSION_TOKEN_KEY, token);
  }

  static async getSession(): Promise<string | null> {
    return await this.securelyRetrieve(this.SESSION_TOKEN_KEY);
  }

  static async clearSession(): Promise<void> {
    await this.securelyDelete(this.SESSION_TOKEN_KEY);
  }

  // Request Signing
  static async signRequest(payload: any): Promise<string> {
    const deviceId = await this.getDeviceId();
    const timestamp = Date.now();
    const data = JSON.stringify({ ...payload, deviceId, timestamp });
    
    const signature = await Crypto.digestStringAsync(
      Crypto.CryptoDigestAlgorithm.SHA256,
      data
    );
    
    return signature;
  }

  // Certificate Pinning (validation)
  static validateCertificate(certificate: string): boolean {
    const expectedFingerprints = [
      'SHA256_FINGERPRINT_1',
      'SHA256_FINGERPRINT_2',
    ];
    
    return expectedFingerprints.includes(certificate);
  }

  // Anti-Tampering
  static async checkIntegrity(): Promise<boolean> {
    // Check if app has been tampered with
    // In production, implement proper integrity checks
    return true;
  }

  // Secure Random
  static async generateSecureRandom(length: number = 32): Promise<string> {
    const randomBytes = await Crypto.getRandomBytesAsync(length);
    return Buffer.from(randomBytes).toString('hex');
  }
}

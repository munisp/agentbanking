import ReactNativeBiometrics, { BiometryTypes } from 'react-native-biometrics';

class BiometricService {
  private rnBiometrics = new ReactNativeBiometrics();

  async checkAvailability() {
    const { available, biometryType } = await this.rnBiometrics.isSensorAvailable();
    
    return {
      available,
      type: biometryType === BiometryTypes.FaceID ? 'Face ID' :
            biometryType === BiometryTypes.TouchID ? 'Touch ID' :
            biometryType === BiometryTypes.Biometrics ? 'Biometrics' : 'None'
    };
  }

  async authenticate(promptMessage: string): Promise<boolean> {
    try {
      const { success } = await this.rnBiometrics.simplePrompt({
        promptMessage,
        cancelButtonText: 'Cancel'
      });
      return success;
    } catch (error) {
      console.error('Biometric auth failed:', error);
      return false;
    }
  }

  async createKeys(): Promise<boolean> {
    try {
      const { publicKey } = await this.rnBiometrics.createKeys();
      return !!publicKey;
    } catch (error) {
      console.error('Key creation failed:', error);
      return false;
    }
  }
}

export const biometricService = new BiometricService();

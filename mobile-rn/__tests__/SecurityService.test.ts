import { SecurityService } from '../src/services/SecurityService';

describe('SecurityService', () => {
  describe('Device ID', () => {
    it('should generate a device ID', async () => {
      const deviceId = await SecurityService.getDeviceId();
      expect(deviceId).toBeDefined();
      expect(typeof deviceId).toBe('string');
      expect(deviceId.length).toBeGreaterThan(0);
    });

    it('should return the same device ID on subsequent calls', async () => {
      const deviceId1 = await SecurityService.getDeviceId();
      const deviceId2 = await SecurityService.getDeviceId();
      expect(deviceId1).toBe(deviceId2);
    });
  });

  describe('Encryption', () => {
    it('should encrypt data', async () => {
      const data = 'sensitive information';
      const encrypted = await SecurityService.encrypt(data);
      expect(encrypted).toBeDefined();
      expect(encrypted).not.toBe(data);
    });

    it('should decrypt encrypted data', async () => {
      const data = 'sensitive information';
      const encrypted = await SecurityService.encrypt(data);
      const decrypted = await SecurityService.decrypt(encrypted);
      expect(decrypted).toBe(data);
    });
  });

  describe('Secure Storage', () => {
    it('should store data securely', async () => {
      await SecurityService.securelyStore('test_key', 'test_value');
      const retrieved = await SecurityService.securelyRetrieve('test_key');
      expect(retrieved).toBe('test_value');
    });

    it('should delete stored data', async () => {
      await SecurityService.securelyStore('test_key', 'test_value');
      await SecurityService.securelyDelete('test_key');
      const retrieved = await SecurityService.securelyRetrieve('test_key');
      expect(retrieved).toBeNull();
    });
  });

  describe('Random Generation', () => {
    it('should generate secure random strings', async () => {
      const random1 = await SecurityService.generateSecureRandom(32);
      const random2 = await SecurityService.generateSecureRandom(32);
      expect(random1).toBeDefined();
      expect(random2).toBeDefined();
      expect(random1).not.toBe(random2);
      expect(random1.length).toBe(64); // 32 bytes = 64 hex characters
    });
  });
});

import { onboardingService } from '../../services/onboarding/onboardingService';

const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: jest.fn((key: string) => store[key] ?? null),
    setItem: jest.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: jest.fn((key: string) => { delete store[key]; }),
    _store: store,
    _reset: () => { store = {}; },
  };
})();
Object.defineProperty(global, 'localStorage', { value: localStorageMock, writable: true });

describe('OnboardingService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorageMock._reset();
    localStorageMock.getItem.mockImplementation((key: string) => localStorageMock._store[key] ?? null);
    localStorageMock.setItem.mockImplementation((key: string, value: string) => { localStorageMock._store[key] = value; });
    localStorageMock.removeItem.mockImplementation((key: string) => { delete localStorageMock._store[key]; });
  });

  describe('isOnboardingComplete', () => {
    it('returns false when not completed', () => {
      expect(onboardingService.isOnboardingComplete()).toBe(false);
    });

    it('returns true after setOnboardingComplete', () => {
      onboardingService.setOnboardingComplete();
      expect(onboardingService.isOnboardingComplete()).toBe(true);
    });
  });

  describe('getOnboardingData / setOnboardingData', () => {
    const data = {
      name: 'John Doe', email: 'john@54link.com', phone: '08099887766',
      address: '1 Lagos St', city: 'Lagos', state: 'Lagos', country: 'NG',
      bvn: '12345678901', nin: '98765432100', platform_role: 'support_agent' as const,
    };

    it('returns null when no data stored', () => {
      expect(onboardingService.getOnboardingData()).toBeNull();
    });

    it('stores and retrieves onboarding data', () => {
      onboardingService.setOnboardingData(data);
      expect(onboardingService.getOnboardingData()).toEqual(data);
    });

    it('returns null on JSON parse error', () => {
      localStorageMock._store['admin_onboarding_data'] = '{invalid json';
      expect(onboardingService.getOnboardingData()).toBeNull();
    });
  });

  describe('resetOnboarding', () => {
    it('clears both onboarding keys', () => {
      onboardingService.setOnboardingComplete();
      onboardingService.setOnboardingData({ name: 'x' } as any);

      onboardingService.resetOnboarding();

      expect(onboardingService.isOnboardingComplete()).toBe(false);
      expect(onboardingService.getOnboardingData()).toBeNull();
    });
  });

  describe('validatePhoneNumber', () => {
    it('validates Nigerian 11-digit format starting with 0', () => {
      expect(onboardingService.validatePhoneNumber('08099887766').valid).toBe(true);
    });

    it('validates Nigerian +234 format (13 digits)', () => {
      expect(onboardingService.validatePhoneNumber('2348099887766').valid).toBe(true);
    });

    it('validates 10-digit format not starting with 0', () => {
      expect(onboardingService.validatePhoneNumber('8099887766').valid).toBe(true);
    });

    it('rejects invalid format', () => {
      const result = onboardingService.validatePhoneNumber('12345');
      expect(result.valid).toBe(false);
      expect(result.error).toBeDefined();
    });

    it('rejects empty string', () => {
      expect(onboardingService.validatePhoneNumber('').valid).toBe(false);
    });
  });

  describe('validateBVN', () => {
    it('accepts exactly 11 digits', () => {
      expect(onboardingService.validateBVN('22345678901').valid).toBe(true);
    });

    it('accepts 11 digits with non-digit separators stripped', () => {
      expect(onboardingService.validateBVN('223-456-78901').valid).toBe(true);
    });

    it('rejects BVN with fewer than 11 digits', () => {
      const result = onboardingService.validateBVN('1234567');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('11 digits');
    });

    it('rejects BVN with more than 11 digits', () => {
      expect(onboardingService.validateBVN('123456789012').valid).toBe(false);
    });
  });

  describe('validateNIN', () => {
    it('accepts exactly 11 digits', () => {
      expect(onboardingService.validateNIN('23456789012').valid).toBe(true);
    });

    it('rejects NIN shorter than 11 digits', () => {
      expect(onboardingService.validateNIN('12345').valid).toBe(false);
    });
  });

  describe('validateEmail', () => {
    it('validates correct email', () => {
      expect(onboardingService.validateEmail('admin@54link.com').valid).toBe(true);
    });

    it('rejects missing @ sign', () => {
      expect(onboardingService.validateEmail('notanemail.com').valid).toBe(false);
    });

    it('rejects empty email', () => {
      expect(onboardingService.validateEmail('').valid).toBe(false);
    });

    it('rejects emails with double dots', () => {
      expect(onboardingService.validateEmail('user..name@example.com').valid).toBe(false);
    });

    it('rejects emails starting with dot', () => {
      expect(onboardingService.validateEmail('.user@example.com').valid).toBe(false);
    });
  });

  describe('validatePhoneNumberAsync', () => {
    it('rejects invalid format without hitting async validation', async () => {
      const result = await onboardingService.validatePhoneNumberAsync('abc');
      expect(result.valid).toBe(false);
    });

    it('accepts valid format and reports it as unverified (no server verification wired)', async () => {
      const result = await onboardingService.validatePhoneNumberAsync('08012345678');
      expect(result.valid).toBe(true);
      expect(result.verified).toBe(false);
    });
  });

  describe('validateBVNAsync', () => {
    it('rejects invalid format without async call', async () => {
      const result = await onboardingService.validateBVNAsync('123');
      expect(result.valid).toBe(false);
    });

    it('accepts 11-digit BVN and reports it as unverified', async () => {
      const result = await onboardingService.validateBVNAsync('22345678901');
      expect(result.valid).toBe(true);
      expect(result.verified).toBe(false);
    });
  });

  describe('validateNINAsync', () => {
    it('accepts 11-digit NIN and reports it as unverified', async () => {
      const result = await onboardingService.validateNINAsync('01234567890');
      expect(result.valid).toBe(true);
      expect(result.verified).toBe(false);
    });

    it('rejects NIN with invalid length', async () => {
      const result = await onboardingService.validateNINAsync('0123456789');
      expect(result.valid).toBe(false);
    });
  });

  describe('validateEmailAsync', () => {
    it('accepts valid email and reports it as unverified', async () => {
      const result = await onboardingService.validateEmailAsync('test@example.com');
      expect(result.valid).toBe(true);
      expect(result.verified).toBe(false);
    });

    it('rejects invalid email format without async validation', async () => {
      const result = await onboardingService.validateEmailAsync('not-an-email');
      expect(result.valid).toBe(false);
    });
  });

  describe('submitOnboarding', () => {
    const validData = {
      name: 'John Doe', email: 'john@54link.com', phone: '08099887766',
      address: '1 Lagos St', city: 'Lagos', state: 'Lagos', country: 'NG',
      bvn: '22345678901', nin: '23456789012', platform_role: 'support_agent' as const,
    };

    it('returns validation errors for invalid fields', async () => {
      const response = await onboardingService.submitOnboarding({ ...validData, bvn: '123' });
      expect(response.success).toBe(false);
      expect(response.errors?.some((error) => error.field === 'bvn')).toBe(true);
    });

    it('fails closed instead of fabricating success when no backend endpoint is configured', async () => {
      await expect(onboardingService.submitOnboarding(validData)).rejects.toThrow(/unavailable/);
      expect(onboardingService.isOnboardingComplete()).toBe(false);
    });
  });
});

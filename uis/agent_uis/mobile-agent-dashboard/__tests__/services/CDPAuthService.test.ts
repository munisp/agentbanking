import { CdpAuthService } from '../../src/services/CDPAuthService';
import axios from 'axios';

let mockStorage: Record<string, string> = {};

const mockAsyncStorage = {
  setItem: jest.fn((key: string, value: string) => { mockStorage[key] = value; return Promise.resolve(); }),
  getItem: jest.fn((key: string) => Promise.resolve(mockStorage[key] ?? null)),
  removeItem: jest.fn((key: string) => { delete mockStorage[key]; return Promise.resolve(); }),
};

jest.mock('@react-native-async-storage/async-storage', () => ({ default: mockAsyncStorage }));
jest.mock('axios');

const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('CdpAuthService', () => {
  let service: CdpAuthService;
  let mockApiPost: jest.Mock;
  let mockApiGet: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    mockStorage = {};

    mockApiPost = jest.fn();
    mockApiGet = jest.fn();

    mockedAxios.create.mockReturnValue({
      post: mockApiPost,
      get: mockApiGet,
      interceptors: {
        request: { use: jest.fn() },
        response: { use: jest.fn() },
      },
    } as any);
    mockedAxios.isAxiosError = jest.fn(() => false) as any;

    service = new CdpAuthService();
  });

  describe('getTokens', () => {
    it('returns tokens when both exist in storage', async () => {
      mockStorage['@CdpAuth:Token'] = 'access-token-123';
      mockStorage['@CdpAuth:RefreshToken'] = 'refresh-token-456';

      const tokens = await service.getTokens();

      expect(tokens).toEqual({ accessToken: 'access-token-123', refreshToken: 'refresh-token-456' });
    });

    it('returns null when tokens are missing', async () => {
      const tokens = await service.getTokens();
      expect(tokens).toBeNull();
    });

    it('returns null when only access token is present', async () => {
      mockStorage['@CdpAuth:Token'] = 'access-token';

      const tokens = await service.getTokens();
      expect(tokens).toBeNull();
    });
  });

  describe('isLoggedIn', () => {
    it('returns true when tokens exist', async () => {
      mockStorage['@CdpAuth:Token'] = 'token';
      mockStorage['@CdpAuth:RefreshToken'] = 'refresh';

      expect(await service.isLoggedIn()).toBe(true);
    });

    it('returns false when no tokens', async () => {
      expect(await service.isLoggedIn()).toBe(false);
    });
  });

  describe('clearSession', () => {
    it('removes both token keys from storage', async () => {
      await service.clearSession();

      expect(mockAsyncStorage.removeItem).toHaveBeenCalledWith('@CdpAuth:Token');
      expect(mockAsyncStorage.removeItem).toHaveBeenCalledWith('@CdpAuth:RefreshToken');
    });
  });

  describe('sendOtp', () => {
    it('returns error response when email is empty', async () => {
      const result = await service.sendOtp('');

      expect(result).toEqual({ success: false, message: 'Email is required for OTP request.' });
      expect(mockApiPost).not.toHaveBeenCalled();
    });

    it('posts to /auth/otp/send with the email', async () => {
      mockApiPost.mockResolvedValue({ data: { success: true, data: { message: 'OTP sent' } } });

      const result = await service.sendOtp('agent@54agent.io');

      expect(mockApiPost).toHaveBeenCalledWith('/auth/otp/send', { email: 'agent@54agent.io' });
      expect(result).toEqual({ success: true, data: { message: 'OTP sent' } });
    });

    it('handles network error with error response', async () => {
      const networkError = new Error('Network Error');
      (networkError as any).request = {};
      mockedAxios.isAxiosError = jest.fn(() => true) as any;
      mockApiPost.mockRejectedValue(networkError);

      const result = await service.sendOtp('agent@54agent.io');

      expect(result.success).toBe(false);
    });
  });

  describe('verifyOtp', () => {
    it('returns error when email or otp is missing', async () => {
      const result = await service.verifyOtp('', '');

      expect(result).toEqual({ success: false, message: 'Email and OTP are required for verification.' });
    });

    it('returns error when only email is provided', async () => {
      const result = await service.verifyOtp('test@test.com', '');

      expect(result).toEqual({ success: false, message: 'Email and OTP are required for verification.' });
    });

    it('saves tokens on successful verification', async () => {
      const authData = { accessToken: 'new-access', refreshToken: 'new-refresh', userId: 'u1', walletCreated: false };
      mockApiPost.mockResolvedValue({ data: { success: true, data: authData } });

      const result = await service.verifyOtp('agent@54agent.io', '123456');

      expect(mockAsyncStorage.setItem).toHaveBeenCalledWith('@CdpAuth:Token', 'new-access');
      expect(mockAsyncStorage.setItem).toHaveBeenCalledWith('@CdpAuth:RefreshToken', 'new-refresh');
      expect(result.success).toBe(true);
    });
  });

  describe('logout', () => {
    it('clears local session even when backend call fails', async () => {
      mockApiPost.mockRejectedValue(new Error('Server error'));

      const result = await service.logout();

      expect(mockAsyncStorage.removeItem).toHaveBeenCalledWith('@CdpAuth:Token');
      expect(mockAsyncStorage.removeItem).toHaveBeenCalledWith('@CdpAuth:RefreshToken');
      expect(result.success).toBe(true);
    });

    it('calls backend logout and returns success', async () => {
      mockApiPost.mockResolvedValue({ data: {} });

      const result = await service.logout();

      expect(mockApiPost).toHaveBeenCalledWith('/auth/logout');
      expect(result.success).toBe(true);
    });
  });

  describe('createWallet', () => {
    it('returns error when user is not logged in', async () => {
      const result = await service.createWallet();

      expect(result).toEqual({ success: false, message: 'User not authenticated. Please log in first.' });
    });

    it('creates wallet when authenticated', async () => {
      mockStorage['@CdpAuth:Token'] = 'access';
      mockStorage['@CdpAuth:RefreshToken'] = 'refresh';
      const walletData = { walletId: 'w-123', message: 'Wallet created' };
      mockApiPost.mockResolvedValue({ data: { success: true, data: walletData } });

      const result = await service.createWallet();

      expect(mockApiPost).toHaveBeenCalledWith('/wallet/create', {});
      expect(result.success).toBe(true);
    });
  });
});

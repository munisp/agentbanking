import { authService } from '../../services/auth/authService';

const mockApiClient = { post: jest.fn(), get: jest.fn() };
jest.mock('../../services/api', () => ({ default: mockApiClient }));

const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: jest.fn((key: string) => store[key] ?? null),
    setItem: jest.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: jest.fn((key: string) => { delete store[key]; }),
    clear: jest.fn(() => { store = {}; }),
    _store: store,
    _reset: () => { store = {}; },
  };
})();

Object.defineProperty(global, 'localStorage', { value: localStorageMock, writable: true });

describe('AuthService (admin)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorageMock._reset();
    localStorageMock.getItem.mockImplementation((key: string) => localStorageMock._store[key] ?? null);
    localStorageMock.setItem.mockImplementation((key: string, value: string) => { localStorageMock._store[key] = value; });
    localStorageMock.removeItem.mockImplementation((key: string) => { delete localStorageMock._store[key]; });
  });

  describe('login', () => {
    it('stores access token and sets auth flag on success', async () => {
      mockApiClient.post.mockResolvedValue({
        data: { access_token: 'access-123', refresh_token: 'refresh-456', keycloak_id: 'kc-1' },
      });

      await authService.login({ email: 'admin@54link.com', password: 'secret', type: 'admin' });

      expect(localStorageMock._store['auth_token']).toBe('access-123');
      expect(localStorageMock._store['access_token']).toBe('access-123');
      expect(localStorageMock._store['54link-dev_auth']).toBe('true');
      expect(localStorageMock._store['keycloak_id']).toBe('kc-1');
    });

    it('stores refresh token when present', async () => {
      mockApiClient.post.mockResolvedValue({
        data: { access_token: 'tok', refresh_token: 'ref-abc' },
      });

      await authService.login({ email: 'a@b.com', password: 'p' });

      expect(localStorageMock._store['refresh_token']).toBe('ref-abc');
    });

    it('stores user when returned in response', async () => {
      const user = { id: 'u1', email: 'admin@54link.com' };
      mockApiClient.post.mockResolvedValue({ data: { access_token: 'tok', user } });

      await authService.login({ email: 'admin@54link.com', password: 'p' });

      expect(localStorageMock._store['auth_user']).toBe(JSON.stringify(user));
    });

    it('posts to /auth/auth/login with credentials', async () => {
      mockApiClient.post.mockResolvedValue({ data: { access_token: 'tok' } });

      await authService.login({ email: 'a@b.com', password: 'pw', type: 'admin' });

      expect(mockApiClient.post).toHaveBeenCalledWith('/auth/auth/login', {
        email: 'a@b.com',
        password: 'pw',
        type: 'admin',
      });
    });

    it('throws extracted error message on API failure', async () => {
      mockApiClient.post.mockRejectedValue({
        response: { data: { detail: { message: 'Invalid credentials' } } },
      });

      await expect(authService.login({ email: 'a@b.com', password: 'wrong' })).rejects.toThrow('Invalid credentials');
    });

    it('throws network error message when no response received', async () => {
      mockApiClient.post.mockRejectedValue({ request: {} });

      await expect(authService.login({ email: 'a@b.com', password: 'pw' })).rejects.toThrow('Network error');
    });
  });

  describe('logout', () => {
    it('removes all auth keys from localStorage', () => {
      localStorageMock._store['auth_token'] = 'tok';
      localStorageMock._store['auth_user'] = '{}';
      localStorageMock._store['54link-dev_auth'] = 'true';

      authService.logout();

      expect(localStorageMock._store['auth_token']).toBeUndefined();
      expect(localStorageMock._store['auth_user']).toBeUndefined();
      expect(localStorageMock._store['54link-dev_auth']).toBeUndefined();
    });
  });

  describe('getToken / setToken / removeToken', () => {
    it('sets and gets token', () => {
      authService.setToken('my-token');
      expect(authService.getToken()).toBe('my-token');
    });

    it('returns null when no token is set', () => {
      expect(authService.getToken()).toBeNull();
    });

    it('removes token', () => {
      authService.setToken('tok');
      authService.removeToken();
      expect(authService.getToken()).toBeNull();
    });
  });

  describe('getUser / setUser / removeUser', () => {
    const user = { id: 'u1', email: 'admin@54link.com' };

    it('sets and gets user', () => {
      authService.setUser(user);
      expect(authService.getUser()).toEqual(user);
    });

    it('returns null when no user stored', () => {
      expect(authService.getUser()).toBeNull();
    });

    it('removes user', () => {
      authService.setUser(user);
      authService.removeUser();
      expect(authService.getUser()).toBeNull();
    });

    it('returns null when stored user JSON is invalid', () => {
      localStorageMock._store['auth_user'] = 'invalid-json{';
      expect(authService.getUser()).toBeNull();
    });
  });

  describe('isAuthenticated', () => {
    it('returns true when token exists', () => {
      authService.setToken('tok');
      expect(authService.isAuthenticated()).toBe(true);
    });

    it('returns false when no token', () => {
      expect(authService.isAuthenticated()).toBe(false);
    });
  });

  describe('changePassword', () => {
    it('posts to /auth/auth/change-password', async () => {
      mockApiClient.post.mockResolvedValue({ data: { success: true } });

      await authService.changePassword('OldPass1!', 'NewPass1!', 'NewPass1!');

      expect(mockApiClient.post).toHaveBeenCalledWith('/auth/auth/change-password', {
        current_password: 'OldPass1!',
        new_password: 'NewPass1!',
        confirm_password: 'NewPass1!',
      });
    });

    it('throws on change password failure', async () => {
      mockApiClient.post.mockRejectedValue({
        response: { data: { message: 'Incorrect current password' } },
      });

      await expect(authService.changePassword('wrong', 'new', 'new')).rejects.toThrow('Incorrect current password');
    });
  });

  describe('fetchUserDetails', () => {
    it('fetches user from API using keycloak_id in localStorage', async () => {
      localStorageMock._store['keycloak_id'] = 'kc-uuid-1';
      const userData = { id: 'u1', email: 'admin@54link.com', keycloak_id: 'kc-uuid-1', access_level: 'super_admin' };
      mockApiClient.get.mockResolvedValue({ data: { admin: userData } });

      const result = await authService.fetchUserDetails();

      expect(mockApiClient.get).toHaveBeenCalledWith('/admin/admin/keycloak/kc-uuid-1');
      expect(result).toEqual(userData);
      expect(localStorageMock._store['platform_role']).toBe('super_admin');
    });

    it('returns null and does not throw when keycloak_id is not found', async () => {
      const result = await authService.fetchUserDetails();
      expect(result).toBeNull();
    });

    it('returns null when API call fails (non-fatal)', async () => {
      localStorageMock._store['keycloak_id'] = 'kc-1';
      mockApiClient.get.mockRejectedValue(new Error('API down'));

      const result = await authService.fetchUserDetails();

      expect(result).toBeNull();
    });
  });
});

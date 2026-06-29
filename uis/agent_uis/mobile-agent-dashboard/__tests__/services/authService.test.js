import { authService } from '../../src/services/authService';

let mockStore = {};

jest.mock('expo-secure-store', () => ({
  setItemAsync: jest.fn((key, value) => { mockStore[key] = value; return Promise.resolve(); }),
  getItemAsync: jest.fn((key) => Promise.resolve(mockStore[key] ?? null)),
  deleteItemAsync: jest.fn((key) => { delete mockStore[key]; return Promise.resolve(); }),
}));

const mockAuthApi = { login: jest.fn(), logout: jest.fn(), refresh: jest.fn() };
const mockAgentApi = { getAgentByKeycloakId: jest.fn() };
const mockUserApi = { getUserByKeycloakId: jest.fn() };
const mockTenantService = { getTenantId: jest.fn(), getTenant: jest.fn() };

jest.mock('../../src/services/apiService', () => ({
  authApi: mockAuthApi,
  agentApi: mockAgentApi,
  userApi: mockUserApi,
}));

jest.mock('../../src/services/tenantService', () => ({ default: mockTenantService }));

describe('authService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockStore = {};
    mockTenantService.getTenantId.mockResolvedValue('bpmgd');
    mockTenantService.getTenant.mockResolvedValue({ tenant_id: 'bpmgd' });
  });

  describe('login', () => {
    it('stores auth token on successful login', async () => {
      mockAuthApi.login.mockResolvedValue({ access_token: 'token-abc', refresh_token: 'refresh-xyz', keycloak_id: 'kc-1' });
      mockUserApi.getUserByKeycloakId.mockResolvedValue({ user: { id: 'u1', name: 'John' } });
      mockAgentApi.getAgentByKeycloakId.mockResolvedValue({ agent: { id: 'a1', name: 'Agent John' } });

      const result = await authService.login('agent@example.com', 'password123');

      expect(mockStore['authToken']).toBe('token-abc');
      expect(mockStore['refreshToken']).toBe('refresh-xyz');
      expect(mockStore['keycloakId']).toBe('kc-1');
      expect(result.token).toBe('token-abc');
    });

    it('stores agent profile and id on successful login', async () => {
      mockAuthApi.login.mockResolvedValue({ access_token: 'tok', refresh_token: 'ref', keycloak_id: 'kc-1' });
      mockUserApi.getUserByKeycloakId.mockResolvedValue({ user: { name: 'John', email: 'j@j.com' } });
      mockAgentApi.getAgentByKeycloakId.mockResolvedValue({ agent: { id: 'agent-id-1', name: 'John Agent' } });

      await authService.login('agent@example.com', 'pass');

      expect(mockStore['agentId']).toBe('agent-id-1');
    });

    it('throws when no access token in response', async () => {
      mockAuthApi.login.mockResolvedValue({ refresh_token: 'ref' });

      await expect(authService.login('x@y.com', 'pass')).rejects.toThrow('No access token in login response');
    });

    it('loads tenant config before calling auth API', async () => {
      mockAuthApi.login.mockResolvedValue({ access_token: 'tok', refresh_token: 'ref', keycloak_id: 'kc-1' });
      mockUserApi.getUserByKeycloakId.mockResolvedValue({ user: {} });
      mockAgentApi.getAgentByKeycloakId.mockResolvedValue({ agent: {} });

      await authService.login('a@b.com', 'pass');

      expect(mockTenantService.getTenantId).toHaveBeenCalled();
      expect(mockTenantService.getTenant).toHaveBeenCalled();
    });

    it('propagates login errors', async () => {
      mockAuthApi.login.mockRejectedValue(new Error('Invalid credentials'));

      await expect(authService.login('bad@user.com', 'wrong')).rejects.toThrow('Invalid credentials');
    });

    it('continues login even when user/agent fetch fails', async () => {
      mockAuthApi.login.mockResolvedValue({ access_token: 'tok', refresh_token: 'ref', keycloak_id: 'kc-1' });
      mockUserApi.getUserByKeycloakId.mockRejectedValue(new Error('User service down'));
      mockAgentApi.getAgentByKeycloakId.mockRejectedValue(new Error('Agent service down'));

      const result = await authService.login('a@b.com', 'pass');

      expect(result.token).toBe('tok');
      expect(result.userDetails).toBeNull();
      expect(result.agentProfile).toBeNull();
    });
  });

  describe('signup', () => {
    it('always throws directing user to admin panel', async () => {
      await expect(authService.signup({ email: 'new@agent.com' })).rejects.toThrow('admin panel');
    });
  });

  describe('validateToken', () => {
    it('returns fresh agent profile when keycloak id is stored', async () => {
      mockStore['keycloakId'] = 'kc-1';
      const profile = { id: 'agent-1', name: 'Agent' };
      mockAgentApi.getAgentByKeycloakId.mockResolvedValue({ agent: profile });

      const result = await authService.validateToken('some-token');

      expect(result).toEqual(profile);
    });

    it('falls back to cached profile when agent API fails', async () => {
      mockStore['keycloakId'] = 'kc-1';
      const cached = { id: 'cached-agent' };
      mockStore['agentProfile'] = JSON.stringify(cached);
      mockAgentApi.getAgentByKeycloakId.mockRejectedValue(new Error('API down'));

      const result = await authService.validateToken('token');

      expect(result).toEqual(cached);
    });

    it('throws when no keycloak id is stored', async () => {
      await expect(authService.validateToken('tok')).rejects.toThrow('No keycloak ID found');
    });

    it('throws when API fails and no cached profile', async () => {
      mockStore['keycloakId'] = 'kc-1';
      mockAgentApi.getAgentByKeycloakId.mockRejectedValue(new Error('fail'));

      await expect(authService.validateToken('tok')).rejects.toThrow('No agent profile available');
    });
  });

  describe('logout', () => {
    it('clears all stored credentials', async () => {
      mockStore['authToken'] = 'tok';
      mockStore['refreshToken'] = 'ref';
      mockStore['keycloakId'] = 'kc-1';
      mockAuthApi.logout.mockResolvedValue({});

      await authService.logout();

      expect(mockStore['authToken']).toBeUndefined();
      expect(mockStore['refreshToken']).toBeUndefined();
      expect(mockStore['keycloakId']).toBeUndefined();
    });

    it('calls logout API when refresh token exists', async () => {
      mockStore['refreshToken'] = 'ref-token';
      mockAuthApi.logout.mockResolvedValue({});

      await authService.logout();

      expect(mockAuthApi.logout).toHaveBeenCalledWith('ref-token');
    });

    it('still clears local data when logout API fails', async () => {
      mockStore['authToken'] = 'tok';
      mockStore['refreshToken'] = 'ref';
      mockAuthApi.logout.mockRejectedValue(new Error('Server error'));

      const result = await authService.logout();

      expect(mockStore['authToken']).toBeUndefined();
      expect(result.success).toBe(true);
    });

    it('succeeds even when no refresh token', async () => {
      const result = await authService.logout();

      expect(mockAuthApi.logout).not.toHaveBeenCalled();
      expect(result.success).toBe(true);
    });
  });

  describe('refreshAccessToken', () => {
    it('refreshes and stores new tokens', async () => {
      mockStore['refreshToken'] = 'old-refresh';
      mockAuthApi.refresh.mockResolvedValue({ access_token: 'new-tok', refresh_token: 'new-ref' });

      const result = await authService.refreshAccessToken();

      expect(mockStore['authToken']).toBe('new-tok');
      expect(mockStore['refreshToken']).toBe('new-ref');
      expect(result.access_token).toBe('new-tok');
    });

    it('throws when no refresh token available', async () => {
      await expect(authService.refreshAccessToken()).rejects.toThrow('No refresh token available');
    });
  });

  describe('resetPassword', () => {
    it('throws with not-yet-available message', async () => {
      await expect(authService.resetPassword('user@example.com')).rejects.toThrow('coming soon');
    });
  });
});

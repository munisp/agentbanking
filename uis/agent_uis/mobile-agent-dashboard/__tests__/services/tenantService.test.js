import tenantService from '../../src/services/tenantService';

let mockStore = {};

jest.mock('expo-secure-store', () => ({
  setItemAsync: jest.fn((key, value) => { mockStore[key] = value; return Promise.resolve(); }),
  getItemAsync: jest.fn((key) => Promise.resolve(mockStore[key] ?? null)),
  deleteItemAsync: jest.fn((key) => { delete mockStore[key]; return Promise.resolve(); }),
}));

jest.mock('../../src/services/apiService', () => ({
  tenantApi: { getTenant: jest.fn() },
}));

global.fetch = jest.fn();

describe('tenantService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockStore = {};
  });

  describe('getTenantId', () => {
    it('returns stored tenant id when present', async () => {
      mockStore['tenant_id'] = 'custom-tenant';

      const id = await tenantService.getTenantId();

      expect(id).toBe('custom-tenant');
    });

    it('returns default tenant id when none stored', async () => {
      const id = await tenantService.getTenantId();

      expect(id).toBe('bpmgd');
    });
  });

  describe('setTenantId', () => {
    it('stores tenant id in SecureStore', async () => {
      await tenantService.setTenantId('my-tenant');

      expect(mockStore['tenant_id']).toBe('my-tenant');
    });
  });

  describe('getTenantConfig', () => {
    it('returns parsed config when stored', async () => {
      const config = { tenant_id: 'abc', name: 'Test Tenant' };
      mockStore['tenant_config'] = JSON.stringify(config);

      const result = await tenantService.getTenantConfig();

      expect(result).toEqual(config);
    });

    it('returns null when no config is stored', async () => {
      const result = await tenantService.getTenantConfig();

      expect(result).toBeNull();
    });

    it('returns null on JSON parse error', async () => {
      mockStore['tenant_config'] = 'invalid-json{{{';

      const result = await tenantService.getTenantConfig();

      expect(result).toBeNull();
    });
  });

  describe('getKeycloakRealm', () => {
    it('extracts realm from auth feature flag', async () => {
      const config = {
        feature_flags: [
          { name: 'auth', config: { realm: 'my-realm' } },
        ],
      };
      mockStore['tenant_config'] = JSON.stringify(config);

      const realm = await tenantService.getKeycloakRealm();

      expect(realm).toBe('my-realm');
    });

    it('falls back to tenant_id when auth flag has no realm', async () => {
      const config = { feature_flags: [{ name: 'auth', config: {} }] };
      mockStore['tenant_config'] = JSON.stringify(config);
      mockStore['tenant_id'] = 'fallback-realm';

      const realm = await tenantService.getKeycloakRealm();

      expect(realm).toBe('fallback-realm');
    });

    it('falls back to "remittance" when no config at all', async () => {
      const realm = await tenantService.getKeycloakRealm();

      expect(realm).toBe('remittance');
    });
  });

  describe('getKeycloakPubKey', () => {
    it('extracts public RSA key from auth feature flag', async () => {
      const config = {
        feature_flags: [
          { name: 'auth', config: { public_rsa_key: 'rsa-pub-key-abc' } },
        ],
      };
      mockStore['tenant_config'] = JSON.stringify(config);

      const key = await tenantService.getKeycloakPubKey();

      expect(key).toBe('rsa-pub-key-abc');
    });

    it('returns "default" when no key in config', async () => {
      const key = await tenantService.getKeycloakPubKey();

      expect(key).toBe('default');
    });
  });

  describe('getTenant', () => {
    it('returns cached config without hitting API', async () => {
      const cached = { tenant_id: 'cached-id', name: 'Cached Tenant' };
      mockStore['tenant_config'] = JSON.stringify(cached);

      const result = await tenantService.getTenant('any-id');

      expect(global.fetch).not.toHaveBeenCalled();
      expect(result).toEqual(cached);
    });

    it('fetches from API when no cache and stores result', async () => {
      const tenant = { tenant_id: 'api-tenant', name: 'API Tenant' };
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ message: 'success', tenant }),
      });

      const result = await tenantService.getTenant('api-tenant');

      expect(global.fetch).toHaveBeenCalled();
      expect(mockStore['tenant_config']).toBe(JSON.stringify(tenant));
      expect(result).toEqual(tenant);
    });

    it('throws when no tenant id provided and none stored', async () => {
      await expect(tenantService.getTenant(null)).rejects.toThrow('Tenant ID is required');
    });

    it('throws when API response is not success', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ message: 'error', tenant: null }),
      });

      await expect(tenantService.getTenant('bad-id')).rejects.toThrow('Invalid tenant response from API');
    });

    it('throws when HTTP response is not ok', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: () => Promise.resolve({}),
      });

      await expect(tenantService.getTenant('missing')).rejects.toThrow('HTTP 404');
    });
  });

  describe('clearTenantConfig', () => {
    it('removes both tenant keys from SecureStore', async () => {
      mockStore['tenant_config'] = '{}';
      mockStore['tenant_id'] = 'x';

      await tenantService.clearTenantConfig();

      expect(mockStore['tenant_config']).toBeUndefined();
      expect(mockStore['tenant_id']).toBeUndefined();
    });
  });

  describe('reloadTenantConfig', () => {
    it('clears cache then fetches fresh config', async () => {
      mockStore['tenant_config'] = JSON.stringify({ old: true });
      const fresh = { tenant_id: 'fresh', name: 'Fresh' };
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ message: 'success', tenant: fresh }),
      });

      const result = await tenantService.reloadTenantConfig('fresh');

      expect(result).toEqual(fresh);
    });
  });
});

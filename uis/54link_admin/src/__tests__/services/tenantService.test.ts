import { tenantService, GLOBAL_FEATURE_CATALOG } from '../../services/tenant/tenantService';

const mockApiClient = { get: jest.fn(), put: jest.fn(), delete: jest.fn() };
jest.mock('../../services/api', () => ({ default: mockApiClient }));
jest.mock('../../services/tenant/getTenantHeaders', () => ({
  getTenantHeaders: jest.fn(() => ({ 'x-tenant-id': 'bpmgd' })),
}));

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

// Must mock import.meta.env for Vite
Object.defineProperty(global, 'import', {
  value: { meta: { env: { DEV: false, VITE_TENANT_ID: 'bpmgd' } } },
  writable: true,
});

describe('TenantService (admin)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorageMock._reset();
    localStorageMock.getItem.mockImplementation((key: string) => localStorageMock._store[key] ?? null);
    localStorageMock.setItem.mockImplementation((key: string, value: string) => { localStorageMock._store[key] = value; });
    localStorageMock.removeItem.mockImplementation((key: string) => { delete localStorageMock._store[key]; });
  });

  describe('getTenant', () => {
    it('always returns the 54link default data', async () => {
      const tenant = await tenantService.getTenant();

      expect(tenant.name).toBe('54Link');
      expect(tenant.tenant_id).toBe('bpmgd');
      expect(tenant.status).toBe('active');
    });

    it('returns default data regardless of tenantId argument', async () => {
      const tenant = await tenantService.getTenant('any-id');

      expect(tenant.tenant_id).toBe('bpmgd');
    });

    it('returns tenant with all feature flags enabled', async () => {
      const tenant = await tenantService.getTenant();

      expect(tenant.feature_flags.length).toBeGreaterThan(0);
      expect(tenant.feature_flags.every(f => f.is_enabled)).toBe(true);
    });
  });

  describe('getTenantConfig', () => {
    it('always returns the 54link default data (not localStorage)', () => {
      const config = tenantService.getTenantConfig();

      expect(config).not.toBeNull();
      expect(config!.name).toBe('54Link');
    });
  });

  describe('hasTenantConfig', () => {
    it('always returns true', () => {
      expect(tenantService.hasTenantConfig()).toBe(true);
    });
  });

  describe('setTenantId', () => {
    it('stores tenant id in localStorage', () => {
      tenantService.setTenantId('new-tenant-id');

      expect(localStorageMock._store['tenant_id']).toBe('new-tenant-id');
    });
  });

  describe('getFeatureFlagsByRole', () => {
    it('returns all feature flags from the default tenant', () => {
      const flags = tenantService.getFeatureFlagsByRole();

      expect(Array.isArray(flags)).toBe(true);
      expect(flags.length).toBeGreaterThan(0);
    });

    it('returns all enabled flags', () => {
      const flags = tenantService.getFeatureFlagsByRole();

      expect(flags.every(f => f.is_enabled)).toBe(true);
    });
  });

  describe('getTenantHeaders', () => {
    it('returns tenant headers object', () => {
      const headers = tenantService.getTenantHeaders();

      expect(headers).toHaveProperty('x-tenant-id');
    });
  });

  describe('getAllTenants', () => {
    it('fetches and returns tenants list with metrics', async () => {
      const apiResponse = {
        message: 'success',
        tenants: [{ id: 1, name: 'Tenant A' }, { id: 2, name: 'Tenant B' }],
        metrics: { total: 2, standard: 1, premium: 1, enterprise: 0 },
      };
      mockApiClient.get.mockResolvedValue({ data: apiResponse });

      const result = await tenantService.getAllTenants();

      expect(mockApiClient.get).toHaveBeenCalledWith('/tenant-management/tenant/all');
      expect(result.tenants).toHaveLength(2);
      expect(result.metrics.total).toBe(2);
    });

    it('returns empty array and zero metrics when API returns none', async () => {
      mockApiClient.get.mockResolvedValue({ data: { message: 'success', tenants: [], metrics: null } });

      const result = await tenantService.getAllTenants();

      expect(result.tenants).toEqual([]);
      expect(result.metrics.total).toBe(0);
    });

    it('throws when API response message is not success', async () => {
      mockApiClient.get.mockResolvedValue({ data: { message: 'error' } });

      await expect(tenantService.getAllTenants()).rejects.toThrow('Invalid response format');
    });
  });

  describe('updateTenant', () => {
    it('puts tenant data and returns updated tenant', async () => {
      const updated = { id: 1, name: 'Updated Tenant', tenant_id: 't1', status: 'active' };
      mockApiClient.put.mockResolvedValue({ data: { message: 'success', tenant: updated } });

      const result = await tenantService.updateTenant('t1', { name: 'Updated Tenant' });

      expect(mockApiClient.put).toHaveBeenCalledWith(
        '/tenant-management/tenant/t1',
        { name: 'Updated Tenant' }
      );
      expect(result).toEqual(updated);
    });

    it('throws when update response format is invalid', async () => {
      mockApiClient.put.mockResolvedValue({ data: { message: 'failure' } });

      await expect(tenantService.updateTenant('t1', {})).rejects.toThrow('Invalid response format');
    });
  });

  describe('deleteTenant', () => {
    it('deletes tenant by id', async () => {
      mockApiClient.delete.mockResolvedValue({ data: { message: 'success' } });

      await expect(tenantService.deleteTenant('t1')).resolves.toBeUndefined();

      expect(mockApiClient.delete).toHaveBeenCalledWith('/tenant-management/tenant/t1');
    });

    it('throws when delete response is not success', async () => {
      mockApiClient.delete.mockResolvedValue({ data: { message: 'error' } });

      await expect(tenantService.deleteTenant('t1')).rejects.toThrow('Invalid response format');
    });
  });

  describe('changeTenant', () => {
    it('sets new tenant id and fetches tenant config', async () => {
      const tenant = await tenantService.changeTenant('new-tenant');

      expect(localStorageMock._store['tenant_id']).toBe('new-tenant');
      expect(tenant.name).toBe('54Link');
    });
  });

  describe('getGlobalFeatures', () => {
    it('fetches global features from API', async () => {
      const features = [{ name: 'auth', is_enabled: true }];
      mockApiClient.get.mockResolvedValue({ data: { message: 'success', tenants: features } });

      const result = await tenantService.getGlobalFeatures();

      expect(result[0].name).toBe('auth');
      expect(result[0].is_enabled).toBe(true);
    });

    it('falls back to GLOBAL_FEATURE_CATALOG when API fails', async () => {
      mockApiClient.get.mockRejectedValue(new Error('API unavailable'));

      const result = await tenantService.getGlobalFeatures();

      expect(result.length).toBe(GLOBAL_FEATURE_CATALOG.length);
      expect(result.every(f => !f.is_enabled)).toBe(true);
    });

    it('falls back when API response shape is unexpected', async () => {
      mockApiClient.get.mockResolvedValue({ data: { message: 'error', tenants: null } });

      const result = await tenantService.getGlobalFeatures();

      expect(result.length).toBe(GLOBAL_FEATURE_CATALOG.length);
    });
  });
});

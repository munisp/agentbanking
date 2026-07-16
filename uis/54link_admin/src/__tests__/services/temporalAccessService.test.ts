import { temporalAccessService } from '../../services/temporalAccessService';

const mockApi = { get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn() };
jest.mock('../../services/api', () => ({ default: mockApi }));

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

describe('TemporalAccessService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorageMock._reset();
    localStorageMock.getItem.mockImplementation((key: string) => localStorageMock._store[key] ?? null);
  });

  describe('listGrants', () => {
    it('fetches grants for a tenant', async () => {
      const grants = [{ id: 'g1', permission: 'read' }, { id: 'g2', permission: 'write' }];
      mockApi.get.mockResolvedValue({ data: { grants } });

      const result = await temporalAccessService.listGrants('tenant-1');

      expect(mockApi.get).toHaveBeenCalledWith(
        expect.stringContaining('tenant_id=tenant-1')
      );
      expect(result).toEqual(grants);
    });

    it('returns empty array when grants key is missing', async () => {
      mockApi.get.mockResolvedValue({ data: {} });

      const result = await temporalAccessService.listGrants('tenant-1');

      expect(result).toEqual([]);
    });
  });

  describe('getGrant', () => {
    it('fetches a single grant by id', async () => {
      const grant = { id: 'g1', permission: 'read', status: 'active' };
      mockApi.get.mockResolvedValue({ data: grant });

      const result = await temporalAccessService.getGrant('g1', 'tenant-1');

      expect(mockApi.get).toHaveBeenCalledWith(
        expect.stringContaining('/grants/g1')
      );
      expect(result).toEqual(grant);
    });
  });

  describe('createGrant', () => {
    const grantRequest = {
      tenant_id: 'tenant-1',
      subject_id: 'user-1',
      subject_type: 'user',
      permission: 'read',
      resource_type: 'account',
      resource_id: 'acc-1',
      duration: '2h',
      reason: 'Audit review',
    };

    it('posts grant request and returns created grant', async () => {
      const created = { id: 'g-new', ...grantRequest, status: 'active' };
      mockApi.post.mockResolvedValue({ data: created });

      const result = await temporalAccessService.createGrant(grantRequest);

      expect(mockApi.post).toHaveBeenCalledWith(
        expect.stringContaining('/grants'),
        grantRequest
      );
      expect(result.id).toBe('g-new');
    });
  });

  describe('revokeGrant', () => {
    it('deletes grant by id', async () => {
      mockApi.delete.mockResolvedValue({ data: {} });

      await temporalAccessService.revokeGrant('g1', 'tenant-1');

      expect(mockApi.delete).toHaveBeenCalledWith(
        expect.stringContaining('/grants/g1')
      );
    });
  });

  describe('extendGrant', () => {
    it('posts extension request with duration', async () => {
      const extended = { id: 'g1', expires_at: '2024-12-31T23:59:59Z' };
      mockApi.post.mockResolvedValue({ data: extended });

      const result = await temporalAccessService.extendGrant('g1', 'tenant-1', '4h');

      expect(mockApi.post).toHaveBeenCalledWith(
        expect.stringContaining('/grants/g1/extend'),
        { duration: '4h' }
      );
      expect(result.id).toBe('g1');
    });
  });

  describe('updateGrant', () => {
    it('puts grant update data', async () => {
      const updated = { id: 'g1', max_usage: 5 };
      mockApi.put.mockResolvedValue({ data: updated });

      const result = await temporalAccessService.updateGrant('g1', 'tenant-1', { max_usage: 5 });

      expect(mockApi.put).toHaveBeenCalledWith(
        expect.stringContaining('/grants/g1'),
        { max_usage: 5 }
      );
      expect(result.max_usage).toBe(5);
    });
  });

  describe('listPolicies', () => {
    it('fetches policies for tenant', async () => {
      const policies = [{ id: 'p1', name: 'Read Policy' }];
      mockApi.get.mockResolvedValue({ data: { policies } });

      const result = await temporalAccessService.listPolicies('tenant-1');

      expect(result).toEqual(policies);
    });

    it('returns empty array when policies key is missing', async () => {
      mockApi.get.mockResolvedValue({ data: {} });

      const result = await temporalAccessService.listPolicies('tenant-1');

      expect(result).toEqual([]);
    });
  });

  describe('createPolicy', () => {
    it('posts policy and returns created policy', async () => {
      const policyReq = {
        tenant_id: 'tenant-1',
        name: 'Audit Policy',
        description: 'Allow audit reads',
        resource_type: 'transaction',
        permission: 'read',
        priority: 1,
        enabled: true,
        rules: [],
      };
      const created = { id: 'p-new', ...policyReq };
      mockApi.post.mockResolvedValue({ data: created });

      const result = await temporalAccessService.createPolicy(policyReq);

      expect(mockApi.post).toHaveBeenCalledWith(expect.stringContaining('/policies'), policyReq);
      expect(result.id).toBe('p-new');
    });
  });

  describe('updatePolicy', () => {
    it('puts policy update', async () => {
      const updated = { id: 'p1', enabled: false };
      mockApi.put.mockResolvedValue({ data: updated });

      const result = await temporalAccessService.updatePolicy('p1', { enabled: false });

      expect(mockApi.put).toHaveBeenCalledWith(
        expect.stringContaining('/policies/p1'),
        { enabled: false }
      );
      expect(result.enabled).toBe(false);
    });
  });

  describe('deletePolicy', () => {
    it('deletes policy by id', async () => {
      mockApi.delete.mockResolvedValue({ data: {} });

      await temporalAccessService.deletePolicy('p1');

      expect(mockApi.delete).toHaveBeenCalledWith(expect.stringContaining('/policies/p1'));
    });
  });

  describe('checkAccess', () => {
    it('posts access check and returns response', async () => {
      const checkReq = {
        tenant_id: 'tenant-1',
        subject_id: 'user-1',
        permission: 'read',
        resource_type: 'account',
        resource_id: 'acc-1',
      };
      const response = { allowed: true, reason: 'Grant found', grant_id: 'g1' };
      mockApi.post.mockResolvedValue({ data: response });

      const result = await temporalAccessService.checkAccess(checkReq);

      expect(mockApi.post).toHaveBeenCalledWith(
        expect.stringContaining('/authorize'),
        checkReq
      );
      expect(result.allowed).toBe(true);
    });
  });

  describe('listUserGrants', () => {
    it('returns grants from array response', async () => {
      const grants = [{ id: 'g1' }];
      mockApi.get.mockResolvedValue({ data: grants });

      const result = await temporalAccessService.listUserGrants('tenant-1');

      expect(result).toEqual(grants);
    });

    it('returns grants from grants key', async () => {
      const grants = [{ id: 'g2' }];
      mockApi.get.mockResolvedValue({ data: { grants } });

      const result = await temporalAccessService.listUserGrants('tenant-1');

      expect(result).toEqual(grants);
    });

    it('returns empty array when no grants', async () => {
      mockApi.get.mockResolvedValue({ data: {} });

      const result = await temporalAccessService.listUserGrants('tenant-1');

      expect(result).toEqual([]);
    });
  });

  describe('listDelegations', () => {
    it('uses keycloak_id from localStorage as delegate_id when none provided', async () => {
      localStorageMock._store['keycloak_id'] = 'kc-current-user';
      mockApi.get.mockResolvedValue({ data: [] });

      await temporalAccessService.listDelegations('tenant-1');

      expect(mockApi.get).toHaveBeenCalledWith(
        expect.stringContaining('delegate_id=kc-current-user')
      );
    });

    it('uses provided delegateId over keycloak_id', async () => {
      localStorageMock._store['keycloak_id'] = 'kc-other';
      mockApi.get.mockResolvedValue({ data: [] });

      await temporalAccessService.listDelegations('tenant-1', 'explicit-delegate');

      expect(mockApi.get).toHaveBeenCalledWith(
        expect.stringContaining('delegate_id=explicit-delegate')
      );
    });

    it('returns delegations from delegations key', async () => {
      const delegations = [{ id: 'd1' }];
      mockApi.get.mockResolvedValue({ data: { delegations } });

      const result = await temporalAccessService.listDelegations('tenant-1');

      expect(result).toEqual(delegations);
    });
  });

  describe('createDelegation', () => {
    it('posts delegation request', async () => {
      const req = {
        tenant_id: 'tenant-1',
        delegator_id: 'admin-1',
        delegate_id: 'user-1',
        permission: 'approve',
        resource_type: 'loan',
        resource_id: 'loan-1',
      };
      const created = { id: 'd-new', ...req };
      mockApi.post.mockResolvedValue({ data: created });

      const result = await temporalAccessService.createDelegation(req);

      expect(result.id).toBe('d-new');
    });
  });

  describe('revokeDelegation', () => {
    it('deletes delegation by id', async () => {
      mockApi.delete.mockResolvedValue({ data: {} });

      await temporalAccessService.revokeDelegation('d1');

      expect(mockApi.delete).toHaveBeenCalledWith(expect.stringContaining('/delegations/d1'));
    });
  });

  describe('searchUsers', () => {
    it('returns all users and admins when no search term', async () => {
      const users = [{ email: 'user1@test.com', keycloak_id: 'kc-1', id: 'u1' }];
      const admins = [{ email: 'admin1@test.com', keycloak_id: 'kc-2', id: 'a1' }];
      mockApi.get
        .mockResolvedValueOnce({ data: { users } })
        .mockResolvedValueOnce({ data: { admins } });

      const result = await temporalAccessService.searchUsers('', 'tenant-1');

      expect(result).toHaveLength(2);
    });

    it('filters results by email search term', async () => {
      const users = [
        { email: 'alice@test.com', keycloak_id: 'kc-1', id: 'u1' },
        { email: 'bob@test.com', keycloak_id: 'kc-2', id: 'u2' },
      ];
      mockApi.get
        .mockResolvedValueOnce({ data: { users } })
        .mockResolvedValueOnce({ data: [] });

      const result = await temporalAccessService.searchUsers('alice', 'tenant-1');

      expect(result).toHaveLength(1);
      expect(result[0].email).toBe('alice@test.com');
    });

    it('returns empty array when both API calls fail', async () => {
      mockApi.get.mockRejectedValue(new Error('Service unavailable'));

      const result = await temporalAccessService.searchUsers('query', 'tenant-1');

      expect(result).toEqual([]);
    });

    it('filters users without email or keycloak_id', async () => {
      const users = [
        { email: 'valid@test.com', keycloak_id: 'kc-1', id: 'u1' },
        { email: null, keycloak_id: 'kc-2', id: 'u2' },
        { email: 'valid2@test.com', keycloak_id: null, id: 'u3' },
      ];
      mockApi.get
        .mockResolvedValueOnce({ data: users })
        .mockResolvedValueOnce({ data: [] });

      const result = await temporalAccessService.searchUsers('', 'tenant-1');

      expect(result).toHaveLength(1);
      expect(result[0].email).toBe('valid@test.com');
    });
  });
});

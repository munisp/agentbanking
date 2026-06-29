import {
  createAdmin,
  getAdminById,
  getAdminByKeycloakId,
  getAdmins,
  suspendAdmin,
  unsuspendAdmin,
} from '../../services/admin/adminService';

const mockApiClient = { post: jest.fn(), get: jest.fn(), patch: jest.fn() };
jest.mock('../../services/api', () => ({ default: mockApiClient }));
jest.mock('../../const', () => ({ BACKEND_URL: 'https://54agent.upi.dev' }));

describe('adminService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('createAdmin', () => {
    const adminPayload = {
      email: 'newadmin@54link.com',
      firstName: 'Jane',
      lastName: 'Doe',
      phone: '08012345678',
      uin: '123456789',
      password: 'SecurePass1!',
    };

    it('posts to orchestrator endpoint and returns data', async () => {
      const created = { id: 'adm-1', ...adminPayload };
      mockApiClient.post.mockResolvedValue({ data: created });

      const result = await createAdmin(adminPayload);

      expect(mockApiClient.post).toHaveBeenCalledWith(
        expect.stringContaining('/orchestrator/admin'),
        adminPayload
      );
      expect(result).toEqual(created);
    });

    it('propagates API errors', async () => {
      mockApiClient.post.mockRejectedValue(new Error('Email already exists'));

      await expect(createAdmin(adminPayload)).rejects.toThrow('Email already exists');
    });
  });

  describe('getAdminById', () => {
    it('fetches admin by numeric id', async () => {
      const admin = { id: 42, email: 'admin42@54link.com' };
      mockApiClient.get.mockResolvedValue({ data: admin });

      const result = await getAdminById(42);

      expect(mockApiClient.get).toHaveBeenCalledWith(expect.stringContaining('/admin/admin/42'));
      expect(result).toEqual(admin);
    });

    it('fetches admin by string id', async () => {
      mockApiClient.get.mockResolvedValue({ data: { id: 'str-id' } });

      const result = await getAdminById('str-id');

      expect(mockApiClient.get).toHaveBeenCalledWith(expect.stringContaining('/admin/admin/str-id'));
      expect(result.id).toBe('str-id');
    });

    it('propagates not-found error', async () => {
      mockApiClient.get.mockRejectedValue(new Error('Admin not found'));

      await expect(getAdminById(999)).rejects.toThrow('Admin not found');
    });
  });

  describe('getAdminByKeycloakId', () => {
    it('fetches admin by keycloak id', async () => {
      const admin = { id: 1, email: 'admin@54link.com', keycloak_id: 'kc-uuid-1' };
      mockApiClient.get.mockResolvedValue({ data: admin });

      const result = await getAdminByKeycloakId('kc-uuid-1');

      expect(mockApiClient.get).toHaveBeenCalledWith(expect.stringContaining('/keycloak/kc-uuid-1'));
      expect(result).toEqual(admin);
    });
  });

  describe('getAdmins', () => {
    it('fetches all admins', async () => {
      const admins = [{ id: 1 }, { id: 2 }];
      mockApiClient.get.mockResolvedValue({ data: admins });

      const result = await getAdmins();

      expect(mockApiClient.get).toHaveBeenCalledWith(expect.stringContaining('/admin/admin'));
      expect(result).toEqual(admins);
    });

    it('returns empty array when no admins', async () => {
      mockApiClient.get.mockResolvedValue({ data: [] });

      const result = await getAdmins();

      expect(result).toEqual([]);
    });
  });

  describe('suspendAdmin', () => {
    it('patches admin to suspended state', async () => {
      const suspended = { id: 5, is_suspended: true };
      mockApiClient.patch.mockResolvedValue({ data: suspended });

      const result = await suspendAdmin(5);

      expect(mockApiClient.patch).toHaveBeenCalledWith(expect.stringContaining('/admin/admin/5/suspend'));
      expect(result).toEqual(suspended);
    });

    it('propagates error when admin not found for suspension', async () => {
      mockApiClient.patch.mockRejectedValue(new Error('Admin not found'));

      await expect(suspendAdmin(999)).rejects.toThrow('Admin not found');
    });
  });

  describe('unsuspendAdmin', () => {
    it('patches admin to unsuspended state', async () => {
      const active = { id: 5, is_suspended: false };
      mockApiClient.patch.mockResolvedValue({ data: active });

      const result = await unsuspendAdmin(5);

      expect(mockApiClient.patch).toHaveBeenCalledWith(expect.stringContaining('/admin/admin/5/unsuspend'));
      expect(result).toEqual(active);
    });
  });
});

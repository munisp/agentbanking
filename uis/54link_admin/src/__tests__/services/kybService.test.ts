import { kybService } from '../../services/kybService';

const mockApiClient = { post: jest.fn(), get: jest.fn(), patch: jest.fn() };
jest.mock('../../services/api', () => ({ default: mockApiClient }));

describe('KYBService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('generateVerificationId', () => {
    it('returns a string starting with verif_', () => {
      const id = kybService.generateVerificationId();
      expect(id).toMatch(/^verif_\d+\d+$/);
    });

    it('generates unique ids on consecutive calls', () => {
      const id1 = kybService.generateVerificationId();
      const id2 = kybService.generateVerificationId();
      expect(id1).not.toBe(id2);
    });
  });

  describe('getAllBusinesses', () => {
    it('fetches and normalizes businesses from array response', async () => {
      const raw = [
        { id: 'b1', tenant_id: 't1', name: 'Acme Corp', verification_status: 'verified', created_at: '2024-01-01' },
      ];
      mockApiClient.get.mockResolvedValue({ data: raw });

      const result = await kybService.getAllBusinesses();

      expect(mockApiClient.get).toHaveBeenCalledWith('/business/api/v1/businesses');
      expect(result[0].business_name).toBe('Acme Corp');
      expect(result[0].verification_status).toBe('approved');
    });

    it('handles paginated response with businesses key', async () => {
      const raw = { total: 1, skip: 0, limit: 10, businesses: [
        { id: 'b2', tenant_id: 't1', name: 'Beta Ltd', verification_status: 'pending', created_at: '2024-01-02' },
      ]};
      mockApiClient.get.mockResolvedValue({ data: raw });

      const result = await kybService.getAllBusinesses();

      expect(result).toHaveLength(1);
      expect(result[0].verification_status).toBe('pending');
    });

    it('maps verification statuses correctly', async () => {
      const statuses = [
        { input: 'verified', expected: 'approved' },
        { input: 'unverified', expected: 'pending' },
        { input: 'under_review', expected: 'under_review' },
        { input: 'rejected', expected: 'rejected' },
        { input: 'approved', expected: 'approved' },
        { input: 'unknown_status', expected: 'pending' },
      ];

      for (const { input, expected } of statuses) {
        mockApiClient.get.mockResolvedValue({ data: [
          { id: 'b1', tenant_id: 't1', name: 'Test', verification_status: input, created_at: '2024-01-01' },
        ]});

        const result = await kybService.getAllBusinesses();
        expect(result[0].verification_status).toBe(expected);
      }
    });

    it('propagates API errors', async () => {
      mockApiClient.get.mockRejectedValue(new Error('Unauthorized'));

      await expect(kybService.getAllBusinesses()).rejects.toThrow('Unauthorized');
    });
  });

  describe('registerBusiness', () => {
    const payload = {
      business_name: 'NewCo Ltd',
      registration_number: 'RC123456',
      business_type: 'LLC',
      industry: 'fintech',
      contact_email: 'info@newco.com',
      contact_phone: '08012345678',
      address: '1 Lagos St',
      country: 'NG',
    };

    it('posts to /businesses with transformed payload', async () => {
      const raw = { id: 'b-new', tenant_id: 't1', name: 'NewCo Ltd', verification_status: 'pending', created_at: '2024-01-01' };
      mockApiClient.post.mockResolvedValue({ data: raw });

      const result = await kybService.registerBusiness(payload);

      const postedBody = mockApiClient.post.mock.calls[0][1];
      expect(postedBody.name).toBe('NewCo Ltd');
      expect(postedBody.email_address).toBe('info@newco.com');
      expect(postedBody.phone_number).toBe('08012345678');
      expect(postedBody.industry_code).toBe('fintech');
      expect(result.business_name).toBe('NewCo Ltd');
    });
  });

  describe('verifyBusiness', () => {
    it('posts to verify endpoint with payload', async () => {
      const response = { success: true, message: 'Business verified' };
      mockApiClient.post.mockResolvedValue({ data: response });

      const result = await kybService.verifyBusiness('b-1', { status: 'approved', notes: 'All good' });

      expect(mockApiClient.post).toHaveBeenCalledWith(
        '/business/api/v1/businesses/b-1/verify',
        { status: 'approved', notes: 'All good' }
      );
      expect(result.success).toBe(true);
    });
  });

  describe('updateBusinessStatus', () => {
    it('patches status with verification_status field', async () => {
      const response = { success: true, message: 'Status updated' };
      mockApiClient.patch.mockResolvedValue({ data: response });

      const result = await kybService.updateBusinessStatus('b-1', 'approved');

      expect(mockApiClient.patch).toHaveBeenCalledWith(
        '/business/api/v1/businesses/b-1/status',
        { verification_status: 'approved' }
      );
      expect(result.success).toBe(true);
    });
  });

  describe('startVerification', () => {
    it('posts to verification/start and returns response', async () => {
      const verificationResp = { status: 'success', verificationId: 'v-1' };
      mockApiClient.post.mockResolvedValue({ data: verificationResp });

      const result = await kybService.startVerification({ businessId: 'b-1', documents: [] });

      expect(mockApiClient.post).toHaveBeenCalledWith('/business/api/v1/verification/start', { businessId: 'b-1', documents: [] });
      expect(result.verificationId).toBe('v-1');
    });

    it('throws when response status is not success', async () => {
      mockApiClient.post.mockResolvedValue({ data: { status: 'error' } });

      await expect(kybService.startVerification({ businessId: 'b-1' })).rejects.toThrow('Invalid response format');
    });
  });

  describe('getVerificationStatus', () => {
    it('fetches status for a verification id', async () => {
      const statusData = { id: 'v-1', status: 'pending' };
      mockApiClient.get.mockResolvedValue({ data: { status: 'success', data: statusData } });

      const result = await kybService.getVerificationStatus('v-1');

      expect(mockApiClient.get).toHaveBeenCalledWith('/business/api/v1/verification/v-1');
      expect(result).toEqual(statusData);
    });

    it('throws when response format is invalid', async () => {
      mockApiClient.get.mockResolvedValue({ data: { status: 'error', data: null } });

      await expect(kybService.getVerificationStatus('v-1')).rejects.toThrow('Invalid response format');
    });
  });

  describe('uploadDocument', () => {
    it('posts FormData to /document/upload', async () => {
      const uploadResp = { status: 'success', url: 'https://storage.example.com/doc.pdf' };
      mockApiClient.post.mockResolvedValue({ data: uploadResp });

      const mockFile = new File(['content'], 'doc.pdf', { type: 'application/pdf' });
      const result = await kybService.uploadDocument(mockFile, 'CAC_CERTIFICATE');

      expect(mockApiClient.post).toHaveBeenCalledWith(
        '/document/upload',
        expect.any(FormData),
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      expect(result.url).toBe('https://storage.example.com/doc.pdf');
    });

    it('throws when upload response has no URL', async () => {
      mockApiClient.post.mockResolvedValue({ data: { status: 'success', url: null } });

      const file = new File(['x'], 'x.pdf');
      await expect(kybService.uploadDocument(file, 'TYPE')).rejects.toThrow('Invalid response format');
    });
  });
});

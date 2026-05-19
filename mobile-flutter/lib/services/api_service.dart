import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// API service that communicates with the 54Link tRPC backend.
/// Uses Dio with JWT bearer token injection and automatic retry on 401.
class ApiService {
  static const String _baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://api.54link.ng/api/trpc',
  );

  late final Dio _dio;
  final FlutterSecureStorage _storage = const FlutterSecureStorage();

  ApiService() {
    _dio = Dio(BaseOptions(
      baseUrl: _baseUrl,
      connectTimeout: const Duration(seconds: 30),
      receiveTimeout: const Duration(seconds: 60),
      sendTimeout: const Duration(seconds: 30),
      headers: {'Content-Type': 'application/json'},
    ));

    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _storage.read(key: 'jwt_token');
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (error, handler) async {
        if (error.response?.statusCode == 401) {
          // Token expired — clear and redirect to login
          await _storage.delete(key: 'jwt_token');
        }
        handler.next(error);
      },
    ));
  }

  // ── Auth ──────────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> login({
    required String agentCode,
    required String pin,
    required String terminalId,
  }) async {
    final response = await _dio.post('/auth.agentLogin', data: {
      'json': {'agentCode': agentCode, 'pin': pin, 'terminalId': terminalId}
    });
    return _unwrap(response);
  }

  Future<void> logout() async {
    await _dio.post('/auth.logout', data: {'json': {}});
    await _storage.delete(key: 'jwt_token');
  }

  Future<Map<String, dynamic>> getMe() async {
    final response = await _dio.get('/auth.me');
    return _unwrap(response);
  }

  // ── Transactions ──────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> cashIn({
    required String customerPhone,
    required double amount,
    String narration = '',
  }) async {
    final response = await _dio.post('/transactions.cashIn', data: {
      'json': {
        'customerPhone': customerPhone,
        'amount': amount,
        'narration': narration,
      }
    });
    return _unwrap(response);
  }

  Future<Map<String, dynamic>> cashOut({
    required String customerPhone,
    required double amount,
    required String withdrawalCode,
  }) async {
    final response = await _dio.post('/transactions.cashOut', data: {
      'json': {
        'customerPhone': customerPhone,
        'amount': amount,
        'withdrawalCode': withdrawalCode,
      }
    });
    return _unwrap(response);
  }

  Future<Map<String, dynamic>> billPayment({
    required String category,
    required String provider,
    required String customerRef,
    required double amount,
  }) async {
    final response = await _dio.post('/transactions.billPayment', data: {
      'json': {
        'category': category,
        'provider': provider,
        'customerRef': customerRef,
        'amount': amount,
      }
    });
    return _unwrap(response);
  }

  Future<Map<String, dynamic>> getTransaction(String reference) async {
    final input = Uri.encodeComponent(jsonEncode({'json': {'reference': reference}}));
    final response = await _dio.get('/transactions.getByRef?input=$input');
    return _unwrap(response);
  }

  Future<List<dynamic>> getTransactionHistory({int page = 1, int limit = 20}) async {
    final input = Uri.encodeComponent(jsonEncode({'json': {'page': page, 'limit': limit}}));
    final response = await _dio.get('/transactions.history?input=$input');
    final data = _unwrap(response);
    return (data['transactions'] as List<dynamic>?) ?? [];
  }

  // ── Float ─────────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getFloatBalance() async {
    final response = await _dio.get('/float.getBalance');
    return _unwrap(response);
  }

  Future<Map<String, dynamic>> requestFloatTopUp({
    required double amount,
    required String bankRef,
  }) async {
    final response = await _dio.post('/float.requestTopUp', data: {
      'json': {'amount': amount, 'bankRef': bankRef}
    });
    return _unwrap(response);
  }

  // ── SIM / Network ─────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getSimStatus() async {
    final response = await _dio.get('/simOrchestrator.getStatus');
    return _unwrap(response);
  }

  Future<void> submitProbeReading({
    required int rssi,
    required int latencyMs,
    required int packetLossX10,
    int? latE6,
    int? lonE6,
  }) async {
    await _dio.post('/simOrchestrator.submitProbeReading', data: {
      'json': {
        'rssi': rssi,
        'latencyMs': latencyMs,
        'packetLossX10': packetLossX10,
        if (latE6 != null) 'latE6': latE6,
        if (lonE6 != null) 'lonE6': lonE6,
      }
    });
  }

  // ── Beneficiaries ─────────────────────────────────────────────────────────

  Future<List<dynamic>> getBeneficiaries() async {
    final response = await _dio.get('/beneficiaries.list');
    return _unwrapList(response);
  }

  Future<Map<String, dynamic>> addBeneficiary({
    required String accountNumber,
    required String bankCode,
    required String nickname,
  }) async {
    final response = await _dio.post('/beneficiaries.add', data: {
      'json': {
        'accountNumber': accountNumber,
        'bankCode': bankCode,
        'nickname': nickname,
      }
    });
    return _unwrap(response);
  }

  Future<void> deleteBeneficiary(String id) async {
    await _dio.post('/beneficiaries.delete', data: {'json': {'id': id}});
  }

  // ── Recurring Payments ────────────────────────────────────────────────────

  Future<List<dynamic>> getRecurringPayments() async {
    final response = await _dio.get('/recurringPayments.list');
    return _unwrapList(response);
  }

  Future<Map<String, dynamic>> createRecurringPayment({
    required String beneficiaryId,
    required double amount,
    required String frequency,
    required DateTime startDate,
    String? description,
  }) async {
    final response = await _dio.post('/recurringPayments.create', data: {
      'json': {
        'beneficiaryId': beneficiaryId,
        'amount': amount,
        'frequency': frequency,
        'startDate': startDate.toIso8601String(),
        if (description != null) 'description': description,
      }
    });
    return _unwrap(response);
  }

  Future<void> cancelRecurringPayment(String id) async {
    await _dio.post('/recurringPayments.cancel', data: {'json': {'id': id}});
  }

  // ── FX Rates ──────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getFxRates({String baseCurrency = 'NGN'}) async {
    final input = Uri.encodeComponent(jsonEncode({'json': {'baseCurrency': baseCurrency}}));
    final response = await _dio.get('/fx.getRates?input=$input');
    return _unwrap(response);
  }

  Future<Map<String, dynamic>> lockFxRate({
    required String fromCurrency,
    required String toCurrency,
    required double amount,
  }) async {
    final response = await _dio.post('/fx.lockRate', data: {
      'json': {
        'fromCurrency': fromCurrency,
        'toCurrency': toCurrency,
        'amount': amount,
      }
    });
    return _unwrap(response);
  }

  Future<Map<String, dynamic>> executeLockedTransfer({
    required String rateLockId,
    required String beneficiaryId,
    String? narration,
  }) async {
    final response = await _dio.post('/fx.executeLockedTransfer', data: {
      'json': {
        'rateLockId': rateLockId,
        'beneficiaryId': beneficiaryId,
        if (narration != null) 'narration': narration,
      }
    });
    return _unwrap(response);
  }

  // ── KYC ───────────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getKycStatus() async {
    final response = await _dio.get('/kyc.getStatus');
    return _unwrap(response);
  }

  Future<Map<String, dynamic>> submitKycDocument({
    required String documentType,
    required String documentNumber,
    String? documentUrl,
  }) async {
    final response = await _dio.post('/kyc.submitDocument', data: {
      'json': {
        'documentType': documentType,
        'documentNumber': documentNumber,
        if (documentUrl != null) 'documentUrl': documentUrl,
      }
    });
    return _unwrap(response);
  }

  // ── Notifications ─────────────────────────────────────────────────────────

  Future<List<dynamic>> getNotifications({int limit = 50, int offset = 0}) async {
    final input = Uri.encodeComponent(jsonEncode({'json': {'limit': limit, 'offset': offset}}));
    final response = await _dio.get('/notifications.list?input=$input');
    return _unwrapList(response);
  }

  Future<void> markNotificationRead(String id) async {
    await _dio.post('/notifications.markRead', data: {'json': {'id': id}});
  }

  Future<void> markAllNotificationsRead() async {
    await _dio.post('/notifications.markAllRead', data: {'json': {}});
  }

  // ── Profile ───────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getProfile() async {
    final response = await _dio.get('/agent.getProfile');
    return _unwrap(response);
  }

  Future<Map<String, dynamic>> updateProfile({
    String? phone,
    String? email,
    String? businessName,
    String? address,
  }) async {
    final response = await _dio.post('/agent.updateProfile', data: {
      'json': {
        if (phone != null) 'phone': phone,
        if (email != null) 'email': email,
        if (businessName != null) 'businessName': businessName,
        if (address != null) 'address': address,
      }
    });
    return _unwrap(response);
  }

  // ── Virtual Cards ─────────────────────────────────────────────────────────

  Future<List<dynamic>> getVirtualCards() async {
    final response = await _dio.get('/virtualCards.list');
    return _unwrapList(response);
  }

  Future<Map<String, dynamic>> createVirtualCard({
    required String currency,
    required double initialLoad,
    String? label,
  }) async {
    final response = await _dio.post('/virtualCards.create', data: {
      'json': {
        'currency': currency,
        'initialLoad': initialLoad,
        if (label != null) 'label': label,
      }
    });
    return _unwrap(response);
  }

  Future<void> freezeVirtualCard(String cardId) async {
    await _dio.post('/virtualCards.freeze', data: {'json': {'cardId': cardId}});
  }

  Future<void> unfreezeVirtualCard(String cardId) async {
    await _dio.post('/virtualCards.unfreeze', data: {'json': {'cardId': cardId}});
  }

  // ── Savings ───────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getSavingsAccount() async {
    final response = await _dio.get('/savings.getAccount');
    return _unwrap(response);
  }

  Future<Map<String, dynamic>> depositToSavings({required double amount}) async {
    final response = await _dio.post('/savings.deposit', data: {
      'json': {'amount': amount}
    });
    return _unwrap(response);
  }

  Future<Map<String, dynamic>> withdrawFromSavings({required double amount}) async {
    final response = await _dio.post('/savings.withdraw', data: {
      'json': {'amount': amount}
    });
    return _unwrap(response);
  }

  // ── Referrals ─────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getReferralStats() async {
    final response = await _dio.get('/referrals.getStats');
    return _unwrap(response);
  }

  Future<String> generateReferralLink() async {
    final response = await _dio.post('/referrals.generateLink', data: {'json': {}});
    final data = _unwrap(response);
    return data['link'] as String? ?? '';
  }

  // ── Biometric / FIDO2 ─────────────────────────────────────────────────────

  Future<Map<String, dynamic>> registerFido2Credential({
    required String credentialId,
    required String publicKey,
    required String deviceName,
  }) async {
    final response = await _dio.post('/customer.registerFido2Credential', data: {
      'json': {
        'credentialId': credentialId,
        'publicKey': publicKey,
        'deviceName': deviceName,
      }
    });
    return _unwrap(response);
  }

  Future<Map<String, dynamic>> verifyFido2Credential({
    required String credentialId,
    required String signature,
    required String clientDataJson,
  }) async {
    final response = await _dio.post('/customer.verifyFido2Credential', data: {
      'json': {
        'credentialId': credentialId,
        'signature': signature,
        'clientDataJson': clientDataJson,
      }
    });
    return _unwrap(response);
  }

  // ── Support ───────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> createSupportTicket({
    required String subject,
    required String message,
    String priority = 'medium',
  }) async {
    final response = await _dio.post('/support.createTicket', data: {
      'json': {
        'subject': subject,
        'message': message,
        'priority': priority,
      }
    });
    return _unwrap(response);
  }

  Future<List<dynamic>> getSupportTickets() async {
    final response = await _dio.get('/support.listTickets');
    return _unwrapList(response);
  }

  // ── Credit ────────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getCreditScore() async {
    final response = await _dio.get('/customer.getCreditScore');
    return _unwrap(response);
  }

  Future<Map<String, dynamic>> applyCreditLimit({
    required double requestedAmount,
    required String purpose,
  }) async {
    final response = await _dio.post('/customer.applyCreditLimit', data: {
      'json': {
        'requestedAmount': requestedAmount,
        'purpose': purpose,
      }
    });
    return _unwrap(response);
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  Map<String, dynamic> _unwrap(Response response) {
    final body = response.data;
    if (body is Map && body.containsKey('result')) {
      final result = body['result'];
      if (result is Map && result.containsKey('data')) {
        return result['data'] as Map<String, dynamic>;
      }
    }
    return body as Map<String, dynamic>;
  }

  List<dynamic> _unwrapList(Response response) {
    final body = response.data;
    if (body is Map && body.containsKey('result')) {
      final result = body['result'];
      if (result is Map && result.containsKey('data')) {
        final data = result['data'];
        if (data is List) return data;
        if (data is Map && data.containsKey('items')) return data['items'] as List;
      }
    }
    if (body is List) return body;
    return [];
  }

  Future<void> saveToken(String token) async {
    await _storage.write(key: 'jwt_token', value: token);
  }

  Future<String?> getToken() async {
    return _storage.read(key: 'jwt_token');
  }
}

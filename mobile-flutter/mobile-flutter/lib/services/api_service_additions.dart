import 'dart:convert';
import 'package:dio/dio.dart';

/// API Service Additions for 12 New Mobile Parity Screens
/// Merge these methods into ApiService class in api_service.dart
///
/// Usage: Add these methods to the existing ApiService class body.

mixin ApiServiceAdditions {
  Dio get dio; // Must be provided by the mixing class

  // ── Agent Performance ──────────────────────────────────────────────────────
  Future<Map<String, dynamic>> getAgentLeaderboard({
    int days = 30, String sortBy = 'points', int page = 1, int limit = 20,
  }) async {
    final input = Uri.encodeComponent(jsonEncode({
      'json': {'days': days, 'sortBy': sortBy, 'page': page, 'limit': limit}
    }));
    final response = await dio.get('/analytics.agentLeaderboard?input=$input');
    return _unwrap(response);
  }

  // ── Customer Wallet ────────────────────────────────────────────────────────
  Future<Map<String, dynamic>> getCustomerWallet() async {
    final response = await dio.get('/customer.account.balance');
    return _unwrap(response);
  }

  Future<List<dynamic>> getCustomerTransactions({int page = 1, int limit = 20}) async {
    final input = Uri.encodeComponent(jsonEncode({
      'json': {'page': page, 'limit': limit}
    }));
    final response = await dio.get('/customer.transactions.list?input=$input');
    return _unwrapList(response);
  }

  Future<Map<String, dynamic>> topUpCustomerWallet({required double amount}) async {
    final response = await dio.post('/customer.account.topUp', data: {
      'json': {'amount': amount}
    });
    return _unwrap(response);
  }

  Future<void> freezeCustomerWallet() async {
    await dio.post('/customer.account.freeze', data: {'json': {}});
  }

  // ── Notification Preferences ───────────────────────────────────────────────
  Future<Map<String, dynamic>> getNotificationPreferences() async {
    final response = await dio.get('/notifications.getPreferences');
    return _unwrap(response);
  }

  Future<void> updateNotificationPreferences(Map<String, dynamic> prefs) async {
    await dio.post('/notifications.updatePreferences', data: {'json': prefs});
  }

  Future<void> sendTestNotification() async {
    await dio.post('/system.notifyOwner', data: {
      'json': {'title': 'Test', 'content': 'Test notification from mobile'}
    });
  }

  // ── Multi-Currency ─────────────────────────────────────────────────────────
  Future<Map<String, dynamic>> getCurrencyRates({String base = 'NGN'}) async {
    final input = Uri.encodeComponent(jsonEncode({'json': {'baseCurrency': base}}));
    final response = await dio.get('/fx.getRates?input=$input');
    return _unwrap(response);
  }

  Future<Map<String, dynamic>> convertCurrency({
    required String from, required String to, required double amount,
  }) async {
    final response = await dio.post('/fx.lockRate', data: {
      'json': {'fromCurrency': from, 'toCurrency': to, 'amount': amount}
    });
    return _unwrap(response);
  }

  // ── Compliance Scheduling ──────────────────────────────────────────────────
  Future<List<dynamic>> getComplianceSchedules() async {
    final response = await dio.get('/compliance.listSchedules');
    return _unwrapList(response);
  }

  Future<Map<String, dynamic>> createComplianceSchedule(Map<String, dynamic> data) async {
    final response = await dio.post('/compliance.createSchedule', data: {'json': data});
    return _unwrap(response);
  }

  Future<void> updateComplianceSchedule(String id, Map<String, dynamic> data) async {
    await dio.post('/compliance.updateSchedule', data: {'json': {'id': id, ...data}});
  }

  // ── Audit Export ───────────────────────────────────────────────────────────
  Future<Map<String, dynamic>> getAuditExportPreview(Map<String, dynamic> filters) async {
    final response = await dio.post('/audit.exportPreview', data: {'json': filters});
    return _unwrap(response);
  }

  Future<Map<String, dynamic>> exportAuditLog(String format, Map<String, dynamic> filters) async {
    final response = await dio.post('/audit.export', data: {
      'json': {'format': format, ...filters}
    });
    return _unwrap(response);
  }

  Future<List<dynamic>> getRecentExports() async {
    final response = await dio.get('/audit.recentExports');
    return _unwrapList(response);
  }

  // ── Helpers ────────────────────────────────────────────────────────────────
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
}

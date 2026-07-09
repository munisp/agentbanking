import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mockito/mockito.dart';
import 'package:mockito/annotations.dart';
import 'package:pos54link/services/api_service.dart';
import 'package:pos54link/providers/auth_provider.dart';

@GenerateMocks([ApiService])
import 'auth_provider_test.mocks.dart';

void main() {
  late MockApiService mockApi;
  late ProviderContainer container;

  setUp(() {
    mockApi = MockApiService();
    container = ProviderContainer(
      overrides: [
        apiServiceProvider.overrideWithValue(mockApi),
      ],
    );
  });

  tearDown(() => container.dispose());

  group('AuthNotifier', () {
    test('initial state is unauthenticated', () {
      final state = container.read(authProvider);
      expect(state.isAuthenticated, isFalse);
      expect(state.isLoading, isFalse);
      expect(state.error, isNull);
    });

    test('checkAuth sets authenticated when token exists', () async {
      when(mockApi.getToken()).thenAnswer((_) async => 'valid-token');
      when(mockApi.getMe()).thenAnswer((_) async => {'name': 'Test Agent', 'agentCode': 'AG001'});

      await container.read(authProvider.notifier).checkAuth();

      final state = container.read(authProvider);
      expect(state.isAuthenticated, isTrue);
      expect(state.user?['name'], equals('Test Agent'));
    });

    test('checkAuth sets unauthenticated when no token', () async {
      when(mockApi.getToken()).thenAnswer((_) async => null);

      await container.read(authProvider.notifier).checkAuth();

      final state = container.read(authProvider);
      expect(state.isAuthenticated, isFalse);
    });

    test('login returns true and sets authenticated on success', () async {
      when(mockApi.login(agentCode: 'AG001', pin: '1234', terminalId: 'PAX-001'))
          .thenAnswer((_) async => {'token': 'jwt-token', 'user': {'name': 'Agent One'}});
      when(mockApi.saveToken(any)).thenAnswer((_) async {});

      final result = await container.read(authProvider.notifier).login(
        agentCode: 'AG001',
        pin: '1234',
        terminalId: 'PAX-001',
      );

      expect(result, isTrue);
      final state = container.read(authProvider);
      expect(state.isAuthenticated, isTrue);
      expect(state.error, isNull);
    });

    test('login returns false and sets error on failure', () async {
      when(mockApi.login(agentCode: any, pin: any, terminalId: any))
          .thenThrow(Exception('Invalid credentials'));

      final result = await container.read(authProvider.notifier).login(
        agentCode: 'BAD',
        pin: '0000',
        terminalId: 'PAX-001',
      );

      expect(result, isFalse);
      final state = container.read(authProvider);
      expect(state.isAuthenticated, isFalse);
      expect(state.error, isNotNull);
    });

    test('logout clears auth state', () async {
      when(mockApi.login(agentCode: any, pin: any, terminalId: any))
          .thenAnswer((_) async => {'token': 'jwt', 'user': {}});
      when(mockApi.saveToken(any)).thenAnswer((_) async {});
      when(mockApi.logout()).thenAnswer((_) async {});

      await container.read(authProvider.notifier).login(
        agentCode: 'AG001', pin: '1234', terminalId: 'PAX-001',
      );
      await container.read(authProvider.notifier).logout();

      final state = container.read(authProvider);
      expect(state.isAuthenticated, isFalse);
      expect(state.user, isNull);
    });
  });
}

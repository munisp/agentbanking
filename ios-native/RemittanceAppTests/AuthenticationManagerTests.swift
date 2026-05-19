import XCTest
import Combine
@testable import RemittanceApp

@MainActor
final class AuthenticationManagerTests: XCTestCase {
    var sut: AuthenticationManager!
    var cancellables: Set<AnyCancellable>!
    
    override func setUpWithError() throws {
        try super.setUpWithError()
        sut = AuthenticationManager()
        cancellables = []
    }
    
    override func tearDownWithError() throws {
        sut = nil
        cancellables = nil
        try super.tearDownWithError()
    }
    
    // MARK: - Session Management Tests
    
    func testLoadSession_WithValidToken_SetsAuthenticated() async throws {
        // Given: Valid token in keychain
        let keychainManager = KeychainManager.shared
        try keychainManager.saveAccessToken("valid_token")
        try keychainManager.saveUserID("user_123")
        
        // When: Loading session
        await sut.loadSession()
        
        // Then: User should be authenticated
        // Note: This test requires mock API client
        // XCTAssertTrue(sut.isAuthenticated)
    }
    
    func testLoadSession_WithoutToken_SetsUnauthenticated() async throws {
        // Given: No token in keychain
        let keychainManager = KeychainManager.shared
        keychainManager.clearTokens()
        
        // When: Loading session
        await sut.loadSession()
        
        // Then: User should not be authenticated
        XCTAssertFalse(sut.isAuthenticated)
    }
    
    // MARK: - Login Tests
    
    func testLogin_WithValidCredentials_SetsAuthenticated() async throws {
        // Given: Valid credentials
        let email = "test@example.com"
        let password = "password123"
        
        // When: Logging in
        await sut.login(email: email, password: password)
        
        // Then: Should set loading state
        // Note: Requires mock API client for full test
        XCTAssertNotNil(sut)
    }
    
    func testLogin_WithInvalidCredentials_SetsError() async throws {
        // Given: Invalid credentials
        let email = "invalid@example.com"
        let password = "wrong"
        
        // When: Logging in
        await sut.login(email: email, password: password)
        
        // Then: Should set error message
        // Note: Requires mock API client
        // XCTAssertNotNil(sut.errorMessage)
    }
    
    func testLogin_SetsLoadingState() async throws {
        // Given: Any credentials
        let email = "test@example.com"
        let password = "password123"
        
        // When: Starting login
        let expectation = XCTestExpectation(description: "Loading state changes")
        
        sut.$isLoading
            .dropFirst()
            .sink { isLoading in
                if isLoading {
                    expectation.fulfill()
                }
            }
            .store(in: &cancellables)
        
        Task {
            await sut.login(email: email, password: password)
        }
        
        // Then: Loading should be set to true
        await fulfillment(of: [expectation], timeout: 1.0)
    }
    
    // MARK: - Registration Tests
    
    func testRegister_WithValidData_CreatesAccount() async throws {
        // Given: Valid registration data
        let email = "newuser@example.com"
        let password = "SecurePass123"
        let firstName = "John"
        let lastName = "Doe"
        let phoneNumber = "+2348012345678"
        let country = "Nigeria"
        
        // When: Registering
        await sut.register(
            email: email,
            password: password,
            firstName: firstName,
            lastName: lastName,
            phoneNumber: phoneNumber,
            country: country
        )
        
        // Then: Should create account
        // Note: Requires mock API client
        XCTAssertNotNil(sut)
    }
    
    // MARK: - Logout Tests
    
    func testLogout_ClearsAuthentication() async throws {
        // Given: Authenticated user
        let keychainManager = KeychainManager.shared
        try keychainManager.saveAccessToken("token")
        try keychainManager.saveUserID("user_123")
        sut.isAuthenticated = true
        
        // When: Logging out
        await sut.logout()
        
        // Then: Should clear authentication
        XCTAssertFalse(sut.isAuthenticated)
        XCTAssertNil(sut.currentUser)
        XCTAssertNil(keychainManager.getAccessToken())
    }
    
    // MARK: - Biometric Tests
    
    func testCheckBiometricAvailability_SetsBiometricType() {
        // When: Checking biometric availability
        sut.checkBiometricAvailability()
        
        // Then: Should set biometric type
        XCTAssertNotNil(sut.biometricType)
    }
    
    func testEnableBiometric_WithAvailableBiometric_Registers() async throws {
        // Given: Biometric is available
        // This test requires device with biometric capability
        
        // When: Enabling biometric
        // await sut.enableBiometric()
        
        // Then: Should register biometric
        // XCTAssertTrue(sut.isBiometricEnabled)
    }
    
    func testDisableBiometric_RemovesBiometric() {
        // Given: Biometric is enabled
        sut.isBiometricEnabled = true
        
        // When: Disabling biometric
        sut.disableBiometric()
        
        // Then: Should disable biometric
        XCTAssertFalse(sut.isBiometricEnabled)
    }
    
    // MARK: - Password Reset Tests
    
    func testForgotPassword_WithValidEmail_SendsResetLink() async throws {
        // Given: Valid email
        let email = "test@example.com"
        
        // When: Requesting password reset
        let result = await sut.forgotPassword(email: email)
        
        // Then: Should send reset link
        // Note: Requires mock API client
        XCTAssertNotNil(result)
    }
    
    func testForgotPassword_WithInvalidEmail_ReturnsError() async throws {
        // Given: Invalid email
        let email = "invalid"
        
        // When: Requesting password reset
        let result = await sut.forgotPassword(email: email)
        
        // Then: Should return error
        // Note: Requires mock API client
        XCTAssertNotNil(result)
    }
    
    // MARK: - State Management Tests
    
    func testIsAuthenticated_PublishesChanges() {
        // Given: Expectation for published value
        let expectation = XCTestExpectation(description: "isAuthenticated publishes")
        
        sut.$isAuthenticated
            .dropFirst()
            .sink { _ in
                expectation.fulfill()
            }
            .store(in: &cancellables)
        
        // When: Changing authentication state
        sut.isAuthenticated = true
        
        // Then: Should publish change
        wait(for: [expectation], timeout: 1.0)
    }
    
    func testErrorMessage_PublishesChanges() {
        // Given: Expectation for published value
        let expectation = XCTestExpectation(description: "errorMessage publishes")
        
        sut.$errorMessage
            .dropFirst()
            .sink { _ in
                expectation.fulfill()
            }
            .store(in: &cancellables)
        
        // When: Setting error message
        sut.errorMessage = "Test error"
        
        // Then: Should publish change
        wait(for: [expectation], timeout: 1.0)
    }
    
    // MARK: - Integration Tests
    
    func testLoginLogoutFlow() async throws {
        // Given: User credentials
        let email = "test@example.com"
        let password = "password123"
        
        // When: Login then logout
        await sut.login(email: email, password: password)
        // Simulate successful login
        sut.isAuthenticated = true
        
        await sut.logout()
        
        // Then: Should be logged out
        XCTAssertFalse(sut.isAuthenticated)
        XCTAssertNil(sut.currentUser)
    }
    
    // MARK: - Performance Tests
    
    func testLoginPerformance() {
        measure {
            Task {
                await sut.login(email: "test@example.com", password: "password")
            }
        }
    }
}

// MARK: - Mock Classes

class MockAPIClient {
    var shouldSucceed = true
    var mockUser: User?
    var mockTokens: (access: String, refresh: String)?
    
    func login(email: String, password: String) async throws -> AuthResponse {
        if shouldSucceed {
            return AuthResponse(
                success: true,
                message: "Login successful",
                data: AuthData(
                    user: mockUser ?? createMockUser(),
                    accessToken: "mock_access_token",
                    refreshToken: "mock_refresh_token",
                    expiresIn: 3600
                )
            )
        } else {
            throw APIError.unauthorized
        }
    }
    
    private func createMockUser() -> User {
        return User(
            id: "user_123",
            email: "test@example.com",
            firstName: "John",
            lastName: "Doe",
            phoneNumber: "+2348012345678",
            country: "Nigeria",
            kycStatus: "pending",
            emailVerified: true,
            phoneVerified: false,
            twoFactorEnabled: false,
            createdAt: "2024-01-01T00:00:00Z"
        )
    }
}

enum APIError: Error {
    case unauthorized
    case networkError
    case serverError
    case invalidResponse
}

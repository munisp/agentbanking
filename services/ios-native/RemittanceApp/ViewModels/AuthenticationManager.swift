import Foundation
import Combine
import SwiftUI

@MainActor
class AuthenticationManager: ObservableObject {
    @Published var isAuthenticated = false
    @Published var isLoading = false
    @Published var currentUser: User?
    @Published var errorMessage: String?
    @Published var biometricType: BiometricType = .none
    @Published var isBiometricEnabled = false
    
    private let apiClient = APIClient.shared
    private let keychainManager = KeychainManager.shared
    private let biometricManager = BiometricAuthManager.shared
    private var cancellables = Set<AnyCancellable>()
    
    init() {
        checkBiometricAvailability()
    }
    
    // MARK: - Session Management
    
    func loadSession() async {
        isLoading = true
        defer { isLoading = false }
        
        // Check if we have a valid token
        guard let token = keychainManager.getAccessToken(),
              let userId = keychainManager.getUserID() else {
            isAuthenticated = false
            return
        }
        
        // Verify token is still valid by fetching user profile
        do {
            let response: ProfileResponse = try await apiClient.request(.profile)
            currentUser = response.data.toUser()
            isAuthenticated = true
            isBiometricEnabled = biometricManager.isBiometricRegistered()
        } catch {
            // Token expired or invalid
            keychainManager.clearTokens()
            isAuthenticated = false
        }
    }
    
    // MARK: - Authentication
    
    func login(email: String, password: String) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        
        do {
            let deviceId = keychainManager.getOrCreateDeviceID()
            let deviceName = UIDevice.current.name
            
            let request = LoginRequest(
                email: email,
                password: password,
                deviceId: deviceId,
                deviceName: deviceName
            )
            
            let response: AuthResponse = try await apiClient.request(
                .login,
                method: .post,
                parameters: request.toDictionary()
            )
            
            // Save tokens
            try keychainManager.saveAccessToken(response.data.accessToken)
            try keychainManager.saveRefreshToken(response.data.refreshToken)
            try keychainManager.saveUserID(response.data.user.id)
            
            currentUser = response.data.user
            isAuthenticated = true
            
        } catch let error as APIError {
            errorMessage = error.errorDescription
        } catch {
            errorMessage = "Login failed. Please try again."
        }
    }
    
    func register(email: String, password: String, firstName: String, lastName: String, phoneNumber: String, country: String) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        
        do {
            let deviceId = keychainManager.getOrCreateDeviceID()
            let deviceName = UIDevice.current.name
            
            let request = RegisterRequest(
                email: email,
                password: password,
                firstName: firstName,
                lastName: lastName,
                phoneNumber: phoneNumber,
                country: country,
                deviceId: deviceId,
                deviceName: deviceName
            )
            
            let response: AuthResponse = try await apiClient.request(
                .register,
                method: .post,
                parameters: request.toDictionary()
            )
            
            // Save tokens
            try keychainManager.saveAccessToken(response.data.accessToken)
            try keychainManager.saveRefreshToken(response.data.refreshToken)
            try keychainManager.saveUserID(response.data.user.id)
            
            currentUser = response.data.user
            isAuthenticated = true
            
        } catch let error as APIError {
            errorMessage = error.errorDescription
        } catch {
            errorMessage = "Registration failed. Please try again."
        }
    }
    
    func logout() async {
        isLoading = true
        defer { isLoading = false }
        
        do {
            // Call logout endpoint
            let _: EmptyResponse = try await apiClient.request(.logout, method: .post)
        } catch {
            // Continue with local logout even if API call fails
        }
        
        // Clear local data
        keychainManager.clearTokens()
        keychainManager.clearUserID()
        currentUser = nil
        isAuthenticated = false
    }
    
    // MARK: - Biometric Authentication
    
    func checkBiometricAvailability() {
        biometricType = biometricManager.getBiometricType()
        isBiometricEnabled = biometricManager.isBiometricRegistered()
    }
    
    func enableBiometric() async {
        guard biometricType != .none else {
            errorMessage = "Biometric authentication is not available on this device"
            return
        }
        
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        
        do {
            // Register biometric with device
            let (publicKey, _) = try await biometricManager.registerBiometric()
            
            // Register with server
            let deviceId = keychainManager.getOrCreateDeviceID()
            let request = BiometricRegisterRequest(publicKey: publicKey, deviceId: deviceId)
            
            let response: BiometricResponse = try await apiClient.request(
                .biometricRegister,
                method: .post,
                parameters: request.toDictionary()
            )
            
            isBiometricEnabled = true
            
        } catch let error as BiometricError {
            errorMessage = error.errorDescription
            biometricManager.removeBiometric()
        } catch let error as APIError {
            errorMessage = error.errorDescription
            biometricManager.removeBiometric()
        } catch {
            errorMessage = "Failed to enable biometric authentication"
            biometricManager.removeBiometric()
        }
    }
    
    func loginWithBiometric() async {
        guard isBiometricEnabled else {
            errorMessage = "Biometric authentication is not enabled"
            return
        }
        
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        
        do {
            // Get challenge from server
            let challengeResponse: BiometricChallengeResponse = try await apiClient.request(.biometricChallenge)
            
            // Sign challenge with biometric
            let signature = try await biometricManager.verifyBiometric(challenge: challengeResponse.challenge)
            
            // Verify with server
            let deviceId = keychainManager.getOrCreateDeviceID()
            let request = BiometricVerifyRequest(
                signature: signature,
                challenge: challengeResponse.challenge,
                deviceId: deviceId
            )
            
            let response: AuthResponse = try await apiClient.request(
                .biometricVerify,
                method: .post,
                parameters: request.toDictionary()
            )
            
            // Save tokens
            try keychainManager.saveAccessToken(response.data.accessToken)
            try keychainManager.saveRefreshToken(response.data.refreshToken)
            try keychainManager.saveUserID(response.data.user.id)
            
            currentUser = response.data.user
            isAuthenticated = true
            
        } catch let error as BiometricError {
            errorMessage = error.errorDescription
        } catch let error as APIError {
            errorMessage = error.errorDescription
        } catch {
            errorMessage = "Biometric authentication failed"
        }
    }
    
    func disableBiometric() {
        biometricManager.removeBiometric()
        isBiometricEnabled = false
    }
    
    // MARK: - Password Reset
    
    func forgotPassword(email: String) async -> Bool {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        
        do {
            let request = ForgotPasswordRequest(email: email)
            let _: MessageResponse = try await apiClient.request(
                .forgotPassword,
                method: .post,
                parameters: request.toDictionary()
            )
            return true
        } catch let error as APIError {
            errorMessage = error.errorDescription
            return false
        } catch {
            errorMessage = "Failed to send password reset email"
            return false
        }
    }
}

// MARK: - Supporting Models

struct LoginRequest: Encodable {
    let email: String
    let password: String
    let deviceId: String?
    let deviceName: String?
}

struct RegisterRequest: Encodable {
    let email: String
    let password: String
    let firstName: String
    let lastName: String
    let phoneNumber: String
    let country: String
    let deviceId: String?
    let deviceName: String?
}

struct BiometricRegisterRequest: Encodable {
    let publicKey: String
    let deviceId: String
}

struct BiometricVerifyRequest: Encodable {
    let signature: String
    let challenge: String
    let deviceId: String
}

struct ForgotPasswordRequest: Encodable {
    let email: String
}

struct AuthResponse: Decodable {
    let success: Bool
    let message: String?
    let data: AuthData
}

struct AuthData: Decodable {
    let user: User
    let accessToken: String
    let refreshToken: String
    let expiresIn: Int
}

struct BiometricResponse: Decodable {
    let success: Bool
    let data: BiometricData
}

struct BiometricData: Decodable {
    let challenge: String
    let publicKeyId: String
}

struct BiometricChallengeResponse: Decodable {
    let challenge: String
}

struct MessageResponse: Decodable {
    let success: Bool
    let message: String
}

struct EmptyResponse: Decodable {}

struct ProfileResponse: Decodable {
    let success: Bool
    let data: UserProfile
}

struct UserProfile: Decodable {
    let id: String
    let email: String
    let firstName: String
    let lastName: String
    let phoneNumber: String
    let country: String
    let kycStatus: String
    let emailVerified: Bool
    let phoneVerified: Bool
    let twoFactorEnabled: Bool
    let createdAt: String
    
    func toUser() -> User {
        return User(
            id: id,
            email: email,
            firstName: firstName,
            lastName: lastName,
            phoneNumber: phoneNumber,
            country: country,
            kycStatus: kycStatus,
            emailVerified: emailVerified,
            phoneVerified: phoneVerified,
            twoFactorEnabled: twoFactorEnabled,
            createdAt: createdAt
        )
    }
}

struct User: Codable, Identifiable {
    let id: String
    let email: String
    let firstName: String
    let lastName: String
    let phoneNumber: String
    let country: String
    let kycStatus: String
    let emailVerified: Bool
    let phoneVerified: Bool
    let twoFactorEnabled: Bool
    let createdAt: String
    
    var fullName: String {
        "\(firstName) \(lastName)"
    }
}

// MARK: - Extensions

extension Encodable {
    func toDictionary() -> [String: Any] {
        guard let data = try? JSONEncoder().encode(self),
              let dictionary = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return [:]
        }
        return dictionary
    }
}

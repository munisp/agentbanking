import Foundation
import LocalAuthentication

enum BiometricType {
    case none
    case touchID
    case faceID
    
    var displayName: String {
        switch self {
        case .none: return "None"
        case .touchID: return "Touch ID"
        case .faceID: return "Face ID"
        }
    }
}

enum BiometricError: LocalizedError {
    case notAvailable
    case notEnrolled
    case lockout
    case cancelled
    case failed
    case unknown(String)
    
    var errorDescription: String? {
        switch self {
        case .notAvailable:
            return "Biometric authentication is not available on this device"
        case .notEnrolled:
            return "No biometric data is enrolled. Please set up Face ID or Touch ID in Settings"
        case .lockout:
            return "Biometric authentication is locked. Please try again later"
        case .cancelled:
            return "Authentication was cancelled"
        case .failed:
            return "Authentication failed"
        case .unknown(let message):
            return message
        }
    }
}

class BiometricAuthManager {
    static let shared = BiometricAuthManager()
    
    private let context = LAContext()
    private let keychainManager = KeychainManager.shared
    
    private init() {}
    
    // MARK: - Availability Check
    
    func getBiometricType() -> BiometricType {
        var error: NSError?
        
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            return .none
        }
        
        switch context.biometryType {
        case .faceID:
            return .faceID
        case .touchID:
            return .touchID
        case .none:
            return .none
        @unknown default:
            return .none
        }
    }
    
    func isBiometricAvailable() -> Bool {
        return getBiometricType() != .none
    }
    
    func canUseBiometric() -> (Bool, BiometricError?) {
        var error: NSError?
        
        let canEvaluate = context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error)
        
        if let error = error {
            let biometricError = mapLAError(error)
            return (false, biometricError)
        }
        
        return (canEvaluate, nil)
    }
    
    // MARK: - Authentication
    
    func authenticate(reason: String = "Authenticate to access your account") async throws {
        let context = LAContext()
        context.localizedCancelTitle = "Cancel"
        context.localizedFallbackTitle = "Use Passcode"
        
        do {
            let success = try await context.evaluatePolicy(
                .deviceOwnerAuthenticationWithBiometrics,
                localizedReason: reason
            )
            
            if !success {
                throw BiometricError.failed
            }
        } catch let error as LAError {
            throw mapLAError(error)
        } catch {
            throw BiometricError.unknown(error.localizedDescription)
        }
    }
    
    func authenticateWithPasscode(reason: String = "Authenticate to access your account") async throws {
        let context = LAContext()
        context.localizedCancelTitle = "Cancel"
        
        do {
            let success = try await context.evaluatePolicy(
                .deviceOwnerAuthentication,
                localizedReason: reason
            )
            
            if !success {
                throw BiometricError.failed
            }
        } catch let error as LAError {
            throw mapLAError(error)
        } catch {
            throw BiometricError.unknown(error.localizedDescription)
        }
    }
    
    // MARK: - Biometric Registration
    
    func registerBiometric() async throws -> (publicKey: String, privateKey: Data) {
        // Ensure biometric is available
        let (canUse, error) = canUseBiometric()
        guard canUse else {
            throw error ?? BiometricError.notAvailable
        }
        
        // Authenticate first
        try await authenticate(reason: "Authenticate to enable biometric login")
        
        // Generate key pair
        let (publicKey, privateKey) = try generateKeyPair()
        
        // Save to keychain
        try keychainManager.saveBiometricPublicKey(publicKey)
        try keychainManager.saveBiometricPrivateKey(privateKey)
        
        return (publicKey, privateKey)
    }
    
    func verifyBiometric(challenge: String) async throws -> String {
        // Authenticate
        try await authenticate(reason: "Authenticate to verify your identity")
        
        // Get private key
        guard let privateKey = try keychainManager.getBiometricPrivateKey() else {
            throw BiometricError.failed
        }
        
        // Sign challenge
        let signature = try signChallenge(challenge, with: privateKey)
        
        return signature
    }
    
    func isBiometricRegistered() -> Bool {
        return (try? keychainManager.getBiometricPublicKey()) != nil
    }
    
    func removeBiometric() {
        keychainManager.clearBiometricKeys()
    }
    
    // MARK: - Private Helpers
    
    private func mapLAError(_ error: Error) -> BiometricError {
        guard let laError = error as? LAError else {
            return .unknown(error.localizedDescription)
        }
        
        switch laError.code {
        case .biometryNotAvailable:
            return .notAvailable
        case .biometryNotEnrolled:
            return .notEnrolled
        case .biometryLockout:
            return .lockout
        case .userCancel:
            return .cancelled
        case .authenticationFailed:
            return .failed
        default:
            return .unknown(laError.localizedDescription)
        }
    }
    
    private func generateKeyPair() throws -> (String, Data) {
        // Generate RSA key pair
        let attributes: [String: Any] = [
            kSecAttrKeyType as String: kSecAttrKeyTypeRSA,
            kSecAttrKeySizeInBits as String: 2048,
            kSecPrivateKeyAttrs as String: [
                kSecAttrIsPermanent as String: false
            ]
        ]
        
        var error: Unmanaged<CFError>?
        guard let privateKey = SecKeyCreateRandomKey(attributes as CFDictionary, &error) else {
            throw error!.takeRetainedValue() as Error
        }
        
        guard let publicKey = SecKeyCopyPublicKey(privateKey) else {
            throw BiometricError.failed
        }
        
        // Export public key
        var exportError: Unmanaged<CFError>?
        guard let publicKeyData = SecKeyCopyExternalRepresentation(publicKey, &exportError) as Data? else {
            throw exportError!.takeRetainedValue() as Error
        }
        
        let publicKeyString = publicKeyData.base64EncodedString()
        
        // Export private key
        guard let privateKeyData = SecKeyCopyExternalRepresentation(privateKey, &exportError) as Data? else {
            throw exportError!.takeRetainedValue() as Error
        }
        
        return (publicKeyString, privateKeyData)
    }
    
    private func signChallenge(_ challenge: String, with privateKeyData: Data) throws -> String {
        // Import private key
        let attributes: [String: Any] = [
            kSecAttrKeyType as String: kSecAttrKeyTypeRSA,
            kSecAttrKeyClass as String: kSecAttrKeyClassPrivate,
            kSecAttrKeySizeInBits as String: 2048
        ]
        
        var error: Unmanaged<CFError>?
        guard let privateKey = SecKeyCreateWithData(privateKeyData as CFData, attributes as CFDictionary, &error) else {
            throw error!.takeRetainedValue() as Error
        }
        
        // Sign challenge
        guard let challengeData = challenge.data(using: .utf8) else {
            throw BiometricError.failed
        }
        
        guard let signature = SecKeyCreateSignature(
            privateKey,
            .rsaSignatureMessagePKCS1v15SHA256,
            challengeData as CFData,
            &error
        ) as Data? else {
            throw error!.takeRetainedValue() as Error
        }
        
        return signature.base64EncodedString()
    }
}

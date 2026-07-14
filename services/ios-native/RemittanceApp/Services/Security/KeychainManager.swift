import Foundation
import Security
import KeychainAccess

enum KeychainKey: String {
    case accessToken = "com.remittance.accessToken"
    case refreshToken = "com.remittance.refreshToken"
    case userID = "com.remittance.userID"
    case biometricPublicKey = "com.remittance.biometricPublicKey"
    case biometricPrivateKey = "com.remittance.biometricPrivateKey"
    case deviceID = "com.remittance.deviceID"
    case pinCode = "com.remittance.pinCode"
}

class KeychainManager {
    static let shared = KeychainManager()
    
    private let keychain: Keychain
    private let biometricKeychain: Keychain
    
    private init() {
        // Standard keychain
        keychain = Keychain(service: "com.remittance.app")
            .synchronizable(false)
            .accessibility(.whenUnlockedThisDeviceOnly)
        
        // Biometric-protected keychain
        biometricKeychain = Keychain(service: "com.remittance.app.biometric")
            .synchronizable(false)
            .accessibility(.whenPasscodeSetThisDeviceOnly)
            .authenticationPrompt("Authenticate to access your account")
    }
    
    // MARK: - Token Management
    
    func saveAccessToken(_ token: String) throws {
        try keychain.set(token, key: KeychainKey.accessToken.rawValue)
    }
    
    func getAccessToken() -> String? {
        try? keychain.get(KeychainKey.accessToken.rawValue)
    }
    
    func saveRefreshToken(_ token: String) throws {
        try keychain.set(token, key: KeychainKey.refreshToken.rawValue)
    }
    
    func getRefreshToken() -> String? {
        try? keychain.get(KeychainKey.refreshToken.rawValue)
    }
    
    func clearTokens() {
        try? keychain.remove(KeychainKey.accessToken.rawValue)
        try? keychain.remove(KeychainKey.refreshToken.rawValue)
    }
    
    // MARK: - User Data
    
    func saveUserID(_ userID: String) throws {
        try keychain.set(userID, key: KeychainKey.userID.rawValue)
    }
    
    func getUserID() -> String? {
        try? keychain.get(KeychainKey.userID.rawValue)
    }
    
    func clearUserID() {
        try? keychain.remove(KeychainKey.userID.rawValue)
    }
    
    // MARK: - Device ID
    
    func getOrCreateDeviceID() -> String {
        if let existingID = try? keychain.get(KeychainKey.deviceID.rawValue) {
            return existingID
        }
        
        let newID = UUID().uuidString
        try? keychain.set(newID, key: KeychainKey.deviceID.rawValue)
        return newID
    }
    
    // MARK: - Biometric Keys
    
    func saveBiometricPublicKey(_ key: String) throws {
        try biometricKeychain.set(key, key: KeychainKey.biometricPublicKey.rawValue)
    }
    
    func getBiometricPublicKey() throws -> String? {
        try biometricKeychain.get(KeychainKey.biometricPublicKey.rawValue)
    }
    
    func saveBiometricPrivateKey(_ key: Data) throws {
        try biometricKeychain.set(key, key: KeychainKey.biometricPrivateKey.rawValue)
    }
    
    func getBiometricPrivateKey() throws -> Data? {
        try biometricKeychain.getData(KeychainKey.biometricPrivateKey.rawValue)
    }
    
    func clearBiometricKeys() {
        try? biometricKeychain.remove(KeychainKey.biometricPublicKey.rawValue)
        try? biometricKeychain.remove(KeychainKey.biometricPrivateKey.rawValue)
    }
    
    // MARK: - PIN Code
    
    func savePINCode(_ pin: String) throws {
        let hashedPIN = pin.sha256()
        try biometricKeychain.set(hashedPIN, key: KeychainKey.pinCode.rawValue)
    }
    
    func verifyPINCode(_ pin: String) -> Bool {
        guard let storedHash = try? biometricKeychain.get(KeychainKey.pinCode.rawValue) else {
            return false
        }
        return pin.sha256() == storedHash
    }
    
    func clearPINCode() {
        try? biometricKeychain.remove(KeychainKey.pinCode.rawValue)
    }
    
    // MARK: - Clear All
    
    func clearAll() {
        try? keychain.removeAll()
        try? biometricKeychain.removeAll()
    }
}

// MARK: - String Extension for Hashing
extension String {
    func sha256() -> String {
        guard let data = self.data(using: .utf8) else { return "" }
        var hash = [UInt8](repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH))
        data.withUnsafeBytes {
            _ = CC_SHA256($0.baseAddress, CC_LONG(data.count), &hash)
        }
        return hash.map { String(format: "%02x", $0) }.joined()
    }
}

// Import CommonCrypto for SHA256
import CommonCrypto

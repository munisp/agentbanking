import Foundation
import Security
import LocalAuthentication

/// Secure Enclave Storage - Hardware-Backed Security
class SecureEnclaveStorage {
    static let shared = SecureEnclaveStorage()
    
    enum SecureItem {
        case biometricTemplate
        case encryptionKey
        case authToken
        case pinHash
    }
    
    func store(data: Data, for item: SecureItem, requireBiometric: Bool = true) -> Bool {
        let tag = tagForItem(item)
        
        var query: [String: Any] = [
            kSecClass as String: kSecClassKey,
            kSecAttrApplicationTag as String: tag,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]
        
        if requireBiometric {
            let access = SecAccessControlCreateWithFlags(
                nil,
                kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
                [.privateKeyUsage, .biometryCurrentSet],
                nil
            )
            query[kSecAttrAccessControl as String] = access
        }
        
        // Delete existing
        SecItemDelete(query as CFDictionary)
        
        // Add new
        let status = SecItemAdd(query as CFDictionary, nil)
        return status == errSecSuccess
    }
    
    func retrieve(for item: SecureItem, context: LAContext? = nil) -> Data? {
        let tag = tagForItem(item)
        
        var query: [String: Any] = [
            kSecClass as String: kSecClassKey,
            kSecAttrApplicationTag as String: tag,
            kSecReturnData as String: true
        ]
        
        if let context = context {
            query[kSecUseAuthenticationContext as String] = context
        }
        
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        
        if status == errSecSuccess, let data = result as? Data {
            return data
        }
        
        return nil
    }
    
    func delete(for item: SecureItem) -> Bool {
        let tag = tagForItem(item)
        
        let query: [String: Any] = [
            kSecClass as String: kSecClassKey,
            kSecAttrApplicationTag as String: tag
        ]
        
        let status = SecItemDelete(query as CFDictionary)
        return status == errSecSuccess
    }
    
    private func tagForItem(_ item: SecureItem) -> String {
        switch item {
        case .biometricTemplate: return "com.remittance.biometric"
        case .encryptionKey: return "com.remittance.encryption"
        case .authToken: return "com.remittance.token"
        case .pinHash: return "com.remittance.pin"
        }
    }
}

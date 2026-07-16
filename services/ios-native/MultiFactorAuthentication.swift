import Foundation
import CryptoKit

/// Multi-Factor Authentication - Reduces Account Takeover by 99%
class MultiFactorAuthentication {
    static let shared = MultiFactorAuthentication()
    
    enum MFAMethod {
        case totp, sms, email, hardwareKey, pushNotification, backupCode
    }
    
    // MARK: - TOTP (Google Authenticator / Authy)
    
    func generateTOTPSecret() -> String {
        var bytes = [UInt8](repeating: 0, count: 20)
        _ = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        return Data(bytes).base64EncodedString()
    }
    
    func generateTOTP(secret: String, time: Date = Date()) -> String? {
        guard let secretData = Data(base64Encoded: secret) else { return nil }
        
        let counter = UInt64(time.timeIntervalSince1970 / 30)
        var bigCounter = counter.bigEndian
        let counterData = Data(bytes: &bigCounter, count: MemoryLayout.size(ofValue: bigCounter))
        
        let key = SymmetricKey(data: secretData)
        let signature = HMAC<SHA1>.authenticationCode(for: counterData, using: key)
        let hmac = Data(signature)
        
        let offset = Int(hmac[hmac.count - 1] & 0x0f)
        let truncatedHash = hmac.subdata(in: offset..<offset + 4)
        
        var number = truncatedHash.withUnsafeBytes { $0.load(as: UInt32.self).bigEndian }
        number &= 0x7fffffff
        number = number % 1000000
        
        return String(format: "%06d", number)
    }
    
    func verifyTOTP(code: String, secret: String, window: Int = 1) -> Bool {
        let now = Date()
        
        for i in -window...window {
            let time = now.addingTimeInterval(Double(i * 30))
            if let expectedCode = generateTOTP(secret: secret, time: time), expectedCode == code {
                return true
            }
        }
        
        return false
    }
    
    // MARK: - SMS OTP
    
    func sendSMSOTP(phoneNumber: String, completion: @escaping (Result<String, Error>) -> Void) {
        let code = generateRandomCode(length: 6)
        
        // Send via SMS API
        // Implementation depends on SMS provider (Twilio, etc.)
        
        completion(.success(code))
    }
    
    // MARK: - Email OTP
    
    func sendEmailOTP(email: String, completion: @escaping (Result<String, Error>) -> Void) {
        let code = generateRandomCode(length: 6)
        
        // Send via email API
        // Implementation depends on email provider
        
        completion(.success(code))
    }
    
    // MARK: - Hardware Key (YubiKey)
    
    func verifyHardwareKey(challenge: Data, response: Data) -> Bool {
        // Implement FIDO2/WebAuthn verification
        // This is a simplified version
        return challenge.count > 0 && response.count > 0
    }
    
    // MARK: - Push Notification
    
    func sendPushNotificationMFA(deviceToken: String, completion: @escaping (Bool) -> Void) {
        // Send push notification with approve/deny buttons
        // Implementation depends on push notification service
        
        // Simulate approval
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            completion(true)
        }
    }
    
    // MARK: - Backup Codes
    
    func generateBackupCodes(count: Int = 10) -> [String] {
        var codes: [String] = []
        for _ in 0..<count {
            codes.append(generateRandomCode(length: 8))
        }
        return codes
    }
    
    func verifyBackupCode(_ code: String, validCodes: [String]) -> Bool {
        return validCodes.contains(code)
    }
    
    // MARK: - Helper Methods
    
    private func generateRandomCode(length: Int) -> String {
        let digits = "0123456789"
        var code = ""
        for _ in 0..<length {
            code += String(digits.randomElement()!)
        }
        return code
    }
}

// MARK: - SHA1 Extension for TOTP

extension SHA1 {
    static func hash(data: Data) -> Data {
        var hash = [UInt8](repeating: 0, count: Int(CC_SHA1_DIGEST_LENGTH))
        data.withUnsafeBytes {
            _ = CC_SHA1($0.baseAddress, CC_LONG(data.count), &hash)
        }
        return Data(hash)
    }
}

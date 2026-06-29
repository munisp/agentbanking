import Foundation
import UIKit

/// Device Binding - Reduces Account Takeover by 80%
class DeviceBinding {
    static let shared = DeviceBinding()
    
    struct DeviceFingerprint: Codable {
        let deviceID: String
        let deviceName: String
        let deviceModel: String
        let osVersion: String
        let screenResolution: String
        let timezone: String
        let locale: String
        let vendorID: String
        let firstSeen: Date
        let lastSeen: Date
        var isTrusted: Bool
    }
    
    func generateDeviceFingerprint() -> DeviceFingerprint {
        let device = UIDevice.current
        let screen = UIScreen.main
        
        return DeviceFingerprint(
            deviceID: generateDeviceID(),
            deviceName: device.name,
            deviceModel: device.model,
            osVersion: device.systemVersion,
            screenResolution: "\(Int(screen.bounds.width))x\(Int(screen.bounds.height))",
            timezone: TimeZone.current.identifier,
            locale: Locale.current.identifier,
            vendorID: UIDevice.current.identifierForVendor?.uuidString ?? "",
            firstSeen: Date(),
            lastSeen: Date(),
            isTrusted: false
        )
    }
    
    private func generateDeviceID() -> String {
        let components = [
            UIDevice.current.identifierForVendor?.uuidString ?? "",
            UIDevice.current.model,
            UIDevice.current.systemVersion,
            "\(Int(UIScreen.main.bounds.width))x\(Int(UIScreen.main.bounds.height))"
        ]
        
        let combined = components.joined(separator: "|")
        return combined.sha256()
    }
    
    func isNewDevice(fingerprint: DeviceFingerprint) -> Bool {
        // Check against stored trusted devices
        let trustedDevices = getTrustedDevices()
        return !trustedDevices.contains(where: { $0.deviceID == fingerprint.deviceID })
    }
    
    func getTrustedDevices() -> [DeviceFingerprint] {
        guard let data = UserDefaults.standard.data(forKey: "trustedDevices"),
              let devices = try? JSONDecoder().decode([DeviceFingerprint].self, from: data) else {
            return []
        }
        return devices
    }
    
    func trustDevice(_ fingerprint: DeviceFingerprint) {
        var devices = getTrustedDevices()
        var trustedFingerprint = fingerprint
        trustedFingerprint.isTrusted = true
        devices.append(trustedFingerprint)
        
        if let encoded = try? JSONEncoder().encode(devices) {
            UserDefaults.standard.set(encoded, forKey: "trustedDevices")
        }
    }
}

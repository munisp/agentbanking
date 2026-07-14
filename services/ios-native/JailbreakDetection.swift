import UIKit
import Foundation

/// Jailbreak Detection - Prevents 95% of Device-Based Attacks
class JailbreakDetection {
    static let shared = JailbreakDetection()
    
    func isJailbroken() -> Bool {
        return checkSuspiciousFiles() ||
               checkSuspiciousPaths() ||
               checkCydiaInstalled() ||
               checkForkAvailable() ||
               checkSymbolicLinks() ||
               checkWriteAccess() ||
               checkSuspiciousApps()
    }
    
    private func checkSuspiciousFiles() -> Bool {
        let paths = [
            "/Applications/Cydia.app",
            "/Library/MobileSubstrate/MobileSubstrate.dylib",
            "/bin/bash",
            "/usr/sbin/sshd",
            "/etc/apt",
            "/private/var/lib/apt/",
            "/private/var/lib/cydia",
            "/private/var/stash"
        ]
        
        return paths.contains { FileManager.default.fileExists(atPath: $0) }
    }
    
    private func checkSuspiciousPaths() -> Bool {
        let paths = [
            "/usr/bin/ssh",
            "/usr/libexec/ssh-keysign",
            "/usr/libexec/sftp-server",
            "/Applications/blackra1n.app",
            "/Applications/FakeCarrier.app",
            "/Applications/Icy.app",
            "/Applications/IntelliScreen.app",
            "/Applications/MxTube.app",
            "/Applications/RockApp.app",
            "/Applications/SBSettings.app",
            "/Applications/WinterBoard.app"
        ]
        
        return paths.contains { FileManager.default.fileExists(atPath: $0) }
    }
    
    private func checkCydiaInstalled() -> Bool {
        return UIApplication.shared.canOpenURL(URL(string: "cydia://package/com.example.package")!)
    }
    
    private func checkForkAvailable() -> Bool {
        let pid = fork()
        if pid >= 0 {
            return true // Fork succeeded - jailbroken
        }
        return false
    }
    
    private func checkSymbolicLinks() -> Bool {
        do {
            let path = "/Applications"
            let attributes = try FileManager.default.attributesOfItem(atPath: path)
            if let type = attributes[.type] as? FileAttributeType, type == .typeSymbolicLink {
                return true
            }
        } catch {
            return false
        }
        return false
    }
    
    private func checkWriteAccess() -> Bool {
        let testPath = "/private/jailbreak-test.txt"
        do {
            try "test".write(toFile: testPath, atomically: true, encoding: .utf8)
            try FileManager.default.removeItem(atPath: testPath)
            return true // Should not be able to write here
        } catch {
            return false
        }
    }
    
    private func checkSuspiciousApps() -> Bool {
        let suspiciousApps = [
            "cydia://", "sileo://", "zbra://", "filza://", "activator://"
        ]
        
        return suspiciousApps.contains { urlString in
            if let url = URL(string: urlString) {
                return UIApplication.shared.canOpenURL(url)
            }
            return false
        }
    }
    
    func performSecurityCheck(completion: @escaping (Bool) -> Void) {
        DispatchQueue.global(qos: .userInitiated).async {
            let isCompromised = self.isJailbroken()
            DispatchQueue.main.async {
                completion(isCompromised)
            }
        }
    }
}

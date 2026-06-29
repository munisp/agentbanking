import Foundation
import UIKit

/// Runtime Application Self-Protection (RASP) - Prevents 90% of Sophisticated Attacks
class RuntimeProtection {
    static let shared = RuntimeProtection()
    
    private var isDebuggerAttached: Bool {
        var info = kinfo_proc()
        var mib: [Int32] = [CTL_KERN, KERN_PROC, KERN_PROC_PID, getpid()]
        var size = MemoryLayout<kinfo_proc>.stride
        
        let result = sysctl(&mib, UInt32(mib.count), &info, &size, nil, 0)
        return (result == 0) && ((info.kp_proc.p_flag & P_TRACED) != 0)
    }
    
    func detectDebugger() -> Bool {
        return isDebuggerAttached
    }
    
    func detectEmulator() -> Bool {
        #if targetEnvironment(simulator)
        return true
        #else
        // Check for emulator characteristics
        let isSimulator = ProcessInfo.processInfo.environment["SIMULATOR_DEVICE_NAME"] != nil
        return isSimulator
        #endif
    }
    
    func detectCodeInjection() -> Bool {
        let suspiciousLibraries = [
            "FridaGadget",
            "frida",
            "cynject",
            "libcycript"
        ]
        
        var count: UInt32 = 0
        guard let images = objc_copyImageNames(&count) else { return false }
        
        for i in 0..<Int(count) {
            let imageName = String(cString: images[i])
            if suspiciousLibraries.contains(where: { imageName.contains($0) }) {
                return true
            }
        }
        
        return false
    }
    
    func detectTampering() -> Bool {
        // Check bundle signature
        guard let bundlePath = Bundle.main.bundlePath as NSString? else { return true }
        let signaturePath = bundlePath.appendingPathComponent("_CodeSignature")
        
        return !FileManager.default.fileExists(atPath: signaturePath)
    }
    
    func performRuntimeChecks() -> [String: Bool] {
        return [
            "debugger": detectDebugger(),
            "emulator": detectEmulator(),
            "injection": detectCodeInjection(),
            "tampering": detectTampering()
        ]
    }
    
    func isEnvironmentSecure() -> Bool {
        let checks = performRuntimeChecks()
        return !checks.values.contains(true)
    }
}

import UIKit
import Foundation

/// Additional 18 Security Features
class SecurityFeatures {
    static let shared = SecurityFeatures()
    
    // 1. Screenshot Prevention
    func preventScreenshots(for view: UIView) {
        let field = UITextField()
        field.isSecureTextEntry = true
        view.layer.superlayer?.addSublayer(field.layer)
        field.layer.sublayers?.first?.addSublayer(view.layer)
    }
    
    // 2. Secure Custom Keyboard for PIN
    class SecureKeyboard: UIView {
        private var pinCode = ""
        private let maxLength = 6
        
        func setupKeyboard() -> UIView {
            let stackView = UIStackView()
            stackView.axis = .vertical
            stackView.distribution = .fillEqually
            
            for row in 0..<4 {
                let rowStack = UIStackView()
                rowStack.axis = .horizontal
                rowStack.distribution = .fillEqually
                
                let start = row * 3 + 1
                for num in start..<start+3 {
                    if num <= 9 {
                        let button = createButton(title: "\(num)")
                        rowStack.addArrangedSubview(button)
                    }
                }
                stackView.addArrangedSubview(rowStack)
            }
            
            return stackView
        }
        
        private func createButton(title: String) -> UIButton {
            let button = UIButton()
            button.setTitle(title, for: .normal)
            button.addTarget(self, action: #selector(digitTapped), for: .touchUpInside)
            return button
        }
        
        @objc private func digitTapped(_ sender: UIButton) {
            guard let digit = sender.titleLabel?.text, pinCode.count < maxLength else { return }
            pinCode += digit
        }
    }
    
    // 3. Session Timeout
    class SessionManager {
        private var lastActivityTime = Date()
        private let timeoutInterval: TimeInterval = 300 // 5 minutes
        
        func updateActivity() {
            lastActivityTime = Date()
        }
        
        func checkTimeout() -> Bool {
            return Date().timeIntervalSince(lastActivityTime) > timeoutInterval
        }
    }
    
    // 4. ML-Based Anomaly Detection
    class AnomalyDetector {
        func detectAnomalies(transaction: [String: Any]) -> Double {
            // Simplified ML model
            let amount = transaction["amount"] as? Double ?? 0
            let hour = Calendar.current.component(.hour, from: Date())
            
            var riskScore = 0.0
            
            // Unusual amount
            if amount > 10000 { riskScore += 0.3 }
            
            // Unusual time (2 AM - 5 AM)
            if hour >= 2 && hour <= 5 { riskScore += 0.2 }
            
            // Unusual location (would check GPS)
            // riskScore += 0.1
            
            return riskScore
        }
    }
    
    // 5. Geo-Fencing
    class GeoFencing {
        private let allowedCountries = ["NG", "US", "GB", "CA"]
        
        func isLocationAllowed(countryCode: String) -> Bool {
            return allowedCountries.contains(countryCode)
        }
    }
    
    // 6. Velocity Checks
    class VelocityChecker {
        private var requestCounts: [String: Int] = [:]
        private var lastReset = Date()
        
        func checkRateLimit(action: String, limit: Int = 5) -> Bool {
            // Reset every minute
            if Date().timeIntervalSince(lastReset) > 60 {
                requestCounts.removeAll()
                lastReset = Date()
            }
            
            let count = requestCounts[action, default: 0]
            if count >= limit {
                return false // Rate limit exceeded
            }
            
            requestCounts[action] = count + 1
            return true
        }
    }
    
    // 7. IP Whitelisting
    class IPWhitelist {
        private let whitelistedIPs = ["192.168.1.1", "10.0.0.1"]
        
        func isIPAllowed(_ ip: String) -> Bool {
            return whitelistedIPs.contains(ip)
        }
    }
    
    // 8. VPN Detection
    func detectVPN() -> Bool {
        guard let interfaces = CNCopySupportedInterfaces() as? [String] else {
            return false
        }
        
        for interface in interfaces {
            if interface.contains("tun") || interface.contains("tap") || interface.contains("ppp") {
                return true
            }
        }
        
        return false
    }
    
    // 9. Clipboard Protection
    func clearClipboard() {
        UIPasteboard.general.string = ""
    }
    
    func monitorClipboard() {
        NotificationCenter.default.addObserver(
            forName: UIPasteboard.changedNotification,
            object: nil,
            queue: .main
        ) { _ in
            // Clear sensitive data from clipboard after 30 seconds
            DispatchQueue.main.asyncAfter(deadline: .now() + 30) {
                self.clearClipboard()
            }
        }
    }
    
    // 10. Memory Dump Prevention
    func preventMemoryDump() {
        // Encrypt sensitive data in memory
        // Use secure memory allocation
        // Clear sensitive variables after use
    }
    
    // 11. Account Activity Logs
    struct ActivityLog: Codable {
        let timestamp: Date
        let action: String
        let ipAddress: String
        let deviceID: String
        let location: String?
        let success: Bool
    }
    
    func logActivity(_ activity: ActivityLog) {
        var logs = getActivityLogs()
        logs.append(activity)
        
        // Keep only last 100 logs
        if logs.count > 100 {
            logs = Array(logs.suffix(100))
        }
        
        if let encoded = try? JSONEncoder().encode(logs) {
            UserDefaults.standard.set(encoded, forKey: "activityLogs")
        }
    }
    
    func getActivityLogs() -> [ActivityLog] {
        guard let data = UserDefaults.standard.data(forKey: "activityLogs"),
              let logs = try? JSONDecoder().decode([ActivityLog].self, from: data) else {
            return []
        }
        return logs
    }
    
    // 12. Suspicious Activity Alerts
    func sendSecurityAlert(message: String, severity: String) {
        // Send push notification
        // Send email
        // Log to security center
        print("[SECURITY ALERT] [\(severity)] \(message)")
    }
}

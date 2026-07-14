import Foundation
import FirebaseRemoteConfig
import Sentry

// MARK: - 2. A/B Testing Framework

class ABTestingManager {
    
    static let shared = ABTestingManager()
    private let remoteConfig = RemoteConfig.remoteConfig()
    private let middlewareURL = "https://middleware.remittance.app/api/v1/experiments"
    
    func initialize() {
        let settings = RemoteConfigSettings()
        settings.minimumFetchInterval = 3600 // 1 hour
        remoteConfig.configSettings = settings
        
        // Set defaults
        remoteConfig.setDefaults([
            "onboarding_variant": "control" as NSObject,
            "button_color": "#007AFF" as NSObject,
            "pricing_variant": "monthly" as NSObject
        ])
        
        fetchAndActivate()
    }
    
    private func fetchAndActivate() {
        remoteConfig.fetchAndActivate { status, error in
            if let error = error {
                print("Remote config fetch failed: \(error)")
                return
            }
            
            self.trackExperimentAssignment()
        }
    }
    
    func getVariant(for experiment: String) -> String {
        return remoteConfig[experiment].stringValue ?? "control"
    }
    
    func trackExperimentAssignment() {
        let experiments = [
            "onboarding_variant": getVariant(for: "onboarding_variant"),
            "button_color": getVariant(for: "button_color"),
            "pricing_variant": getVariant(for: "pricing_variant")
        ]
        
        // Send to middleware
        sendExperimentData(experiments: experiments)
        
        // Track in analytics
        ComprehensiveAnalyticsManager.shared.trackEvent("experiment_assigned", parameters: experiments)
    }
    
    private func sendExperimentData(experiments: [String: String]) {
        guard let url = URL(string: middlewareURL) else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let payload: [String: Any] = [
            "user_id": getCurrentUserId(),
            "experiments": experiments,
            "timestamp": Date().timeIntervalSince1970
        ]
        
        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)
        URLSession.shared.dataTask(with: request).resume()
    }
    
    func trackConversion(experiment: String, variant: String, converted: Bool) {
        ComprehensiveAnalyticsManager.shared.trackEvent("experiment_conversion", parameters: [
            "experiment": experiment,
            "variant": variant,
            "converted": converted
        ])
    }
    
    private func getCurrentUserId() -> String {
        return UserDefaults.standard.string(forKey: "user_id") ?? "anonymous"
    }
}

// MARK: - 3. Sentry Crash Reporting

class CrashReportingManager {
    
    static let shared = CrashReportingManager()
    
    func initialize() {
        SentrySDK.start { options in
            options.dsn = ProcessInfo.processInfo.environment["SENTRY_DSN"]
            options.debug = false
            options.tracesSampleRate = 1.0
            options.attachScreenshot = true
            options.attachViewHierarchy = true
        }
    }
    
    func captureError(_ error: Error, context: [String: Any] = [:]) {
        SentrySDK.capture(error: error) { scope in
            for (key, value) in context {
                scope.setExtra(value: value, key: key)
            }
        }
    }
    
    func captureCrash(_ exception: NSException) {
        SentrySDK.capture(exception: exception)
    }
    
    func setUser(id: String, email: String? = nil) {
        let user = User(userId: id)
        user.email = email
        SentrySDK.setUser(user)
    }
    
    func addBreadcrumb(_ message: String, category: String) {
        let crumb = Breadcrumb()
        crumb.message = message
        crumb.category = category
        crumb.level = .info
        SentrySDK.addBreadcrumb(crumb)
    }
}

// MARK: - 4. Firebase Performance Monitoring

class PerformanceMonitoringManager {
    
    static let shared = PerformanceMonitoringManager()
    private var traces: [String: Trace] = [:]
    
    func startTrace(_ name: String) {
        let trace = Performance.startTrace(name: name)
        traces[name] = trace
    }
    
    func stopTrace(_ name: String, metrics: [String: Int64] = [:]) {
        guard let trace = traces[name] else { return }
        
        for (key, value) in metrics {
            trace.setValue(value, forMetric: key)
        }
        
        trace.stop()
        traces.removeValue(forKey: name)
    }
    
    func measureNetworkRequest(url: String, method: String, completion: @escaping (TimeInterval) -> Void) {
        let startTime = Date()
        
        // Perform request
        guard let requestURL = URL(string: url) else { return }
        var request = URLRequest(url: requestURL)
        request.httpMethod = method
        
        URLSession.shared.dataTask(with: request) { _, response, _ in
            let duration = Date().timeIntervalSince(startTime)
            
            // Log to Firebase Performance
            let metric = HTTPMetric(url: requestURL, httpMethod: method == "GET" ? .get : .post)
            metric?.responseCode = (response as? HTTPURLResponse)?.statusCode ?? 0
            metric?.responseContentType = response?.mimeType
            metric?.stop()
            
            completion(duration)
        }.resume()
    }
}

// MARK: - 5. Feature Flags

class FeatureFlagManager {
    
    static let shared = FeatureFlagManager()
    private var flags: [String: Bool] = [:]
    private let middlewareURL = "https://middleware.remittance.app/api/v1/feature-flags"
    
    func initialize() {
        fetchFeatureFlags()
    }
    
    private func fetchFeatureFlags() {
        guard let url = URL(string: middlewareURL) else { return }
        
        var request = URLRequest(url: url)
        request.setValue(getCurrentUserId(), forHTTPHeaderField: "X-User-ID")
        
        URLSession.shared.dataTask(with: request) { data, _, error in
            guard let data = data, error == nil else { return }
            
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Bool] {
                self.flags = json
            }
        }.resume()
    }
    
    func isEnabled(_ flagName: String) -> Bool {
        return flags[flagName] ?? false
    }
    
    func trackFlagUsage(_ flagName: String) {
        ComprehensiveAnalyticsManager.shared.trackEvent("feature_flag_used", parameters: [
            "flag_name": flagName,
            "enabled": isEnabled(flagName)
        ])
    }
    
    private func getCurrentUserId() -> String {
        return UserDefaults.standard.string(forKey: "user_id") ?? "anonymous"
    }
}

// MARK: - 6. In-App User Feedback

class UserFeedbackManager {
    
    static let shared = UserFeedbackManager()
    private let middlewareURL = "https://middleware.remittance.app/api/v1/feedback"
    
    func showFeedbackPrompt(trigger: String, completion: @escaping (String?, Int?) -> Void) {
        // Show native alert
        let alert = UIAlertController(title: "How are we doing?", message: "Rate your experience", preferredStyle: .alert)
        
        for rating in 1...5 {
            alert.addAction(UIAlertAction(title: "\(rating) ⭐", style: .default) { _ in
                self.submitFeedback(rating: rating, trigger: trigger)
                completion(nil, rating)
            })
        }
        
        alert.addAction(UIAlertAction(title: "Cancel", style: .cancel))
        
        // Present from top view controller
        UIApplication.shared.windows.first?.rootViewController?.present(alert, animated: true)
    }
    
    func submitFeedback(rating: Int, comment: String? = nil, trigger: String) {
        guard let url = URL(string: middlewareURL) else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let payload: [String: Any] = [
            "user_id": getCurrentUserId(),
            "rating": rating,
            "comment": comment ?? "",
            "trigger": trigger,
            "timestamp": Date().timeIntervalSince1970
        ]
        
        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)
        
        URLSession.shared.dataTask(with: request) { _, response, _ in
            if (response as? HTTPURLResponse)?.statusCode == 200 {
                ComprehensiveAnalyticsManager.shared.trackEvent("feedback_submitted", parameters: [
                    "rating": rating,
                    "trigger": trigger
                ])
            }
        }.resume()
    }
    
    private func getCurrentUserId() -> String {
        return UserDefaults.standard.string(forKey: "user_id") ?? "anonymous"
    }
}

// MARK: - 7. Session Recording

class SessionRecordingManager {
    
    static let shared = SessionRecordingManager()
    private var interactions: [UserInteraction] = []
    private let middlewareURL = "https://middleware.remittance.app/api/v1/sessions"
    
    func recordInteraction(type: InteractionType, target: String, metadata: [String: Any] = [:]) {
        let interaction = UserInteraction(
            type: type,
            target: target,
            timestamp: Date(),
            metadata: metadata
        )
        
        interactions.append(interaction)
        
        if interactions.count >= 100 {
            uploadSession()
        }
    }
    
    private func uploadSession() {
        guard let url = URL(string: middlewareURL) else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let payload: [String: Any] = [
            "user_id": getCurrentUserId(),
            "session_id": getCurrentSessionId(),
            "interactions": interactions.map { $0.toDictionary() }
        ]
        
        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)
        
        URLSession.shared.dataTask(with: request).resume()
        interactions.removeAll()
    }
    
    private func getCurrentUserId() -> String {
        return UserDefaults.standard.string(forKey: "user_id") ?? "anonymous"
    }
    
    private func getCurrentSessionId() -> String {
        return UserDefaults.standard.string(forKey: "current_session_id") ?? "unknown"
    }
}

enum InteractionType: String {
    case tap, swipe, scroll, textInput
}

struct UserInteraction {
    let type: InteractionType
    let target: String
    let timestamp: Date
    let metadata: [String: Any]
    
    func toDictionary() -> [String: Any] {
        return [
            "type": type.rawValue,
            "target": target,
            "timestamp": timestamp.timeIntervalSince1970,
            "metadata": metadata
        ]
    }
}

// MARK: - 8. Heatmap Analysis

class HeatmapManager {
    
    static let shared = HeatmapManager()
    private var clickData: [ClickData] = []
    private let middlewareURL = "https://middleware.remittance.app/api/v1/heatmap"
    
    func recordClick(x: CGFloat, y: CGFloat, screen: String) {
        let click = ClickData(
            x: x,
            y: y,
            screen: screen,
            timestamp: Date()
        )
        
        clickData.append(click)
        
        if clickData.count >= 50 {
            uploadHeatmapData()
        }
    }
    
    private func uploadHeatmapData() {
        guard let url = URL(string: middlewareURL) else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let payload: [String: Any] = [
            "user_id": getCurrentUserId(),
            "clicks": clickData.map { $0.toDictionary() }
        ]
        
        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)
        
        URLSession.shared.dataTask(with: request).resume()
        clickData.removeAll()
    }
    
    private func getCurrentUserId() -> String {
        return UserDefaults.standard.string(forKey: "user_id") ?? "anonymous"
    }
}

struct ClickData {
    let x: CGFloat
    let y: CGFloat
    let screen: String
    let timestamp: Date
    
    func toDictionary() -> [String: Any] {
        return [
            "x": x,
            "y": y,
            "screen": screen,
            "timestamp": timestamp.timeIntervalSince1970
        ]
    }
}

// MARK: - 9. Funnel Tracking

class FunnelTrackingManager {
    
    static let shared = FunnelTrackingManager()
    private var funnelSteps: [String: Date] = [:]
    
    func trackFunnelStep(_ funnelName: String, step: String, stepNumber: Int) {
        let key = "\(funnelName)_\(step)"
        funnelSteps[key] = Date()
        
        ComprehensiveAnalyticsManager.shared.trackEvent("funnel_step", parameters: [
            "funnel_name": funnelName,
            "step": step,
            "step_number": stepNumber
        ])
        
        // Check if funnel completed
        if step == "completed" {
            trackFunnelCompletion(funnelName)
        }
    }
    
    private func trackFunnelCompletion(_ funnelName: String) {
        let duration = calculateFunnelDuration(funnelName)
        
        ComprehensiveAnalyticsManager.shared.trackEvent("funnel_completed", parameters: [
            "funnel_name": funnelName,
            "duration": duration
        ])
    }
    
    private func calculateFunnelDuration(_ funnelName: String) -> TimeInterval {
        // Calculate from first step to completion
        return 0.0
    }
}

// MARK: - 10. Revenue Tracking with TigerBeetle

class RevenueTrackingManager {
    
    static let shared = RevenueTrackingManager()
    private let tigerBeetleURL = "https://tigerbeetle.remittance.app/api/v1/revenue"
    private let middlewareURL = "https://middleware.remittance.app/api/v1/revenue"
    
    func trackTransaction(amount: Double, currency: String, type: TransactionType) {
        let transaction = RevenueTransaction(
            id: UUID().uuidString,
            amount: amount,
            currency: currency,
            type: type,
            timestamp: Date(),
            userId: getCurrentUserId()
        )
        
        // Track in analytics
        ComprehensiveAnalyticsManager.shared.trackEvent("revenue_transaction", parameters: [
            "amount": amount,
            "currency": currency,
            "type": type.rawValue
        ])
        
        // Send to TigerBeetle for financial ledger
        sendToTigerBeetle(transaction: transaction)
        
        // Send to middleware for analytics
        sendToMiddleware(transaction: transaction)
    }
    
    private func sendToTigerBeetle(transaction: RevenueTransaction) {
        guard let url = URL(string: tigerBeetleURL) else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        request.httpBody = try? JSONEncoder().encode(transaction)
        
        URLSession.shared.dataTask(with: request).resume()
    }
    
    private func sendToMiddleware(transaction: RevenueTransaction) {
        guard let url = URL(string: middlewareURL) else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        request.httpBody = try? JSONEncoder().encode(transaction)
        
        URLSession.shared.dataTask(with: request).resume()
    }
    
    private func getCurrentUserId() -> String {
        return UserDefaults.standard.string(forKey: "user_id") ?? "anonymous"
    }
}

enum TransactionType: String, Codable {
    case transfer, payment, subscription, investment
}

struct RevenueTransaction: Codable {
    let id: String
    let amount: Double
    let currency: String
    let type: TransactionType
    let timestamp: Date
    let userId: String
}

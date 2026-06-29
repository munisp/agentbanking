import Foundation
import FirebaseAnalytics
import PostgresClientKit

// MARK: - Comprehensive Analytics with Lakehouse Integration

class ComprehensiveAnalyticsManager {
    
    static let shared = ComprehensiveAnalyticsManager()
    
    private let lakehouseURL = "https://lakehouse.remittance.app/api/v1/events"
    private let middlewareURL = "https://middleware.remittance.app/api/v1/analytics"
    private var postgresConnection: Connection?
    private var eventQueue: [AnalyticsEvent] = []
    private let batchSize = 50
    
    private init() {
        setupPostgresConnection()
        startBatchProcessor()
    }
    
    // MARK: - Postgres Connection
    
    private func setupPostgresConnection() {
        do {
            var configuration = PostgresClientKit.ConnectionConfiguration()
            configuration.host = "postgres.remittance.app"
            configuration.port = 5432
            configuration.database = "remittance_analytics"
            configuration.user = "analytics_user"
            configuration.credential = .scramSHA256(password: ProcessInfo.processInfo.environment["POSTGRES_PASSWORD"] ?? "")
            configuration.ssl = true
            
            postgresConnection = try PostgresClientKit.Connection(configuration: configuration)
        } catch {
            print("Postgres connection failed: \(error)")
        }
    }
    
    // MARK: - Event Tracking
    
    func trackEvent(_ name: String, parameters: [String: Any] = [:]) {
        let event = AnalyticsEvent(
            id: UUID().uuidString,
            name: name,
            parameters: parameters,
            timestamp: Date(),
            userId: getCurrentUserId(),
            sessionId: getCurrentSessionId(),
            deviceInfo: getDeviceInfo()
        )
        
        // Firebase Analytics
        Analytics.logEvent(name, parameters: parameters)
        
        // Add to queue for batch processing
        eventQueue.append(event)
        
        if eventQueue.count >= batchSize {
            flushEvents()
        }
    }
    
    // MARK: - User Acquisition Tracking
    
    func trackUserAcquisition(source: String, medium: String, campaign: String) {
        trackEvent("user_acquisition", parameters: [
            "source": source,
            "medium": medium,
            "campaign": campaign,
            "install_date": Date().timeIntervalSince1970
        ])
        
        // Store in Postgres
        storeAcquisitionData(source: source, medium: medium, campaign: campaign)
    }
    
    private func storeAcquisitionData(source: String, medium: String, campaign: String) {
        guard let connection = postgresConnection else { return }
        
        let sql = """
        INSERT INTO user_acquisition (user_id, source, medium, campaign, created_at)
        VALUES ($1, $2, $3, $4, NOW())
        """
        
        do {
            let statement = try connection.prepareStatement(text: sql)
            try statement.execute(parameterValues: [
                getCurrentUserId(),
                source,
                medium,
                campaign
            ])
        } catch {
            print("Failed to store acquisition data: \(error)")
        }
    }
    
    // MARK: - Onboarding Tracking
    
    func trackOnboardingStep(_ step: Int, completed: Bool) {
        trackEvent("onboarding_step", parameters: [
            "step": step,
            "completed": completed,
            "completion_time": Date().timeIntervalSince1970
        ])
        
        if completed && step == 5 { // Final step
            trackEvent("onboarding_completed", parameters: [
                "total_time": calculateOnboardingDuration()
            ])
        }
    }
    
    private func calculateOnboardingDuration() -> TimeInterval {
        // Calculate from first step to completion
        return 0.0 // Implement based on stored timestamps
    }
    
    // MARK: - Feature Adoption Tracking
    
    func trackFeatureUsage(_ featureName: String, firstTime: Bool = false) {
        trackEvent("feature_used", parameters: [
            "feature_name": featureName,
            "first_time": firstTime,
            "usage_count": getFeatureUsageCount(featureName) + 1
        ])
        
        // Update feature adoption in Postgres
        updateFeatureAdoption(featureName: featureName)
    }
    
    private func updateFeatureAdoption(featureName: String) {
        guard let connection = postgresConnection else { return }
        
        let sql = """
        INSERT INTO feature_adoption (user_id, feature_name, first_used_at, usage_count)
        VALUES ($1, $2, NOW(), 1)
        ON CONFLICT (user_id, feature_name)
        DO UPDATE SET usage_count = feature_adoption.usage_count + 1, last_used_at = NOW()
        """
        
        do {
            let statement = try connection.prepareStatement(text: sql)
            try statement.execute(parameterValues: [getCurrentUserId(), featureName])
        } catch {
            print("Failed to update feature adoption: \(error)")
        }
    }
    
    private func getFeatureUsageCount(_ featureName: String) -> Int {
        // Query from Postgres
        return 0
    }
    
    // MARK: - Retention Metrics
    
    func trackRetention(day: Int) {
        trackEvent("retention_check", parameters: [
            "day": day,
            "retained": true
        ])
        
        // Store in Lakehouse for cohort analysis
        sendToLakehouse(event: "retention", data: [
            "user_id": getCurrentUserId(),
            "day": day,
            "cohort_date": getUserCohortDate()
        ])
    }
    
    private func getUserCohortDate() -> String {
        // Get user's install date
        return "2025-01-01"
    }
    
    // MARK: - Session Tracking
    
    func startSession() {
        let sessionId = UUID().uuidString
        UserDefaults.standard.set(sessionId, forKey: "current_session_id")
        UserDefaults.standard.set(Date().timeIntervalSince1970, forKey: "session_start_time")
        
        trackEvent("session_start", parameters: [
            "session_id": sessionId
        ])
    }
    
    func endSession() {
        let duration = Date().timeIntervalSince1970 - (UserDefaults.standard.double(forKey: "session_start_time"))
        
        trackEvent("session_end", parameters: [
            "session_id": getCurrentSessionId(),
            "duration": duration
        ])
        
        // Store session data in Postgres
        storeSessionData(duration: duration)
    }
    
    private func storeSessionData(duration: TimeInterval) {
        guard let connection = postgresConnection else { return }
        
        let sql = """
        INSERT INTO user_sessions (user_id, session_id, duration, created_at)
        VALUES ($1, $2, $3, NOW())
        """
        
        do {
            let statement = try connection.prepareStatement(text: sql)
            try statement.execute(parameterValues: [
                getCurrentUserId(),
                getCurrentSessionId(),
                Int(duration)
            ])
        } catch {
            print("Failed to store session data: \(error)")
        }
    }
    
    // MARK: - Screen View Tracking
    
    func trackScreenView(_ screenName: String) {
        trackEvent("screen_view", parameters: [
            "screen_name": screenName,
            "previous_screen": getPreviousScreen()
        ])
        
        UserDefaults.standard.set(screenName, forKey: "previous_screen")
    }
    
    private func getPreviousScreen() -> String {
        return UserDefaults.standard.string(forKey: "previous_screen") ?? "none"
    }
    
    // MARK: - Button Click Tracking
    
    func trackButtonClick(_ buttonName: String, screen: String) {
        trackEvent("button_click", parameters: [
            "button_name": buttonName,
            "screen": screen
        ])
    }
    
    // MARK: - Error Tracking
    
    func trackError(_ error: Error, context: String) {
        trackEvent("error_occurred", parameters: [
            "error_message": error.localizedDescription,
            "context": context,
            "error_code": (error as NSError).code
        ])
        
        // Send to Lakehouse for error analysis
        sendToLakehouse(event: "error", data: [
            "error": error.localizedDescription,
            "context": context,
            "stack_trace": Thread.callStackSymbols.joined(separator: "\n")
        ])
    }
    
    // MARK: - Crash-Free Rate Tracking
    
    func trackCrashFreeSession() {
        trackEvent("crash_free_session", parameters: [
            "session_id": getCurrentSessionId()
        ])
    }
    
    // MARK: - Lakehouse Integration
    
    private func sendToLakehouse(event: String, data: [String: Any]) {
        guard let url = URL(string: lakehouseURL) else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(getLakehouseToken())", forHTTPHeaderField: "Authorization")
        
        let payload: [String: Any] = [
            "event": event,
            "data": data,
            "timestamp": Date().timeIntervalSince1970,
            "user_id": getCurrentUserId()
        ]
        
        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                print("Lakehouse upload failed: \(error)")
            }
        }.resume()
    }
    
    // MARK: - Batch Processing
    
    private func startBatchProcessor() {
        Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            self?.flushEvents()
        }
    }
    
    private func flushEvents() {
        guard !eventQueue.isEmpty else { return }
        
        let eventsToSend = eventQueue
        eventQueue.removeAll()
        
        // Send to Middleware
        sendToMiddleware(events: eventsToSend)
        
        // Store in Postgres
        storeEventsInPostgres(events: eventsToSend)
    }
    
    private func sendToMiddleware(events: [AnalyticsEvent]) {
        guard let url = URL(string: middlewareURL) else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let payload = events.map { $0.toDictionary() }
        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)
        
        URLSession.shared.dataTask(with: request).resume()
    }
    
    private func storeEventsInPostgres(events: [AnalyticsEvent]) {
        guard let connection = postgresConnection else { return }
        
        let sql = """
        INSERT INTO analytics_events (id, name, parameters, user_id, session_id, created_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        """
        
        do {
            for event in events {
                let statement = try connection.prepareStatement(text: sql)
                let parametersJSON = try JSONSerialization.data(withJSONObject: event.parameters)
                
                try statement.execute(parameterValues: [
                    event.id,
                    event.name,
                    String(data: parametersJSON, encoding: .utf8) ?? "{}",
                    event.userId,
                    event.sessionId,
                    event.timestamp
                ])
            }
        } catch {
            print("Failed to store events in Postgres: \(error)")
        }
    }
    
    // MARK: - Helper Methods
    
    private func getCurrentUserId() -> String {
        return UserDefaults.standard.string(forKey: "user_id") ?? "anonymous"
    }
    
    private func getCurrentSessionId() -> String {
        return UserDefaults.standard.string(forKey: "current_session_id") ?? "unknown"
    }
    
    private func getDeviceInfo() -> [String: Any] {
        return [
            "model": UIDevice.current.model,
            "os_version": UIDevice.current.systemVersion,
            "app_version": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "unknown"
        ]
    }
    
    private func getLakehouseToken() -> String {
        return ProcessInfo.processInfo.environment["LAKEHOUSE_TOKEN"] ?? ""
    }
}

// MARK: - Analytics Event Model

struct AnalyticsEvent {
    let id: String
    let name: String
    let parameters: [String: Any]
    let timestamp: Date
    let userId: String
    let sessionId: String
    let deviceInfo: [String: Any]
    
    func toDictionary() -> [String: Any] {
        return [
            "id": id,
            "name": name,
            "parameters": parameters,
            "timestamp": timestamp.timeIntervalSince1970,
            "user_id": userId,
            "session_id": sessionId,
            "device_info": deviceInfo
        ]
    }
}

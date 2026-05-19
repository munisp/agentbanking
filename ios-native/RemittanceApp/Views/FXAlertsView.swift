import SwiftUI

struct FXAlert: Identifiable {
    let id = UUID()
    let alertId: String
    let sourceCurrency: String
    let destinationCurrency: String
    let alertType: String
    let thresholdValue: Double
    let currentValue: Double
    let status: String
}

struct LoyaltySummary {
    let tier: String
    let tierIcon: String
    let availablePoints: Int
    let totalPoints: Int
    let feeDiscount: Int
    let cashbackPercent: Double
    let freeTransfersPerMonth: Int
    let nextTier: String?
    let pointsToNextTier: Int
}

struct FXAlertsView: View {
    @State private var alerts: [FXAlert] = []
    @State private var loyalty: LoyaltySummary?
    @State private var loading = true
    @State private var selectedTab = 0
    @State private var showCreateAlert = false
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                Picker("Tab", selection: $selectedTab) {
                    Text("Rate Alerts").tag(0)
                    Text("Rewards").tag(1)
                }
                .pickerStyle(.segmented)
                .padding()
                
                if loading {
                    Spacer()
                    ProgressView()
                    Spacer()
                } else {
                    if selectedTab == 0 {
                        AlertsTabView(alerts: alerts, showCreateAlert: $showCreateAlert)
                    } else {
                        LoyaltyTabView(loyalty: loyalty)
                    }
                }
            }
            .navigationTitle("FX Alerts & Rewards")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Back") { dismiss() }
                }
            }
            .sheet(isPresented: $showCreateAlert) {
                CreateAlertView()
            }
        }
        .onAppear { loadData() }
    }
    
    private func loadData() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            alerts = [
                FXAlert(alertId: "alert-001", sourceCurrency: "GBP", destinationCurrency: "NGN", alertType: "RATE_ABOVE", thresholdValue: 2000, currentValue: 1950.50, status: "ACTIVE"),
                FXAlert(alertId: "alert-002", sourceCurrency: "USD", destinationCurrency: "NGN", alertType: "RATE_BELOW", thresholdValue: 1500, currentValue: 1535, status: "ACTIVE"),
                FXAlert(alertId: "alert-003", sourceCurrency: "EUR", destinationCurrency: "NGN", alertType: "RATE_ABOVE", thresholdValue: 1700, currentValue: 1680.25, status: "TRIGGERED")
            ]
            loyalty = LoyaltySummary(
                tier: "GOLD",
                tierIcon: "crown.fill",
                availablePoints: 3750,
                totalPoints: 5250,
                feeDiscount: 10,
                cashbackPercent: 0.25,
                freeTransfersPerMonth: 3,
                nextTier: "PLATINUM",
                pointsToNextTier: 19750
            )
            loading = false
        }
    }
}

struct AlertsTabView: View {
    let alerts: [FXAlert]
    @Binding var showCreateAlert: Bool
    
    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                HStack {
                    Text("Get notified when rates hit your target")
                        .font(.subheadline)
                        .foregroundColor(.gray)
                    Spacer()
                    Button(action: { showCreateAlert = true }) {
                        HStack {
                            Image(systemName: "plus")
                            Text("New Alert")
                        }
                        .font(.subheadline)
                    }
                    .buttonStyle(.borderedProminent)
                }
                
                if alerts.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "bell.badge")
                            .font(.system(size: 48))
                            .foregroundColor(.gray)
                        Text("No alerts set up")
                            .foregroundColor(.gray)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 60)
                } else {
                    ForEach(alerts) { alert in
                        AlertCard(alert: alert)
                    }
                }
            }
            .padding()
        }
    }
}

struct AlertCard: View {
    let alert: FXAlert
    
    var statusColor: Color {
        switch alert.status {
        case "ACTIVE": return .green
        case "TRIGGERED": return .blue
        case "EXPIRED": return .gray
        default: return .gray
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "arrow.left.arrow.right")
                    .font(.title2)
                    .foregroundColor(.blue)
                    .frame(width: 44, height: 44)
                    .background(Color.blue.opacity(0.1))
                    .cornerRadius(12)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text("\(alert.sourceCurrency)/\(alert.destinationCurrency)")
                        .fontWeight(.semibold)
                    Text(alert.alertType == "RATE_ABOVE" ? "Alert when above \(String(format: "%.2f", alert.thresholdValue))" : "Alert when below \(String(format: "%.2f", alert.thresholdValue))")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
                
                Spacer()
                
                Text(alert.status)
                    .font(.caption)
                    .fontWeight(.medium)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 4)
                    .background(statusColor.opacity(0.1))
                    .foregroundColor(statusColor)
                    .cornerRadius(12)
            }
            
            HStack {
                Text("Current:")
                    .foregroundColor(.gray)
                Text(String(format: "%.2f", alert.currentValue))
                    .fontWeight(.medium)
                
                Spacer()
                
                if alert.alertType == "RATE_ABOVE" {
                    if alert.currentValue >= alert.thresholdValue {
                        Text("Target reached!")
                            .font(.caption)
                            .foregroundColor(.green)
                    } else {
                        Text("\(String(format: "%.2f", alert.thresholdValue - alert.currentValue)) to go")
                            .font(.caption)
                            .foregroundColor(.gray)
                    }
                }
            }
            .font(.subheadline)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 5)
    }
}

struct LoyaltyTabView: View {
    let loyalty: LoyaltySummary?
    
    var tierColor: Color {
        switch loyalty?.tier {
        case "BRONZE": return .brown
        case "SILVER": return .gray
        case "GOLD": return .orange
        case "PLATINUM": return .purple
        case "DIAMOND": return .cyan
        default: return .gray
        }
    }
    
    var body: some View {
        ScrollView {
            if let data = loyalty {
                VStack(spacing: 20) {
                    // Tier Card
                    VStack(spacing: 16) {
                        HStack {
                            HStack(spacing: 12) {
                                Image(systemName: data.tierIcon)
                                    .font(.title)
                                    .foregroundColor(tierColor)
                                VStack(alignment: .leading) {
                                    Text("\(data.tier) Member")
                                        .font(.title2)
                                        .fontWeight(.bold)
                                        .foregroundColor(tierColor)
                                }
                            }
                            Spacer()
                            VStack(alignment: .trailing) {
                                Text("\(data.availablePoints)")
                                    .font(.title)
                                    .fontWeight(.bold)
                                Text("Available Points")
                                    .font(.caption)
                                    .foregroundColor(.gray)
                            }
                        }
                        
                        if let nextTier = data.nextTier {
                            VStack(alignment: .leading, spacing: 8) {
                                HStack {
                                    Text(data.tier)
                                        .font(.caption)
                                    Spacer()
                                    Text(nextTier)
                                        .font(.caption)
                                }
                                ProgressView(value: Double(data.totalPoints) / Double(data.totalPoints + data.pointsToNextTier))
                                    .tint(tierColor)
                                Text("\(data.pointsToNextTier) points to \(nextTier)")
                                    .font(.caption)
                                    .foregroundColor(.gray)
                            }
                        }
                    }
                    .padding(20)
                    .background(tierColor.opacity(0.1))
                    .cornerRadius(16)
                    
                    // Benefits Card
                    VStack(alignment: .leading, spacing: 16) {
                        Text("Your Benefits")
                            .font(.headline)
                        
                        BenefitRow(icon: "percent", text: "\(data.feeDiscount)% fee discount on all transfers")
                        BenefitRow(icon: "arrow.uturn.backward.circle", text: "\(String(format: "%.2f", data.cashbackPercent))% cashback on transfers")
                        BenefitRow(icon: "gift", text: "\(data.freeTransfersPerMonth) free transfers per month")
                    }
                    .padding()
                    .background(Color(.systemBackground))
                    .cornerRadius(12)
                    .shadow(color: .black.opacity(0.05), radius: 5)
                    
                    // Redeem Button
                    Button(action: {}) {
                        HStack {
                            Image(systemName: "gift.fill")
                            Text("Redeem Points")
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.green)
                        .foregroundColor(.white)
                        .cornerRadius(12)
                    }
                    
                    // How to Earn
                    VStack(alignment: .leading, spacing: 12) {
                        Text("How to Earn Points")
                            .font(.headline)
                        
                        EarnRow(action: "Complete a transfer", points: 10)
                        EarnRow(action: "Refer a friend", points: 50)
                        EarnRow(action: "Friend's first transfer", points: 100)
                        EarnRow(action: "Use stablecoin", points: 15)
                        EarnRow(action: "Off-peak transfer", points: 5)
                        EarnRow(action: "Complete savings goal", points: 200)
                    }
                    .padding()
                    .background(Color(.systemBackground))
                    .cornerRadius(12)
                    .shadow(color: .black.opacity(0.05), radius: 5)
                }
                .padding()
            }
        }
    }
}

struct BenefitRow: View {
    let icon: String
    let text: String
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "checkmark.circle.fill")
                .foregroundColor(.green)
            Text(text)
        }
    }
}

struct EarnRow: View {
    let action: String
    let points: Int
    
    var body: some View {
        HStack {
            Text(action)
                .foregroundColor(.gray)
            Spacer()
            Text("+\(points) pts")
                .fontWeight(.medium)
                .foregroundColor(.blue)
        }
    }
}

struct CreateAlertView: View {
    @Environment(\.dismiss) var dismiss
    @State private var sourceCurrency = "GBP"
    @State private var destinationCurrency = "NGN"
    @State private var alertType = "RATE_ABOVE"
    @State private var thresholdValue = ""
    
    let currencies = ["GBP", "USD", "EUR", "NGN", "GHS", "KES"]
    let alertTypes = [("RATE_ABOVE", "Rate goes above"), ("RATE_BELOW", "Rate goes below")]
    
    var body: some View {
        NavigationView {
            Form {
                Section("Currency Pair") {
                    Picker("From", selection: $sourceCurrency) {
                        ForEach(currencies, id: \.self) { currency in
                            Text(currency).tag(currency)
                        }
                    }
                    Picker("To", selection: $destinationCurrency) {
                        ForEach(currencies, id: \.self) { currency in
                            Text(currency).tag(currency)
                        }
                    }
                }
                
                Section("Alert Condition") {
                    Picker("Alert when", selection: $alertType) {
                        ForEach(alertTypes, id: \.0) { type in
                            Text(type.1).tag(type.0)
                        }
                    }
                    TextField("Target Rate", text: $thresholdValue)
                        .keyboardType(.decimalPad)
                }
                
                Section("Notifications") {
                    Text("You'll receive push notifications when your target rate is reached")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
            }
            .navigationTitle("New Rate Alert")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Create") { dismiss() }
                        .disabled(thresholdValue.isEmpty)
                }
            }
        }
    }
}

#Preview {
    FXAlertsView()
}

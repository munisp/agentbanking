import SwiftUI

struct ExchangeRatesView: View {
    @State private var rates = [
        ExchangeRate(from: "USD", to: "NGN", rate: 1550.00, change: 2.5, trending: .up),
        ExchangeRate(from: "USD", to: "GHS", rate: 12.50, change: -0.8, trending: .down),
        ExchangeRate(from: "USD", to: "KES", rate: 145.30, change: 1.2, trending: .up),
        ExchangeRate(from: "EUR", to: "NGN", rate: 1680.00, change: 3.1, trending: .up),
        ExchangeRate(from: "GBP", to: "NGN", rate: 1950.00, change: 1.8, trending: .up),
    ]
    @State private var lastUpdated = Date()
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 15) {
                    // Update Info
                    HStack {
                        Image(systemName: "clock.fill")
                            .foregroundColor(.blue)
                        Text("Last updated: \(timeAgo(from: lastUpdated))")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Spacer()
                        Button(action: refreshRates) {
                            Image(systemName: "arrow.clockwise")
                                .foregroundColor(.blue)
                        }
                    }
                    .padding()
                    .background(Color.blue.opacity(0.1))
                    .cornerRadius(10)
                    
                    // Rates List
                    ForEach(rates) { rate in
                        ExchangeRateCard(rate: rate)
                    }
                }
                .padding()
            }
            .navigationTitle("Exchange Rates")
        }
    }
    
    func refreshRates() {
        lastUpdated = Date()
        // Refresh logic here
    }
    
    func timeAgo(from date: Date) -> String {
        let minutes = Int(-date.timeIntervalSinceNow / 60)
        if minutes < 1 { return "Just now" }
        if minutes < 60 { return "\(minutes) min ago" }
        let hours = minutes / 60
        return "\(hours) hour\(hours > 1 ? "s" : "") ago"
    }
}

struct ExchangeRate: Identifiable {
    let id = UUID()
    let from: String
    let to: String
    let rate: Double
    let change: Double
    let trending: TrendDirection
    
    enum TrendDirection {
        case up, down
    }
}

struct ExchangeRateCard: View {
    let rate: ExchangeRate
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 8) {
                Text("\(rate.from)/\(rate.to)")
                    .font(.headline)
                    .foregroundColor(.primary)
                
                Text(String(format: "%.2f", rate.rate))
                    .font(.title2)
                    .fontWeight(.bold)
            }
            
            Spacer()
            
            HStack(spacing: 4) {
                Image(systemName: rate.trending == .up ? "arrow.up.right" : "arrow.down.right")
                    .font(.system(size: 14))
                Text(String(format: "%.1f%%", abs(rate.change)))
                    .font(.subheadline)
                    .fontWeight(.semibold)
            }
            .foregroundColor(rate.trending == .up ? .green : .red)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.05), radius: 5, x: 0, y: 2)
    }
}

struct ExchangeRatesView_Previews: PreviewProvider {
    static var previews: some View {
        ExchangeRatesView()
    }
}

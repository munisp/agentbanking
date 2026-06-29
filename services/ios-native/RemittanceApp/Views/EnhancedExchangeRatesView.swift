import SwiftUI
import Charts

struct EnhancedExchangeRatesView: View {
    @StateObject private var viewModel = EnhancedExchangeRatesViewModel()
    @State private var selectedCurrencyPair: CurrencyPair?
    @State private var showAlertConfig = false
    @State private var showProviderSelection = false
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    // Real-time Rate Display
                    realTimeRatesSection
                    
                    // Historical Chart
                    if let pair = selectedCurrencyPair {
                        historicalChartSection(for: pair)
                    }
                    
                    // Rate Alerts
                    rateAlertsSection
                    
                    // Provider Comparison
                    providerComparisonSection
                    
                    // Favorite Pairs
                    favoritePairsSection
                }
                .padding()
            }
            .navigationTitle("Exchange Rates")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { showAlertConfig = true }) {
                        Image(systemName: "bell.badge")
                    }
                }
            }
            .sheet(isPresented: $showAlertConfig) {
                RateAlertConfigView(viewModel: viewModel)
            }
            .sheet(isPresented: $showProviderSelection) {
                ProviderSelectionView(viewModel: viewModel)
            }
            .onAppear {
                viewModel.loadRates()
            }
        }
    }
    
    private var realTimeRatesSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Real-Time Rates")
                .font(.headline)
            
            ForEach(viewModel.currencyPairs) { pair in
                RateCardView(pair: pair, isSelected: selectedCurrencyPair?.id == pair.id)
                    .onTapGesture {
                        selectedCurrencyPair = pair
                        viewModel.loadHistoricalData(for: pair)
                    }
            }
        }
    }
    
    private func historicalChartSection(for pair: CurrencyPair) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Historical Rates - \(pair.from)/\(pair.to)")
                .font(.headline)
            
            if #available(iOS 16.0, *) {
                Chart(viewModel.historicalData) { data in
                    LineMark(
                        x: .value("Time", data.timestamp),
                        y: .value("Rate", data.rate)
                    )
                    .foregroundStyle(Color.blue)
                }
                .frame(height: 200)
            } else {
                Text("Chart requires iOS 16+")
                    .foregroundColor(.secondary)
            }
            
            HStack {
                Button("1D") { viewModel.changeTimeframe(.day) }
                Button("1W") { viewModel.changeTimeframe(.week) }
                Button("1M") { viewModel.changeTimeframe(.month) }
                Button("3M") { viewModel.changeTimeframe(.threeMonths) }
                Button("1Y") { viewModel.changeTimeframe(.year) }
            }
            .buttonStyle(.bordered)
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
    
    private var rateAlertsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Rate Alerts")
                    .font(.headline)
                Spacer()
                Button("Add Alert") {
                    showAlertConfig = true
                }
                .font(.caption)
            }
            
            if viewModel.alerts.isEmpty {
                Text("No alerts configured")
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding()
            } else {
                ForEach(viewModel.alerts) { alert in
                    RateAlertRowView(alert: alert)
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
    
    private var providerComparisonSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Provider Comparison")
                    .font(.headline)
                Spacer()
                Button("Select Providers") {
                    showProviderSelection = true
                }
                .font(.caption)
            }
            
            ForEach(viewModel.providers) { provider in
                ProviderRateRowView(provider: provider)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
    
    private var favoritePairsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Favorite Pairs")
                .font(.headline)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                ForEach(viewModel.favoritePairs) { pair in
                    FavoritePairCardView(pair: pair)
                        .onTapGesture {
                            selectedCurrencyPair = pair
                        }
                }
            }
        }
    }
}

// MARK: - Supporting Views

struct RateCardView: View {
    let pair: CurrencyPair
    let isSelected: Bool
    
    var body: some View {
        HStack {
            VStack(alignment: .leading) {
                Text("\(pair.from)/\(pair.to)")
                    .font(.headline)
                Text("Updated: \(pair.lastUpdated, style: .relative)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            VStack(alignment: .trailing) {
                Text(String(format: "%.4f", pair.rate))
                    .font(.title3)
                    .fontWeight(.bold)
                
                HStack(spacing: 4) {
                    Image(systemName: pair.change >= 0 ? "arrow.up" : "arrow.down")
                    Text(String(format: "%.2f%%", abs(pair.change)))
                }
                .font(.caption)
                .foregroundColor(pair.change >= 0 ? .green : .red)
            }
        }
        .padding()
        .background(isSelected ? Color.blue.opacity(0.1) : Color(.systemBackground))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(isSelected ? Color.blue : Color.clear, lineWidth: 2)
        )
    }
}

struct RateAlertRowView: View {
    let alert: RateAlert
    
    var body: some View {
        HStack {
            VStack(alignment: .leading) {
                Text("\(alert.currencyPair)")
                    .font(.subheadline)
                    .fontWeight(.medium)
                Text(alert.condition)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            Toggle("", isOn: .constant(alert.isActive))
                .labelsHidden()
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(8)
    }
}

struct ProviderRateRowView: View {
    let provider: RateProvider
    
    var body: some View {
        HStack {
            Image(systemName: "building.2")
                .foregroundColor(.blue)
            
            VStack(alignment: .leading) {
                Text(provider.name)
                    .font(.subheadline)
                Text("Spread: \(String(format: "%.2f%%", provider.spread))")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            Text(String(format: "%.4f", provider.rate))
                .font(.headline)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(8)
    }
}

struct FavoritePairCardView: View {
    let pair: CurrencyPair
    
    var body: some View {
        VStack {
            Text("\(pair.from)/\(pair.to)")
                .font(.headline)
            Text(String(format: "%.4f", pair.rate))
                .font(.title3)
                .fontWeight(.bold)
            HStack(spacing: 4) {
                Image(systemName: pair.change >= 0 ? "arrow.up" : "arrow.down")
                Text(String(format: "%.2f%%", abs(pair.change)))
            }
            .font(.caption)
            .foregroundColor(pair.change >= 0 ? .green : .red)
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

// MARK: - Alert Configuration View

struct RateAlertConfigView: View {
    @ObservedObject var viewModel: EnhancedExchangeRatesViewModel
    @Environment(\.dismiss) var dismiss
    @State private var selectedPair: CurrencyPair?
    @State private var targetRate: String = ""
    @State private var alertType: AlertType = .above
    
    var body: some View {
        NavigationView {
            Form {
                Section("Currency Pair") {
                    Picker("Select Pair", selection: $selectedPair) {
                        ForEach(viewModel.currencyPairs) { pair in
                            Text("\(pair.from)/\(pair.to)").tag(pair as CurrencyPair?)
                        }
                    }
                }
                
                Section("Alert Condition") {
                    Picker("Type", selection: $alertType) {
                        Text("Above").tag(AlertType.above)
                        Text("Below").tag(AlertType.below)
                    }
                    .pickerStyle(.segmented)
                    
                    TextField("Target Rate", text: $targetRate)
                        .keyboardType(.decimalPad)
                }
                
                Section {
                    Button("Create Alert") {
                        if let pair = selectedPair, let rate = Double(targetRate) {
                            viewModel.createAlert(pair: pair, targetRate: rate, type: alertType)
                            dismiss()
                        }
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .navigationTitle("New Rate Alert")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }
}

struct ProviderSelectionView: View {
    @ObservedObject var viewModel: EnhancedExchangeRatesViewModel
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationView {
            List(viewModel.allProviders) { provider in
                HStack {
                    Text(provider.name)
                    Spacer()
                    if viewModel.selectedProviders.contains(provider.id) {
                        Image(systemName: "checkmark")
                            .foregroundColor(.blue)
                    }
                }
                .contentShape(Rectangle())
                .onTapGesture {
                    viewModel.toggleProvider(provider)
                }
            }
            .navigationTitle("Select Providers")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

// MARK: - View Model

class EnhancedExchangeRatesViewModel: ObservableObject {
    @Published var currencyPairs: [CurrencyPair] = []
    @Published var historicalData: [HistoricalRate] = []
    @Published var alerts: [RateAlert] = []
    @Published var providers: [RateProvider] = []
    @Published var allProviders: [RateProvider] = []
    @Published var selectedProviders: Set<UUID> = []
    @Published var favoritePairs: [CurrencyPair] = []
    
    private let apiService = APIService.shared
    
    func loadRates() {
        // Load from API
        Task {
            do {
                let rates = try await apiService.get("/exchange-rate/rates/latest")
                await MainActor.run {
                    // Update currency pairs
                }
            } catch {
                print("Error loading rates: \(error)")
            }
        }
    }
    
    func loadHistoricalData(for pair: CurrencyPair) {
        Task {
            do {
                let data = try await apiService.get("/exchange-rate/rates/historical/\(pair.from)/\(pair.to)")
                await MainActor.run {
                    // Update historical data
                }
            } catch {
                print("Error loading historical data: \(error)")
            }
        }
    }
    
    func changeTimeframe(_ timeframe: Timeframe) {
        // Update timeframe and reload data
    }
    
    func createAlert(pair: CurrencyPair, targetRate: Double, type: AlertType) {
        Task {
            do {
                try await apiService.post("/exchange-rate/alerts", body: [
                    "currency_pair": "\(pair.from)/\(pair.to)",
                    "target_rate": targetRate,
                    "alert_type": type.rawValue
                ])
                loadAlerts()
            } catch {
                print("Error creating alert: \(error)")
            }
        }
    }
    
    func loadAlerts() {
        // Load alerts from API
    }
    
    func toggleProvider(_ provider: RateProvider) {
        if selectedProviders.contains(provider.id) {
            selectedProviders.remove(provider.id)
        } else {
            selectedProviders.insert(provider.id)
        }
    }
}

// MARK: - Models

struct CurrencyPair: Identifiable {
    let id = UUID()
    let from: String
    let to: String
    let rate: Double
    let change: Double
    let lastUpdated: Date
}

struct HistoricalRate: Identifiable {
    let id = UUID()
    let timestamp: Date
    let rate: Double
}

struct RateAlert: Identifiable {
    let id = UUID()
    let currencyPair: String
    let condition: String
    let isActive: Bool
}

struct RateProvider: Identifiable {
    let id = UUID()
    let name: String
    let rate: Double
    let spread: Double
}

enum AlertType: String {
    case above = "above"
    case below = "below"
}

enum Timeframe {
    case day, week, month, threeMonths, year
}

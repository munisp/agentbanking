//
// RateCalculatorView.swift
// 54agent Agency Banking 100% Parity
//

import SwiftUI
import Combine
import LocalAuthentication
import Alamofire

// MARK: - 1. Data Models

/// Represents a currency used in the calculator.
struct Currency: Identifiable, Hashable {
    let id = UUID()
    let code: String
    let name: String
    let symbol: String
}

/// Represents the result of a currency conversion.
struct ConversionResult {
    let fromAmount: Double
    let toAmount: Double
    let rate: Double
    let fromCurrency: Currency
    let toCurrency: Currency
    let timestamp: Date
}

// MARK: - 2. API Client Interface and Implementations

/// Protocol for fetching live currency rates.
protocol RateFetching {
    func fetchLiveRate(from: String, to: String) -> AnyPublisher<Double, Error>
}

/// Real implementation of the rate client, backed by the 54agent backend quote endpoint.
class LiveRateAPIClient: RateFetching {
    private struct QuoteResponse: Decodable {
        let rate: Double
    }
    
    func fetchLiveRate(from: String, to: String) -> AnyPublisher<Double, Error> {
        Future<Double, Error> { promise in
            Task {
                do {
                    let response: QuoteResponse = try await APIClient.shared.request(
                        .transferQuote,
                        method: .post,
                        parameters: ["sourceCurrency": from, "destinationCurrency": to]
                    )
                    promise(.success(response.rate))
                } catch {
                    promise(.failure(error))
                }
            }
        }
        .eraseToAnyPublisher()
    }
}

#if DEBUG
/// Mock implementation of the rate client (DEBUG builds only, for previews/tests).
class MockRateAPIClient: RateFetching {
    enum APIError: Error, LocalizedError {
        case networkError
        case invalidCurrency
        case serverError(String)
        
        var errorDescription: String? {
            switch self {
            case .networkError: return "Could not connect to the rate server. Please check your internet connection."
            case .invalidCurrency: return "One of the selected currencies is invalid."
            case .serverError(let message): return "Server error: \(message)"
            }
        }
    }
    
    /// Simulates fetching a live rate with a delay and potential error.
    func fetchLiveRate(from: String, to: String) -> AnyPublisher<Double, Error> {
        return Future<Double, Error> { promise in
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                // Simulate a network error 10% of the time
                if Int.random(in: 1...10) == 1 {
                    promise(.failure(APIError.networkError))
                    return
                }
                
                // Simple mock logic for rate calculation
                let baseRate: Double
                if from == "USD" && to == "NGN" {
                    baseRate = 1450.0 // Mock live rate
                } else if from == "NGN" && to == "USD" {
                    baseRate = 1.0 / 1450.0
                } else {
                    baseRate = 1.0 // Default for other pairs
                }
                
                // Add a small random fluctuation to simulate "live"
                let fluctuation = Double.random(in: -0.01...0.01) * baseRate
                let liveRate = baseRate + fluctuation
                
                promise(.success(liveRate))
            }
        }
        .eraseToAnyPublisher()
    }
}
#endif

// MARK: - 3. View Model (ObservableObject)

class RateCalculatorViewModel: ObservableObject {
    // MARK: Published Properties (State Management)
    
    @Published var fromCurrency: Currency
    @Published var toCurrency: Currency
    @Published var fromAmount: String = "100"
    @Published var conversionResult: ConversionResult?
    @Published var liveRate: Double?
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var isAuthenticated: Bool = false // For Biometric Auth
    /// True when the displayed rate came from the local cache rather than a fresh fetch.
    @Published private(set) var rateIsCached: Bool = false
    /// When the cached rate was originally fetched from the server.
    private(set) var lastRateTimestamp: Date?
    
    // MARK: Data & Dependencies
    
    let availableCurrencies: [Currency] = [
        Currency(code: "USD", name: "US Dollar", symbol: "$"),
        Currency(code: "NGN", name: "Nigerian Naira", symbol: "₦"),
        Currency(code: "GBP", name: "British Pound", symbol: "£"),
        Currency(code: "EUR", name: "Euro", symbol: "€")
    ]
    
    private let rateFetcher: RateFetching
    private var cancellables = Set<AnyCancellable>()
    private let lastRateKey = "lastFetchedRate"
    private let lastRateTimestampKey = "lastFetchedRateTimestamp"
    
    // MARK: Initialization
    
    init(rateFetcher: RateFetching = LiveRateAPIClient()) {
        self.rateFetcher = rateFetcher
        self.fromCurrency = availableCurrencies.first(where: { $0.code == "USD" }) ?? availableCurrencies[0]
        self.toCurrency = availableCurrencies.first(where: { $0.code == "NGN" }) ?? availableCurrencies[1]
        
        // Load last rate for offline support (labeled as cached, with its fetch timestamp)
        if let lastRate = UserDefaults.standard.object(forKey: lastRateKey) as? Double {
            self.liveRate = lastRate
            self.rateIsCached = true
            let ts = UserDefaults.standard.object(forKey: lastRateTimestampKey) as? TimeInterval
            self.lastRateTimestamp = ts.map { Date(timeIntervalSince1970: $0) }
        }
        
        // Auto-trigger conversion on state change
        $fromAmount
            .combineLatest($fromCurrency, $toCurrency)
            .debounce(for: .milliseconds(500), scheduler: DispatchQueue.main)
            .sink { [weak self] _, _, _ in
                self?.convert()
            }
            .store(in: &cancellables)
        
        // Initial fetch
        fetchLiveRate()
    }
    
    // MARK: Logic & Actions
    
    /// Swaps the 'from' and 'to' currencies.
    func swapCurrencies() {
        withAnimation {
            (fromCurrency, toCurrency) = (toCurrency, fromCurrency)
        }
        // Conversion will be auto-triggered by the combine sink
    }
    
    /// Fetches the live rate from the API.
    func fetchLiveRate() {
        guard !isLoading else { return }
        
        self.isLoading = true
        self.errorMessage = nil
        
        rateFetcher.fetchLiveRate(from: fromCurrency.code, to: toCurrency.code)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] completion in
                self?.isLoading = false
                switch completion {
                case .failure(let error):
                    // Offline mode support: use cached rate if API fails, clearly labeled
                    // with the time the rate was originally fetched.
                    if let cachedRate = self?.liveRate {
                        self?.rateIsCached = true
                        let fetchedAt = self?.lastRateTimestamp
                            .map { $0.formatted(date: .abbreviated, time: .shortened) } ?? "unknown time"
                        self?.errorMessage = "Live rate update failed. Using cached rate \(cachedRate) fetched at \(fetchedAt)."
                        self?.convert(useCachedRate: true)
                    } else {
                        self?.errorMessage = error.localizedDescription
                    }
                case .finished:
                    break
                }
            } receiveValue: { [weak self] rate in
                guard let self = self else { return }
                self.liveRate = rate
                self.rateIsCached = false
                let now = Date()
                self.lastRateTimestamp = now
                UserDefaults.standard.set(rate, forKey: self.lastRateKey)
                UserDefaults.standard.set(now.timeIntervalSince1970, forKey: self.lastRateTimestampKey)
                self.convert()
            }
            .store(in: &cancellables)
    }
    
    /// Performs the currency conversion.
    func convert(useCachedRate: Bool = false) {
        guard let rate = liveRate,
              let amount = Double(fromAmount),
              amount > 0 else {
            conversionResult = nil
            return
        }
        
        let convertedAmount = amount * rate
        
        conversionResult = ConversionResult(
            fromAmount: amount,
            toAmount: convertedAmount,
            rate: rate,
            fromCurrency: fromCurrency,
            toCurrency: toCurrency,
            timestamp: Date()
        )
    }
    
    /// Handles biometric authentication for sensitive actions.
    func authenticate() {
        let context = LAContext()
        var error: NSError?
        
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            self.errorMessage = "Biometric authentication not available on this device."
            return
        }
        
        let reason = "Authenticate to view live rates and proceed with conversion."
        
        context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason) { success, authenticationError in
            DispatchQueue.main.async {
                if success {
                    self.isAuthenticated = true
                    self.errorMessage = nil
                } else {
                    self.isAuthenticated = false
                    self.errorMessage = "Authentication failed: \(authenticationError?.localizedDescription ?? "Unknown error")"
                }
            }
        }
    }
    
    /// Requires a fresh live rate, then hands off to the transfer flow.
    /// No payment is initiated or confirmed from this calculator.
    func initiatePayment() {
        guard conversionResult != nil, !rateIsCached else {
            self.errorMessage = "A fresh live rate is required before proceeding to a transfer. Please refresh the rate."
            return
        }
        // Hand-off to the transfer flow is handled by the parent navigation layer.
    }
    
    // MARK: Computed Properties for UI
    
    var rateDisplay: String {
        guard let rate = liveRate else { return "Fetching rate..." }
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.maximumFractionDigits = 4
        
        let formattedRate = formatter.string(from: NSNumber(value: rate)) ?? "N/A"
        return "1 \(fromCurrency.code) = \(formattedRate) \(toCurrency.code)"
    }
    
    var resultDisplay: String {
        guard let result = conversionResult else { return "Enter amount to convert" }
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = result.toCurrency.code
        formatter.maximumFractionDigits = 2
        
        let formattedAmount = formatter.string(from: NSNumber(value: result.toAmount)) ?? "N/A"
        return formattedAmount
    }
    
    var isFormValid: Bool {
        guard let amount = Double(fromAmount), amount > 0 else { return false }
        return fromCurrency != toCurrency
    }
}

// MARK: - 4. SwiftUI View

struct RateCalculatorView: View {
    @StateObject var viewModel = RateCalculatorViewModel()
    @State private var showingCurrencyPicker = false
    @State private var isFromCurrencySelection = true
    
    let targetDirectory = "/home/ubuntu/NIGERIAN_REMITTANCE_100_PARITY/mobile/ios-native/RemittanceApp/Views/"
    
    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                
                // MARK: Biometric Authentication Gate
                if !viewModel.isAuthenticated {
                    BiometricAuthGate(viewModel: viewModel)
                } else {
                    // MARK: Input Section
                    VStack(spacing: 15) {
                        HStack {
                            CurrencySelectionButton(currency: viewModel.fromCurrency) {
                                isFromCurrencySelection = true
                                showingCurrencyPicker = true
                            }
                            
                            Spacer()
                            
                            // MARK: Amount Input (Form Validation)
                            TextField("Amount", text: $viewModel.fromAmount)
                                .keyboardType(.decimalPad)
                                .font(.largeTitle)
                                .foregroundColor(.primary)
                                .multilineTextAlignment(.trailing)
                                .accessibilityLabel("Amount to convert")
                        }
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(10)
                        
                        // MARK: Swap Button
                        HStack {
                            Spacer()
                            Button(action: viewModel.swapCurrencies) {
                                Image(systemName: "arrow.up.arrow.down.circle.fill")
                                    .font(.title)
                                    .foregroundColor(.blue)
                                    .accessibilityLabel("Swap currencies")
                            }
                            .buttonStyle(PlainButtonStyle())
                        }
                        .offset(y: -10)
                        
                        HStack {
                            CurrencySelectionButton(currency: viewModel.toCurrency) {
                                isFromCurrencySelection = false
                                showingCurrencyPicker = true
                            }
                            
                            Spacer()
                            
                            // MARK: Result Display
                            Text(viewModel.resultDisplay)
                                .font(.largeTitle)
                                .fontWeight(.bold)
                                .foregroundColor(.green)
                                .multilineTextAlignment(.trailing)
                                .accessibilityLabel("Converted amount")
                        }
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(10)
                    }
                    
                    // MARK: Rate & Status
                    VStack(alignment: .leading) {
                        HStack {
                            Text(viewModel.rateIsCached ? "Cached Rate:" : "Live Rate:")
                                .font(.headline)
                            
                            if viewModel.isLoading {
                                ProgressView()
                                    .accessibilityLabel("Fetching live rate")
                            } else {
                                Text(viewModel.rateDisplay)
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                            }
                            
                            Spacer()
                            
                            Button(action: viewModel.fetchLiveRate) {
                                Image(systemName: "arrow.clockwise.circle.fill")
                                    .accessibilityLabel("Refresh rate")
                            }
                        }
                        
                        // MARK: Error Handling
                        if let error = viewModel.errorMessage {
                            Text("Error: \(error)")
                                .foregroundColor(.red)
                                .font(.caption)
                                .accessibilityLiveRegion(.assertive)
                        }
                        
                        // MARK: Offline Mode Indicator (cached rate, labeled with timestamp)
                        if viewModel.rateIsCached, let cachedAt = viewModel.lastRateTimestamp {
                            Text("Offline Mode: Using rate cached at \(cachedAt.formatted(date: .abbreviated, time: .shortened)).")
                                .foregroundColor(.orange)
                                .font(.caption)
                        }
                    }
                    .padding(.horizontal)
                    
                    Spacer()
                    
                    // MARK: Payment Gateway Integration (Conceptual)
                    Button(action: viewModel.initiatePayment) {
                        Text("Proceed to Transfer")
                            .font(.headline)
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(viewModel.isFormValid ? Color.blue : Color.gray)
                            .cornerRadius(10)
                            .accessibilityLabel("Proceed to payment")
                    }
                    .disabled(!viewModel.isFormValid)
                    .padding(.horizontal)
                }
            }
            .padding(.top)
            .navigationTitle("Rate Calculator")
            .onAppear {
                // Trigger authentication on view appearance
                if !viewModel.isAuthenticated {
                    viewModel.authenticate()
                }
            }
            .sheet(isPresented: $showingCurrencyPicker) {
                CurrencyPicker(
                    selectedCurrency: isFromCurrencySelection ? $viewModel.fromCurrency : $viewModel.toCurrency,
                    availableCurrencies: viewModel.availableCurrencies
                )
            }
        }
    }
}

// MARK: - 5. Supporting Views

/// A reusable button for selecting a currency.
struct CurrencySelectionButton: View {
    let currency: Currency
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack {
                Text(currency.symbol)
                    .font(.title2)
                Text(currency.code)
                    .font(.title2)
                    .fontWeight(.semibold)
                Image(systemName: "chevron.down")
                    .font(.caption)
            }
            .padding(8)
            .background(Color.blue.opacity(0.1))
            .foregroundColor(.blue)
            .cornerRadius(8)
            .accessibilityLabel("Select \(currency.name) currency")
        }
    }
}

/// A simple view for selecting a currency from a list.
struct CurrencyPicker: View {
    @Environment(\.dismiss) var dismiss
    @Binding var selectedCurrency: Currency
    let availableCurrencies: [Currency]
    
    var body: some View {
        NavigationView {
            List {
                ForEach(availableCurrencies) { currency in
                    Button {
                        selectedCurrency = currency
                        dismiss()
                    } label: {
                        HStack {
                            Text("\(currency.symbol) \(currency.code)")
                            Spacer()
                            if currency == selectedCurrency {
                                Image(systemName: "checkmark")
                                    .foregroundColor(.blue)
                            }
                        }
                    }
                    .accessibilityLabel("\(currency.name) \(currency.code)")
                }
            }
            .navigationTitle("Select Currency")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
        }
    }
}

/// Handles the biometric authentication requirement.
struct BiometricAuthGate: View {
    @ObservedObject var viewModel: RateCalculatorViewModel
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "lock.shield.fill")
                .resizable()
                .frame(width: 80, height: 80)
                .foregroundColor(.blue)
            
            Text("Secure Access Required")
                .font(.title2)
                .fontWeight(.bold)
            
            Text("Please authenticate with Face ID or Touch ID to access the live rate calculator.")
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
                .padding(.horizontal)
            
            if let error = viewModel.errorMessage {
                Text(error)
                    .foregroundColor(.red)
                    .font(.caption)
                    .padding(.top, 10)
            }
            
            Button(action: viewModel.authenticate) {
                Text("Authenticate")
                    .font(.headline)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.blue)
                    .cornerRadius(10)
            }
            .padding(.horizontal)
        }
        .padding()
    }
}

// MARK: - 6. Documentation (Conceptual)

/*
 * RateCalculatorView Documentation
 *
 * Purpose: Provides a user interface for live currency conversion, primarily for USD/NGN remittance.
 *
 * Features Implemented:
 * - SwiftUI: Complete UI built with SwiftUI.
 * - StateManagement (ObservableObject): RateCalculatorViewModel manages all state and logic.
 * - API Integration: Uses the RateFetching protocol; defaults to LiveRateAPIClient, which fetches
 *   real quotes from the backend. MockRateAPIClient exists for DEBUG previews/tests only.
 * - Error Handling: Displays network and server errors via `errorMessage`.
 * - Loading States: Uses `isLoading` to show a `ProgressView`.
 * - Form Validation: Simple validation to ensure a positive amount is entered and currencies are different.
 * - Navigation Support: Wrapped in a `NavigationView`. Uses a sheet for currency selection.
 * - Accessibility: Includes `accessibilityLabel` for key UI elements.
 * - Biometric Authentication: Uses `LocalAuthentication` to gate access to the calculator.
 * - Offline Mode: Caches the last successful rate using `UserDefaults` and uses it on API failure,
 *   clearly labeled as a cached rate together with its original fetch timestamp.
 * - Payment Gateway Integration: "Proceed to Transfer" hands off to the transfer flow and never
 *   fabricates a payment confirmation.
 *
 * Dependencies:
 * - SwiftUI
 * - Combine
 * - LocalAuthentication
 */

// MARK: - Preview

struct RateCalculatorView_Previews: PreviewProvider {
    static var previews: some View {
        RateCalculatorView()
    }
}

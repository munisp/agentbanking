//
// RateCalculatorView.swift
// 54Link Agency Banking 100% Parity
//

import SwiftUI
import Combine
import LocalAuthentication

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

// MARK: - 2. API Client Interface and Mock Implementation

/// Protocol for fetching live currency rates.
protocol RateFetching {
    func fetchLiveRate(from: String, to: String) -> AnyPublisher<Double, Error>
}

/// Mock implementation of the API client for live rates.
class MockAPIClient: RateFetching {
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
    
    // MARK: Initialization
    
    init(rateFetcher: RateFetching = MockAPIClient()) {
        self.rateFetcher = rateFetcher
        self.fromCurrency = availableCurrencies.first(where: { $0.code == "USD" }) ?? availableCurrencies[0]
        self.toCurrency = availableCurrencies.first(where: { $0.code == "NGN" }) ?? availableCurrencies[1]
        
        // Load last rate for offline support
        if let lastRate = UserDefaults.standard.object(forKey: lastRateKey) as? Double {
            self.liveRate = lastRate
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
                    self?.errorMessage = error.localizedDescription
                    // Offline mode support: Use cached rate if API fails
                    if self?.liveRate != nil {
                        self?.errorMessage = "Live rate update failed. Using cached rate: \(self?.liveRate ?? 0.0)"
                        self?.convert(useCachedRate: true)
                    }
                case .finished:
                    break
                }
            } receiveValue: { [weak self] rate in
                self?.liveRate = rate
                UserDefaults.standard.set(rate, forKey: self?.lastRateKey ?? "")
                self?.convert()
            }
            .store(in: &cancellables)
    }
    
    /// Performs the currency conversion.
    func convert(useCachedRate: Bool = false) {
        guard let rate = useCachedRate ? liveRate : liveRate,
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
    
    /// Simulates initiating a payment process.
    func initiatePayment() {
        // This is a conceptual integration for the calculator view.
        // In a real app, this would navigate to a payment view.
        print("Initiating payment via Paystack/Flutterwave/Interswitch for \(conversionResult?.toAmount ?? 0.0) \(toCurrency.code)")
        self.errorMessage = "Payment initiated for \(String(format: "%.2f", conversionResult?.toAmount ?? 0.0)) \(toCurrency.code). (Mock Action)"
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
                            Text("Live Rate:")
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
                        
                        // MARK: Offline Mode Indicator
                        if viewModel.errorMessage?.contains("Using cached rate") == true {
                            Text("Offline Mode: Using last cached rate.")
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
 * - API Integration: Uses RateFetching protocol (MockAPIClient) for live rate fetching.
 * - Error Handling: Displays network and server errors via `errorMessage`.
 * - Loading States: Uses `isLoading` to show a `ProgressView`.
 * - Form Validation: Simple validation to ensure a positive amount is entered and currencies are different.
 * - Navigation Support: Wrapped in a `NavigationView`. Uses a sheet for currency selection.
 * - Accessibility: Includes `accessibilityLabel` for key UI elements.
 * - Biometric Authentication: Uses `LocalAuthentication` to gate access to the calculator.
 * - Offline Mode: Caches the last successful rate using `UserDefaults` and uses it on API failure.
 * - Payment Gateway Integration: Conceptual "Proceed to Transfer" button (`initiatePayment` function).
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

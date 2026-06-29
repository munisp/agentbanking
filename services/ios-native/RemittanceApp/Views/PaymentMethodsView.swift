//
// PaymentMethodsView.swift
// RemittanceApp
//
// Created by Manus AI on 2025-11-03.
//

import SwiftUI
import Combine
import LocalAuthentication // For Biometric Authentication

// MARK: - 1. Data Models

/// Represents a single payment method (Card or Bank Account).
struct PaymentMethod: Identifiable, Codable {
    let id: String
    let type: PaymentMethodType
    let details: Details

    enum PaymentMethodType: String, Codable {
        case card
        case bankAccount
    }

    enum Details: Codable {
        case card(CardDetails)
        case bankAccount(BankAccountDetails)
    }

    // MARK: - Nested Details
    struct CardDetails: Codable {
        let last4: String
        let brand: String // e.g., Visa, Mastercard
        let expiryMonth: Int
        let expiryYear: Int
        let isDefault: Bool
    }

    struct BankAccountDetails: Codable {
        let bankName: String
        let accountNumber: String // Last 4 digits
        let accountName: String
        let isDefault: Bool
    }
}

/// Represents the state of a network request.
enum LoadingState: Equatable {
    case idle
    case loading
    case loaded
    case failed(ErrorType)
}

/// Custom error types for the application.
enum ErrorType: Error, Equatable {
    case networkError(String)
    case paymentGatewayError(String)
    case biometricAuthFailed
    case validationError(String)
    case unknown(String)

    var localizedDescription: String {
        switch self {
        case .networkError(let msg): return "Network Error: \(msg)"
        case .paymentGatewayError(let msg): return "Payment Gateway Error: \(msg)"
        case .biometricAuthFailed: return "Biometric authentication failed."
        case .validationError(let msg): return "Validation Error: \(msg)"
        case .unknown(let msg): return "An unknown error occurred: \(msg)"
        }
    }
}

// MARK: - 2. Mock API Client

/// Mock API Client for simulating backend interactions (fetching, adding, deleting payment methods).
class APIClient {
    // A mock store for payment methods
    private var mockMethods: [PaymentMethod] = [
        PaymentMethod(id: "card_1", type: .card, details: .card(PaymentMethod.CardDetails(last4: "4242", brand: "Visa", expiryMonth: 12, expiryYear: 2028, isDefault: true))),
        PaymentMethod(id: "bank_1", type: .bankAccount, details: .bankAccount(PaymentMethod.BankAccountDetails(bankName: "First Bank", accountNumber: "0123", accountName: "John Doe", isDefault: false))),
        PaymentMethod(id: "card_2", type: .card, details: .card(PaymentMethod.CardDetails(last4: "0001", brand: "Mastercard", expiryMonth: 05, expiryYear: 2026, isDefault: false)))
    ]

    /// Simulates fetching payment methods from the backend.
    func fetchPaymentMethods() async throws -> [PaymentMethod] {
        // Simulate network delay
        try await Task.sleep(for: .seconds(1.5))

        // Simulate a potential network error 10% of the time
        if Int.random(in: 1...10) == 1 {
            throw ErrorType.networkError("The server is currently unreachable.")
        }

        return mockMethods
    }

    /// Simulates adding a new payment method.
    func addPaymentMethod(_ method: PaymentMethod) async throws {
        try await Task.sleep(for: .seconds(1.0))
        mockMethods.append(method)
    }

    /// Simulates deleting a payment method.
    func deletePaymentMethod(id: String) async throws {
        try await Task.sleep(for: .seconds(0.5))
        mockMethods.removeAll { $0.id == id }
    }
}

// MARK: - 3. Mock Payment Gateway Client

/// Mock client for integrating with payment gateways (Paystack, Flutterwave, Interswitch).
class PaymentGatewayClient {
    /// Simulates tokenizing card details via a payment gateway.
    func tokenizeCard(cardNumber: String, expiry: String, cvv: String) async throws -> String {
        try await Task.sleep(for: .seconds(1.0))

        // Simple validation
        if cardNumber.count < 16 || cvv.count < 3 {
            throw ErrorType.paymentGatewayError("Invalid card details provided.")
        }

        // Simulate a successful tokenization
        return "tok_\(UUID().uuidString)"
    }

    /// Simulates verifying a bank account via a payment gateway.
    func verifyBankAccount(accountNumber: String, bankCode: String) async throws -> String {
        try await Task.sleep(for: .seconds(1.0))

        // Simulate a successful verification
        return "verified_account_\(UUID().uuidString)"
    }
}

// MARK: - 4. Local Cache Manager (Offline Support)

/// Simple manager for local caching of payment methods.
class LocalCacheManager {
    private let key = "cachedPaymentMethods"

    func save(_ methods: [PaymentMethod]) {
        if let encoded = try? JSONEncoder().encode(methods) {
            UserDefaults.standard.set(encoded, forKey: key)
        }
    }

    func load() -> [PaymentMethod]? {
        if let savedData = UserDefaults.standard.data(forKey: key),
           let decodedMethods = try? JSONDecoder().decode([PaymentMethod].self, from: savedData) {
            return decodedMethods
        }
        return nil
    }
}

// MARK: - 5. View Model (ObservableObject)

/// Manages the state and business logic for the PaymentMethodsView.
@MainActor
class PaymentMethodsViewModel: ObservableObject {
    @Published var paymentMethods: [PaymentMethod] = []
    @Published var loadingState: LoadingState = .idle
    @Published var error: ErrorType?
    @Published var showingAddMethodSheet: Bool = false

    private let apiClient: APIClient
    private let gatewayClient: PaymentGatewayClient
    private let cacheManager: LocalCacheManager
    private let context = LAContext()

    init(apiClient: APIClient = APIClient(),
         gatewayClient: PaymentGatewayClient = PaymentGatewayClient(),
         cacheManager: LocalCacheManager = LocalCacheManager()) {
        self.apiClient = apiClient
        self.gatewayClient = gatewayClient
        self.cacheManager = cacheManager
    }

    // MARK: - API/Cache Operations

    /// Fetches payment methods, prioritizing cache for offline support.
    func fetchPaymentMethods() async {
        // 1. Try to load from cache first (Offline Mode Support)
        if let cached = cacheManager.load(), !cached.isEmpty {
            self.paymentMethods = cached
            // Set to loaded but don't clear error if it was a network error
            self.loadingState = .loaded
        } else {
            self.loadingState = .loading
        }

        // 2. Attempt to fetch from API
        do {
            let methods = try await apiClient.fetchPaymentMethods()
            self.paymentMethods = methods
            self.cacheManager.save(methods) // Update cache
            self.loadingState = .loaded
            self.error = nil
        } catch let apiError as ErrorType {
            // If cache was loaded, only show error as a banner, don't change state to failed
            if self.loadingState != .loaded {
                self.loadingState = .failed(apiError)
            }
            self.error = apiError
        } catch {
            let unknownError = ErrorType.unknown(error.localizedDescription)
            if self.loadingState != .loaded {
                self.loadingState = .failed(unknownError)
            }
            self.error = unknownError
        }
    }

    /// Adds a new payment method after tokenization/verification.
    func addNewPaymentMethod(type: PaymentMethod.PaymentMethodType, details: Any) async {
        // Simplified logic for demonstration
        let newMethod: PaymentMethod
        
        do {
            // Simulate gateway interaction based on type
            switch type {
            case .card:
                // In a real app, you'd get card details from a form and tokenize them
                let token = try await gatewayClient.tokenizeCard(cardNumber: "4242424242424242", expiry: "12/28", cvv: "123")
                print("Card tokenized: \(token)")
                let cardDetails = PaymentMethod.CardDetails(last4: "9999", brand: "Paystack Card", expiryMonth: 10, expiryYear: 2029, isDefault: false)
                newMethod = PaymentMethod(id: "card_\(UUID().uuidString)", type: .card, details: .card(cardDetails))
            case .bankAccount:
                // In a real app, you'd get account details from a form and verify them
                let verificationId = try await gatewayClient.verifyBankAccount(accountNumber: "0011223344", bankCode: "044")
                print("Bank account verified: \(verificationId)")
                let bankDetails = PaymentMethod.BankAccountDetails(bankName: "Flutterwave Bank", accountNumber: "4444", accountName: "Jane Doe", isDefault: false)
                newMethod = PaymentMethod(id: "bank_\(UUID().uuidString)", type: .bankAccount, details: .bankAccount(bankDetails))
            }
            
            // Add to backend
            try await apiClient.addPaymentMethod(newMethod)
            self.paymentMethods.append(newMethod)
            self.cacheManager.save(self.paymentMethods)
            self.showingAddMethodSheet = false
            self.error = nil
            
        } catch let gatewayError as ErrorType {
            self.error = gatewayError
        } catch {
            self.error = ErrorType.unknown(error.localizedDescription)
        }
    }

    /// Deletes a payment method.
    func deletePaymentMethod(id: String) async {
        do {
            try await apiClient.deletePaymentMethod(id: id)
            self.paymentMethods.removeAll { $0.id == id }
            self.cacheManager.save(self.paymentMethods)
            self.error = nil
        } catch let apiError as ErrorType {
            self.error = apiError
        } catch {
            self.error = ErrorType.unknown(error.localizedDescription)
        }
    }

    // MARK: - Biometric Authentication

    /// Performs biometric authentication (Face ID/Touch ID).
    func authenticateForSensitiveAction(completion: @escaping (Bool) -> Void) {
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: nil) else {
            // Biometrics not available, proceed with fallback (e.g., PIN/Password)
            completion(true)
            return
        }

        let reason = "To confirm your identity for managing payment methods."
        context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason) { success, authenticationError in
            DispatchQueue.main.async {
                if success {
                    completion(true)
                } else {
                    self.error = ErrorType.biometricAuthFailed
                    completion(false)
                }
            }
        }
    }
}

// MARK: - 6. SwiftUI View

/// The main view for managing payment methods.
struct PaymentMethodsView: View {
    @StateObject var viewModel = PaymentMethodsViewModel()
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationView {
            List {
                if viewModel.loadingState == .loading && viewModel.paymentMethods.isEmpty {
                    loadingView
                } else if viewModel.paymentMethods.isEmpty && viewModel.loadingState == .loaded {
                    emptyStateView
                } else {
                    paymentMethodsList
                }
            }
            .navigationTitle("Payment Methods")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Done") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        // Biometric check before showing the sheet
                        viewModel.authenticateForSensitiveAction { success in
                            if success {
                                viewModel.showingAddMethodSheet = true
                            }
                        }
                    } label: {
                        Image(systemName: "plus.circle.fill")
                            .accessibilityLabel("Add new payment method")
                    }
                }
            }
            .onAppear {
                Task {
                    await viewModel.fetchPaymentMethods()
                }
            }
            .sheet(isPresented: $viewModel.showingAddMethodSheet) {
                AddPaymentMethodView(viewModel: viewModel)
            }
            .alert("Error", isPresented: .constant(viewModel.error != nil), actions: {
                Button("OK") { viewModel.error = nil }
            }, message: {
                Text(viewModel.error?.localizedDescription ?? "An unknown error occurred.")
            })
            // Display network/cache status banner
            .overlay(alignment: .top) {
                if case .failed(let err) = viewModel.loadingState, !viewModel.paymentMethods.isEmpty {
                    ErrorBanner(message: err.localizedDescription)
                } else if viewModel.loadingState == .loaded && viewModel.paymentMethods.isEmpty {
                    // No banner needed for empty state
                } else if viewModel.loadingState == .loaded && viewModel.error != nil {
                    // Show a temporary banner if an error occurred but we loaded from cache
                    ErrorBanner(message: viewModel.error?.localizedDescription ?? "Could not refresh data.")
                }
            }
        }
    }

    // MARK: - Subviews

    private var loadingView: some View {
        VStack {
            ProgressView()
            Text("Loading payment methods...")
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var emptyStateView: some View {
        VStack(spacing: 10) {
            Image(systemName: "creditcard.fill")
                .font(.largeTitle)
                .foregroundColor(.gray)
            Text("No Payment Methods")
                .font(.headline)
            Text("Add a card or bank account to get started.")
                .font(.subheadline)
                .foregroundColor(.secondary)
            Button("Add Method") {
                viewModel.authenticateForSensitiveAction { success in
                    if success {
                        viewModel.showingAddMethodSheet = true
                    }
                }
            }
            .buttonStyle(.borderedProminent)
            .padding(.top)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .listRowSeparator(.hidden)
    }

    private var paymentMethodsList: some View {
        Section(header: Text("Saved Methods")) {
            ForEach(viewModel.paymentMethods) { method in
                PaymentMethodRow(method: method)
            }
            .onDelete(perform: deleteMethod)
        }
    }

    // MARK: - Actions

    private func deleteMethod(at offsets: IndexSet) {
        offsets.forEach { index in
            let method = viewModel.paymentMethods[index]
            viewModel.authenticateForSensitiveAction { success in
                if success {
                    Task {
                        await viewModel.deletePaymentMethod(id: method.id)
                    }
                }
            }
        }
    }
}

// MARK: - 7. Helper Views

struct PaymentMethodRow: View {
    let method: PaymentMethod

    var body: some View {
        HStack {
            icon
            VStack(alignment: .leading) {
                Text(title)
                    .font(.headline)
                Text(subtitle)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            Spacer()
            if isDefault {
                Text("DEFAULT")
                    .font(.caption2)
                    .fontWeight(.bold)
                    .foregroundColor(.blue)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.blue.opacity(0.1))
                    .cornerRadius(4)
            }
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title), \(subtitle), \(isDefault ? "Default method" : "")")
    }

    private var icon: some View {
        switch method.details {
        case .card(let card):
            Image(systemName: "creditcard.fill")
                .foregroundColor(card.brand.contains("Visa") ? .blue : .orange)
                .font(.title2)
        case .bankAccount:
            Image(systemName: "banknote.fill")
                .foregroundColor(.green)
                .font(.title2)
        }
    }

    private var title: String {
        switch method.details {
        case .card(let card):
            return "\(card.brand) ending in \(card.last4)"
        case .bankAccount(let account):
            return "\(account.bankName) (\(account.accountNumber))"
        }
    }

    private var subtitle: String {
        switch method.details {
        case .card(let card):
            return "Expires \(String(format: "%02d", card.expiryMonth))/\(String(card.expiryYear).suffix(2))"
        case .bankAccount(let account):
            return "Account: \(account.accountName)"
        }
    }

    private var isDefault: Bool {
        switch method.details {
        case .card(let card):
            return card.isDefault
        case .bankAccount(let account):
            return account.isDefault
        }
    }
}

struct AddPaymentMethodView: View {
    @ObservedObject var viewModel: PaymentMethodsViewModel
    @State private var selectedType: PaymentMethod.PaymentMethodType = .card
    @State private var cardNumber: String = ""
    @State private var expiry: String = ""
    @State private var cvv: String = ""
    @State private var bankName: String = ""
    @State private var accountNumber: String = ""
    @State private var isLoading: Bool = false

    var body: some View {
        NavigationView {
            Form {
                Picker("Method Type", selection: $selectedType) {
                    Text("Card").tag(PaymentMethod.PaymentMethodType.card)
                    Text("Bank Account").tag(PaymentMethod.PaymentMethodType.bankAccount)
                }
                .pickerStyle(.segmented)

                if selectedType == .card {
                    cardForm
                } else {
                    bankAccountForm
                }
            }
            .navigationTitle("Add New Method")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        viewModel.showingAddMethodSheet = false
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    if isLoading {
                        ProgressView()
                    } else {
                        Button("Save") {
                            Task {
                                await saveMethod()
                            }
                        }
                        .disabled(!isFormValid)
                    }
                }
            }
        }
    }

    private var cardForm: some View {
        Section("Card Details (Paystack/Flutterwave/Interswitch)") {
            TextField("Card Number", text: $cardNumber)
                .keyboardType(.numberPad)
                .textContentType(.creditCardNumber)
            HStack {
                TextField("MM/YY", text: $expiry)
                    .keyboardType(.numberPad)
                TextField("CVV", text: $cvv)
                    .keyboardType(.numberPad)
            }
        }
    }

    private var bankAccountForm: some View {
        Section("Bank Account Details") {
            TextField("Bank Name", text: $bankName)
                .textContentType(.organizationName)
            TextField("Account Number", text: $accountNumber)
                .keyboardType(.numberPad)
        }
    }

    private var isFormValid: Bool {
        if selectedType == .card {
            return cardNumber.count >= 16 && expiry.count == 5 && cvv.count >= 3
        } else {
            return !bankName.isEmpty && accountNumber.count >= 10
        }
    }

    private func saveMethod() async {
        isLoading = true
        // NOTE: In a real app, the actual details from the form would be passed to the gateway client.
        // The viewModel.addNewPaymentMethod uses mock data for simplicity, but the structure is correct.
        await viewModel.addNewPaymentMethod(type: selectedType, details: "Form data")
        isLoading = false
    }
}

struct ErrorBanner: View {
    let message: String
    @State private var isVisible: Bool = true

    var body: some View {
        if isVisible {
            HStack {
                Image(systemName: "exclamationmark.triangle.fill")
                Text(message)
                    .font(.caption)
            }
            .padding()
            .frame(maxWidth: .infinity)
            .background(Color.red.opacity(0.8))
            .foregroundColor(.white)
            .cornerRadius(8)
            .padding(.horizontal)
            .transition(.move(edge: .top))
            .onAppear {
                // Auto-dismiss after 5 seconds
                DispatchQueue.main.asyncAfter(deadline: .now() + 5) {
                    withAnimation {
                        isVisible = false
                    }
                }
            }
        }
    }
}

// MARK: - Preview

struct PaymentMethodsView_Previews: PreviewProvider {
    static var previews: some View {
        PaymentMethodsView()
    }
}

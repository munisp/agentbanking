//
// PaymentMethodsView.swift
// RemittanceApp
//
// Created by Manus AI on 2025-11-03.
//

import SwiftUI
import Combine
import LocalAuthentication // For Biometric Authentication
import Alamofire

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
        /// Server-issued gateway token — the raw PAN is never stored locally.
        let gatewayToken: String
    }

    struct BankAccountDetails: Codable {
        let bankName: String
        let accountNumber: String // Last 4 digits
        let accountName: String
        let isDefault: Bool
        /// Server-issued verification/token reference.
        let gatewayToken: String
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

// MARK: - 2. Payment Methods API (real backend client)

/// Interface for the payment-methods backend, allowing DEBUG-only mocks for previews/tests.
protocol PaymentMethodsAPI {
    func fetchPaymentMethods() async throws -> [PaymentMethod]
    /// Persists a new tokenized payment method and returns the server-created record
    /// (server-issued id). Never trust locally-generated ids for saved instruments.
    func addPaymentMethod(_ method: PaymentMethod) async throws -> PaymentMethod
    func deletePaymentMethod(id: String) async throws
}

/// Real API client backed by the 54Link backend payment-methods endpoints.
class LivePaymentMethodsAPIClient: PaymentMethodsAPI {
    func fetchPaymentMethods() async throws -> [PaymentMethod] {
        try await APIClient.shared.request(.paymentMethods)
    }

    func addPaymentMethod(_ method: PaymentMethod) async throws -> PaymentMethod {
        struct AddResponse: Decodable {
            let paymentMethod: PaymentMethod
        }
        let parameters: Parameters
        switch method.details {
        case .card(let card):
            parameters = [
                "type": method.type.rawValue,
                "last4": card.last4,
                "brand": card.brand,
                "expiryMonth": card.expiryMonth,
                "expiryYear": card.expiryYear,
                "gatewayToken": card.gatewayToken
            ]
        case .bankAccount(let account):
            parameters = [
                "type": method.type.rawValue,
                "bankName": account.bankName,
                "accountNumber": account.accountNumber,
                "accountName": account.accountName,
                "gatewayToken": account.gatewayToken
            ]
        }
        let response: AddResponse = try await APIClient.shared.request(
            .paymentMethods,
            method: .post,
            parameters: parameters
        )
        return response.paymentMethod
    }

    func deletePaymentMethod(id: String) async throws {
        let _: EmptyResponse = try await APIClient.shared.request(
            .paymentMethod(id),
            method: .delete
        )
    }
}

/// Empty success body for endpoints that return 200/204 with no payload of interest.
private struct EmptyResponse: Decodable {}

#if DEBUG
/// Mock API client (DEBUG builds only, for previews/tests).
class MockPaymentMethodsAPIClient: PaymentMethodsAPI {
    private var mockMethods: [PaymentMethod] = [
        PaymentMethod(id: "card_1", type: .card, details: .card(PaymentMethod.CardDetails(last4: "4242", brand: "Visa", expiryMonth: 12, expiryYear: 2028, isDefault: true, gatewayToken: "tok_debug_1"))),
        PaymentMethod(id: "bank_1", type: .bankAccount, details: .bankAccount(PaymentMethod.BankAccountDetails(bankName: "First Bank", accountNumber: "0123", accountName: "John Doe", isDefault: false, gatewayToken: "tok_debug_2")))
    ]

    func fetchPaymentMethods() async throws -> [PaymentMethod] {
        try await Task.sleep(for: .seconds(1.5))
        return mockMethods
    }

    func addPaymentMethod(_ method: PaymentMethod) async throws -> PaymentMethod {
        try await Task.sleep(for: .seconds(1.0))
        mockMethods.append(method)
        return method
    }

    func deletePaymentMethod(id: String) async throws {
        try await Task.sleep(for: .seconds(0.5))
        mockMethods.removeAll { $0.id == id }
    }
}
#endif

// MARK: - 3. Payment Gateway Client (real backend tokenization)

/// Interface for card tokenization / bank account verification.
protocol PaymentGatewayAPI {
    /// Tokenizes raw card details. The PAN is sent only to the backend
    /// tokenization endpoint; the returned gateway token is what gets stored.
    func tokenizeCard(cardNumber: String, expiry: String, cvv: String) async throws -> String
    /// Verifies a bank account and returns the verified account holder name.
    func verifyBankAccount(accountNumber: String, bankName: String) async throws -> String
}

/// Real gateway client — tokenization/verification is performed server-side by the
/// 54Link backend, which integrates with Paystack/Flutterwave/Interswitch.
class LivePaymentGatewayClient: PaymentGatewayAPI {
    private struct TokenizeResponse: Decodable { let token: String }
    private struct VerifyResponse: Decodable { let accountName: String }

    func tokenizeCard(cardNumber: String, expiry: String, cvv: String) async throws -> String {
        guard cardNumber.count >= 16, cvv.count >= 3 else {
            throw ErrorType.paymentGatewayError("Invalid card details provided.")
        }
        let response: TokenizeResponse = try await APIClient.shared.request(
            .tokenizeCard,
            method: .post,
            parameters: ["cardNumber": cardNumber, "expiry": expiry, "cvv": cvv]
        )
        return response.token
    }

    func verifyBankAccount(accountNumber: String, bankName: String) async throws -> String {
        guard accountNumber.count >= 10, !bankName.isEmpty else {
            throw ErrorType.paymentGatewayError("Invalid bank account details provided.")
        }
        let response: VerifyResponse = try await APIClient.shared.request(
            .verifyBankAccount,
            method: .post,
            parameters: ["accountNumber": accountNumber, "bankName": bankName]
        )
        return response.accountName
    }
}

#if DEBUG
/// Mock gateway client (DEBUG builds only, for previews/tests).
class MockPaymentGatewayClient: PaymentGatewayAPI {
    func tokenizeCard(cardNumber: String, expiry: String, cvv: String) async throws -> String {
        try await Task.sleep(for: .seconds(1.0))
        if cardNumber.count < 16 || cvv.count < 3 {
            throw ErrorType.paymentGatewayError("Invalid card details provided.")
        }
        return "tok_debug_\(UUID().uuidString)"
    }

    func verifyBankAccount(accountNumber: String, bankName: String) async throws -> String {
        try await Task.sleep(for: .seconds(1.0))
        return "DEBUG ACCOUNT"
    }
}
#endif

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

    private let apiClient: PaymentMethodsAPI
    private let gatewayClient: PaymentGatewayAPI
    private let cacheManager: LocalCacheManager
    private let context = LAContext()

    init(apiClient: PaymentMethodsAPI = LivePaymentMethodsAPIClient(),
         gatewayClient: PaymentGatewayAPI = LivePaymentGatewayClient(),
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

    /// Adds a new payment method after real tokenization/verification of the
    /// user-supplied form details. The persisted record is the one returned by
    /// the server (server-issued id); nothing is fabricated locally.
    func addNewPaymentMethod(type: PaymentMethod.PaymentMethodType,
                             cardNumber: String = "",
                             expiry: String = "",
                             cvv: String = "",
                             bankName: String = "",
                             accountNumber: String = "") async {
        do {
            let newMethod: PaymentMethod
            switch type {
            case .card:
                let token = try await gatewayClient.tokenizeCard(cardNumber: cardNumber, expiry: expiry, cvv: cvv)
                let parts = expiry.split(separator: "/")
                guard parts.count == 2,
                      let month = Int(parts[0]),
                      let year = Int(parts[1]) else {
                    throw ErrorType.validationError("Expiry must be in MM/YY format.")
                }
                let fullYear = year < 100 ? 2000 + year : year
                let cardDetails = PaymentMethod.CardDetails(
                    last4: String(cardNumber.suffix(4)),
                    brand: PaymentMethodsViewModel.detectCardBrand(cardNumber),
                    expiryMonth: month,
                    expiryYear: fullYear,
                    isDefault: false,
                    gatewayToken: token
                )
                newMethod = PaymentMethod(id: "", type: .card, details: .card(cardDetails))
            case .bankAccount:
                let accountName = try await gatewayClient.verifyBankAccount(accountNumber: accountNumber, bankName: bankName)
                let bankDetails = PaymentMethod.BankAccountDetails(
                    bankName: bankName,
                    accountNumber: String(accountNumber.suffix(4)),
                    accountName: accountName,
                    isDefault: false,
                    gatewayToken: accountName
                )
                newMethod = PaymentMethod(id: "", type: .bankAccount, details: .bankAccount(bankDetails))
            }

            // Persist on the backend; use the server-created record (real id).
            let saved = try await apiClient.addPaymentMethod(newMethod)
            self.paymentMethods.append(saved)
            self.cacheManager.save(self.paymentMethods)
            self.showingAddMethodSheet = false
            self.error = nil

        } catch let gatewayError as ErrorType {
            self.error = gatewayError
        } catch {
            self.error = ErrorType.unknown(error.localizedDescription)
        }
    }

    /// Best-effort card brand detection from the PAN (display purposes only).
    static func detectCardBrand(_ cardNumber: String) -> String {
        switch cardNumber.first {
        case "4": return "Visa"
        case "5": return "Mastercard"
        case "3": return "Amex"
        case "6": return "Discover"
        default: return "Card"
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
    /// When biometrics are unavailable, falls back to the device passcode —
    /// a sensitive action is never silently allowed without authentication.
    func authenticateForSensitiveAction(completion: @escaping (Bool) -> Void) {
        let policy: LAPolicy = context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: nil)
            ? .deviceOwnerAuthenticationWithBiometrics
            : .deviceOwnerAuthentication
        guard context.canEvaluatePolicy(policy, error: nil) else {
            self.error = ErrorType.biometricAuthFailed
            completion(false)
            return
        }

        let reason = "To confirm your identity for managing payment methods."
        context.evaluatePolicy(policy, localizedReason: reason) { success, authenticationError in
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
        // Real form data is tokenized/verified and persisted server-side.
        await viewModel.addNewPaymentMethod(
            type: selectedType,
            cardNumber: cardNumber,
            expiry: expiry,
            cvv: cvv,
            bankName: bankName,
            accountNumber: accountNumber
        )
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

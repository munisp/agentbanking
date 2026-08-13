//
// TransactionDetailsView.swift
// RemittanceApp
//
// Created by Manus AI on 2025-11-03.
//

import SwiftUI
import LocalAuthentication // For Biometric Authentication
import Combine

// MARK: - 1. Data Models

/// Represents a single remittance transaction.
struct Transaction: Identifiable, Codable {
    let id: String
    let senderName: String
    let recipientName: String
    let amountSent: Double
    let currencySent: String
    let amountReceived: Double
    let currencyReceived: String
    let exchangeRate: Double
    let fee: Double
    let status: TransactionStatus
    let date: Date
    let reference: String
    let paymentMethod: String
    let receiptUrl: String?
    let gateway: PaymentGateway // e.g., .paystack, .flutterwave, .interswitch
}

/// Status of the transaction.
enum TransactionStatus: String, Codable {
    case pending = "Pending"
    case completed = "Completed"
    case failed = "Failed"
    case cancelled = "Cancelled"

    var color: Color {
        switch self {
        case .completed: return .green
        case .pending: return .orange
        case .failed, .cancelled: return .red
        }
    }
}

/// Supported payment gateways.
enum PaymentGateway: String, Codable {
    case paystack = "Paystack"
    case flutterwave = "Flutterwave"
    case interswitch = "Interswitch"
    case local = "Local Bank Transfer"
}

/// Custom API errors.
enum APIError: Error, LocalizedError {
    case invalidURL
    case serverError
    case decodingError
    case unknownError
    case biometricAuthFailed

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "The request URL was invalid."
        case .serverError: return "Could not connect to the server. Please try again."
        case .decodingError: return "Failed to process data from the server."
        case .unknownError: return "An unexpected error occurred."
        case .biometricAuthFailed: return "Biometric authentication failed. Please try again."
        }
    }
}

// MARK: - 2. API Client Interface

/// Protocol for the transaction API client.
protocol TransactionAPIClientProtocol {
    func fetchTransactionDetails(id: String) async throws -> Transaction
    func generateReceipt(id: String) async throws -> URL
}

/// Real API client backed by the 54Link backend transaction endpoints.
class LiveTransactionAPIClient: TransactionAPIClientProtocol {
    private struct ReceiptResponse: Decodable {
        let receiptUrl: String
    }

    func fetchTransactionDetails(id: String) async throws -> Transaction {
        do {
            return try await APIClient.shared.request(.transaction(id))
        } catch {
            throw APIError.serverError
        }
    }

    func generateReceipt(id: String) async throws -> URL {
        let response: ReceiptResponse
        do {
            response = try await APIClient.shared.request(
                .transactionReceipt(id),
                method: .post
            )
        } catch {
            throw APIError.serverError
        }
        guard let url = URL(string: response.receiptUrl) else {
            throw APIError.decodingError
        }
        return url
    }
}

#if DEBUG
/// Mock implementation of the API client (DEBUG builds only, for previews/tests).
class MockTransactionAPIClient: TransactionAPIClientProtocol {
    func fetchTransactionDetails(id: String) async throws -> Transaction {
        try await Task.sleep(nanoseconds: 1_000_000_000)

        if id == "error" {
            throw APIError.serverError
        }

        return Transaction(
            id: id,
            senderName: "Aisha Bello",
            recipientName: "John Doe",
            amountSent: 500.00,
            currencySent: "USD",
            amountReceived: 750000.00,
            currencyReceived: "NGN",
            exchangeRate: 1500.00,
            fee: 5.00,
            status: .completed,
            date: Date().addingTimeInterval(-86400 * 2), // 2 days ago
            reference: "TXN-DEBUG-12345",
            paymentMethod: "Card ending in 4242",
            receiptUrl: nil,
            gateway: .paystack
        )
    }

    func generateReceipt(id: String) async throws -> URL {
        try await Task.sleep(nanoseconds: 500_000_000)
        throw APIError.serverError // no real receipt exists in DEBUG previews
    }
}
#endif

// MARK: - 3. View Model (StateManagement)

@MainActor
class TransactionDetailsViewModel: ObservableObject {
    @Published var transaction: Transaction?
    @Published var isLoading: Bool = false
    @Published var error: APIError?
    @Published var receiptURL: URL?
    @Published var isShowingShareSheet: Bool = false

    private let api: TransactionAPIClientProtocol
    private let transactionId: String
    private let localAuthContext = LAContext()

    /// Dependency injection for API client and transaction ID.
    init(transactionId: String, api: TransactionAPIClientProtocol = LiveTransactionAPIClient()) {
        self.transactionId = transactionId
        self.api = api
    }

    /// Fetches transaction details from the API.
    func loadTransactionDetails() async {
        // Placeholder for Offline Mode/Local Caching check
        if let cachedTransaction = loadFromCache(id: transactionId) {
            self.transaction = cachedTransaction
            return
        }

        isLoading = true
        error = nil
        do {
            let fetchedTransaction = try await api.fetchTransactionDetails(id: transactionId)
            self.transaction = fetchedTransaction
            saveToCache(transaction: fetchedTransaction)
        } catch let apiError as APIError {
            self.error = apiError
        } catch {
            self.error = .unknownError
        }
        isLoading = false
    }

    /// Handles the receipt download process, including biometric authentication.
    /// Falls back to the device passcode when biometrics are unavailable — the
    /// download is never performed without the user authenticating.
    func downloadReceipt() async {
        guard transaction != nil else { return }

        let reason = "Securely download your transaction receipt."
        let policy: LAPolicy = localAuthContext.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: nil)
            ? .deviceOwnerAuthenticationWithBiometrics
            : .deviceOwnerAuthentication

        guard localAuthContext.canEvaluatePolicy(policy, error: nil) else {
            self.error = .biometricAuthFailed
            return
        }

        do {
            let success = try await localAuthContext.evaluatePolicy(policy, localizedReason: reason)
            if success {
                await performReceiptDownload()
            } else {
                self.error = .biometricAuthFailed
            }
        } catch {
            self.error = .biometricAuthFailed
        }
    }

    /// Performs the actual API call for receipt download.
    private func performReceiptDownload() async {
        guard let transaction = transaction else { return }
        isLoading = true
        error = nil
        do {
            let url = try await api.generateReceipt(id: transaction.id)
            self.receiptURL = url
        } catch let apiError as APIError {
            self.error = apiError
        } catch {
            self.error = .unknownError
        }
        isLoading = false
    }

    /// Placeholder for sharing transaction details.
    func shareTransactionDetails() {
        // In a real app, this would prepare the data for a UIActivityViewController
        self.isShowingShareSheet = true
    }

    // MARK: - Offline Mode/Caching Implementation

    private func saveToCache(transaction: Transaction) {
        // Simple in-memory cache placeholder
        print("Transaction \(transaction.id) saved to local cache.")
    }

    private func loadFromCache(id: String) -> Transaction? {
        // Simple check to simulate offline data availability
        // In a real app, this would use Core Data or Realm
        print("Checking local cache for transaction \(id)...")
        return nil // Always return nil for now to force API call
    }
}

// MARK: - 4. SwiftUI View

struct TransactionDetailsView: View {
    @StateObject var viewModel: TransactionDetailsViewModel
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationView {
            Group {
                if viewModel.isLoading {
                    ProgressView("Loading Transaction Details...")
                } else if let error = viewModel.error {
                    ErrorView(error: error) {
                        Task { await viewModel.loadTransactionDetails() }
                    }
                } else if let transaction = viewModel.transaction {
                    ScrollView {
                        VStack(spacing: 20) {
                            StatusHeader(status: transaction.status)
                            TransactionSummary(transaction: transaction)
                            DetailSection(transaction: transaction)
                            ActionButtons(viewModel: viewModel)
                        }
                        .padding()
                    }
                } else {
                    // Initial state or no data found
                    ContentUnavailableView("No Transaction Found", systemImage: "magnifyingglass")
                        .onAppear {
                            Task { await viewModel.loadTransactionDetails() }
                        }
                }
            }
            .navigationTitle("Transaction Details")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
            .alert("Receipt Downloaded", isPresented: .constant(viewModel.receiptURL != nil), actions: {
                Button("OK") { viewModel.receiptURL = nil }
            }, message: {
                Text("Your receipt has been securely downloaded and is ready to view.")
            })
            .sheet(isPresented: $viewModel.isShowingShareSheet) {
                // Placeholder for a proper Share Sheet (UIActivityViewController wrapper)
                Text("Share Sheet Placeholder for Transaction: \(viewModel.transaction?.reference ?? "")")
                    .presentationDetents([.medium])
            }
        }
        .onAppear {
            // Ensure data is loaded on first appearance
            if viewModel.transaction == nil && viewModel.error == nil {
                Task { await viewModel.loadTransactionDetails() }
            }
        }
    }
}

// MARK: - Subviews

/// Displays the transaction status prominently.
private struct StatusHeader: View {
    let status: TransactionStatus

    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: status == .completed ? "checkmark.circle.fill" : "xmark.circle.fill")
                .resizable()
                .frame(width: 60, height: 60)
                .foregroundColor(status.color)
                .accessibilityLabel("Transaction Status: \(status.rawValue)")

            Text(status.rawValue)
                .font(.title2)
                .fontWeight(.bold)
                .foregroundColor(status.color)
        }
    }
}

/// Displays the main summary of the transaction amounts.
private struct TransactionSummary: View {
    let transaction: Transaction

    var body: some View {
        VStack(alignment: .center, spacing: 10) {
            Text("\(transaction.amountSent, specifier: "%.2f") \(transaction.currencySent)")
                .font(.largeTitle)
                .fontWeight(.heavy)
                .foregroundColor(.primary)
                .accessibilityLabel("Amount sent: \(transaction.amountSent) \(transaction.currencySent)")

            Image(systemName: "arrow.down.forward.circle.fill")
                .foregroundColor(.gray)

            Text("\(transaction.amountReceived, specifier: "%.2f") \(transaction.currencyReceived)")
                .font(.title)
                .fontWeight(.semibold)
                .foregroundColor(.secondary)
                .accessibilityLabel("Amount received: \(transaction.amountReceived) \(transaction.currencyReceived)")
        }
        .padding(.vertical)
        .frame(maxWidth: .infinity)
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

/// Displays detailed information in a list format.
private struct DetailSection: View {
    let transaction: Transaction

    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            DetailRow(label: "Reference Number", value: transaction.reference)
            DetailRow(label: "Date", value: transaction.date, isDate: true)
            DetailRow(label: "Sender", value: transaction.senderName)
            DetailRow(label: "Recipient", value: transaction.recipientName)
            Divider()
            DetailRow(label: "Exchange Rate", value: "\(transaction.exchangeRate, specifier: "%.2f")")
            DetailRow(label: "Transfer Fee", value: "\(transaction.fee, specifier: "%.2f") \(transaction.currencySent)")
            DetailRow(label: "Payment Method", value: transaction.paymentMethod)
            DetailRow(label: "Payment Gateway", value: transaction.gateway.rawValue)
        }
        .padding()
        .background(Color.white)
        .cornerRadius(12)
        .shadow(radius: 1)
    }
}

/// Reusable row for displaying a detail pair.
private struct DetailRow: View {
    let label: String
    let value: String
    var isDate: Bool = false
    let date: Date?

    init(label: String, value: String, isDate: Bool = false) {
        self.label = label
        self.value = value
        self.isDate = isDate
        self.date = nil
    }

    init(label: String, value: Date, isDate: Bool = true) {
        self.label = label
        self.date = value
        self.isDate = isDate
        self.value = ""
    }

    var body: some View {
        HStack {
            Text(label)
                .font(.subheadline)
                .foregroundColor(.gray)
                .accessibilityLabel(label)

            Spacer()

            if isDate, let date = date {
                Text(date, style: .date)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .accessibilityValue(date.formatted(date: .long, time: .shortened))
            } else {
                Text(value)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .accessibilityValue(value)
            }
        }
    }
}

/// View for displaying errors and a retry button.
private struct ErrorView: View {
    let error: APIError
    let retryAction: () -> Void

    var body: some View {
        VStack(spacing: 15) {
            Image(systemName: "exclamationmark.triangle.fill")
                .resizable()
                .frame(width: 50, height: 50)
                .foregroundColor(.red)
            Text("Error")
                .font(.title)
                .fontWeight(.bold)
            Text(error.localizedDescription)
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
            Button("Try Again") {
                retryAction()
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }
}

/// Contains the primary actions for the transaction details.
private struct ActionButtons: View {
    @ObservedObject var viewModel: TransactionDetailsViewModel

    var body: some View {
        VStack(spacing: 10) {
            Button {
                Task { await viewModel.downloadReceipt() }
            } label: {
                HStack {
                    Image(systemName: "doc.text.fill")
                    Text("Download Receipt")
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(viewModel.isLoading)
            .accessibilityLabel("Download Receipt")

            Button {
                viewModel.shareTransactionDetails()
            } label: {
                HStack {
                    Image(systemName: "square.and.arrow.up")
                    Text("Share Details")
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .controlSize(.large)
            .disabled(viewModel.isLoading)
            .accessibilityLabel("Share Transaction Details")
        }
        .padding(.top, 10)
    }
}

// MARK: - 5. Preview

#Preview {
    // Example of how to initialize the view with a mock ID
    TransactionDetailsView(viewModel: TransactionDetailsViewModel(transactionId: "mock-txn-123"))
}

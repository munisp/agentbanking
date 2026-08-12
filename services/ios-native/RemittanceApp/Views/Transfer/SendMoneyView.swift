import SwiftUI
import Alamofire

struct SendMoneyView: View {
    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var walletManager: WalletManager
    @StateObject private var viewModel = SendMoneyViewModel()
    
    @State private var currentStep: TransferStep = .selectBeneficiary
    @State private var selectedBeneficiary: Beneficiary?
    @State private var amount: String = ""
    @State private var sourceCurrency: String = "NGN"
    @State private var destinationCurrency: String = "USD"
    @State private var paymentSystem: String = "NIBSS"
    @State private var purpose: String = ""
    @State private var showBeneficiaryPicker = false
    @State private var showAddBeneficiary = false
    
    var body: some View {
        NavigationView {
            ZStack {
                switch currentStep {
                case .selectBeneficiary:
                    beneficiarySelectionView
                case .enterAmount:
                    amountEntryView
                case .reviewTransfer:
                    reviewTransferView
                case .confirmTransfer:
                    confirmationView
                }
                
                if viewModel.isLoading {
                    LoadingOverlay()
                }
            }
            .navigationTitle("Send Money")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
            .alert("Error", isPresented: .constant(viewModel.errorMessage != nil)) {
                Button("OK") {
                    viewModel.errorMessage = nil
                }
            } message: {
                Text(viewModel.errorMessage ?? "")
            }
        }
    }
    
    // MARK: - Beneficiary Selection
    
    var beneficiarySelectionView: View {
        ScrollView {
            VStack(spacing: 24) {
                // Progress indicator
                ProgressSteps(currentStep: 1, totalSteps: 4)
                
                // Header
                VStack(spacing: 8) {
                    Text("Who are you sending to?")
                        .font(.title2)
                        .fontWeight(.bold)
                    
                    Text("Select a beneficiary or add a new one")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.top)
                
                // Add new beneficiary button
                Button(action: { showAddBeneficiary = true }) {
                    HStack {
                        Image(systemName: "plus.circle.fill")
                            .font(.title2)
                        Text("Add New Beneficiary")
                            .fontWeight(.semibold)
                        Spacer()
                        Image(systemName: "chevron.right")
                    }
                    .padding()
                    .background(Color("PrimaryColor").opacity(0.1))
                    .foregroundColor(Color("PrimaryColor"))
                    .cornerRadius(12)
                }
                
                // Recent beneficiaries
                if !viewModel.beneficiaries.isEmpty {
                    VStack(alignment: .leading, spacing: 16) {
                        Text("Recent Beneficiaries")
                            .font(.headline)
                        
                        ForEach(viewModel.beneficiaries.prefix(5)) { beneficiary in
                            BeneficiaryCard(beneficiary: beneficiary) {
                                selectedBeneficiary = beneficiary
                                withAnimation {
                                    currentStep = .enterAmount
                                }
                            }
                        }
                        
                        if viewModel.beneficiaries.count > 5 {
                            Button("View All Beneficiaries") {
                                showBeneficiaryPicker = true
                            }
                            .font(.subheadline)
                            .foregroundColor(Color("PrimaryColor"))
                        }
                    }
                } else {
                    EmptyStateView(
                        icon: "person.crop.circle.badge.plus",
                        title: "No Beneficiaries",
                        message: "Add your first beneficiary to start sending money"
                    )
                }
            }
            .padding()
        }
        .sheet(isPresented: $showAddBeneficiary) {
            AddBeneficiaryView()
        }
        .sheet(isPresented: $showBeneficiaryPicker) {
            BeneficiaryPickerView(selectedBeneficiary: $selectedBeneficiary) {
                withAnimation {
                    currentStep = .enterAmount
                }
            }
        }
        .task {
            await viewModel.loadBeneficiaries()
        }
    }
    
    // MARK: - Amount Entry
    
    var amountEntryView: View {
        ScrollView {
            VStack(spacing: 24) {
                // Progress indicator
                ProgressSteps(currentStep: 2, totalSteps: 4)
                
                // Selected beneficiary
                if let beneficiary = selectedBeneficiary {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Sending to")
                                .font(.caption)
                                .foregroundColor(.secondary)
                            Text(beneficiary.name)
                                .font(.headline)
                        }
                        
                        Spacer()
                        
                        Button("Change") {
                            withAnimation {
                                currentStep = .selectBeneficiary
                            }
                        }
                        .font(.subheadline)
                        .foregroundColor(Color("PrimaryColor"))
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)
                }
                
                // Amount input
                VStack(alignment: .leading, spacing: 16) {
                    Text("How much?")
                        .font(.title2)
                        .fontWeight(.bold)
                    
                    // Source currency amount
                    VStack(alignment: .leading, spacing: 8) {
                        Text("You send")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        
                        HStack {
                            TextField("0.00", text: $amount)
                                .font(.system(size: 36, weight: .bold))
                                .keyboardType(.decimalPad)
                            
                            Picker("Currency", selection: $sourceCurrency) {
                                Text("NGN").tag("NGN")
                                Text("USD").tag("USD")
                                Text("GBP").tag("GBP")
                                Text("EUR").tag("EUR")
                            }
                            .pickerStyle(.menu)
                        }
                        
                        Divider()
                    }
                    
                    // Exchange rate
                    if let rate = viewModel.exchangeRate {
                        HStack {
                            Text("Exchange Rate")
                                .font(.subheadline)
                            Spacer()
                            Text("1 \(sourceCurrency) = \(rate, specifier: "%.4f") \(destinationCurrency)")
                                .font(.subheadline)
                                .fontWeight(.semibold)
                        }
                        .padding()
                        .background(Color("PrimaryColor").opacity(0.1))
                        .cornerRadius(8)
                    }
                    
                    // Destination currency amount
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Recipient gets")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        
                        HStack {
                            Text(calculatedDestinationAmount)
                                .font(.system(size: 36, weight: .bold))
                                .foregroundColor(Color("PrimaryColor"))
                            
                            Picker("Currency", selection: $destinationCurrency) {
                                Text("USD").tag("USD")
                                Text("GBP").tag("GBP")
                                Text("EUR").tag("EUR")
                                Text("NGN").tag("NGN")
                            }
                            .pickerStyle(.menu)
                        }
                        
                        Divider()
                    }
                    
                    // Fee breakdown
                    VStack(spacing: 12) {
                        FeeRow(label: "Transfer Fee", amount: viewModel.transferFee, currency: sourceCurrency)
                        FeeRow(label: "Exchange Fee", amount: viewModel.exchangeFee, currency: sourceCurrency)
                        
                        Divider()
                        
                        HStack {
                            Text("Total Amount")
                                .fontWeight(.semibold)
                            Spacer()
                            Text("\(sourceCurrency) \(totalAmount, specifier: "%.2f")")
                                .fontWeight(.bold)
                        }
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)
                    
                    // Payment system
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Payment System")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        
                        Picker("Payment System", selection: $paymentSystem) {
                            Text("NIBSS (Nigeria)").tag("NIBSS")
                            Text("PAPSS (Pan-African)").tag("PAPSS")
                            Text("PIX (Brazil)").tag("PIX")
                            Text("UPI (India)").tag("UPI")
                            Text("SWIFT").tag("SWIFT")
                        }
                        .pickerStyle(.menu)
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(8)
                    }
                    
                    // Purpose
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Purpose of Transfer")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        
                        TextField("e.g., Family support, Business payment", text: $purpose)
                            .padding()
                            .background(Color(.systemGray6))
                            .cornerRadius(8)
                    }
                }
                
                Spacer(minLength: 20)
                
                // Continue button
                Button(action: {
                    withAnimation {
                        currentStep = .reviewTransfer
                    }
                }) {
                    Text("Continue")
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(isAmountValid ? Color("PrimaryColor") : Color.gray)
                        .cornerRadius(12)
                }
                .disabled(!isAmountValid)
            }
            .padding()
        }
        .onChange(of: amount) { _ in
            Task {
                await viewModel.getExchangeRate(from: sourceCurrency, to: destinationCurrency)
            }
        }
        .onChange(of: sourceCurrency) { _ in
            Task {
                await viewModel.getExchangeRate(from: sourceCurrency, to: destinationCurrency)
            }
        }
        .onChange(of: destinationCurrency) { _ in
            Task {
                await viewModel.getExchangeRate(from: sourceCurrency, to: destinationCurrency)
            }
        }
    }
    
    // MARK: - Review Transfer
    
    var reviewTransferView: View {
        ScrollView {
            VStack(spacing: 24) {
                // Progress indicator
                ProgressSteps(currentStep: 3, totalSteps: 4)
                
                // Header
                Text("Review Transfer")
                    .font(.title2)
                    .fontWeight(.bold)
                
                // Transfer details
                VStack(spacing: 16) {
                    // Beneficiary
                    DetailRow(
                        label: "Recipient",
                        value: selectedBeneficiary?.name ?? "",
                        icon: "person.fill"
                    )
                    
                    // Amount
                    DetailRow(
                        label: "You send",
                        value: "\(sourceCurrency) \(amount)",
                        icon: "arrow.up.circle.fill"
                    )
                    
                    DetailRow(
                        label: "They receive",
                        value: "\(destinationCurrency) \(calculatedDestinationAmount)",
                        icon: "arrow.down.circle.fill"
                    )
                    
                    Divider()
                    
                    // Fees
                    DetailRow(label: "Transfer Fee", value: "\(sourceCurrency) \(viewModel.transferFee, specifier: "%.2f")")
                    DetailRow(label: "Exchange Fee", value: "\(sourceCurrency) \(viewModel.exchangeFee, specifier: "%.2f")")
                    
                    Divider()
                    
                    // Total
                    HStack {
                        Text("Total Amount")
                            .font(.headline)
                        Spacer()
                        Text("\(sourceCurrency) \(totalAmount, specifier: "%.2f")")
                            .font(.headline)
                            .foregroundColor(Color("PrimaryColor"))
                    }
                    
                    Divider()
                    
                    // Additional details
                    DetailRow(label: "Payment System", value: paymentSystem)
                    DetailRow(label: "Purpose", value: purpose.isEmpty ? "Not specified" : purpose)
                    DetailRow(label: "Estimated Arrival", value: "Within 24 hours")
                }
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(12)
                
                // Important notice
                HStack(alignment: .top, spacing: 12) {
                    Image(systemName: "info.circle.fill")
                        .foregroundColor(.blue)
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Important")
                            .font(.subheadline)
                            .fontWeight(.semibold)
                        
                        Text("Please review all details carefully. Once confirmed, this transfer cannot be cancelled.")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                .padding()
                .background(Color.blue.opacity(0.1))
                .cornerRadius(12)
                
                Spacer(minLength: 20)
                
                // Action buttons
                VStack(spacing: 12) {
                    Button(action: {
                        Task {
                            await confirmTransfer()
                        }
                    }) {
                        Text("Confirm Transfer")
                            .font(.headline)
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color("PrimaryColor"))
                            .cornerRadius(12)
                    }
                    
                    Button("Edit Details") {
                        withAnimation {
                            currentStep = .enterAmount
                        }
                    }
                    .foregroundColor(Color("PrimaryColor"))
                }
            }
            .padding()
        }
    }
    
    // MARK: - Confirmation
    
    var confirmationView: View {
        VStack(spacing: 24) {
            Spacer()
            
            // Success icon
            ZStack {
                Circle()
                    .fill(Color.green.opacity(0.1))
                    .frame(width: 120, height: 120)
                
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 80))
                    .foregroundColor(.green)
            }
            
            // Success message
            VStack(spacing: 12) {
                Text("Transfer Successful!")
                    .font(.title)
                    .fontWeight(.bold)
                
                Text("Your money is on its way")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            
            // Transfer details
            if let transferId = viewModel.transferId {
                VStack(spacing: 16) {
                    DetailRow(label: "Transfer ID", value: transferId)
                    DetailRow(label: "Amount Sent", value: "\(sourceCurrency) \(amount)")
                    DetailRow(label: "Recipient Gets", value: "\(destinationCurrency) \(calculatedDestinationAmount)")
                    DetailRow(label: "Status", value: "Processing")
                }
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(12)
            }
            
            Spacer()
            
            // Action buttons
            VStack(spacing: 12) {
                Button(action: {
                    // Share receipt
                }) {
                    HStack {
                        Image(systemName: "square.and.arrow.up")
                        Text("Share Receipt")
                    }
                    .font(.headline)
                    .foregroundColor(Color("PrimaryColor"))
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color("PrimaryColor").opacity(0.1))
                    .cornerRadius(12)
                }
                
                Button(action: {
                    dismiss()
                }) {
                    Text("Done")
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color("PrimaryColor"))
                        .cornerRadius(12)
                }
            }
        }
        .padding()
    }
    
    // MARK: - Helper Views
    
    // MARK: - Computed Properties
    
    var calculatedDestinationAmount: String {
        guard let amountValue = Double(amount),
              let rate = viewModel.exchangeRate else {
            return "0.00"
        }
        return String(format: "%.2f", amountValue * rate)
    }
    
    var totalAmount: Double {
        guard let amountValue = Double(amount) else { return 0 }
        return amountValue + viewModel.transferFee + viewModel.exchangeFee
    }
    
    var isAmountValid: Bool {
        guard let amountValue = Double(amount) else { return false }
        // A live rate quote is required before proceeding to review.
        return amountValue > 0 && !purpose.isEmpty && viewModel.exchangeRate != nil
    }
    
    // MARK: - Methods
    
    func confirmTransfer() async {
        guard let beneficiary = selectedBeneficiary,
              let amountValue = Double(amount) else { return }
        
        await viewModel.initiateTransfer(
            beneficiaryId: beneficiary.id,
            amount: amountValue,
            sourceCurrency: sourceCurrency,
            destinationCurrency: destinationCurrency,
            paymentSystem: paymentSystem,
            purpose: purpose
        )
        
        if viewModel.transferId != nil {
            withAnimation {
                currentStep = .confirmTransfer
            }
        }
    }
}

// MARK: - Supporting Views

struct ProgressSteps: View {
    let currentStep: Int
    let totalSteps: Int
    
    var body: some View {
        HStack(spacing: 8) {
            ForEach(1...totalSteps, id: \.self) { step in
                Circle()
                    .fill(step <= currentStep ? Color("PrimaryColor") : Color.gray.opacity(0.3))
                    .frame(width: 8, height: 8)
            }
        }
    }
}

struct BeneficiaryCard: View {
    let beneficiary: Beneficiary
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack(spacing: 16) {
                // Avatar
                Circle()
                    .fill(Color("PrimaryColor").opacity(0.2))
                    .frame(width: 50, height: 50)
                    .overlay(
                        Text(beneficiary.name.prefix(1).uppercased())
                            .font(.title3)
                            .fontWeight(.semibold)
                            .foregroundColor(Color("PrimaryColor"))
                    )
                
                // Details
                VStack(alignment: .leading, spacing: 4) {
                    Text(beneficiary.name)
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.primary)
                    
                    Text(beneficiary.accountNumber)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                Image(systemName: "chevron.right")
                    .foregroundColor(.secondary)
            }
            .padding()
            .background(Color(.systemGray6))
            .cornerRadius(12)
        }
    }
}

struct FeeRow: View {
    let label: String
    let amount: Double
    let currency: String
    
    var body: some View {
        HStack {
            Text(label)
                .font(.subheadline)
            Spacer()
            Text("\(currency) \(amount, specifier: "%.2f")")
                .font(.subheadline)
                .fontWeight(.medium)
        }
    }
}

struct DetailRow: View {
    let label: String
    let value: String
    var icon: String? = nil
    
    var body: some View {
        HStack {
            if let icon = icon {
                Image(systemName: icon)
                    .foregroundColor(Color("PrimaryColor"))
            }
            
            Text(label)
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            Spacer()
            
            Text(value)
                .font(.subheadline)
                .fontWeight(.medium)
        }
    }
}

struct LoadingOverlay: View {
    var body: some View {
        ZStack {
            Color.black.opacity(0.3)
                .ignoresSafeArea()
            
            VStack(spacing: 16) {
                ProgressView()
                    .scaleEffect(1.5)
                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                
                Text("Processing...")
                    .foregroundColor(.white)
                    .fontWeight(.semibold)
            }
            .padding(32)
            .background(Color(.systemGray6))
            .cornerRadius(16)
        }
    }
}

// MARK: - Enums

enum TransferStep {
    case selectBeneficiary
    case enterAmount
    case reviewTransfer
    case confirmTransfer
}

// MARK: - Placeholder Views

struct AddBeneficiaryView: View {
    var body: some View {
        Text("Add Beneficiary View")
    }
}

struct BeneficiaryPickerView: View {
    @Binding var selectedBeneficiary: Beneficiary?
    let onSelect: () -> Void
    
    var body: some View {
        Text("Beneficiary Picker View")
    }
}

// MARK: - Transfer API DTOs

private struct SMVQuoteRequest: Encodable {
    let sourceCurrency: String
    let destinationCurrency: String
    let amount: Double
}

private struct SMVQuoteResponse: Decodable {
    let rate: Double
    let transferFee: Double?
    let exchangeFee: Double?
}

private struct SMVInitiateRequest: Encodable {
    let beneficiaryId: String
    let amount: Double
    let sourceCurrency: String
    let destinationCurrency: String
    let paymentSystem: String
    let purpose: String
}

private struct SMVInitiateResponse: Decodable {
    let transferId: String
    let status: String?
}

private func smvJsonParameters<T: Encodable>(_ value: T) throws -> [String: Any] {
    let data = try JSONEncoder().encode(value)
    return (try JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
}

// MARK: - ViewModel

@MainActor
class SendMoneyViewModel: ObservableObject {
    @Published var beneficiaries: [Beneficiary] = []
    @Published var exchangeRate: Double?
    @Published var transferFee: Double = 0
    @Published var exchangeFee: Double = 0
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var transferId: String?
    
    /// Loads beneficiaries from the backend. Errors surface to the user; no fake
    /// beneficiaries are ever shown.
    func loadBeneficiaries() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let response: [Beneficiary] = try await APIClient.shared.request(.beneficiaries)
            beneficiaries = response
        } catch {
            errorMessage = "Could not load beneficiaries: \(error.localizedDescription)"
        }
    }
    
    /// Fetches a live exchange rate quote from the backend. On failure the rate is
    /// cleared so the flow cannot proceed on a stale or fabricated quote.
    func getExchangeRate(from: String, to: String) async {
        guard from != to else {
            exchangeRate = 1.0
            transferFee = 0
            exchangeFee = 0
            return
        }
        do {
            let quoteRequest = SMVQuoteRequest(
                sourceCurrency: from,
                destinationCurrency: to,
                amount: 0
            )
            let response: SMVQuoteResponse = try await APIClient.shared.request(
                .transferQuote,
                method: .post,
                parameters: smvJsonParameters(quoteRequest)
            )
            exchangeRate = response.rate
            transferFee = response.transferFee ?? 0
            exchangeFee = response.exchangeFee ?? 0
        } catch {
            exchangeRate = nil
            errorMessage = "Could not fetch a live exchange rate: \(error.localizedDescription)"
        }
    }
    
    /// Initiates the transfer via the backend. The success screen is only reached with a
    /// server-issued transferId; failures surface an honest error and no receipt is shown.
    func initiateTransfer(
        beneficiaryId: String,
        amount: Double,
        sourceCurrency: String,
        destinationCurrency: String,
        paymentSystem: String,
        purpose: String
    ) async {
        isLoading = true
        defer { isLoading = false }
        errorMessage = nil
        transferId = nil
        
        guard exchangeRate != nil else {
            errorMessage = "No live exchange rate available. Please go back and refresh the rate."
            return
        }
        
        let transferRequest = SMVInitiateRequest(
            beneficiaryId: beneficiaryId,
            amount: amount,
            sourceCurrency: sourceCurrency,
            destinationCurrency: destinationCurrency,
            paymentSystem: paymentSystem,
            purpose: purpose
        )
        
        do {
            let response: SMVInitiateResponse = try await APIClient.shared.request(
                .transferInitiate,
                method: .post,
                parameters: smvJsonParameters(transferRequest)
            )
            transferId = response.transferId
        } catch {
            errorMessage = "Transfer failed: \(error.localizedDescription). No money has been sent."
        }
    }
}

// MARK: - Models

struct Beneficiary: Identifiable, Codable {
    let id: String
    let name: String
    let accountNumber: String
    let bankName: String
    let country: String
}

#Preview {
    SendMoneyView()
        .environmentObject(WalletManager())
}

import SwiftUI

struct MultiChannelPaymentView: View {
    @StateObject private var viewModel = MultiChannelPaymentViewModel()
    @State private var selectedChannel: PaymentChannel = .card
    @State private var amount: String = ""
    @State private var showSuccess = false
    @State private var showSplitConfig = false
    
    let recipient: Beneficiary
    
    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Amount Section
                amountSection
                
                // Payment Channel Selection
                paymentChannelSection
                
                // Channel-Specific Details
                channelDetailsSection
                
                // Split Payment Option
                splitPaymentSection
                
                // Payment Summary
                paymentSummarySection
                
                // Action Buttons
                actionButtons
            }
            .padding()
        }
        .navigationTitle("Pay \(recipient.name)")
        .sheet(isPresented: $showSplitConfig) {
            SplitPaymentConfigView(viewModel: viewModel)
        }
        .sheet(isPresented: $showSuccess) {
            PaymentSuccessView(transaction: viewModel.completedTransaction)
        }
    }
    
    private var amountSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Amount")
                .font(.headline)
            
            HStack {
                Text(recipient.currency)
                    .font(.title2)
                    .fontWeight(.bold)
                
                TextField("0.00", text: $amount)
                    .font(.title)
                    .keyboardType(.decimalPad)
                    .multilineTextAlignment(.trailing)
            }
            .padding()
            .background(Color(.systemGray6))
            .cornerRadius(12)
            
            if let amountValue = Double(amount) {
                Text("≈ $\(viewModel.convertedAmount(amountValue, to: "USD"), specifier: "%.2f") USD")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }
    
    private var paymentChannelSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Payment Method")
                .font(.headline)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                PaymentChannelCard(
                    channel: .card,
                    isSelected: selectedChannel == .card,
                    action: { selectedChannel = .card }
                )
                
                PaymentChannelCard(
                    channel: .bank,
                    isSelected: selectedChannel == .bank,
                    action: { selectedChannel = .bank }
                )
                
                PaymentChannelCard(
                    channel: .ussd,
                    isSelected: selectedChannel == .ussd,
                    action: { selectedChannel = .ussd }
                )
                
                PaymentChannelCard(
                    channel: .mobileMoney,
                    isSelected: selectedChannel == .mobileMoney,
                    action: { selectedChannel = .mobileMoney }
                )
                
                PaymentChannelCard(
                    channel: .qr,
                    isSelected: selectedChannel == .qr,
                    action: { selectedChannel = .qr }
                )
                
                PaymentChannelCard(
                    channel: .virtualAccount,
                    isSelected: selectedChannel == .virtualAccount,
                    action: { selectedChannel = .virtualAccount }
                )
            }
        }
    }
    
    @ViewBuilder
    private var channelDetailsSection: some View {
        switch selectedChannel {
        case .card:
            CardPaymentDetailsView(viewModel: viewModel)
        case .bank:
            BankTransferDetailsView(viewModel: viewModel)
        case .ussd:
            USSDPaymentDetailsView(viewModel: viewModel)
        case .mobileMoney:
            MobileMoneyDetailsView(viewModel: viewModel)
        case .qr:
            QRPaymentDetailsView(viewModel: viewModel)
        case .virtualAccount:
            VirtualAccountDetailsView(viewModel: viewModel)
        }
    }
    
    private var splitPaymentSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Split Payment")
                    .font(.headline)
                
                Spacer()
                
                Toggle("", isOn: $viewModel.enableSplit)
                    .labelsHidden()
            }
            
            if viewModel.enableSplit {
                Button(action: { showSplitConfig = true }) {
                    HStack {
                        Image(systemName: "person.2")
                        Text("Configure Split (\(viewModel.splitRecipients.count) recipients)")
                        Spacer()
                        Image(systemName: "chevron.right")
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                }
                .buttonStyle(.plain)
            }
        }
    }
    
    private var paymentSummarySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Summary")
                .font(.headline)
            
            VStack(spacing: 8) {
                SummaryRow(label: "Amount", value: "\(recipient.currency) \(amount)")
                SummaryRow(label: "Fee", value: "\(recipient.currency) \(viewModel.calculateFee(Double(amount) ?? 0), specifier: "%.2f")")
                SummaryRow(label: "Exchange Rate", value: "1 \(recipient.currency) = \(viewModel.exchangeRate, specifier: "%.4f") USD")
                
                Divider()
                
                SummaryRow(
                    label: "Total",
                    value: "\(recipient.currency) \(viewModel.totalAmount(Double(amount) ?? 0), specifier: "%.2f")",
                    isTotal: true
                )
            }
            .padding()
            .background(Color(.systemGray6))
            .cornerRadius(12)
        }
    }
    
    private var actionButtons: some View {
        VStack(spacing: 12) {
            Button(action: { processPayment() }) {
                HStack {
                    if viewModel.isProcessing {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    }
                    Text(viewModel.isProcessing ? "Processing..." : "Pay Now")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.blue)
                .foregroundColor(.white)
                .cornerRadius(12)
            }
            .disabled(viewModel.isProcessing || amount.isEmpty)
            
            Button("Save as Draft") {
                viewModel.saveDraft()
            }
            .frame(maxWidth: .infinity)
            .padding()
            .background(Color(.systemGray6))
            .foregroundColor(.primary)
            .cornerRadius(12)
        }
    }
    
    private func processPayment() {
        guard let amountValue = Double(amount) else { return }
        
        viewModel.processPayment(
            amount: amountValue,
            channel: selectedChannel,
            recipient: recipient
        ) { success in
            if success {
                showSuccess = true
            }
        }
    }
}

// MARK: - Payment Channel Card

struct PaymentChannelCard: View {
    let channel: PaymentChannel
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                Image(systemName: channel.icon)
                    .font(.title2)
                    .foregroundColor(isSelected ? .white : .blue)
                
                Text(channel.name)
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundColor(isSelected ? .white : .primary)
            }
            .frame(maxWidth: .infinity)
            .padding()
            .background(isSelected ? Color.blue : Color(.systemGray6))
            .cornerRadius(12)
        }
    }
}

// MARK: - Channel-Specific Views

struct CardPaymentDetailsView: View {
    @ObservedObject var viewModel: MultiChannelPaymentViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Card Details")
                .font(.headline)
            
            if viewModel.savedCards.isEmpty {
                Button("Add New Card") {
                    viewModel.showAddCard = true
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(8)
            } else {
                ForEach(viewModel.savedCards) { card in
                    SavedCardRow(card: card, isSelected: viewModel.selectedCard?.id == card.id)
                        .onTapGesture {
                            viewModel.selectedCard = card
                        }
                }
            }
        }
    }
}

struct BankTransferDetailsView: View {
    @ObservedObject var viewModel: MultiChannelPaymentViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Bank Transfer")
                .font(.headline)
            
            Picker("Select Bank", selection: $viewModel.selectedBank) {
                ForEach(viewModel.availableBanks) { bank in
                    Text(bank.name).tag(bank as Bank?)
                }
            }
            .pickerStyle(.menu)
            
            TextField("Account Number", text: $viewModel.accountNumber)
                .textFieldStyle(.roundedBorder)
                .keyboardType(.numberPad)
        }
    }
}

struct USSDPaymentDetailsView: View {
    @ObservedObject var viewModel: MultiChannelPaymentViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("USSD Payment")
                .font(.headline)
            
            Text("Dial the USSD code below to complete payment:")
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            HStack {
                Text(viewModel.ussdCode)
                    .font(.title3)
                    .fontWeight(.bold)
                
                Spacer()
                
                Button(action: { viewModel.copyUSSDCode() }) {
                    Image(systemName: "doc.on.doc")
                }
            }
            .padding()
            .background(Color(.systemGray6))
            .cornerRadius(8)
        }
    }
}

struct MobileMoneyDetailsView: View {
    @ObservedObject var viewModel: MultiChannelPaymentViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Mobile Money")
                .font(.headline)
            
            Picker("Provider", selection: $viewModel.selectedMobileMoneyProvider) {
                ForEach(viewModel.mobileMoneyProviders) { provider in
                    Text(provider.name).tag(provider as MobileMoneyProvider?)
                }
            }
            .pickerStyle(.segmented)
            
            TextField("Phone Number", text: $viewModel.phoneNumber)
                .textFieldStyle(.roundedBorder)
                .keyboardType(.phonePad)
        }
    }
}

struct QRPaymentDetailsView: View {
    @ObservedObject var viewModel: MultiChannelPaymentViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("QR Payment")
                .font(.headline)
            
            if let qrCode = viewModel.qrCode {
                Image(uiImage: qrCode)
                    .resizable()
                    .scaledToFit()
                    .frame(height: 200)
                    .frame(maxWidth: .infinity)
            } else {
                Button("Generate QR Code") {
                    viewModel.generateQRCode()
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(8)
            }
        }
    }
}

struct VirtualAccountDetailsView: View {
    @ObservedObject var viewModel: MultiChannelPaymentViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Virtual Account")
                .font(.headline)
            
            if let account = viewModel.virtualAccount {
                VStack(alignment: .leading, spacing: 8) {
                    DetailRow(label: "Bank", value: account.bankName)
                    DetailRow(label: "Account Number", value: account.accountNumber)
                    DetailRow(label: "Account Name", value: account.accountName)
                }
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(8)
                
                Button("Copy Account Details") {
                    viewModel.copyAccountDetails()
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.blue.opacity(0.1))
                .foregroundColor(.blue)
                .cornerRadius(8)
            } else {
                Button("Create Virtual Account") {
                    viewModel.createVirtualAccount()
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(8)
            }
        }
    }
}

// MARK: - Supporting Views

struct SummaryRow: View {
    let label: String
    let value: String
    var isTotal: Bool = false
    
    var body: some View {
        HStack {
            Text(label)
                .foregroundColor(isTotal ? .primary : .secondary)
                .fontWeight(isTotal ? .semibold : .regular)
            Spacer()
            Text(value)
                .fontWeight(isTotal ? .bold : .regular)
        }
    }
}

struct SavedCardRow: View {
    let card: SavedCard
    let isSelected: Bool
    
    var body: some View {
        HStack {
            Image(systemName: "creditcard")
            VStack(alignment: .leading) {
                Text("•••• \(card.last4)")
                    .fontWeight(.medium)
                Text(card.brand)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Spacer()
            if isSelected {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.blue)
            }
        }
        .padding()
        .background(isSelected ? Color.blue.opacity(0.1) : Color(.systemGray6))
        .cornerRadius(8)
    }
}

struct DetailRow: View {
    let label: String
    let value: String
    
    var body: some View {
        HStack {
            Text(label)
                .foregroundColor(.secondary)
            Spacer()
            Text(value)
                .fontWeight(.medium)
        }
    }
}

// MARK: - Split Payment Config View

struct SplitPaymentConfigView: View {
    @ObservedObject var viewModel: MultiChannelPaymentViewModel
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationView {
            List {
                ForEach(viewModel.splitRecipients) { recipient in
                    HStack {
                        VStack(alignment: .leading) {
                            Text(recipient.name)
                            Text("\(recipient.percentage, specifier: "%.0f")%")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        Spacer()
                        Text("\(recipient.amount, specifier: "%.2f")")
                            .fontWeight(.medium)
                    }
                }
                .onDelete { indexSet in
                    viewModel.splitRecipients.remove(atOffsets: indexSet)
                }
                
                Button("Add Recipient") {
                    viewModel.addSplitRecipient()
                }
            }
            .navigationTitle("Split Payment")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

// MARK: - Payment Success View

struct PaymentSuccessView: View {
    let transaction: Transaction?
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 80))
                .foregroundColor(.green)
            
            Text("Payment Successful!")
                .font(.title)
                .fontWeight(.bold)
            
            if let transaction = transaction {
                VStack(spacing: 12) {
                    Text("Reference: \(transaction.reference)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Text("\(transaction.currency) \(transaction.amount, specifier: "%.2f")")
                        .font(.title2)
                        .fontWeight(.bold)
                }
            }
            
            Button("Done") {
                dismiss()
            }
            .frame(maxWidth: .infinity)
            .padding()
            .background(Color.blue)
            .foregroundColor(.white)
            .cornerRadius(12)
            .padding(.horizontal)
        }
        .padding()
    }
}

// MARK: - View Model

class MultiChannelPaymentViewModel: ObservableObject {
    @Published var isProcessing = false
    @Published var enableSplit = false
    @Published var splitRecipients: [SplitRecipient] = []
    @Published var savedCards: [SavedCard] = []
    @Published var selectedCard: SavedCard?
    @Published var availableBanks: [Bank] = []
    @Published var selectedBank: Bank?
    @Published var accountNumber = ""
    @Published var ussdCode = ""
    @Published var mobileMoneyProviders: [MobileMoneyProvider] = []
    @Published var selectedMobileMoneyProvider: MobileMoneyProvider?
    @Published var phoneNumber = ""
    @Published var qrCode: UIImage?
    @Published var virtualAccount: VirtualAccount?
    @Published var showAddCard = false
    @Published var completedTransaction: Transaction?
    @Published var exchangeRate: Double = 1.0
    
    private let apiService = APIService.shared
    
    func convertedAmount(_ amount: Double, to currency: String) -> Double {
        return amount * exchangeRate
    }
    
    func calculateFee(_ amount: Double) -> Double {
        return amount * 0.015 // 1.5% fee
    }
    
    func totalAmount(_ amount: Double) -> Double {
        return amount + calculateFee(amount)
    }
    
    func processPayment(amount: Double, channel: PaymentChannel, recipient: Beneficiary, completion: @escaping (Bool) -> Void) {
        isProcessing = true
        
        Task {
            do {
                let response = try await apiService.post("/payments/initiate", body: [
                    "amount": amount,
                    "channel": channel.rawValue,
                    "recipient_id": recipient.id.uuidString,
                    "split_enabled": enableSplit,
                    "split_recipients": splitRecipients.map { ["id": $0.id.uuidString, "percentage": $0.percentage] }
                ])
                
                await MainActor.run {
                    isProcessing = false
                    completion(true)
                }
            } catch {
                await MainActor.run {
                    isProcessing = false
                    completion(false)
                }
            }
        }
    }
    
    func saveDraft() {
        // Save payment as draft
    }
    
    func copyUSSDCode() {
        UIPasteboard.general.string = ussdCode
    }
    
    func generateQRCode() {
        // Generate QR code
    }
    
    func createVirtualAccount() {
        // Create virtual account
    }
    
    func copyAccountDetails() {
        // Copy account details
    }
    
    func addSplitRecipient() {
        // Add split recipient
    }
}

// MARK: - Models

enum PaymentChannel: String {
    case card, bank, ussd, mobileMoney, qr, virtualAccount
    
    var name: String {
        switch self {
        case .card: return "Card"
        case .bank: return "Bank"
        case .ussd: return "USSD"
        case .mobileMoney: return "Mobile Money"
        case .qr: return "QR Code"
        case .virtualAccount: return "Virtual Account"
        }
    }
    
    var icon: String {
        switch self {
        case .card: return "creditcard"
        case .bank: return "building.columns"
        case .ussd: return "phone"
        case .mobileMoney: return "iphone"
        case .qr: return "qrcode"
        case .virtualAccount: return "wallet.pass"
        }
    }
}

struct Beneficiary: Identifiable {
    let id = UUID()
    let name: String
    let currency: String
}

struct SavedCard: Identifiable {
    let id = UUID()
    let last4: String
    let brand: String
}

struct Bank: Identifiable {
    let id = UUID()
    let name: String
    let code: String
}

struct MobileMoneyProvider: Identifiable {
    let id = UUID()
    let name: String
}

struct VirtualAccount {
    let bankName: String
    let accountNumber: String
    let accountName: String
}

struct SplitRecipient: Identifiable {
    let id = UUID()
    let name: String
    let percentage: Double
    let amount: Double
}

struct Transaction {
    let reference: String
    let amount: Double
    let currency: String
}

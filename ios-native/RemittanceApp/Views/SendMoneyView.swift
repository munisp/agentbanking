//
// SendMoneyView.swift
// 54Link Agency Banking
//
// World-class money transfer experience with FX transparency, rate locking, and offline support
//

import SwiftUI

// MARK: - Data Models

struct ExchangeRate: Codable {
    let from: String
    let to: String
    let rate: Double
    let lastUpdated: String
    let provider: String
}

struct RateLock: Identifiable {
    let id: String
    let rate: Double
    let expiresAt: Date
    let lockedAt: Date
}

struct FeeBreakdown {
    let transferFee: Double
    let networkFee: Double
    let totalFees: Double
    let feePercentage: Double
}

struct DeliveryEstimate: Identifiable {
    let id = UUID()
    let method: String
    let estimatedTime: String
    let available: Bool
}

// MARK: - Constants

let currencyFlags: [String: String] = [
    "GBP": "\u{1F1EC}\u{1F1E7}", "USD": "\u{1F1FA}\u{1F1F8}",
    "EUR": "\u{1F1EA}\u{1F1FA}", "NGN": "\u{1F1F3}\u{1F1EC}",
    "GHS": "\u{1F1EC}\u{1F1ED}", "KES": "\u{1F1F0}\u{1F1EA}"
]

let currencySymbols: [String: String] = [
    "GBP": "£", "USD": "$", "EUR": "€", "NGN": "₦", "GHS": "₵", "KES": "KSh"
]

let sourceCurrencies = ["GBP", "USD", "EUR", "NGN"]
let destinationCurrencies = ["NGN", "GHS", "KES", "USD", "GBP"]

let mockRates: [String: [String: Double]] = [
    "GBP": ["NGN": 1950.50, "GHS": 15.20, "KES": 165.30, "USD": 1.27],
    "USD": ["NGN": 1535.00, "GHS": 11.95, "KES": 130.20, "GBP": 0.79],
    "EUR": ["NGN": 1680.25, "GHS": 13.10, "KES": 142.50, "GBP": 0.86],
    "NGN": ["GHS": 0.0078, "KES": 0.085, "USD": 0.00065, "GBP": 0.00051]
]

let deliveryMethods: [String: [DeliveryEstimate]] = [
    "NGN": [
        DeliveryEstimate(method: "bank_transfer", estimatedTime: "Instant - 30 mins", available: true),
        DeliveryEstimate(method: "mobile_money", estimatedTime: "Instant", available: true),
        DeliveryEstimate(method: "cash_pickup", estimatedTime: "1 - 4 hours", available: true)
    ],
    "default": [
        DeliveryEstimate(method: "bank_transfer", estimatedTime: "1 - 2 business days", available: true)
    ]
]

// MARK: - View Model

@MainActor
final class SendMoneyViewModel: ObservableObject {
    @Published var currentStep = 1
    @Published var recipient = ""
    @Published var recipientName = ""
    @Published var recipientType = "phone"
    @Published var amount = ""
    @Published var sourceCurrency = "GBP"
    @Published var destinationCurrency = "NGN"
    @Published var note = ""
    @Published var deliveryMethod = "bank_transfer"
    @Published var selectedBank = ""
    
    @Published var exchangeRate: ExchangeRate?
    @Published var rateLock: RateLock?
    @Published var isLoadingRate = false
    @Published var rateRefreshCountdown = 30
    @Published var showRateHistory = false
    
    @Published var isSubmitting = false
    @Published var errorMessage: String?
    @Published var successMessage: String?
    @Published var pendingCount = 0
    @Published var isOnline = true
    
    var receivedAmount: Double {
        let amountValue = Double(amount) ?? 0
        let rate = rateLock?.rate ?? exchangeRate?.rate ?? 0
        return amountValue * rate
    }
    
    var feeBreakdown: FeeBreakdown? {
        guard let amountValue = Double(amount), amountValue > 0 else { return nil }
        let corridor = "\(sourceCurrency)-\(destinationCurrency)"
        let (fixed, percentage): (Double, Double) = {
            switch corridor {
            case "GBP-NGN": return (0.99, 0.5)
            case "USD-NGN": return (2.99, 0.5)
            case "EUR-NGN": return (1.99, 0.5)
            default: return (50.0, 1.5)
            }
        }()
        let transferFee = fixed + (amountValue * percentage / 100)
        let networkFee = deliveryMethod == "cash_pickup" ? 2.00 : 0.0
        let totalFees = transferFee + networkFee
        return FeeBreakdown(
            transferFee: transferFee,
            networkFee: networkFee,
            totalFees: totalFees,
            feePercentage: (totalFees / amountValue) * 100
        )
    }
    
    var deliveryEstimates: [DeliveryEstimate] {
        deliveryMethods[destinationCurrency] ?? deliveryMethods["default"]!
    }
    
    var isStepValid: Bool {
        switch currentStep {
        case 1: return !recipientName.isEmpty && recipient.count >= 5
        case 2: return (Double(amount) ?? 0) > 0 && exchangeRate != nil
        case 3: return !isSubmitting
        default: return false
        }
    }
    
    func fetchExchangeRate() async {
        guard rateLock == nil else { return }
        isLoadingRate = true
        
        try? await Task.sleep(nanoseconds: 500_000_000)
        
        let rate = mockRates[sourceCurrency]?[destinationCurrency] ?? 1.0
        exchangeRate = ExchangeRate(
            from: sourceCurrency,
            to: destinationCurrency,
            rate: rate,
            lastUpdated: "Just now",
            provider: "Market Rate"
        )
        isLoadingRate = false
        rateRefreshCountdown = 30
    }
    
    func lockRate() {
        guard let rate = exchangeRate else { return }
        rateLock = RateLock(
            id: "lock_\(Date().timeIntervalSince1970)",
            rate: rate.rate,
            expiresAt: Date().addingTimeInterval(600),
            lockedAt: Date()
        )
    }
    
    func unlockRate() {
        rateLock = nil
        Task { await fetchExchangeRate() }
    }
    
    func submitTransfer() async {
        isSubmitting = true
        
        try? await Task.sleep(nanoseconds: 1_500_000_000)
        
        if !isOnline {
            pendingCount += 1
            successMessage = "Transfer queued. Will sync when online."
        } else {
            successMessage = "Transfer successful! Ref: TXN\(Int(Date().timeIntervalSince1970))"
        }
        isSubmitting = false
    }
    
    func startRateRefreshTimer() {
        Task {
            while rateLock == nil {
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                if rateRefreshCountdown > 0 {
                    rateRefreshCountdown -= 1
                } else {
                    await fetchExchangeRate()
                }
            }
        }
    }
}

// MARK: - Main View

struct SendMoneyView: View {
    @StateObject private var viewModel = SendMoneyViewModel()
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Offline indicator
                if !viewModel.isOnline {
                    HStack {
                        Circle()
                            .fill(Color.orange)
                            .frame(width: 8, height: 8)
                        Text("Offline Mode")
                            .font(.caption)
                            .foregroundColor(.orange)
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(Color.orange.opacity(0.1))
                    .cornerRadius(16)
                    .padding(.top, 8)
                }
                
                // Pending transactions banner
                if viewModel.pendingCount > 0 {
                    HStack {
                        ZStack {
                            Circle()
                                .fill(Color.blue)
                                .frame(width: 32, height: 32)
                            Text("\(viewModel.pendingCount)")
                                .font(.caption.bold())
                                .foregroundColor(.white)
                        }
                        VStack(alignment: .leading) {
                            Text("Pending Transactions")
                                .font(.subheadline.bold())
                            Text("Will sync when online")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        Spacer()
                    }
                    .padding()
                    .background(Color.blue.opacity(0.1))
                    .cornerRadius(12)
                    .padding()
                }
                
                // Progress indicator
                ProgressStepsView(currentStep: viewModel.currentStep)
                    .padding()
                
                // Error message
                if let error = viewModel.errorMessage {
                    HStack {
                        Image(systemName: "exclamationmark.circle.fill")
                            .foregroundColor(.red)
                        Text(error)
                            .font(.subheadline)
                        Spacer()
                        Button(action: { viewModel.errorMessage = nil }) {
                            Image(systemName: "xmark")
                                .foregroundColor(.secondary)
                        }
                    }
                    .padding()
                    .background(Color.red.opacity(0.1))
                    .cornerRadius(12)
                    .padding(.horizontal)
                }
                
                // Success message
                if let success = viewModel.successMessage {
                    HStack {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.green)
                        Text(success)
                            .font(.subheadline)
                    }
                    .padding()
                    .background(Color.green.opacity(0.1))
                    .cornerRadius(12)
                    .padding(.horizontal)
                }
                
                ScrollView {
                    VStack(spacing: 20) {
                        switch viewModel.currentStep {
                        case 1:
                            RecipientStepView(viewModel: viewModel)
                        case 2:
                            AmountStepView(viewModel: viewModel)
                        case 3:
                            ConfirmStepView(viewModel: viewModel)
                        default:
                            EmptyView()
                        }
                    }
                    .padding()
                }
                
                // Navigation buttons
                HStack(spacing: 12) {
                    if viewModel.currentStep > 1 {
                        Button("Back") {
                            viewModel.currentStep -= 1
                        }
                        .buttonStyle(.bordered)
                    } else {
                        Button("Cancel") {
                            dismiss()
                        }
                        .buttonStyle(.bordered)
                    }
                    
                    Button(action: {
                        if viewModel.currentStep < 3 {
                            viewModel.currentStep += 1
                        } else {
                            Task { await viewModel.submitTransfer() }
                        }
                    }) {
                        HStack {
                            if viewModel.isSubmitting {
                                ProgressView()
                                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                                Text("Processing...")
                            } else if viewModel.currentStep == 3 {
                                Image(systemName: "paperplane.fill")
                                Text("Send \(currencySymbols[viewModel.sourceCurrency] ?? "")\(viewModel.amount)")
                            } else {
                                Text("Continue")
                            }
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(!viewModel.isStepValid)
                }
                .padding()
            }
            .navigationTitle("Send Money")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark")
                    }
                }
            }
        }
        .task {
            await viewModel.fetchExchangeRate()
            viewModel.startRateRefreshTimer()
        }
    }
}

// MARK: - Progress Steps View

struct ProgressStepsView: View {
    let currentStep: Int
    let steps = ["Recipient", "Amount", "Confirm"]
    
    var body: some View {
        HStack {
            ForEach(Array(steps.enumerated()), id: \.offset) { index, label in
                let stepNum = index + 1
                let isCompleted = currentStep > stepNum
                let isCurrent = currentStep == stepNum
                
                VStack {
                    ZStack {
                        Circle()
                            .fill(isCompleted || isCurrent ? Color.blue : Color.gray.opacity(0.3))
                            .frame(width: 40, height: 40)
                        
                        if isCompleted {
                            Image(systemName: "checkmark")
                                .foregroundColor(.white)
                                .font(.system(size: 16, weight: .bold))
                        } else {
                            Text("\(stepNum)")
                                .foregroundColor(isCurrent ? .white : .gray)
                                .font(.system(size: 16, weight: .bold))
                        }
                    }
                    
                    Text(label)
                        .font(.caption)
                        .foregroundColor(isCurrent ? .blue : .secondary)
                }
                
                if index < steps.count - 1 {
                    Rectangle()
                        .fill(isCompleted ? Color.blue : Color.gray.opacity(0.3))
                        .frame(height: 2)
                }
            }
        }
    }
}

// MARK: - Recipient Step View

struct RecipientStepView: View {
    @ObservedObject var viewModel: SendMoneyViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("Who are you sending to?")
                .font(.title2.bold())
            
            // Recipient type selection
            HStack(spacing: 12) {
                ForEach([("phone", "Phone", "phone.fill"), ("email", "Email", "envelope.fill"), ("bank", "Bank", "building.columns.fill")], id: \.0) { type, label, icon in
                    let isSelected = viewModel.recipientType == type
                    Button(action: { viewModel.recipientType = type }) {
                        VStack {
                            Image(systemName: icon)
                                .font(.title2)
                            Text(label)
                                .font(.caption)
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(isSelected ? Color.blue.opacity(0.1) : Color.gray.opacity(0.1))
                        .foregroundColor(isSelected ? .blue : .secondary)
                        .cornerRadius(12)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(isSelected ? Color.blue : Color.clear, lineWidth: 2)
                        )
                    }
                }
            }
            
            // Recipient name
            VStack(alignment: .leading, spacing: 8) {
                Text("Recipient Name")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                TextField("Enter full name", text: $viewModel.recipientName)
                    .textFieldStyle(.roundedBorder)
            }
            
            // Recipient identifier
            VStack(alignment: .leading, spacing: 8) {
                Text(viewModel.recipientType == "phone" ? "Phone Number" : viewModel.recipientType == "email" ? "Email Address" : "Account Number")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                TextField(viewModel.recipientType == "phone" ? "+234 XXX XXX XXXX" : viewModel.recipientType == "email" ? "email@example.com" : "0123456789", text: $viewModel.recipient)
                    .textFieldStyle(.roundedBorder)
                    .keyboardType(viewModel.recipientType == "phone" ? .phonePad : viewModel.recipientType == "email" ? .emailAddress : .numberPad)
            }
            
            // Bank selection
            if viewModel.recipientType == "bank" {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Select Bank")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    Picker("Bank", selection: $viewModel.selectedBank) {
                        Text("Select a bank").tag("")
                        ForEach(["Access Bank", "First Bank", "GTBank", "UBA", "Zenith Bank"], id: \.self) { bank in
                            Text(bank).tag(bank)
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(8)
                }
            }
            
            // Destination currency
            VStack(alignment: .leading, spacing: 12) {
                Text("Sending to")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                HStack(spacing: 8) {
                    ForEach(destinationCurrencies.prefix(4), id: \.self) { currency in
                        let isSelected = viewModel.destinationCurrency == currency
                        Button(action: { viewModel.destinationCurrency = currency }) {
                            VStack {
                                Text(currencyFlags[currency] ?? "")
                                    .font(.title)
                                Text(currency)
                                    .font(.caption.bold())
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(isSelected ? Color.blue.opacity(0.1) : Color.gray.opacity(0.1))
                            .cornerRadius(12)
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(isSelected ? Color.blue : Color.clear, lineWidth: 2)
                            )
                        }
                        .foregroundColor(isSelected ? .blue : .primary)
                    }
                }
            }
        }
    }
}

// MARK: - Amount Step View

struct AmountStepView: View {
    @ObservedObject var viewModel: SendMoneyViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("How much are you sending?")
                .font(.title2.bold())
            
            // Amount input
            HStack {
                Picker("Currency", selection: $viewModel.sourceCurrency) {
                    ForEach(sourceCurrencies, id: \.self) { currency in
                        Text("\(currencyFlags[currency] ?? "") \(currency)").tag(currency)
                    }
                }
                .pickerStyle(.menu)
                .frame(width: 120)
                
                TextField("0.00", text: $viewModel.amount)
                    .keyboardType(.decimalPad)
                    .font(.title2)
                    .textFieldStyle(.roundedBorder)
            }
            
            // Received amount
            HStack {
                Text("They receive")
                    .foregroundColor(.secondary)
                Spacer()
                Text("\(currencySymbols[viewModel.destinationCurrency] ?? "")\(String(format: "%.2f", viewModel.receivedAmount)) \(viewModel.destinationCurrency)")
                    .font(.title3.bold())
                    .foregroundColor(.blue)
            }
            .padding()
            .background(Color.gray.opacity(0.1))
            .cornerRadius(12)
            
            // Exchange rate card
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Exchange Rate")
                        .font(.subheadline.bold())
                    Spacer()
                    if viewModel.isLoadingRate {
                        ProgressView()
                    } else if viewModel.rateLock != nil {
                        HStack(spacing: 4) {
                            Image(systemName: "lock.fill")
                                .font(.caption)
                            Text("Locked")
                                .font(.caption)
                        }
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.green)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                    } else {
                        Text("Refreshes in \(viewModel.rateRefreshCountdown)s")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                Text("1 \(viewModel.sourceCurrency) = \(String(format: "%.4f", viewModel.exchangeRate?.rate ?? 0)) \(viewModel.destinationCurrency)")
                    .font(.title2.bold())
                
                HStack(spacing: 12) {
                    if viewModel.rateLock != nil {
                        Button("Unlock") {
                            viewModel.unlockRate()
                        }
                        .buttonStyle(.bordered)
                        .tint(.red)
                    } else {
                        Button(action: { viewModel.lockRate() }) {
                            HStack {
                                Image(systemName: "lock.fill")
                                Text("Lock Rate")
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(viewModel.exchangeRate == nil || viewModel.isLoadingRate)
                    }
                    
                    Button(viewModel.showRateHistory ? "Hide" : "History") {
                        viewModel.showRateHistory.toggle()
                    }
                    .buttonStyle(.bordered)
                }
                
                if viewModel.showRateHistory {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("7-Day Rate History")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        
                        HStack(alignment: .bottom, spacing: 4) {
                            ForEach([0.98, 0.99, 1.01, 0.97, 1.02, 0.99, 1.0], id: \.self) { multiplier in
                                RoundedRectangle(cornerRadius: 2)
                                    .fill(Color.blue.opacity(0.7))
                                    .frame(height: CGFloat(multiplier * 50))
                            }
                        }
                        .frame(height: 60)
                    }
                    .padding(.top, 8)
                }
            }
            .padding()
            .background(Color.blue.opacity(0.05))
            .cornerRadius(16)
            
            // Fee breakdown
            if let fees = viewModel.feeBreakdown {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Fee Breakdown")
                        .font(.subheadline.bold())
                    
                    HStack {
                        Text("Transfer fee")
                            .foregroundColor(.secondary)
                        Spacer()
                        Text("\(currencySymbols[viewModel.sourceCurrency] ?? "")\(String(format: "%.2f", fees.transferFee))")
                    }
                    .font(.subheadline)
                    
                    if fees.networkFee > 0 {
                        HStack {
                            Text("Cash pickup fee")
                                .foregroundColor(.secondary)
                            Spacer()
                            Text("\(currencySymbols[viewModel.sourceCurrency] ?? "")\(String(format: "%.2f", fees.networkFee))")
                        }
                        .font(.subheadline)
                    }
                    
                    Divider()
                    
                    HStack {
                        Text("Total fees")
                            .font(.subheadline.bold())
                        Spacer()
                        Text("\(currencySymbols[viewModel.sourceCurrency] ?? "")\(String(format: "%.2f", fees.totalFees)) (\(String(format: "%.1f", fees.feePercentage))%)")
                            .font(.subheadline.bold())
                    }
                }
                .padding()
                .background(Color.gray.opacity(0.1))
                .cornerRadius(12)
            }
            
            // Delivery method
            VStack(alignment: .leading, spacing: 12) {
                Text("Delivery Method")
                    .font(.subheadline.bold())
                
                ForEach(viewModel.deliveryEstimates) { estimate in
                    let isSelected = viewModel.deliveryMethod == estimate.method
                    Button(action: { viewModel.deliveryMethod = estimate.method }) {
                        HStack {
                            Image(systemName: estimate.method == "bank_transfer" ? "building.columns.fill" : estimate.method == "mobile_money" ? "iphone" : "banknote.fill")
                                .foregroundColor(isSelected ? .blue : .secondary)
                            
                            VStack(alignment: .leading) {
                                Text(estimate.method.replacingOccurrences(of: "_", with: " ").capitalized)
                                    .font(.subheadline.bold())
                                Text(estimate.estimatedTime)
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
                        .background(isSelected ? Color.blue.opacity(0.1) : Color.gray.opacity(0.1))
                        .cornerRadius(12)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(isSelected ? Color.blue : Color.clear, lineWidth: 2)
                        )
                    }
                    .foregroundColor(.primary)
                    .disabled(!estimate.available)
                }
            }
            
            // Note
            VStack(alignment: .leading, spacing: 8) {
                Text("Note (optional)")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                TextField("Add a message", text: $viewModel.note, axis: .vertical)
                    .lineLimit(2...4)
                    .textFieldStyle(.roundedBorder)
            }
        }
    }
}

// MARK: - Confirm Step View

struct ConfirmStepView: View {
    @ObservedObject var viewModel: SendMoneyViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("Confirm Transfer")
                .font(.title2.bold())
            
            // Amount summary card
            VStack(spacing: 16) {
                Text("You're sending")
                    .foregroundColor(.white.opacity(0.8))
                Text("\(currencySymbols[viewModel.sourceCurrency] ?? "")\(viewModel.amount)")
                    .font(.largeTitle.bold())
                    .foregroundColor(.white)
                Text(viewModel.sourceCurrency)
                    .foregroundColor(.white.opacity(0.8))
                
                Image(systemName: "arrow.down")
                    .font(.title)
                    .foregroundColor(.white.opacity(0.6))
                
                Text("\(viewModel.recipientName) receives")
                    .foregroundColor(.white.opacity(0.8))
                Text("\(currencySymbols[viewModel.destinationCurrency] ?? "")\(String(format: "%.2f", viewModel.receivedAmount))")
                    .font(.largeTitle.bold())
                    .foregroundColor(.white)
                Text(viewModel.destinationCurrency)
                    .foregroundColor(.white.opacity(0.8))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 24)
            .background(
                LinearGradient(colors: [.blue, .purple], startPoint: .topLeading, endPoint: .bottomTrailing)
            )
            .cornerRadius(20)
            
            // Details
            VStack(spacing: 0) {
                DetailRow(label: "Recipient", value: viewModel.recipientName)
                DetailRow(label: viewModel.recipientType == "phone" ? "Phone" : viewModel.recipientType == "email" ? "Email" : "Account", value: viewModel.recipient)
                DetailRow(label: "Exchange Rate", value: "1 \(viewModel.sourceCurrency) = \(String(format: "%.4f", viewModel.rateLock?.rate ?? viewModel.exchangeRate?.rate ?? 0)) \(viewModel.destinationCurrency)\(viewModel.rateLock != nil ? " (Locked)" : "")")
                DetailRow(label: "Delivery Method", value: viewModel.deliveryMethod.replacingOccurrences(of: "_", with: " ").capitalized)
                DetailRow(label: "Estimated Delivery", value: viewModel.deliveryEstimates.first { $0.method == viewModel.deliveryMethod }?.estimatedTime ?? "-")
                DetailRow(label: "Total Fees", value: "\(currencySymbols[viewModel.sourceCurrency] ?? "")\(String(format: "%.2f", viewModel.feeBreakdown?.totalFees ?? 0))")
                if !viewModel.note.isEmpty {
                    DetailRow(label: "Note", value: viewModel.note)
                }
            }
            .background(Color.gray.opacity(0.1))
            .cornerRadius(12)
            
            // Total to pay
            HStack {
                Text("Total to Pay")
                    .font(.headline)
                Spacer()
                Text("\(currencySymbols[viewModel.sourceCurrency] ?? "")\(String(format: "%.2f", (Double(viewModel.amount) ?? 0) + (viewModel.feeBreakdown?.totalFees ?? 0)))")
                    .font(.title2.bold())
                    .foregroundColor(.blue)
            }
            .padding()
            .background(Color.blue.opacity(0.1))
            .cornerRadius(12)
            
            // Offline warning
            if !viewModel.isOnline {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.orange)
                    VStack(alignment: .leading) {
                        Text("You're currently offline")
                            .font(.subheadline.bold())
                        Text("This transfer will be queued and processed when you're back online.")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                .padding()
                .background(Color.orange.opacity(0.1))
                .cornerRadius(12)
            }
        }
    }
}

struct DetailRow: View {
    let label: String
    let value: String
    
    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(label)
                    .foregroundColor(.secondary)
                Spacer()
                Text(value)
                    .fontWeight(.medium)
            }
            .padding()
            
            Divider()
        }
    }
}

// MARK: - Preview

#Preview {
    SendMoneyView()
}

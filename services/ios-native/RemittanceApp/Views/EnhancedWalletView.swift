import SwiftUI

struct EnhancedWalletView: View {
    @StateObject private var viewModel = EnhancedWalletViewModel()
    @State private var showCurrencyConverter = false
    @State private var showTransferSheet = false
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                totalBalanceCard
                currencyBalancesSection
                quickActionsSection
                recentTransactionsSection
            }
            .padding()
        }
        .navigationTitle("Multi-Currency Wallet")
        .sheet(isPresented: $showCurrencyConverter) {
            CurrencyConverterView(viewModel: viewModel)
        }
        .sheet(isPresented: $showTransferSheet) {
            CurrencyTransferView(viewModel: viewModel)
        }
        .onAppear { viewModel.loadWalletData() }
    }
    
    private var totalBalanceCard: some View {
        VStack(spacing: 12) {
            Text("Total Balance")
                .font(.subheadline)
                .foregroundColor(.secondary)
            Text("$\(viewModel.totalBalanceUSD, specifier: "%.2f")")
                .font(.system(size: 36, weight: .bold))
            Text("≈ \(viewModel.primaryCurrency) \(viewModel.totalBalancePrimary, specifier: "%.2f")")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(LinearGradient(colors: [.blue, .purple], startPoint: .topLeading, endPoint: .bottomTrailing))
        .foregroundColor(.white)
        .cornerRadius(16)
    }
    
    private var currencyBalancesSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Currency Balances")
                .font(.headline)
            
            ForEach(viewModel.currencyBalances) { balance in
                CurrencyBalanceRow(balance: balance)
                    .onTapGesture {
                        viewModel.selectedCurrency = balance
                    }
            }
        }
    }
    
    private var quickActionsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Quick Actions")
                .font(.headline)
            
            HStack(spacing: 12) {
                QuickActionButton(icon: "arrow.left.arrow.right", title: "Convert", action: { showCurrencyConverter = true })
                QuickActionButton(icon: "arrow.up", title: "Transfer", action: { showTransferSheet = true })
                QuickActionButton(icon: "plus", title: "Add Funds", action: { viewModel.showAddFunds() })
                QuickActionButton(icon: "arrow.down", title: "Withdraw", action: { viewModel.showWithdraw() })
            }
        }
    }
    
    private var recentTransactionsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Recent Transactions")
                .font(.headline)
            
            ForEach(viewModel.recentTransactions) { transaction in
                WalletTransactionRow(transaction: transaction)
            }
        }
    }
}

struct CurrencyBalanceRow: View {
    let balance: CurrencyBalance
    
    var body: some View {
        HStack {
            Image(systemName: "dollarsign.circle.fill")
                .font(.title2)
                .foregroundColor(.blue)
            
            VStack(alignment: .leading) {
                Text(balance.currency)
                    .font(.headline)
                Text(balance.currencyName)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            VStack(alignment: .trailing) {
                Text("\(balance.amount, specifier: "%.2f")")
                    .font(.headline)
                Text("≈ $\(balance.usdEquivalent, specifier: "%.2f")")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct QuickActionButton: View {
    let icon: String
    let title: String
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.title2)
                Text(title)
                    .font(.caption)
            }
            .frame(maxWidth: .infinity)
            .padding()
            .background(Color(.systemGray6))
            .cornerRadius(12)
        }
    }
}

struct CurrencyConverterView: View {
    @ObservedObject var viewModel: EnhancedWalletViewModel
    @Environment(\.dismiss) var dismiss
    @State private var fromCurrency: String = "USD"
    @State private var toCurrency: String = "NGN"
    @State private var amount: String = ""
    
    var body: some View {
        NavigationView {
            Form {
                Section("From") {
                    Picker("Currency", selection: $fromCurrency) {
                        ForEach(viewModel.availableCurrencies, id: \.self) { currency in
                            Text(currency).tag(currency)
                        }
                    }
                    TextField("Amount", text: $amount)
                        .keyboardType(.decimalPad)
                }
                
                Section("To") {
                    Picker("Currency", selection: $toCurrency) {
                        ForEach(viewModel.availableCurrencies, id: \.self) { currency in
                            Text(currency).tag(currency)
                        }
                    }
                    if let convertedAmount = viewModel.convert(amount: Double(amount) ?? 0, from: fromCurrency, to: toCurrency) {
                        Text("\(convertedAmount, specifier: "%.2f") \(toCurrency)")
                            .font(.title3)
                            .fontWeight(.bold)
                    }
                }
                
                Section {
                    Button("Convert Now") {
                        viewModel.performConversion(amount: Double(amount) ?? 0, from: fromCurrency, to: toCurrency)
                        dismiss()
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .navigationTitle("Currency Converter")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }
}

struct CurrencyTransferView: View {
    @ObservedObject var viewModel: EnhancedWalletViewModel
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationView {
            Form {
                Section("Transfer Details") {
                    Text("Instant transfer between your currency balances")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .navigationTitle("Currency Transfer")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }
}

struct WalletTransactionRow: View {
    let transaction: WalletTransaction
    
    var body: some View {
        HStack {
            Image(systemName: transaction.type == .credit ? "arrow.down.circle.fill" : "arrow.up.circle.fill")
                .foregroundColor(transaction.type == .credit ? .green : .red)
            
            VStack(alignment: .leading) {
                Text(transaction.description)
                    .font(.subheadline)
                Text(transaction.timestamp, style: .relative)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            Text("\(transaction.type == .credit ? "+" : "-")\(transaction.amount, specifier: "%.2f") \(transaction.currency)")
                .fontWeight(.medium)
                .foregroundColor(transaction.type == .credit ? .green : .red)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(8)
    }
}

class EnhancedWalletViewModel: ObservableObject {
    @Published var totalBalanceUSD: Double = 0
    @Published var totalBalancePrimary: Double = 0
    @Published var primaryCurrency = "NGN"
    @Published var currencyBalances: [CurrencyBalance] = []
    @Published var recentTransactions: [WalletTransaction] = []
    @Published var availableCurrencies: [String] = ["USD", "NGN", "GBP", "EUR"]
    @Published var selectedCurrency: CurrencyBalance?
    
    func loadWalletData() {}
    func convert(amount: Double, from: String, to: String) -> Double? { return amount * 1.5 }
    func performConversion(amount: Double, from: String, to: String) {}
    func showAddFunds() {}
    func showWithdraw() {}
}

struct CurrencyBalance: Identifiable {
    let id = UUID()
    let currency: String
    let currencyName: String
    let amount: Double
    let usdEquivalent: Double
}

struct WalletTransaction: Identifiable {
    let id = UUID()
    let description: String
    let amount: Double
    let currency: String
    let type: TransactionType
    let timestamp: Date
}

enum TransactionType {
    case credit, debit
}

import SwiftUI

struct EnhancedVirtualAccountView: View {
    @StateObject private var viewModel = VirtualAccountViewModel()
    @State private var showCreateAccount = false
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Virtual Accounts List
                ForEach(viewModel.accounts) { account in
                    VirtualAccountCard(account: account)
                }
                
                // Create New Account Button
                Button(action: { showCreateAccount = true }) {
                    Label("Create Virtual Account", systemImage: "plus.circle")
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(12)
                }
                
                // Recent Transactions
                if !viewModel.recentTransactions.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Recent Transactions")
                            .font(.headline)
                        
                        ForEach(viewModel.recentTransactions) { transaction in
                            TransactionRow(transaction: transaction)
                        }
                    }
                }
            }
            .padding()
        }
        .navigationTitle("Virtual Accounts")
        .sheet(isPresented: $showCreateAccount) {
            CreateVirtualAccountView(viewModel: viewModel)
        }
        .onAppear {
            viewModel.loadAccounts()
        }
    }
}

struct VirtualAccountCard: View {
    let account: VirtualAccountModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading) {
                    Text(account.bankName)
                        .font(.headline)
                    Text(account.accountName)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                Spacer()
                if account.isActive {
                    Text("Active")
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.green.opacity(0.2))
                        .foregroundColor(.green)
                        .cornerRadius(4)
                }
            }
            
            Divider()
            
            HStack {
                VStack(alignment: .leading) {
                    Text("Account Number")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(account.accountNumber)
                        .font(.title3)
                        .fontWeight(.bold)
                }
                Spacer()
                Button(action: {}) {
                    Image(systemName: "doc.on.doc")
                }
            }
            
            HStack {
                VStack(alignment: .leading) {
                    Text("Balance")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("\(account.currency) \(account.balance, specifier: "%.2f")")
                        .font(.title3)
                        .fontWeight(.bold)
                }
                Spacer()
                VStack(alignment: .trailing) {
                    Text("Transactions")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("\(account.transactionCount)")
                        .font(.title3)
                        .fontWeight(.bold)
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct CreateVirtualAccountView: View {
    @ObservedObject var viewModel: VirtualAccountViewModel
    @Environment(\.dismiss) var dismiss
    @State private var selectedBank: BankProvider?
    @State private var accountPurpose = ""
    
    var body: some View {
        NavigationView {
            Form {
                Section("Bank Provider") {
                    Picker("Select Bank", selection: $selectedBank) {
                        ForEach(viewModel.availableBanks) { bank in
                            Text(bank.name).tag(bank as BankProvider?)
                        }
                    }
                }
                
                Section("Account Purpose") {
                    TextField("Purpose", text: $accountPurpose)
                }
                
                Section {
                    Button("Create Account") {
                        if let bank = selectedBank {
                            viewModel.createAccount(bank: bank, purpose: accountPurpose)
                            dismiss()
                        }
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .navigationTitle("New Virtual Account")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }
}

class VirtualAccountViewModel: ObservableObject {
    @Published var accounts: [VirtualAccountModel] = []
    @Published var recentTransactions: [VirtualAccountTransaction] = []
    @Published var availableBanks: [BankProvider] = []
    
    func loadAccounts() {}
    func createAccount(bank: BankProvider, purpose: String) {}
}

struct VirtualAccountModel: Identifiable {
    let id = UUID()
    let bankName: String
    let accountName: String
    let accountNumber: String
    let currency: String
    let balance: Double
    let transactionCount: Int
    let isActive: Bool
}

struct VirtualAccountTransaction: Identifiable {
    let id = UUID()
    let amount: Double
    let sender: String
    let timestamp: Date
}

struct BankProvider: Identifiable {
    let id = UUID()
    let name: String
    let code: String
}

struct TransactionRow: View {
    let transaction: VirtualAccountTransaction
    
    var body: some View {
        HStack {
            VStack(alignment: .leading) {
                Text(transaction.sender)
                    .font(.subheadline)
                Text(transaction.timestamp, style: .relative)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Spacer()
            Text("+\(transaction.amount, specifier: "%.2f")")
                .fontWeight(.medium)
                .foregroundColor(.green)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(8)
    }
}

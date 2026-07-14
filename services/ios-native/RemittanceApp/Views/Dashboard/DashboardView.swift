import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var walletManager: WalletManager
    @EnvironmentObject var authManager: AuthenticationManager
    @State private var showSendMoney = false
    @State private var showAddFunds = false
    @State private var showQRScanner = false
    @State private var refreshing = false
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 24) {
                    // Header with user info
                    headerView
                    
                    // Total balance card
                    totalBalanceCard
                    
                    // Quick actions
                    quickActionsView
                    
                    // Currency balances
                    currencyBalancesView
                    
                    // Recent transactions
                    recentTransactionsView
                }
                .padding()
            }
            .navigationTitle("Dashboard")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: {
                        Task {
                            await refreshData()
                        }
                    }) {
                        Image(systemName: "arrow.clockwise")
                            .rotationEffect(.degrees(refreshing ? 360 : 0))
                    }
                }
            }
            .refreshable {
                await refreshData()
            }
            .task {
                await loadInitialData()
            }
            .sheet(isPresented: $showSendMoney) {
                SendMoneyView()
            }
            .sheet(isPresented: $showAddFunds) {
                AddFundsView()
            }
            .sheet(isPresented: $showQRScanner) {
                QRScannerView()
            }
        }
    }
    
    var headerView: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Welcome back,")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                Text(authManager.currentUser?.firstName ?? "User")
                    .font(.title2)
                    .fontWeight(.bold)
            }
            
            Spacer()
            
            // Profile picture placeholder
            Circle()
                .fill(Color("PrimaryColor").opacity(0.2))
                .frame(width: 50, height: 50)
                .overlay(
                    Text(authManager.currentUser?.firstName.prefix(1).uppercased() ?? "U")
                        .font(.title3)
                        .fontWeight(.semibold)
                        .foregroundColor(Color("PrimaryColor"))
                )
        }
    }
    
    var totalBalanceCard: some View {
        VStack(spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Total Balance")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.8))
                    
                    if walletManager.isLoading && walletManager.balances.isEmpty {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    } else {
                        Text("$\(walletManager.totalBalanceUSD, specifier: "%.2f")")
                            .font(.system(size: 36, weight: .bold))
                            .foregroundColor(.white)
                    }
                }
                
                Spacer()
                
                Image(systemName: "eye.slash.fill")
                    .foregroundColor(.white.opacity(0.8))
            }
            
            Divider()
                .background(Color.white.opacity(0.3))
            
            HStack(spacing: 24) {
                VStack(spacing: 4) {
                    Text("Available")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.8))
                    Text("$\(walletManager.totalBalanceUSD, specifier: "%.2f")")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.white)
                }
                
                Spacer()
                
                VStack(spacing: 4) {
                    Text("Pending")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.8))
                    Text("$0.00")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.white)
                }
            }
        }
        .padding(24)
        .background(
            LinearGradient(
                gradient: Gradient(colors: [Color("PrimaryColor"), Color("SecondaryColor")]),
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .cornerRadius(20)
        .shadow(color: Color("PrimaryColor").opacity(0.3), radius: 10, x: 0, y: 5)
    }
    
    var quickActionsView: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Quick Actions")
                .font(.headline)
            
            HStack(spacing: 16) {
                QuickActionButton(
                    icon: "paperplane.fill",
                    title: "Send",
                    color: Color("PrimaryColor")
                ) {
                    showSendMoney = true
                }
                
                QuickActionButton(
                    icon: "plus.circle.fill",
                    title: "Add Funds",
                    color: .green
                ) {
                    showAddFunds = true
                }
                
                QuickActionButton(
                    icon: "qrcode.viewfinder",
                    title: "Scan QR",
                    color: .orange
                ) {
                    showQRScanner = true
                }
                
                QuickActionButton(
                    icon: "arrow.left.arrow.right",
                    title: "Exchange",
                    color: .purple
                ) {
                    // Exchange action
                }
            }
        }
    }
    
    var currencyBalancesView: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("My Currencies")
                    .font(.headline)
                
                Spacer()
                
                NavigationLink(destination: WalletView()) {
                    Text("See All")
                        .font(.subheadline)
                        .foregroundColor(Color("PrimaryColor"))
                }
            }
            
            if walletManager.balances.isEmpty && !walletManager.isLoading {
                EmptyStateView(
                    icon: "dollarsign.circle",
                    title: "No Balances",
                    message: "Add funds to get started"
                )
            } else {
                ForEach(walletManager.balances.prefix(3)) { balance in
                    CurrencyBalanceRow(balance: balance)
                }
            }
        }
    }
    
    var recentTransactionsView: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Recent Transactions")
                    .font(.headline)
                
                Spacer()
                
                NavigationLink(destination: TransactionsView()) {
                    Text("See All")
                        .font(.subheadline)
                        .foregroundColor(Color("PrimaryColor"))
                }
            }
            
            if walletManager.transactions.isEmpty && !walletManager.isLoading {
                EmptyStateView(
                    icon: "arrow.left.arrow.right.circle",
                    title: "No Transactions",
                    message: "Your transaction history will appear here"
                )
            } else {
                ForEach(walletManager.transactions.prefix(5)) { transaction in
                    NavigationLink(destination: TransactionDetailView(transactionId: transaction.id)) {
                        TransactionRow(transaction: transaction)
                    }
                }
            }
        }
    }
    
    func loadInitialData() async {
        async let balances: () = walletManager.loadBalances()
        async let transactions: () = walletManager.loadTransactions(refresh: true)
        
        _ = await (balances, transactions)
    }
    
    func refreshData() async {
        refreshing = true
        await loadInitialData()
        try? await Task.sleep(nanoseconds: 500_000_000)
        refreshing = false
    }
}

struct QuickActionButton: View {
    let icon: String
    let title: String
    let color: Color
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            VStack(spacing: 12) {
                ZStack {
                    Circle()
                        .fill(color.opacity(0.1))
                        .frame(width: 60, height: 60)
                    
                    Image(systemName: icon)
                        .font(.title2)
                        .foregroundColor(color)
                }
                
                Text(title)
                    .font(.caption)
                    .foregroundColor(.primary)
            }
        }
        .frame(maxWidth: .infinity)
    }
}

struct CurrencyBalanceRow: View {
    let balance: CurrencyBalance
    
    var body: some View {
        HStack(spacing: 16) {
            // Currency icon
            ZStack {
                Circle()
                    .fill(Color("PrimaryColor").opacity(0.1))
                    .frame(width: 50, height: 50)
                
                Text(balance.currencySymbol)
                    .font(.title3)
                    .fontWeight(.semibold)
                    .foregroundColor(Color("PrimaryColor"))
            }
            
            // Currency info
            VStack(alignment: .leading, spacing: 4) {
                Text(balance.currencyName)
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                Text(balance.currency)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            // Amount
            VStack(alignment: .trailing, spacing: 4) {
                Text(balance.formattedAmount)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                
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

struct TransactionRow: View {
    let transaction: Transaction
    
    var body: some View {
        HStack(spacing: 16) {
            // Transaction icon
            ZStack {
                Circle()
                    .fill(transaction.statusColor.opacity(0.1))
                    .frame(width: 50, height: 50)
                
                Image(systemName: transaction.typeIcon)
                    .foregroundColor(transaction.statusColor)
            }
            
            // Transaction info
            VStack(alignment: .leading, spacing: 4) {
                Text(transaction.recipient ?? transaction.sender ?? "Transaction")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .lineLimit(1)
                
                Text(formatDate(transaction.createdAt))
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            // Amount and status
            VStack(alignment: .trailing, spacing: 4) {
                Text("\(transaction.type.lowercased() == "sent" ? "-" : "+")\(transaction.currency) \(transaction.amount, specifier: "%.2f")")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(transaction.type.lowercased() == "sent" ? .red : .green)
                
                Text(transaction.status.capitalized)
                    .font(.caption)
                    .foregroundColor(transaction.statusColor)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
    
    func formatDate(_ dateString: String) -> String {
        // Simplified date formatting
        return "Today"
    }
}

struct EmptyStateView: View {
    let icon: String
    let title: String
    let message: String
    
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: icon)
                .font(.system(size: 60))
                .foregroundColor(.secondary)
            
            VStack(spacing: 8) {
                Text(title)
                    .font(.headline)
                
                Text(message)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(40)
    }
}

// Placeholder views for navigation
struct SendMoneyView: View {
    var body: some View {
        Text("Send Money View")
    }
}

struct AddFundsView: View {
    var body: some View {
        Text("Add Funds View")
    }
}

struct QRScannerView: View {
    var body: some View {
        Text("QR Scanner View")
    }
}

struct WalletView: View {
    var body: some View {
        Text("Wallet View")
    }
}

struct TransactionsView: View {
    var body: some View {
        Text("Transactions View")
    }
}

struct TransactionDetailView: View {
    let transactionId: String
    
    var body: some View {
        Text("Transaction Detail: \(transactionId)")
    }
}

#Preview {
    DashboardView()
        .environmentObject(WalletManager())
        .environmentObject(AuthenticationManager())
}

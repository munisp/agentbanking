import SwiftUI

struct ContentView: View {
    @EnvironmentObject var authManager: AuthManager
    
    var body: some View {
        Group {
            if authManager.isAuthenticated {
                MainTabView()
            } else {
                LoginView()
            }
        }
    }
}

struct MainTabView: View {
    @State private var selectedTab = 0
    
    var body: some View {
        TabView(selection: $selectedTab) {
            DashboardView()
                .tabItem {
                    Image(systemName: "house.fill")
                    Text("Home")
                }
                .tag(0)
            
            WalletView()
                .tabItem {
                    Image(systemName: "wallet.pass.fill")
                    Text("Wallet")
                }
                .tag(1)
            
            TransactionHistoryView()
                .tabItem {
                    Image(systemName: "list.bullet.rectangle")
                    Text("Transactions")
                }
                .tag(2)
            
            CardsView()
                .tabItem {
                    Image(systemName: "creditcard.fill")
                    Text("Cards")
                }
                .tag(3)
            
            SettingsView()
                .tabItem {
                    Image(systemName: "gearshape.fill")
                    Text("Settings")
                }
                .tag(4)
        }
        .accentColor(.blue)
    }
}

struct DashboardView: View {
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    // Balance Card
                    BalanceCard()
                    
                    // Quick Actions
                    QuickActionsView()
                    
                    // Exchange Rates
                    ExchangeRatesCard()
                    
                    // Recent Transactions
                    RecentTransactionsCard()
                }
                .padding()
            }
            .navigationTitle("Dashboard")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    NavigationLink(destination: ProfileView()) {
                        Image(systemName: "person.circle.fill")
                            .font(.title2)
                    }
                }
            }
        }
    }
}

struct BalanceCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Total Balance")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.8))
            
            Text("NGN 250,000.00")
                .font(.system(size: 32, weight: .bold))
                .foregroundColor(.white)
            
            HStack(spacing: 12) {
                NavigationLink(destination: EnhancedWalletView()) {
                    Text("View Wallet")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .background(Color.white.opacity(0.2))
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }
                
                NavigationLink(destination: MultiChannelPaymentView()) {
                    Text("Send Money")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .background(Color.white)
                        .foregroundColor(.blue)
                        .cornerRadius(8)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(24)
        .background(
            LinearGradient(
                gradient: Gradient(colors: [Color.blue, Color.blue.opacity(0.8)]),
                startPoint: .leading,
                endPoint: .trailing
            )
        )
        .cornerRadius(16)
    }
}

struct QuickActionsView: View {
    let actions = [
        ("Send", "arrow.up.circle.fill", Color.blue),
        ("Receive", "arrow.down.circle.fill", Color.green),
        ("Stablecoin", "bitcoinsign.circle.fill", Color.purple),
        ("Bills", "doc.text.fill", Color.orange),
        ("Batch", "doc.on.doc.fill", Color.indigo),
        ("Savings", "target", Color.teal),
        ("FX Alerts", "bell.badge.fill", Color.pink),
        ("Track", "location.fill", Color.cyan)
    ]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Quick Actions")
                .font(.headline)
            
            HStack(spacing: 16) {
                ForEach(actions, id: \.0) { action in
                    NavigationLink(destination: destinationView(for: action.0)) {
                        VStack(spacing: 8) {
                            Image(systemName: action.1)
                                .font(.title2)
                                .foregroundColor(action.2)
                                .frame(width: 50, height: 50)
                                .background(action.2.opacity(0.1))
                                .cornerRadius(12)
                            
                            Text(action.0)
                                .font(.caption)
                                .foregroundColor(.primary)
                        }
                    }
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 5, x: 0, y: 2)
    }
    
    @ViewBuilder
    func destinationView(for action: String) -> some View {
        switch action {
        case "Send":
            MultiChannelPaymentView()
        case "Receive":
            ReceiveMoneyView()
        case "Stablecoin":
            StablecoinView()
        case "Bills":
            AirtimeBillPaymentView()
        case "Batch":
            BatchPaymentsView()
        case "Savings":
            SavingsGoalsView()
        case "FX Alerts":
            FXAlertsView()
        case "Track":
            TransferTrackingView(transferId: "demo-transfer")
        default:
            EmptyView()
        }
    }
}

struct ExchangeRatesCard: View {
    let rates = [
        ("USD/NGN", "1,550.00"),
        ("GBP/NGN", "1,980.00"),
        ("EUR/NGN", "1,700.00"),
        ("GHS/NGN", "125.00")
    ]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Exchange Rates")
                    .font(.headline)
                Spacer()
                NavigationLink(destination: EnhancedExchangeRatesView()) {
                    Text("View all")
                        .font(.subheadline)
                        .foregroundColor(.blue)
                }
            }
            
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(rates, id: \.0) { rate in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(rate.0)
                                .font(.caption)
                                .foregroundColor(.secondary)
                            Text(rate.1)
                                .font(.headline)
                        }
                        .padding(12)
                        .background(Color(.secondarySystemBackground))
                        .cornerRadius(8)
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 5, x: 0, y: 2)
    }
}

struct RecentTransactionsCard: View {
    let transactions = [
        ("Sent to John Doe", "-NGN 50,000", false),
        ("Received from Jane", "+NGN 25,000", true),
        ("MTN Airtime", "-NGN 2,000", false)
    ]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Recent Transactions")
                    .font(.headline)
                Spacer()
                NavigationLink(destination: TransactionHistoryView()) {
                    Text("View all")
                        .font(.subheadline)
                        .foregroundColor(.blue)
                }
            }
            
            ForEach(transactions, id: \.0) { tx in
                HStack {
                    Image(systemName: tx.2 ? "arrow.down.circle.fill" : "arrow.up.circle.fill")
                        .foregroundColor(tx.2 ? .green : .blue)
                        .font(.title2)
                    
                    Text(tx.0)
                        .font(.subheadline)
                    
                    Spacer()
                    
                    Text(tx.1)
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(tx.2 ? .green : .primary)
                }
                .padding(.vertical, 8)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 5, x: 0, y: 2)
    }
}

#Preview {
    ContentView()
        .environmentObject(AuthManager())
        .environmentObject(NetworkManager())
}

import SwiftUI

// MARK: - Data Models
struct StablecoinBalance: Identifiable {
    let id = UUID()
    let chain: String
    let stablecoin: String
    let balance: String
    let pendingBalance: String
}

struct StablecoinTransaction: Identifiable {
    let id: String
    let type: String
    let chain: String
    let stablecoin: String
    let amount: String
    let status: String
    let createdAt: String
    let txHash: String?
}

struct Chain: Identifiable {
    let id: String
    let name: String
    let symbol: String
    let fee: String
    let color: Color
}

struct Stablecoin: Identifiable {
    let id: String
    let name: String
    let symbol: String
    let color: Color
}

// MARK: - Configuration
let chains: [Chain] = [
    Chain(id: "tron", name: "Tron", symbol: "TRX", fee: "$1", color: .red),
    Chain(id: "ethereum", name: "Ethereum", symbol: "ETH", fee: "$5", color: .blue),
    Chain(id: "solana", name: "Solana", symbol: "SOL", fee: "$0.01", color: .purple),
    Chain(id: "polygon", name: "Polygon", symbol: "MATIC", fee: "$0.10", color: .indigo),
    Chain(id: "bsc", name: "BNB Chain", symbol: "BNB", fee: "$0.30", color: .yellow)
]

let stablecoins: [Stablecoin] = [
    Stablecoin(id: "usdt", name: "Tether", symbol: "USDT", color: .green),
    Stablecoin(id: "usdc", name: "USD Coin", symbol: "USDC", color: .blue),
    Stablecoin(id: "pyusd", name: "PayPal USD", symbol: "PYUSD", color: Color(red: 0.15, green: 0.39, blue: 0.92)),
    Stablecoin(id: "dai", name: "Dai", symbol: "DAI", color: .yellow)
]

// MARK: - Main View
struct StablecoinView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var selectedTab = 0
    @State private var isOnline = true
    
    let tabs = ["Wallet", "Send", "Receive", "Convert", "Buy/Sell"]
    
    // Sample data
    let balances: [StablecoinBalance] = [
        StablecoinBalance(chain: "tron", stablecoin: "usdt", balance: "1,250.00", pendingBalance: "50.00"),
        StablecoinBalance(chain: "ethereum", stablecoin: "usdc", balance: "500.00", pendingBalance: "0"),
        StablecoinBalance(chain: "solana", stablecoin: "usdt", balance: "200.00", pendingBalance: "0")
    ]
    
    let transactions: [StablecoinTransaction] = [
        StablecoinTransaction(id: "1", type: "deposit", chain: "tron", stablecoin: "usdt", amount: "500.00", status: "completed", createdAt: "2024-01-15", txHash: nil),
        StablecoinTransaction(id: "2", type: "withdrawal", chain: "ethereum", stablecoin: "usdc", amount: "100.00", status: "confirming", createdAt: "2024-01-14", txHash: nil),
        StablecoinTransaction(id: "3", type: "conversion", chain: "solana", stablecoin: "usdt", amount: "200.00", status: "completed", createdAt: "2024-01-13", txHash: nil)
    ]
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 0) {
                    // Header with gradient
                    headerView
                    
                    // Tab selector
                    tabSelector
                    
                    // Content based on selected tab
                    switch selectedTab {
                    case 0:
                        walletContent
                    case 1:
                        sendContent
                    case 2:
                        receiveContent
                    case 3:
                        convertContent
                    case 4:
                        rampContent
                    default:
                        walletContent
                    }
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button(action: { dismiss() }) {
                        Image(systemName: "chevron.left")
                            .foregroundColor(.white)
                    }
                }
                ToolbarItem(placement: .principal) {
                    Text("Stablecoin Wallet")
                        .font(.headline)
                        .foregroundColor(.white)
                }
            }
            .toolbarBackground(
                LinearGradient(colors: [Color.blue, Color.purple], startPoint: .leading, endPoint: .trailing),
                for: .navigationBar
            )
            .toolbarBackground(.visible, for: .navigationBar)
        }
    }
    
    // MARK: - Header View
    private var headerView: some View {
        ZStack {
            LinearGradient(colors: [Color.blue, Color.purple], startPoint: .leading, endPoint: .trailing)
            
            VStack(spacing: 8) {
                Text("Total Balance")
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.8))
                
                Text("$1,950.00")
                    .font(.system(size: 36, weight: .bold))
                    .foregroundColor(.white)
                
                HStack(spacing: 4) {
                    Image(systemName: "chart.line.uptrend.xyaxis")
                        .font(.caption)
                    Text("ML-optimized rates active")
                        .font(.caption)
                }
                .foregroundColor(.white.opacity(0.8))
                
                // Quick Actions
                HStack(spacing: 20) {
                    quickActionButton(icon: "arrow.up", label: "Send") { selectedTab = 1 }
                    quickActionButton(icon: "arrow.down", label: "Receive") { selectedTab = 2 }
                    quickActionButton(icon: "arrow.left.arrow.right", label: "Convert") { selectedTab = 3 }
                    quickActionButton(icon: "globe", label: "Buy/Sell") { selectedTab = 4 }
                }
                .padding(.top, 16)
            }
            .padding(.vertical, 24)
        }
    }
    
    private func quickActionButton(icon: String, label: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.title3)
                Text(label)
                    .font(.caption)
            }
            .foregroundColor(.white)
            .padding(12)
            .background(Color.white.opacity(0.2))
            .cornerRadius(12)
        }
    }
    
    // MARK: - Tab Selector
    private var tabSelector: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 0) {
                ForEach(Array(tabs.enumerated()), id: \.offset) { index, tab in
                    Button(action: { selectedTab = index }) {
                        Text(tab)
                            .font(.subheadline)
                            .fontWeight(selectedTab == index ? .semibold : .regular)
                            .foregroundColor(selectedTab == index ? .blue : .gray)
                            .padding(.horizontal, 16)
                            .padding(.vertical, 12)
                            .background(
                                VStack {
                                    Spacer()
                                    if selectedTab == index {
                                        Rectangle()
                                            .fill(Color.blue)
                                            .frame(height: 2)
                                    }
                                }
                            )
                    }
                }
            }
        }
        .background(Color(.systemBackground))
    }
    
    // MARK: - Wallet Content
    private var walletContent: some View {
        VStack(spacing: 16) {
            // Balances
            balancesCard
            
            // Transactions
            transactionsCard
            
            // Features
            featuresSection
        }
        .padding()
    }
    
    private var balancesCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Your Balances")
                .font(.headline)
            
            ForEach(balances) { balance in
                balanceRow(balance)
                if balance.id != balances.last?.id {
                    Divider()
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.05), radius: 8)
    }
    
    private func balanceRow(_ balance: StablecoinBalance) -> some View {
        let stablecoin = stablecoins.first { $0.id == balance.stablecoin }
        let chain = chains.first { $0.id == balance.chain }
        
        return HStack {
            Circle()
                .fill(stablecoin?.color ?? .gray)
                .frame(width: 40, height: 40)
                .overlay(
                    Text(stablecoin?.symbol.prefix(1) ?? "?")
                        .font(.headline)
                        .foregroundColor(.white)
                )
            
            VStack(alignment: .leading, spacing: 2) {
                Text(stablecoin?.symbol ?? balance.stablecoin.uppercased())
                    .font(.subheadline)
                    .fontWeight(.medium)
                Text(chain?.name ?? balance.chain)
                    .font(.caption)
                    .foregroundColor(.gray)
            }
            
            Spacer()
            
            VStack(alignment: .trailing, spacing: 2) {
                Text("$\(balance.balance)")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                if balance.pendingBalance != "0" {
                    Text("+$\(balance.pendingBalance) pending")
                        .font(.caption)
                        .foregroundColor(.yellow)
                }
            }
        }
        .padding(.vertical, 4)
    }
    
    private var transactionsCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Recent Transactions")
                .font(.headline)
            
            ForEach(transactions) { tx in
                transactionRow(tx)
                if tx.id != transactions.last?.id {
                    Divider()
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.05), radius: 8)
    }
    
    private func transactionRow(_ tx: StablecoinTransaction) -> some View {
        let isDeposit = tx.type == "deposit"
        
        return HStack {
            Circle()
                .fill(isDeposit ? Color.green.opacity(0.2) : Color.red.opacity(0.2))
                .frame(width: 40, height: 40)
                .overlay(
                    Image(systemName: isDeposit ? "arrow.down" : "arrow.up")
                        .foregroundColor(isDeposit ? .green : .red)
                )
            
            VStack(alignment: .leading, spacing: 2) {
                Text(tx.type.capitalized)
                    .font(.subheadline)
                    .fontWeight(.medium)
                Text(tx.createdAt)
                    .font(.caption)
                    .foregroundColor(.gray)
            }
            
            Spacer()
            
            VStack(alignment: .trailing, spacing: 2) {
                Text("\(isDeposit ? "+" : "-")$\(tx.amount)")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(isDeposit ? .green : .red)
                statusChip(tx.status)
            }
        }
        .padding(.vertical, 4)
    }
    
    private func statusChip(_ status: String) -> some View {
        let (bgColor, textColor): (Color, Color) = {
            switch status {
            case "completed": return (Color.green.opacity(0.2), Color.green)
            case "confirming": return (Color.yellow.opacity(0.2), Color.orange)
            case "pending": return (Color.blue.opacity(0.2), Color.blue)
            case "failed": return (Color.red.opacity(0.2), Color.red)
            default: return (Color.gray.opacity(0.2), Color.gray)
            }
        }()
        
        return Text(status)
            .font(.caption2)
            .foregroundColor(textColor)
            .padding(.horizontal, 8)
            .padding(.vertical, 2)
            .background(bgColor)
            .cornerRadius(8)
    }
    
    private var featuresSection: some View {
        VStack(spacing: 12) {
            HStack(spacing: 12) {
                featureCard(icon: "bolt.fill", title: "Instant Transfers", subtitle: "Send in seconds", color: .yellow)
                featureCard(icon: "shield.fill", title: "Secure", subtitle: "Multi-chain security", color: .green)
            }
            HStack(spacing: 12) {
                featureCard(icon: "chart.line.uptrend.xyaxis", title: "ML Rates", subtitle: "AI-optimized timing", color: .blue)
                featureCard(icon: "wifi.slash", title: "Offline Ready", subtitle: "Queue when offline", color: .purple)
            }
        }
    }
    
    private func featureCard(icon: String, title: String, subtitle: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(color)
            Text(title)
                .font(.subheadline)
                .fontWeight(.medium)
            Text(subtitle)
                .font(.caption)
                .foregroundColor(.gray)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.05), radius: 8)
    }
    
    // MARK: - Send Content
    private var sendContent: some View {
        SendStablecoinView()
    }
    
    // MARK: - Receive Content
    private var receiveContent: some View {
        ReceiveStablecoinView()
    }
    
    // MARK: - Convert Content
    private var convertContent: some View {
        ConvertStablecoinView()
    }
    
    // MARK: - Ramp Content
    private var rampContent: some View {
        RampStablecoinView()
    }
}

// MARK: - Send Stablecoin View
struct SendStablecoinView: View {
    @State private var selectedChain = chains[0]
    @State private var selectedStablecoin = stablecoins[0]
    @State private var amount = ""
    @State private var address = ""
    
    var body: some View {
        VStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 16) {
                Text("Send Stablecoin")
                    .font(.headline)
                
                // Network Selection
                Text("Network")
                    .font(.subheadline)
                    .foregroundColor(.gray)
                
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(chains.prefix(3)) { chain in
                            Button(action: { selectedChain = chain }) {
                                Text(chain.name)
                                    .font(.caption)
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 8)
                                    .background(selectedChain.id == chain.id ? Color.blue : Color.gray.opacity(0.2))
                                    .foregroundColor(selectedChain.id == chain.id ? .white : .primary)
                                    .cornerRadius(8)
                            }
                        }
                    }
                }
                
                // Stablecoin Selection
                Text("Stablecoin")
                    .font(.subheadline)
                    .foregroundColor(.gray)
                
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(stablecoins.prefix(3)) { coin in
                            Button(action: { selectedStablecoin = coin }) {
                                Text(coin.symbol)
                                    .font(.caption)
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 8)
                                    .background(selectedStablecoin.id == coin.id ? Color.blue : Color.gray.opacity(0.2))
                                    .foregroundColor(selectedStablecoin.id == coin.id ? .white : .primary)
                                    .cornerRadius(8)
                            }
                        }
                    }
                }
                
                // Amount
                VStack(alignment: .leading, spacing: 4) {
                    Text("Amount")
                        .font(.subheadline)
                        .foregroundColor(.gray)
                    HStack {
                        Text("$")
                        TextField("0.00", text: $amount)
                            .keyboardType(.decimalPad)
                    }
                    .padding()
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(8)
                }
                
                // Address
                VStack(alignment: .leading, spacing: 4) {
                    Text("Recipient Address")
                        .font(.subheadline)
                        .foregroundColor(.gray)
                    TextField("Enter wallet address", text: $address)
                        .padding()
                        .background(Color.gray.opacity(0.1))
                        .cornerRadius(8)
                }
                
                // Fee info
                HStack {
                    Text("Network Fee")
                        .font(.subheadline)
                        .foregroundColor(.gray)
                    Spacer()
                    Text(selectedChain.fee)
                        .font(.subheadline)
                }
                
                Button(action: { /* Send */ }) {
                    Text("Send Now")
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(!amount.isEmpty && !address.isEmpty ? Color.blue : Color.gray)
                        .cornerRadius(12)
                }
                .disabled(amount.isEmpty || address.isEmpty)
            }
            .padding()
            .background(Color(.systemBackground))
            .cornerRadius(16)
            .shadow(color: .black.opacity(0.05), radius: 8)
        }
        .padding()
    }
}

// MARK: - Receive Stablecoin View
struct ReceiveStablecoinView: View {
    let addresses = [
        ("tron", "TN3W4H6rK2ce4vX9YnFQHwKENnHjoxb3m9"),
        ("ethereum", "0x742d35Cc6634C0532925a3b844Bc9e7595f5bE21"),
        ("solana", "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d")
    ]
    
    var body: some View {
        VStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 16) {
                Text("Receive Stablecoin")
                    .font(.headline)
                
                ForEach(addresses, id: \.0) { chainId, address in
                    let chain = chains.first { $0.id == chainId }
                    addressCard(chain: chain, address: address)
                }
            }
            .padding()
            .background(Color(.systemBackground))
            .cornerRadius(16)
            .shadow(color: .black.opacity(0.05), radius: 8)
            
            // Tips
            VStack(alignment: .leading, spacing: 8) {
                Text("Tips for Receiving")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(.blue)
                
                Text("Always verify the network matches the sender's. Tron (TRC20) has the lowest fees. Deposits are confirmed automatically.")
                    .font(.caption)
                    .foregroundColor(.blue.opacity(0.8))
            }
            .padding()
            .background(Color.blue.opacity(0.1))
            .cornerRadius(12)
        }
        .padding()
    }
    
    private func addressCard(chain: Chain?, address: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(chain?.name ?? "Unknown")
                    .font(.subheadline)
                    .fontWeight(.medium)
                Spacer()
                Button(action: {
                    UIPasteboard.general.string = address
                }) {
                    Image(systemName: "doc.on.doc")
                        .font(.caption)
                        .foregroundColor(.blue)
                }
            }
            
            Text(address)
                .font(.caption)
                .foregroundColor(.gray)
                .padding(8)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.gray.opacity(0.1))
                .cornerRadius(8)
            
            Text("Supports: USDT, USDC")
                .font(.caption2)
                .foregroundColor(.gray)
        }
        .padding()
        .background(Color.gray.opacity(0.05))
        .cornerRadius(12)
    }
}

// MARK: - Convert Stablecoin View
struct ConvertStablecoinView: View {
    @State private var fromStablecoin = stablecoins[0]
    @State private var toStablecoin = stablecoins[1]
    @State private var amount = ""
    @State private var showQuote = false
    
    var body: some View {
        VStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 16) {
                Text("Convert Stablecoin")
                    .font(.headline)
                
                // From
                Text("From")
                    .font(.subheadline)
                    .foregroundColor(.gray)
                
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(stablecoins) { coin in
                            Button(action: { fromStablecoin = coin }) {
                                Text(coin.symbol)
                                    .font(.caption)
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 8)
                                    .background(fromStablecoin.id == coin.id ? Color.blue : Color.gray.opacity(0.2))
                                    .foregroundColor(fromStablecoin.id == coin.id ? .white : .primary)
                                    .cornerRadius(8)
                            }
                        }
                    }
                }
                
                // Amount
                VStack(alignment: .leading, spacing: 4) {
                    Text("Amount")
                        .font(.subheadline)
                        .foregroundColor(.gray)
                    HStack {
                        Text("$")
                        TextField("0.00", text: $amount)
                            .keyboardType(.decimalPad)
                            .onChange(of: amount) { _ in showQuote = false }
                    }
                    .padding()
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(8)
                }
                
                // Swap button
                HStack {
                    Spacer()
                    Button(action: {
                        let temp = fromStablecoin
                        fromStablecoin = toStablecoin
                        toStablecoin = temp
                    }) {
                        Image(systemName: "arrow.up.arrow.down")
                            .padding(8)
                            .background(Color.gray.opacity(0.1))
                            .cornerRadius(8)
                    }
                    Spacer()
                }
                
                // To
                Text("To")
                    .font(.subheadline)
                    .foregroundColor(.gray)
                
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(stablecoins) { coin in
                            Button(action: { toStablecoin = coin }) {
                                Text(coin.symbol)
                                    .font(.caption)
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 8)
                                    .background(toStablecoin.id == coin.id ? Color.blue : Color.gray.opacity(0.2))
                                    .foregroundColor(toStablecoin.id == coin.id ? .white : .primary)
                                    .cornerRadius(8)
                            }
                        }
                    }
                }
                
                // Get Quote button
                if !showQuote {
                    Button(action: { showQuote = true }) {
                        Text("Get Quote")
                            .font(.subheadline)
                            .foregroundColor(.blue)
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.blue.opacity(0.1))
                            .cornerRadius(12)
                    }
                    .disabled(amount.isEmpty)
                }
                
                // Quote display
                if showQuote && !amount.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("You'll receive")
                                .foregroundColor(.gray)
                            Spacer()
                            Text("$\(amount)")
                                .font(.title3)
                                .fontWeight(.bold)
                        }
                        
                        HStack {
                            Text("Rate")
                                .font(.caption)
                                .foregroundColor(.gray)
                            Spacer()
                            Text("1 \(fromStablecoin.symbol) = 0.9998 \(toStablecoin.symbol)")
                                .font(.caption)
                        }
                        
                        HStack {
                            Text("Fee")
                                .font(.caption)
                                .foregroundColor(.gray)
                            Spacer()
                            Text("$0.50")
                                .font(.caption)
                        }
                        
                        HStack(spacing: 4) {
                            Image(systemName: "chart.line.uptrend.xyaxis")
                                .font(.caption2)
                            Text("ML-optimized rate applied")
                                .font(.caption2)
                        }
                        .foregroundColor(.green)
                    }
                    .padding()
                    .background(Color.green.opacity(0.1))
                    .cornerRadius(12)
                }
                
                Button(action: { /* Convert */ }) {
                    Text("Convert Now")
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(showQuote && !amount.isEmpty ? Color.blue : Color.gray)
                        .cornerRadius(12)
                }
                .disabled(!showQuote || amount.isEmpty)
            }
            .padding()
            .background(Color(.systemBackground))
            .cornerRadius(16)
            .shadow(color: .black.opacity(0.05), radius: 8)
        }
        .padding()
    }
}

// MARK: - Ramp Stablecoin View
struct RampStablecoinView: View {
    @State private var isOnRamp = true
    @State private var selectedFiat = "NGN"
    @State private var amount = ""
    @State private var selectedStablecoin = stablecoins[0]
    
    let fiats = [("NGN", "Nigerian Naira"), ("USD", "US Dollar"), ("EUR", "Euro"), ("GBP", "British Pound")]
    
    var currencySymbol: String {
        switch selectedFiat {
        case "NGN": return "₦"
        case "EUR": return "€"
        case "GBP": return "£"
        default: return "$"
        }
    }
    
    var body: some View {
        VStack(spacing: 16) {
            VStack(spacing: 0) {
                // Toggle
                HStack(spacing: 0) {
                    Button(action: { isOnRamp = true }) {
                        Text("Buy Stablecoin")
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(isOnRamp ? .white : .gray)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(isOnRamp ? Color.blue : Color.clear)
                            .cornerRadius(12)
                    }
                    
                    Button(action: { isOnRamp = false }) {
                        Text("Sell Stablecoin")
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(!isOnRamp ? .white : .gray)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(!isOnRamp ? Color.blue : Color.clear)
                            .cornerRadius(12)
                    }
                }
                .padding(4)
                .background(Color.gray.opacity(0.1))
                .cornerRadius(16)
                
                VStack(alignment: .leading, spacing: 16) {
                    Text(isOnRamp ? "Buy Stablecoin with Fiat" : "Sell Stablecoin for Fiat")
                        .font(.headline)
                        .padding(.top, 16)
                    
                    // Fiat selection
                    Text(isOnRamp ? "Pay with" : "Receive in")
                        .font(.subheadline)
                        .foregroundColor(.gray)
                    
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(fiats.prefix(3), id: \.0) { code, _ in
                                Button(action: { selectedFiat = code }) {
                                    Text(code)
                                        .font(.caption)
                                        .padding(.horizontal, 12)
                                        .padding(.vertical, 8)
                                        .background(selectedFiat == code ? Color.blue : Color.gray.opacity(0.2))
                                        .foregroundColor(selectedFiat == code ? .white : .primary)
                                        .cornerRadius(8)
                                }
                            }
                        }
                    }
                    
                    // Amount
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Amount")
                            .font(.subheadline)
                            .foregroundColor(.gray)
                        HStack {
                            Text(currencySymbol)
                            TextField("0.00", text: $amount)
                                .keyboardType(.decimalPad)
                        }
                        .padding()
                        .background(Color.gray.opacity(0.1))
                        .cornerRadius(8)
                    }
                    
                    // Stablecoin selection
                    Text(isOnRamp ? "Receive" : "Sell")
                        .font(.subheadline)
                        .foregroundColor(.gray)
                    
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(stablecoins.prefix(3)) { coin in
                                Button(action: { selectedStablecoin = coin }) {
                                    Text(coin.symbol)
                                        .font(.caption)
                                        .padding(.horizontal, 12)
                                        .padding(.vertical, 8)
                                        .background(selectedStablecoin.id == coin.id ? Color.blue : Color.gray.opacity(0.2))
                                        .foregroundColor(selectedStablecoin.id == coin.id ? .white : .primary)
                                        .cornerRadius(8)
                                }
                            }
                        }
                    }
                    
                    // Rate info
                    VStack(spacing: 8) {
                        HStack {
                            Text("Current Rate")
                                .font(.caption)
                                .foregroundColor(.gray)
                            Spacer()
                            Text(rateText)
                                .font(.caption)
                        }
                        HStack {
                            Text("Fee")
                                .font(.caption)
                                .foregroundColor(.gray)
                            Spacer()
                            Text("1%")
                                .font(.caption)
                        }
                    }
                    .padding()
                    .background(Color.gray.opacity(0.05))
                    .cornerRadius(8)
                    
                    Button(action: { /* Process */ }) {
                        Text(isOnRamp ? "Buy Now" : "Sell Now")
                            .font(.headline)
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(!amount.isEmpty ? Color.blue : Color.gray)
                            .cornerRadius(12)
                    }
                    .disabled(amount.isEmpty)
                }
            }
            .padding()
            .background(Color(.systemBackground))
            .cornerRadius(16)
            .shadow(color: .black.opacity(0.05), radius: 8)
            
            // Payment methods
            VStack(alignment: .leading, spacing: 12) {
                Text("Payment Methods")
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                paymentMethodRow(icon: "building.columns", title: "Bank Transfer", subtitle: "Instant for NGN, 1-2 days for others")
                paymentMethodRow(icon: "creditcard", title: "Debit/Credit Card", subtitle: "Instant, 2.5% fee")
                paymentMethodRow(icon: "iphone", title: "Mobile Money", subtitle: "M-Pesa, MTN MoMo, Airtel Money")
            }
            .padding()
            .background(Color(.systemBackground))
            .cornerRadius(16)
            .shadow(color: .black.opacity(0.05), radius: 8)
        }
        .padding()
    }
    
    private var rateText: String {
        switch selectedFiat {
        case "NGN": return "1 USDT = ₦1,650"
        case "EUR": return "1 USDT = €0.92"
        case "GBP": return "1 USDT = £0.79"
        default: return "1 USDT = $1.00"
        }
    }
    
    private func paymentMethodRow(icon: String, title: String, subtitle: String) -> some View {
        HStack(spacing: 12) {
            Circle()
                .fill(Color.gray.opacity(0.1))
                .frame(width: 40, height: 40)
                .overlay(
                    Image(systemName: icon)
                        .foregroundColor(.gray)
                )
            
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.subheadline)
                    .fontWeight(.medium)
                Text(subtitle)
                    .font(.caption)
                    .foregroundColor(.gray)
            }
        }
    }
}

// MARK: - Preview
struct StablecoinView_Previews: PreviewProvider {
    static var previews: some View {
        StablecoinView()
    }
}

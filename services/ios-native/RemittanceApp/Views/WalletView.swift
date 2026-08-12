import SwiftUI

/// Wallet balance as reported by the backend.
struct WalletBalance: Decodable {
    let currency: String
    let balance: Double

    enum CodingKeys: String, CodingKey {
        case currency
        case balance
        case availableBalance
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        currency = try c.decodeIfPresent(String.self, forKey: .currency) ?? ""
        if let b = try c.decodeIfPresent(Double.self, forKey: .balance) {
            balance = b
        } else if let b = try c.decodeIfPresent(Double.self, forKey: .availableBalance) {
            balance = b
        } else {
            throw DecodingError.keyNotFound(
                CodingKeys.balance,
                .init(codingPath: c.codingPath, debugDescription: "No balance field in wallet balance payload")
            )
        }
    }
}

struct WalletView: View {
    @State private var balance: Double?
    @State private var balanceCurrency: String = ""
    @State private var showBalance = true
    @State private var transactions: [WalletTransaction] = []
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    // Balance Card
                    ZStack {
                        LinearGradient(
                            gradient: Gradient(colors: [Color.purple, Color.blue]),
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )

                        VStack(spacing: 20) {
                            HStack {
                                VStack(alignment: .leading, spacing: 8) {
                                    Text("Total Balance")
                                        .font(.subheadline)
                                        .foregroundColor(.white.opacity(0.8))

                                    if isLoading {
                                        ProgressView()
                                            .tint(.white)
                                    } else if let balance {
                                        Text(showBalance ? String(format: "%@ %.2f", balanceCurrency, balance) : "\u{2022}\u{2022}\u{2022}\u{2022}\u{2022}\u{2022}")
                                            .font(.system(size: 36, weight: .bold))
                                            .foregroundColor(.white)
                                    } else {
                                        Text("Balance unavailable")
                                            .font(.headline)
                                            .foregroundColor(.white)
                                    }
                                }

                                Spacer()

                                Button(action: { showBalance.toggle() }) {
                                    Image(systemName: showBalance ? "eye.fill" : "eye.slash.fill")
                                        .foregroundColor(.white)
                                        .font(.title3)
                                }
                            }

                            HStack(spacing: 15) {
                                WalletActionButton(icon: "arrow.up.right", title: "Send")
                                WalletActionButton(icon: "arrow.down.left", title: "Receive")
                            }
                        }
                        .padding(24)
                    }
                    .frame(height: 200)
                    .cornerRadius(20)
                    .shadow(color: Color.black.opacity(0.2), radius: 10, x: 0, y: 5)

                    if let errorMessage {
                        Text(errorMessage)
                            .font(.caption)
                            .foregroundColor(.red)
                            .padding(.horizontal)
                    }

                    // Recent Transactions
                    VStack(alignment: .leading, spacing: 15) {
                        Text("Recent Transactions")
                            .font(.headline)

                        if transactions.isEmpty && !isLoading {
                            Text(errorMessage == nil ? "No transactions yet." : "Could not load transactions.")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        } else {
                            ForEach(transactions) { transaction in
                                TransactionRow(transaction: transaction)
                            }
                        }
                    }
                    .padding()
                    .background(Color(.systemBackground))
                    .cornerRadius(16)
                    .shadow(color: Color.black.opacity(0.05), radius: 5, x: 0, y: 2)
                }
                .padding()
            }
            .navigationTitle("My Wallet")
        }
        .task {
            await loadWallet()
        }
    }

    /// Loads the real wallet balance and recent transactions from the backend.
    /// Nothing is displayed until the server responds; failures are surfaced.
    private func loadWallet() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            let balances: [WalletBalance] = try await APIClient.shared.request(.walletBalances)
            if let primary = balances.first {
                balance = primary.balance
                balanceCurrency = primary.currency
            }
        } catch {
            errorMessage = "Could not load balance: \(error.localizedDescription)"
            return
        }

        do {
            transactions = try await APIClient.shared.request(.transactions)
        } catch {
            errorMessage = "Could not load transactions: \(error.localizedDescription)"
        }
    }
}

struct WalletTransaction: Identifiable, Decodable {
    let id = UUID()
    let type: TransactionType
    let amount: Double
    let counterparty: String
    let date: Date

    enum TransactionType: String, Decodable {
        case sent, received
    }

    enum CodingKeys: String, CodingKey {
        case type, amount, counterparty, date
    }

    init(type: TransactionType, amount: Double, counterparty: String, date: Date) {
        self.type = type
        self.amount = amount
        self.counterparty = counterparty
        self.date = date
    }

    /// Decodes server payloads, accepting ISO-8601 strings or epoch seconds
    /// for the date so a malformed clock never yields fabricated rows.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        type = try c.decode(TransactionType.self, forKey: .type)
        amount = try c.decode(Double.self, forKey: .amount)
        counterparty = try c.decode(String.self, forKey: .counterparty)
        if let iso = try? c.decode(String.self, forKey: .date) {
            let fmt = ISO8601DateFormatter()
            fmt.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            guard let d = fmt.date(from: iso) ?? ISO8601DateFormatter().date(from: iso) else {
                throw DecodingError.dataCorruptedError(forKey: .date, in: c, debugDescription: "Unparseable date: \(iso)")
            }
            date = d
        } else {
            date = Date(timeIntervalSince1970: try c.decode(Double.self, forKey: .date))
        }
    }
}

struct WalletActionButton: View {
    let icon: String
    let title: String
    
    var body: some View {
        Button(action: {}) {
            HStack {
                Image(systemName: icon)
                Text(title)
            }
            .font(.headline)
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding()
            .background(Color.white.opacity(0.2))
            .cornerRadius(12)
        }
    }
}

struct TransactionRow: View {
    let transaction: WalletTransaction
    
    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(transaction.type == .received ? Color.green.opacity(0.2) : Color.red.opacity(0.2))
                    .frame(width: 44, height: 44)
                
                Image(systemName: transaction.type == .received ? "arrow.down.left" : "arrow.up.right")
                    .foregroundColor(transaction.type == .received ? .green : .red)
            }
            
            VStack(alignment: .leading, spacing: 4) {
                Text(transaction.counterparty)
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                Text(formatDate(transaction.date))
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            Text("\(transaction.type == .received ? "+" : "-")\(String(format: "%.2f", transaction.amount))")
                .font(.subheadline)
                .fontWeight(.semibold)
                .foregroundColor(transaction.type == .received ? .green : .red)
        }
        .padding(.vertical, 8)
    }
    
    func formatDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d, yyyy"
        return formatter.string(from: date)
    }
}

struct WalletView_Previews: PreviewProvider {
    static var previews: some View {
        WalletView()
    }
}

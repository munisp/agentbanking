import SwiftUI

struct WalletView: View {
    @State private var balance: Double = 2450.00
    @State private var showBalance = true
    @State private var transactions = [
        WalletTransaction(type: .received, amount: 500, counterparty: "John Doe", date: Date()),
        WalletTransaction(type: .sent, amount: 200, counterparty: "Jane Smith", date: Date().addingTimeInterval(-86400)),
        WalletTransaction(type: .received, amount: 750, counterparty: "Bob Johnson", date: Date().addingTimeInterval(-172800)),
    ]
    
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
                                    
                                    Text(showBalance ? String(format: "$%.2f", balance) : "••••••")
                                        .font(.system(size: 36, weight: .bold))
                                        .foregroundColor(.white)
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
                    
                    // Recent Transactions
                    VStack(alignment: .leading, spacing: 15) {
                        Text("Recent Transactions")
                            .font(.headline)
                        
                        ForEach(transactions) { transaction in
                            TransactionRow(transaction: transaction)
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
    }
}

struct WalletTransaction: Identifiable {
    let id = UUID()
    let type: TransactionType
    let amount: Double
    let counterparty: String
    let date: Date
    
    enum TransactionType {
        case sent, received
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
            
            Text("\(transaction.type == .received ? "+" : "-")$\(String(format: "%.2f", transaction.amount))")
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

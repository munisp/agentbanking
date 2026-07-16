import SwiftUI

struct VirtualCardManagementView: View {
    @StateObject private var viewModel = VirtualCardViewModel()
    @State private var showCreateCard = false
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                if viewModel.cards.isEmpty {
                    emptyStateView
                } else {
                    cardsSection
                }
                
                createCardButton
                cardLimitsSection
                transactionsSection
            }
            .padding()
        }
        .navigationTitle("Virtual Cards")
        .sheet(isPresented: $showCreateCard) {
            CreateVirtualCardView(viewModel: viewModel)
        }
        .onAppear { viewModel.loadCards() }
    }
    
    private var emptyStateView: some View {
        VStack(spacing: 16) {
            Image(systemName: "creditcard")
                .font(.system(size: 60))
                .foregroundColor(.secondary)
            Text("No Virtual Cards")
                .font(.title2)
                .fontWeight(.bold)
            Text("Create a virtual card for secure online payments")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
    }
    
    private var cardsSection: some View {
        VStack(spacing: 16) {
            ForEach(viewModel.cards) { card in
                VirtualCardView(card: card, viewModel: viewModel)
            }
        }
    }
    
    private var createCardButton: some View {
        Button(action: { showCreateCard = true }) {
            Label("Create New Card", systemImage: "plus.circle.fill")
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.blue)
                .foregroundColor(.white)
                .cornerRadius(12)
        }
    }
    
    private var cardLimitsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Card Limits")
                .font(.headline)
            
            VStack(spacing: 8) {
                LimitRow(label: "Daily Limit", current: 500, total: 1000)
                LimitRow(label: "Monthly Limit", current: 2500, total: 10000)
            }
            .padding()
            .background(Color(.systemGray6))
            .cornerRadius(12)
        }
    }
    
    private var transactionsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Recent Transactions")
                .font(.headline)
            
            ForEach(viewModel.recentTransactions) { transaction in
                CardTransactionRow(transaction: transaction)
            }
        }
    }
}

struct VirtualCardView: View {
    let card: VirtualCard
    @ObservedObject var viewModel: VirtualCardViewModel
    @State private var showDetails = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text(card.name)
                    .font(.headline)
                    .foregroundColor(.white)
                Spacer()
                Menu {
                    Button(action: { viewModel.freezeCard(card) }) {
                        Label(card.isFrozen ? "Unfreeze" : "Freeze", systemImage: card.isFrozen ? "play.fill" : "pause.fill")
                    }
                    Button(action: { showDetails = true }) {
                        Label("View Details", systemImage: "eye")
                    }
                    Button(role: .destructive, action: { viewModel.deleteCard(card) }) {
                        Label("Delete", systemImage: "trash")
                    }
                } label: {
                    Image(systemName: "ellipsis")
                        .foregroundColor(.white)
                }
            }
            
            Spacer()
            
            if showDetails {
                VStack(alignment: .leading, spacing: 8) {
                    Text("•••• •••• •••• \(card.last4)")
                        .font(.title3)
                        .fontWeight(.bold)
                    
                    HStack {
                        VStack(alignment: .leading) {
                            Text("CVV")
                                .font(.caption)
                            Text(card.cvv)
                                .font(.subheadline)
                                .fontWeight(.medium)
                        }
                        
                        Spacer()
                        
                        VStack(alignment: .leading) {
                            Text("Expires")
                                .font(.caption)
                            Text(card.expiryDate)
                                .font(.subheadline)
                                .fontWeight(.medium)
                        }
                    }
                }
                .foregroundColor(.white)
            } else {
                Text("Tap to reveal details")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.7))
            }
            
            HStack {
                Text("\(card.currency) \(card.balance, specifier: "%.2f")")
                    .font(.title3)
                    .fontWeight(.bold)
                Spacer()
                if card.isFrozen {
                    Text("FROZEN")
                        .font(.caption)
                        .fontWeight(.bold)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.red)
                        .cornerRadius(4)
                }
            }
            .foregroundColor(.white)
        }
        .padding()
        .frame(height: 200)
        .background(LinearGradient(colors: [.blue, .purple], startPoint: .topLeading, endPoint: .bottomTrailing))
        .cornerRadius(16)
        .onTapGesture {
            withAnimation {
                showDetails.toggle()
            }
        }
    }
}

struct CreateVirtualCardView: View {
    @ObservedObject var viewModel: VirtualCardViewModel
    @Environment(\.dismiss) var dismiss
    @State private var cardName = ""
    @State private var currency = "USD"
    @State private var spendingLimit = ""
    
    var body: some View {
        NavigationView {
            Form {
                Section("Card Details") {
                    TextField("Card Name", text: $cardName)
                    Picker("Currency", selection: $currency) {
                        Text("USD").tag("USD")
                        Text("NGN").tag("NGN")
                        Text("EUR").tag("EUR")
                        Text("GBP").tag("GBP")
                    }
                }
                
                Section("Spending Limit") {
                    TextField("Daily Limit", text: $spendingLimit)
                        .keyboardType(.numberPad)
                }
                
                Section {
                    Button("Create Card") {
                        viewModel.createCard(name: cardName, currency: currency, limit: Double(spendingLimit) ?? 0)
                        dismiss()
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .navigationTitle("New Virtual Card")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }
}

struct LimitRow: View {
    let label: String
    let current: Double
    let total: Double
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(label)
                    .font(.subheadline)
                Spacer()
                Text("$\(current, specifier: "%.0f") / $\(total, specifier: "%.0f")")
                    .font(.subheadline)
                    .fontWeight(.medium)
            }
            
            ProgressView(value: current / total)
                .tint(.blue)
        }
    }
}

struct CardTransactionRow: View {
    let transaction: CardTransaction
    
    var body: some View {
        HStack {
            Image(systemName: "creditcard")
                .foregroundColor(.blue)
            
            VStack(alignment: .leading) {
                Text(transaction.merchant)
                    .font(.subheadline)
                Text(transaction.timestamp, style: .relative)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            Text("-$\(transaction.amount, specifier: "%.2f")")
                .fontWeight(.medium)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(8)
    }
}

class VirtualCardViewModel: ObservableObject {
    @Published var cards: [VirtualCard] = []
    @Published var recentTransactions: [CardTransaction] = []
    
    func loadCards() {}
    func createCard(name: String, currency: String, limit: Double) {}
    func freezeCard(_ card: VirtualCard) {}
    func deleteCard(_ card: VirtualCard) {}
}

struct VirtualCard: Identifiable {
    let id = UUID()
    let name: String
    let last4: String
    let cvv: String
    let expiryDate: String
    let currency: String
    let balance: Double
    let isFrozen: Bool
}

struct CardTransaction: Identifiable {
    let id = UUID()
    let merchant: String
    let amount: Double
    let timestamp: Date
}

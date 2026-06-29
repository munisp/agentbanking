import SwiftUI

struct TransactionsListView: View {
    @EnvironmentObject var walletManager: WalletManager
    @State private var searchText = ""
    @State private var selectedFilter: TransactionFilter = .all
    @State private var showFilterSheet = false
    @State private var selectedTransaction: Transaction?
    
    var filteredTransactions: [Transaction] {
        var transactions = walletManager.transactions
        
        // Apply filter
        switch selectedFilter {
        case .all:
            break
        case .sent:
            transactions = transactions.filter { $0.type.lowercased() == "sent" }
        case .received:
            transactions = transactions.filter { $0.type.lowercased() == "received" }
        case .pending:
            transactions = transactions.filter { $0.status.lowercased() == "pending" }
        case .completed:
            transactions = transactions.filter { $0.status.lowercased() == "completed" }
        case .failed:
            transactions = transactions.filter { $0.status.lowercased() == "failed" }
        }
        
        // Apply search
        if !searchText.isEmpty {
            transactions = transactions.filter {
                $0.recipient?.localizedCaseInsensitiveContains(searchText) == true ||
                $0.sender?.localizedCaseInsensitiveContains(searchText) == true ||
                $0.id.localizedCaseInsensitiveContains(searchText)
            }
        }
        
        return transactions
    }
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Search bar
                HStack {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(.secondary)
                    
                    TextField("Search transactions", text: $searchText)
                    
                    if !searchText.isEmpty {
                        Button(action: { searchText = "" }) {
                            Image(systemName: "xmark.circle.fill")
                                .foregroundColor(.secondary)
                        }
                    }
                }
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(12)
                .padding()
                
                // Filter chips
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 12) {
                        ForEach(TransactionFilter.allCases, id: \.self) { filter in
                            FilterChip(
                                title: filter.rawValue,
                                isSelected: selectedFilter == filter
                            ) {
                                selectedFilter = filter
                            }
                        }
                    }
                    .padding(.horizontal)
                }
                .padding(.bottom, 8)
                
                // Transactions list
                if filteredTransactions.isEmpty {
                    Spacer()
                    EmptyStateView(
                        icon: "arrow.left.arrow.right.circle",
                        title: "No Transactions",
                        message: searchText.isEmpty ? "Your transaction history will appear here" : "No transactions match your search"
                    )
                    Spacer()
                } else {
                    List {
                        ForEach(groupedTransactions.keys.sorted(by: >), id: \.self) { date in
                            Section(header: Text(formatSectionDate(date))) {
                                ForEach(groupedTransactions[date] ?? []) { transaction in
                                    Button(action: {
                                        selectedTransaction = transaction
                                    }) {
                                        TransactionListRow(transaction: transaction)
                                    }
                                }
                            }
                        }
                        
                        // Load more
                        if walletManager.hasMoreTransactions {
                            HStack {
                                Spacer()
                                ProgressView()
                                Spacer()
                            }
                            .onAppear {
                                Task {
                                    await walletManager.loadMoreTransactions()
                                }
                            }
                        }
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .navigationTitle("Transactions")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { showFilterSheet = true }) {
                        Image(systemName: "line.3.horizontal.decrease.circle")
                    }
                }
            }
            .refreshable {
                await walletManager.loadTransactions(refresh: true)
            }
            .sheet(item: $selectedTransaction) { transaction in
                TransactionDetailSheet(transaction: transaction)
            }
            .sheet(isPresented: $showFilterSheet) {
                FilterSheet(selectedFilter: $selectedFilter)
            }
        }
    }
    
    var groupedTransactions: [String: [Transaction]] {
        Dictionary(grouping: filteredTransactions) { transaction in
            formatDate(transaction.createdAt)
        }
    }
    
    func formatDate(_ dateString: String) -> String {
        // Simplified date formatting
        return "Today" // In production, parse and format properly
    }
    
    func formatSectionDate(_ dateString: String) -> String {
        return dateString
    }
}

struct TransactionListRow: View {
    let transaction: Transaction
    
    var body: some View {
        HStack(spacing: 16) {
            // Icon
            ZStack {
                Circle()
                    .fill(transaction.statusColor.opacity(0.1))
                    .frame(width: 50, height: 50)
                
                Image(systemName: transaction.typeIcon)
                    .font(.title3)
                    .foregroundColor(transaction.statusColor)
            }
            
            // Details
            VStack(alignment: .leading, spacing: 4) {
                Text(transaction.recipient ?? transaction.sender ?? "Transaction")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .lineLimit(1)
                
                HStack(spacing: 8) {
                    Text(formatDate(transaction.createdAt))
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Circle()
                        .fill(Color.secondary)
                        .frame(width: 3, height: 3)
                    
                    Text(transaction.status.capitalized)
                        .font(.caption)
                        .foregroundColor(transaction.statusColor)
                }
            }
            
            Spacer()
            
            // Amount
            VStack(alignment: .trailing, spacing: 4) {
                Text("\(transaction.type.lowercased() == "sent" ? "-" : "+")\(transaction.currency) \(transaction.amount, specifier: "%.2f")")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(transaction.type.lowercased() == "sent" ? .red : .green)
                
                if let fee = transaction.fee, fee > 0 {
                    Text("Fee: \(transaction.currency) \(fee, specifier: "%.2f")")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding(.vertical, 4)
    }
    
    func formatDate(_ dateString: String) -> String {
        return "Today" // Simplified
    }
}

struct FilterChip: View {
    let title: String
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.subheadline)
                .fontWeight(isSelected ? .semibold : .regular)
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(isSelected ? Color("PrimaryColor") : Color(.systemGray6))
                .foregroundColor(isSelected ? .white : .primary)
                .cornerRadius(20)
        }
    }
}

struct TransactionDetailSheet: View {
    let transaction: Transaction
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 24) {
                    // Status icon
                    ZStack {
                        Circle()
                            .fill(transaction.statusColor.opacity(0.1))
                            .frame(width: 100, height: 100)
                        
                        Image(systemName: transaction.typeIcon)
                            .font(.system(size: 50))
                            .foregroundColor(transaction.statusColor)
                    }
                    .padding(.top)
                    
                    // Amount
                    VStack(spacing: 8) {
                        Text("\(transaction.type.lowercased() == "sent" ? "-" : "+")\(transaction.currency) \(transaction.amount, specifier: "%.2f")")
                            .font(.system(size: 36, weight: .bold))
                            .foregroundColor(transaction.type.lowercased() == "sent" ? .red : .green)
                        
                        Text(transaction.status.capitalized)
                            .font(.subheadline)
                            .padding(.horizontal, 16)
                            .padding(.vertical, 6)
                            .background(transaction.statusColor.opacity(0.1))
                            .foregroundColor(transaction.statusColor)
                            .cornerRadius(12)
                    }
                    
                    // Details
                    VStack(spacing: 16) {
                        DetailRow(label: "Transaction ID", value: transaction.id)
                        
                        if let recipient = transaction.recipient {
                            DetailRow(label: "Recipient", value: recipient, icon: "person.fill")
                        }
                        
                        if let sender = transaction.sender {
                            DetailRow(label: "Sender", value: sender, icon: "person.fill")
                        }
                        
                        DetailRow(label: "Date", value: formatDate(transaction.createdAt), icon: "calendar")
                        DetailRow(label: "Payment Method", value: transaction.paymentSystem ?? "N/A", icon: "creditcard.fill")
                        
                        if let fee = transaction.fee {
                            DetailRow(label: "Fee", value: "\(transaction.currency) \(fee, specifier: "%.2f")")
                        }
                        
                        if let reference = transaction.reference {
                            DetailRow(label: "Reference", value: reference)
                        }
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)
                    
                    // Actions
                    VStack(spacing: 12) {
                        Button(action: {
                            // Download receipt
                        }) {
                            HStack {
                                Image(systemName: "arrow.down.circle.fill")
                                Text("Download Receipt")
                            }
                            .font(.headline)
                            .foregroundColor(Color("PrimaryColor"))
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color("PrimaryColor").opacity(0.1))
                            .cornerRadius(12)
                        }
                        
                        Button(action: {
                            // Share
                        }) {
                            HStack {
                                Image(systemName: "square.and.arrow.up")
                                Text("Share")
                            }
                            .font(.headline)
                            .foregroundColor(Color("PrimaryColor"))
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color("PrimaryColor").opacity(0.1))
                            .cornerRadius(12)
                        }
                        
                        if transaction.status.lowercased() == "pending" {
                            Button(action: {
                                // Cancel transaction
                            }) {
                                HStack {
                                    Image(systemName: "xmark.circle.fill")
                                    Text("Cancel Transaction")
                                }
                                .font(.headline)
                                .foregroundColor(.red)
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.red.opacity(0.1))
                                .cornerRadius(12)
                            }
                        }
                    }
                }
                .padding()
            }
            .navigationTitle("Transaction Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
    
    func formatDate(_ dateString: String) -> String {
        return "Today at 10:30 AM" // Simplified
    }
}

struct FilterSheet: View {
    @Binding var selectedFilter: TransactionFilter
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationView {
            List {
                Section("Transaction Type") {
                    ForEach([TransactionFilter.all, .sent, .received], id: \.self) { filter in
                        Button(action: {
                            selectedFilter = filter
                            dismiss()
                        }) {
                            HStack {
                                Text(filter.rawValue)
                                Spacer()
                                if selectedFilter == filter {
                                    Image(systemName: "checkmark")
                                        .foregroundColor(Color("PrimaryColor"))
                                }
                            }
                        }
                        .foregroundColor(.primary)
                    }
                }
                
                Section("Status") {
                    ForEach([TransactionFilter.pending, .completed, .failed], id: \.self) { filter in
                        Button(action: {
                            selectedFilter = filter
                            dismiss()
                        }) {
                            HStack {
                                Text(filter.rawValue)
                                Spacer()
                                if selectedFilter == filter {
                                    Image(systemName: "checkmark")
                                        .foregroundColor(Color("PrimaryColor"))
                                }
                            }
                        }
                        .foregroundColor(.primary)
                    }
                }
            }
            .navigationTitle("Filter Transactions")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

enum TransactionFilter: String, CaseIterable {
    case all = "All"
    case sent = "Sent"
    case received = "Received"
    case pending = "Pending"
    case completed = "Completed"
    case failed = "Failed"
}

// Extensions for Transaction model
extension Transaction {
    var typeIcon: String {
        switch type.lowercased() {
        case "sent":
            return "arrow.up.circle.fill"
        case "received":
            return "arrow.down.circle.fill"
        default:
            return "arrow.left.arrow.right.circle.fill"
        }
    }
    
    var statusColor: Color {
        switch status.lowercased() {
        case "completed":
            return .green
        case "pending":
            return .orange
        case "failed":
            return .red
        default:
            return .gray
        }
    }
}

#Preview {
    TransactionsListView()
        .environmentObject(WalletManager())
}

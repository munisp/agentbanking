import SwiftUI

struct PaymentBatch: Identifiable {
    let id = UUID()
    let batchId: String
    let name: String
    let status: String
    let totalAmount: Double
    let currency: String
    let totalPayments: Int
    let completedPayments: Int
    let failedPayments: Int
    let createdAt: Date
    let recurrence: String?
}

struct BatchPaymentsView: View {
    @State private var batches: [PaymentBatch] = []
    @State private var loading = true
    @State private var selectedTab = 0
    @State private var showCreateSheet = false
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                Picker("Tab", selection: $selectedTab) {
                    Text("Batches").tag(0)
                    Text("Scheduled").tag(1)
                }
                .pickerStyle(.segmented)
                .padding()
                
                if loading {
                    Spacer()
                    ProgressView()
                    Spacer()
                } else {
                    if selectedTab == 0 {
                        BatchesListView(batches: batches.filter { $0.recurrence == nil })
                    } else {
                        BatchesListView(batches: batches.filter { $0.recurrence != nil })
                    }
                }
            }
            .navigationTitle("Batch Payments")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Back") { dismiss() }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { showCreateSheet = true }) {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showCreateSheet) {
                CreateBatchView()
            }
        }
        .onAppear { loadBatches() }
    }
    
    private func loadBatches() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            batches = [
                PaymentBatch(batchId: "BATCH-001", name: "January Payroll", status: "COMPLETED", totalAmount: 5000000, currency: "NGN", totalPayments: 50, completedPayments: 50, failedPayments: 0, createdAt: Date().addingTimeInterval(-86400), recurrence: nil),
                PaymentBatch(batchId: "BATCH-002", name: "Vendor Payments", status: "PROCESSING", totalAmount: 2500000, currency: "NGN", totalPayments: 25, completedPayments: 15, failedPayments: 2, createdAt: Date().addingTimeInterval(-3600), recurrence: nil),
                PaymentBatch(batchId: "BATCH-003", name: "Monthly Rent", status: "SCHEDULED", totalAmount: 150000, currency: "NGN", totalPayments: 1, completedPayments: 0, failedPayments: 0, createdAt: Date(), recurrence: "MONTHLY")
            ]
            loading = false
        }
    }
}

struct BatchesListView: View {
    let batches: [PaymentBatch]
    
    var body: some View {
        if batches.isEmpty {
            VStack(spacing: 16) {
                Image(systemName: "doc.text")
                    .font(.system(size: 48))
                    .foregroundColor(.gray)
                Text("No batches found")
                    .foregroundColor(.gray)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            ScrollView {
                LazyVStack(spacing: 12) {
                    ForEach(batches) { batch in
                        BatchCard(batch: batch)
                    }
                }
                .padding()
            }
        }
    }
}

struct BatchCard: View {
    let batch: PaymentBatch
    
    var statusColor: Color {
        switch batch.status {
        case "COMPLETED": return .green
        case "PROCESSING": return .blue
        case "PENDING", "SCHEDULED": return .orange
        case "FAILED": return .red
        default: return .gray
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(batch.name)
                        .fontWeight(.semibold)
                    Text(batch.batchId)
                        .font(.caption)
                        .foregroundColor(.gray)
                }
                Spacer()
                Text(batch.status)
                    .font(.caption)
                    .fontWeight(.medium)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 4)
                    .background(statusColor.opacity(0.1))
                    .foregroundColor(statusColor)
                    .cornerRadius(12)
            }
            
            HStack {
                VStack(alignment: .leading) {
                    Text("Total Amount")
                        .font(.caption)
                        .foregroundColor(.gray)
                    Text("\(batch.currency) \(String(format: "%,.0f", batch.totalAmount))")
                        .fontWeight(.medium)
                }
                Spacer()
                VStack(alignment: .trailing) {
                    Text("Payments")
                        .font(.caption)
                        .foregroundColor(.gray)
                    Text("\(batch.completedPayments)/\(batch.totalPayments)")
                        .fontWeight(.medium)
                }
            }
            
            if batch.status == "PROCESSING" {
                ProgressView(value: Double(batch.completedPayments) / Double(batch.totalPayments))
                    .tint(.blue)
            }
            
            if let recurrence = batch.recurrence {
                HStack {
                    Image(systemName: "repeat")
                        .font(.caption)
                        .foregroundColor(.purple)
                    Text(recurrence)
                        .font(.caption)
                        .foregroundColor(.purple)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 5)
    }
}

struct CreateBatchView: View {
    @Environment(\.dismiss) var dismiss
    @State private var batchName = ""
    @State private var selectedFile: String?
    
    var body: some View {
        NavigationView {
            Form {
                Section("Batch Details") {
                    TextField("Batch Name", text: $batchName)
                }
                
                Section("Upload CSV") {
                    Button(action: {}) {
                        HStack {
                            Image(systemName: "doc.badge.plus")
                            Text("Select CSV File")
                        }
                    }
                    
                    Button(action: {}) {
                        HStack {
                            Image(systemName: "arrow.down.doc")
                            Text("Download Template")
                        }
                    }
                }
                
                Section("CSV Format") {
                    Text("Required columns: recipient_name, recipient_account, recipient_bank, amount, currency, reference")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
            }
            .navigationTitle("Create Batch")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Create") { dismiss() }
                        .disabled(batchName.isEmpty)
                }
            }
        }
    }
}

#Preview {
    BatchPaymentsView()
}

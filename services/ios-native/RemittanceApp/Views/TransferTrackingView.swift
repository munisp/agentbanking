import SwiftUI

struct TrackingEvent: Identifiable {
    let id = UUID()
    let state: String
    let timestamp: Date
    let description: String
    let location: String?
}

struct TransferTrackingData {
    let transferId: String
    let trackingId: String
    let currentState: String
    let progressPercent: Int
    let senderName: String
    let recipientName: String
    let amount: Double
    let currency: String
    let destinationCurrency: String
    let destinationAmount: Double
    let corridor: String
    let createdAt: Date
    let estimatedCompletion: Date
    let events: [TrackingEvent]
}

struct TransferTrackingView: View {
    let transferId: String
    @State private var tracking: TransferTrackingData?
    @State private var loading = true
    @Environment(\.dismiss) var dismiss
    
    let transferStates = [
        ("INITIATED", "Transfer Initiated", "doc.text"),
        ("PENDING", "Pending", "clock"),
        ("RESERVED", "Funds Reserved", "lock"),
        ("IN_NETWORK", "In Network", "globe"),
        ("AT_DESTINATION", "At Destination", "building.2"),
        ("COMPLETED", "Completed", "checkmark.circle")
    ]
    
    var body: some View {
        NavigationView {
            ScrollView {
                if loading {
                    ProgressView()
                        .padding(.top, 100)
                } else if let data = tracking {
                    VStack(spacing: 20) {
                        // Amount Card
                        VStack(spacing: 16) {
                            HStack {
                                VStack(alignment: .leading) {
                                    Text("Sending")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.8))
                                    Text("\(data.currency) \(String(format: "%.2f", data.amount))")
                                        .font(.title2)
                                        .fontWeight(.bold)
                                        .foregroundColor(.white)
                                }
                                Spacer()
                                VStack(alignment: .trailing) {
                                    Text("Receiving")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.8))
                                    Text("\(data.destinationCurrency) \(String(format: "%.0f", data.destinationAmount))")
                                        .font(.title2)
                                        .fontWeight(.bold)
                                        .foregroundColor(.white)
                                }
                            }
                            
                            HStack {
                                VStack(alignment: .leading) {
                                    Text("From")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.8))
                                    Text(data.senderName)
                                        .fontWeight(.medium)
                                        .foregroundColor(.white)
                                }
                                Spacer()
                                Text(data.corridor)
                                    .font(.caption)
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 4)
                                    .background(Color.white.opacity(0.2))
                                    .cornerRadius(12)
                                    .foregroundColor(.white)
                                Spacer()
                                VStack(alignment: .trailing) {
                                    Text("To")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.8))
                                    Text(data.recipientName)
                                        .fontWeight(.medium)
                                        .foregroundColor(.white)
                                }
                            }
                        }
                        .padding(20)
                        .background(LinearGradient(colors: [.blue, .blue.opacity(0.8)], startPoint: .leading, endPoint: .trailing))
                        .cornerRadius(16)
                        
                        // Progress Card
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text("Progress")
                                    .fontWeight(.medium)
                                Spacer()
                                Text("\(data.progressPercent)%")
                                    .foregroundColor(.blue)
                            }
                            ProgressView(value: Double(data.progressPercent) / 100)
                                .tint(.blue)
                        }
                        .padding()
                        .background(Color(.systemBackground))
                        .cornerRadius(12)
                        .shadow(color: .black.opacity(0.05), radius: 5)
                        
                        // Status Timeline
                        VStack(alignment: .leading, spacing: 16) {
                            Text("Transfer Status")
                                .font(.headline)
                            
                            let currentIndex = transferStates.firstIndex { $0.0 == data.currentState } ?? 0
                            
                            ForEach(Array(transferStates.enumerated()), id: \.offset) { index, state in
                                let isCompleted = index < currentIndex
                                let isCurrent = index == currentIndex
                                let event = data.events.first { $0.state == state.0 }
                                
                                HStack(alignment: .top, spacing: 12) {
                                    VStack(spacing: 0) {
                                        Circle()
                                            .fill(isCompleted ? Color.green : (isCurrent ? Color.blue : Color.gray.opacity(0.3)))
                                            .frame(width: 32, height: 32)
                                            .overlay(
                                                Image(systemName: isCompleted ? "checkmark" : state.2)
                                                    .font(.caption)
                                                    .foregroundColor(.white)
                                            )
                                        
                                        if index < transferStates.count - 1 {
                                            Rectangle()
                                                .fill(isCompleted ? Color.green : Color.gray.opacity(0.3))
                                                .frame(width: 2, height: 40)
                                        }
                                    }
                                    
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(state.1)
                                            .fontWeight(isCurrent ? .bold : .regular)
                                            .foregroundColor(index > currentIndex ? .gray : .primary)
                                        
                                        if let event = event {
                                            Text(event.timestamp, style: .time)
                                                .font(.caption)
                                                .foregroundColor(.gray)
                                            if let location = event.location {
                                                Text(location)
                                                    .font(.caption)
                                                    .foregroundColor(.gray)
                                            }
                                        }
                                    }
                                    Spacer()
                                }
                            }
                        }
                        .padding()
                        .background(Color(.systemBackground))
                        .cornerRadius(12)
                        .shadow(color: .black.opacity(0.05), radius: 5)
                        
                        // Details Card
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Transfer Details")
                                .font(.headline)
                            
                            DetailRow(label: "Tracking ID", value: data.trackingId)
                            DetailRow(label: "Payment Network", value: data.corridor)
                            DetailRow(label: "Created", value: data.createdAt.formatted(date: .abbreviated, time: .shortened))
                        }
                        .padding()
                        .background(Color(.systemBackground))
                        .cornerRadius(12)
                        .shadow(color: .black.opacity(0.05), radius: 5)
                    }
                    .padding()
                }
            }
            .navigationTitle("Transfer Tracking")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Back") { dismiss() }
                }
            }
        }
        .onAppear { loadTracking() }
    }
    
    private func loadTracking() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            tracking = TransferTrackingData(
                transferId: transferId,
                trackingId: "TRK-\(transferId.prefix(8).uppercased())",
                currentState: "IN_NETWORK",
                progressPercent: 60,
                senderName: "John Doe",
                recipientName: "Jane Smith",
                amount: 500,
                currency: "GBP",
                destinationCurrency: "NGN",
                destinationAmount: 975250,
                corridor: "MOJALOOP",
                createdAt: Date().addingTimeInterval(-3600),
                estimatedCompletion: Date().addingTimeInterval(1800),
                events: [
                    TrackingEvent(state: "INITIATED", timestamp: Date().addingTimeInterval(-3600), description: "Transfer initiated", location: nil),
                    TrackingEvent(state: "PENDING", timestamp: Date().addingTimeInterval(-3500), description: "Awaiting verification", location: nil),
                    TrackingEvent(state: "RESERVED", timestamp: Date().addingTimeInterval(-3000), description: "Funds reserved", location: nil),
                    TrackingEvent(state: "IN_NETWORK", timestamp: Date().addingTimeInterval(-1800), description: "Processing", location: "Lagos Hub")
                ]
            )
            loading = false
        }
    }
}

struct DetailRow: View {
    let label: String
    let value: String
    
    var body: some View {
        HStack {
            Text(label)
                .foregroundColor(.gray)
            Spacer()
            Text(value)
                .fontWeight(.medium)
        }
    }
}

#Preview {
    TransferTrackingView(transferId: "test-123")
}

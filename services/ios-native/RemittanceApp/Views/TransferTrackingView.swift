import SwiftUI

struct TrackingEvent: Identifiable, Decodable {
    let id = UUID()
    let state: String
    let timestamp: Date
    let description: String
    let location: String?

    enum CodingKeys: String, CodingKey {
        case state, timestamp, description, location
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        state = try c.decode(String.self, forKey: .state)
        description = try c.decode(String.self, forKey: .description)
        location = try c.decodeIfPresent(String.self, forKey: .location)
        if let iso = try? c.decode(String.self, forKey: .timestamp) {
            let fmt = ISO8601DateFormatter()
            fmt.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            guard let d = fmt.date(from: iso) ?? ISO8601DateFormatter().date(from: iso) else {
                throw DecodingError.dataCorruptedError(forKey: .timestamp, in: c, debugDescription: "Unparseable date: \(iso)")
            }
            timestamp = d
        } else {
            timestamp = Date(timeIntervalSince1970: try c.decode(Double.self, forKey: .timestamp))
        }
    }
}

struct TransferTrackingData: Decodable {
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

    enum CodingKeys: String, CodingKey {
        case transferId, trackingId, currentState, progressPercent
        case senderName, recipientName, amount, currency
        case destinationCurrency, destinationAmount, corridor
        case createdAt, estimatedCompletion, events
    }

    /// Accepts ISO-8601 strings or epoch seconds for all dates.
    init(from decoder: Decoder) throws {
        func decodeDate(_ container: KeyedDecodingContainer<CodingKeys>, _ key: CodingKeys) throws -> Date {
            if let iso = try? container.decode(String.self, forKey: key) {
                let fmt = ISO8601DateFormatter()
                fmt.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
                if let d = fmt.date(from: iso) ?? ISO8601DateFormatter().date(from: iso) {
                    return d
                }
                throw DecodingError.dataCorruptedError(forKey: key, in: container, debugDescription: "Unparseable date: \(iso)")
            }
            return Date(timeIntervalSince1970: try container.decode(Double.self, forKey: key))
        }
        let c = try decoder.container(keyedBy: CodingKeys.self)
        transferId = try c.decode(String.self, forKey: .transferId)
        trackingId = try c.decode(String.self, forKey: .trackingId)
        currentState = try c.decode(String.self, forKey: .currentState)
        progressPercent = try c.decode(Int.self, forKey: .progressPercent)
        senderName = try c.decode(String.self, forKey: .senderName)
        recipientName = try c.decode(String.self, forKey: .recipientName)
        amount = try c.decode(Double.self, forKey: .amount)
        currency = try c.decode(String.self, forKey: .currency)
        destinationCurrency = try c.decode(String.self, forKey: .destinationCurrency)
        destinationAmount = try c.decode(Double.self, forKey: .destinationAmount)
        corridor = try c.decode(String.self, forKey: .corridor)
        createdAt = try decodeDate(c, .createdAt)
        estimatedCompletion = try decodeDate(c, .estimatedCompletion)
        events = try c.decode([TrackingEvent].self, forKey: .events)
    }
}

struct TransferTrackingView: View {
    let transferId: String
    @State private var tracking: TransferTrackingData?
    @State private var loading = true
    @State private var loadError: String?
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
                } else if let loadError {
                    VStack(spacing: 12) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.largeTitle)
                            .foregroundColor(.orange)
                        Text(loadError)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                        Button("Retry") {
                            self.loadError = nil
                            loading = true
                            loadTracking()
                        }
                        .buttonStyle(.borderedProminent)
                    }
                    .padding(.top, 100)
                    .padding(.horizontal)
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
        Task {
            do {
                // Real tracking data from the backend transfer-tracking endpoint.
                tracking = try await APIClient.shared.request(.transferTracking(transferId))
                loading = false
            } catch {
                loadError = "Could not load tracking information: \(error.localizedDescription)"
                loading = false
            }
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

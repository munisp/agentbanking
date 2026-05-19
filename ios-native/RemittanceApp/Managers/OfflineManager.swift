import Foundation
import Combine

/**
 * OfflineManager - Handles offline-first architecture for iOS
 *
 * Features:
 * - Pending transfer queue with idempotency keys
 * - Cached wallet balances, beneficiaries, transactions
 * - Background sync when connectivity restored
 * - Weak network mode support
 */

// MARK: - Models

struct PendingTransfer: Codable, Identifiable {
    let id: String
    let idempotencyKey: String
    let type: TransferType
    let payload: TransferPayload
    var status: TransferStatus
    var retryCount: Int
    var lastError: String?
    let createdAt: Date
    var syncedAt: Date?
    var serverTransactionId: String?
    
    enum TransferType: String, Codable {
        case transfer
        case airtime
        case billPayment = "bill_payment"
        case walletFund = "wallet_fund"
    }
    
    enum TransferStatus: String, Codable {
        case pending
        case syncing
        case completed
        case failed
    }
}

struct TransferPayload: Codable {
    let recipientName: String
    let recipientPhone: String
    let recipientBank: String?
    let recipientAccountNumber: String?
    let amount: Double
    let sourceCurrency: String
    let destinationCurrency: String
    let exchangeRate: Double
    let fee: Double
    let totalAmount: Double
    let deliveryMethod: String
    let note: String?
}

struct CachedWalletBalance: Codable, Identifiable {
    var id: String { currency }
    let currency: String
    let balance: Double
    let availableBalance: Double
    let pendingBalance: Double
    let lastUpdatedAt: Date
    let cachedAt: Date
}

struct CachedBeneficiary: Codable, Identifiable {
    let id: String
    let name: String
    let phone: String
    let email: String?
    let bankName: String?
    let bankCode: String?
    let accountNumber: String?
    let accountType: AccountType
    var isFavorite: Bool
    var lastUsedAt: Date?
    let cachedAt: Date
    
    enum AccountType: String, Codable {
        case phone
        case email
        case bank
    }
}

struct CachedTransaction: Codable, Identifiable {
    let id: String
    let type: String
    let status: String
    let amount: Double
    let currency: String
    let fee: Double
    let description: String
    let recipientName: String?
    let recipientPhone: String?
    let referenceNumber: String
    let createdAt: Date
    let completedAt: Date?
    let cachedAt: Date
}

struct CachedExchangeRate: Codable, Identifiable {
    var id: String { pair }
    let pair: String
    let rate: Double
    let inverseRate: Double
    let lastUpdatedAt: Date
    let cachedAt: Date
}

// MARK: - Offline Store

class OfflineStore: ObservableObject {
    static let shared = OfflineStore()
    
    @Published var pendingTransfers: [PendingTransfer] = []
    @Published var walletBalances: [CachedWalletBalance] = []
    @Published var beneficiaries: [CachedBeneficiary] = []
    @Published var transactions: [CachedTransaction] = []
    @Published var exchangeRates: [CachedExchangeRate] = []
    @Published var isOnline: Bool = true
    @Published var syncInProgress: Bool = false
    
    private let fileManager = FileManager.default
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()
    
    private var documentsDirectory: URL {
        fileManager.urls(for: .documentDirectory, in: .userDomainMask)[0]
    }
    
    private init() {
        loadAllData()
        setupNetworkMonitoring()
    }
    
    // MARK: - File Paths
    
    private var pendingTransfersURL: URL {
        documentsDirectory.appendingPathComponent("pending_transfers.json")
    }
    
    private var walletBalancesURL: URL {
        documentsDirectory.appendingPathComponent("wallet_balances.json")
    }
    
    private var beneficiariesURL: URL {
        documentsDirectory.appendingPathComponent("beneficiaries.json")
    }
    
    private var transactionsURL: URL {
        documentsDirectory.appendingPathComponent("transactions.json")
    }
    
    private var exchangeRatesURL: URL {
        documentsDirectory.appendingPathComponent("exchange_rates.json")
    }
    
    // MARK: - Network Monitoring
    
    private func setupNetworkMonitoring() {
        // In production, use NWPathMonitor
        // For now, check periodically
        Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            self?.checkConnectivity()
        }
    }
    
    private func checkConnectivity() {
        // Simple connectivity check
        guard let url = URL(string: "https://www.google.com") else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "HEAD"
        request.timeoutInterval = 5.0
        
        URLSession.shared.dataTask(with: request) { [weak self] _, response, error in
            DispatchQueue.main.async {
                let wasOnline = self?.isOnline ?? false
                self?.isOnline = error == nil && (response as? HTTPURLResponse)?.statusCode == 200
                
                // Trigger sync when coming back online
                if !wasOnline && self?.isOnline == true {
                    self?.syncPendingTransfers()
                }
            }
        }.resume()
    }
    
    // MARK: - Data Loading
    
    private func loadAllData() {
        pendingTransfers = loadData(from: pendingTransfersURL) ?? []
        walletBalances = loadData(from: walletBalancesURL) ?? []
        beneficiaries = loadData(from: beneficiariesURL) ?? []
        transactions = loadData(from: transactionsURL) ?? []
        exchangeRates = loadData(from: exchangeRatesURL) ?? []
    }
    
    private func loadData<T: Decodable>(from url: URL) -> T? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        return try? decoder.decode(T.self, from: data)
    }
    
    private func saveData<T: Encodable>(_ data: T, to url: URL) {
        guard let encoded = try? encoder.encode(data) else { return }
        try? encoded.write(to: url)
    }
    
    // MARK: - Pending Transfers (Outbox)
    
    func generateIdempotencyKey() -> String {
        let timestamp = Int(Date().timeIntervalSince1970 * 1000)
        let random1 = String(Int.random(in: 100000...999999))
        let random2 = String(Int.random(in: 100000...999999))
        return "idem_\(timestamp)_\(random1)_\(random2)"
    }
    
    func addPendingTransfer(
        type: PendingTransfer.TransferType,
        payload: TransferPayload
    ) -> String {
        let id = UUID().uuidString
        let idempotencyKey = generateIdempotencyKey()
        
        let transfer = PendingTransfer(
            id: id,
            idempotencyKey: idempotencyKey,
            type: type,
            payload: payload,
            status: .pending,
            retryCount: 0,
            lastError: nil,
            createdAt: Date(),
            syncedAt: nil,
            serverTransactionId: nil
        )
        
        pendingTransfers.append(transfer)
        saveData(pendingTransfers, to: pendingTransfersURL)
        
        // Try to sync immediately if online
        if isOnline {
            syncPendingTransfers()
        }
        
        return id
    }
    
    func updatePendingTransfer(id: String, status: PendingTransfer.TransferStatus, error: String? = nil) {
        guard let index = pendingTransfers.firstIndex(where: { $0.id == id }) else { return }
        
        pendingTransfers[index].status = status
        if let error = error {
            pendingTransfers[index].lastError = error
            pendingTransfers[index].retryCount += 1
        }
        
        saveData(pendingTransfers, to: pendingTransfersURL)
    }
    
    func markTransferSynced(id: String, serverTransactionId: String) {
        guard let index = pendingTransfers.firstIndex(where: { $0.id == id }) else { return }
        
        pendingTransfers[index].status = .completed
        pendingTransfers[index].syncedAt = Date()
        pendingTransfers[index].serverTransactionId = serverTransactionId
        
        saveData(pendingTransfers, to: pendingTransfersURL)
    }
    
    func removePendingTransfer(id: String) {
        pendingTransfers.removeAll { $0.id == id }
        saveData(pendingTransfers, to: pendingTransfersURL)
    }
    
    var pendingCount: Int {
        pendingTransfers.filter { $0.status == .pending || $0.status == .failed }.count
    }
    
    // MARK: - Sync
    
    func syncPendingTransfers() {
        guard !syncInProgress && isOnline else { return }
        
        syncInProgress = true
        
        let transfersToSync = pendingTransfers.filter {
            ($0.status == .pending || $0.status == .failed) && $0.retryCount < 5
        }
        
        guard !transfersToSync.isEmpty else {
            syncInProgress = false
            return
        }
        
        for transfer in transfersToSync {
            syncTransfer(transfer)
        }
    }
    
    private func syncTransfer(_ transfer: PendingTransfer) {
        updatePendingTransfer(id: transfer.id, status: .syncing)
        
        let endpoint = getEndpoint(for: transfer.type)
        guard let url = URL(string: "\(APIConfig.baseURL)\(endpoint)") else {
            updatePendingTransfer(id: transfer.id, status: .failed, error: "Invalid URL")
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(transfer.idempotencyKey, forHTTPHeaderField: "Idempotency-Key")
        
        // Add auth token if available
        if let token = AuthManager.shared.accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        let body: [String: Any] = [
            "recipient_name": transfer.payload.recipientName,
            "recipient_phone": transfer.payload.recipientPhone,
            "recipient_bank": transfer.payload.recipientBank ?? "",
            "recipient_account": transfer.payload.recipientAccountNumber ?? "",
            "amount": transfer.payload.amount,
            "source_currency": transfer.payload.sourceCurrency,
            "destination_currency": transfer.payload.destinationCurrency,
            "exchange_rate": transfer.payload.exchangeRate,
            "fee": transfer.payload.fee,
            "delivery_method": transfer.payload.deliveryMethod,
            "note": transfer.payload.note ?? "",
            "idempotency_key": transfer.idempotencyKey
        ]
        
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    self?.updatePendingTransfer(id: transfer.id, status: .failed, error: error.localizedDescription)
                    return
                }
                
                guard let httpResponse = response as? HTTPURLResponse else {
                    self?.updatePendingTransfer(id: transfer.id, status: .failed, error: "Invalid response")
                    return
                }
                
                if httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 {
                    if let data = data,
                       let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                       let transactionId = json["transaction_id"] as? String ?? json["id"] as? String {
                        self?.markTransferSynced(id: transfer.id, serverTransactionId: transactionId)
                    } else {
                        self?.markTransferSynced(id: transfer.id, serverTransactionId: "unknown")
                    }
                } else {
                    let errorMessage = "HTTP \(httpResponse.statusCode)"
                    self?.updatePendingTransfer(id: transfer.id, status: .failed, error: errorMessage)
                }
                
                // Check if all syncs are complete
                let stillSyncing = self?.pendingTransfers.contains { $0.status == .syncing } ?? false
                if !stillSyncing {
                    self?.syncInProgress = false
                }
            }
        }.resume()
    }
    
    private func getEndpoint(for type: PendingTransfer.TransferType) -> String {
        switch type {
        case .transfer:
            return "/api/v1/transactions/transfer"
        case .airtime:
            return "/api/v1/airtime/purchase"
        case .billPayment:
            return "/api/v1/bills/pay"
        case .walletFund:
            return "/api/v1/wallet/fund"
        }
    }
    
    // MARK: - Cache Management
    
    func cacheWalletBalances(_ balances: [CachedWalletBalance]) {
        walletBalances = balances
        saveData(walletBalances, to: walletBalancesURL)
    }
    
    func cacheBeneficiaries(_ newBeneficiaries: [CachedBeneficiary]) {
        beneficiaries = newBeneficiaries
        saveData(beneficiaries, to: beneficiariesURL)
    }
    
    func cacheTransactions(_ newTransactions: [CachedTransaction]) {
        transactions = newTransactions
        saveData(transactions, to: transactionsURL)
    }
    
    func cacheExchangeRates(_ rates: [CachedExchangeRate]) {
        exchangeRates = rates
        saveData(exchangeRates, to: exchangeRatesURL)
    }
    
    func getCachedExchangeRate(pair: String) -> CachedExchangeRate? {
        exchangeRates.first { $0.pair == pair }
    }
    
    // MARK: - Cleanup
    
    func clearOldCache(maxAgeDays: Int = 7) {
        let cutoff = Date().addingTimeInterval(-Double(maxAgeDays * 24 * 60 * 60))
        
        // Clear old completed transfers
        pendingTransfers.removeAll {
            $0.status == .completed && ($0.syncedAt ?? Date()) < cutoff
        }
        saveData(pendingTransfers, to: pendingTransfersURL)
    }
    
    func clearAll() {
        pendingTransfers = []
        walletBalances = []
        beneficiaries = []
        transactions = []
        exchangeRates = []
        
        try? fileManager.removeItem(at: pendingTransfersURL)
        try? fileManager.removeItem(at: walletBalancesURL)
        try? fileManager.removeItem(at: beneficiariesURL)
        try? fileManager.removeItem(at: transactionsURL)
        try? fileManager.removeItem(at: exchangeRatesURL)
    }
}

// MARK: - API Config

struct APIConfig {
    static var baseURL: String {
        // In production, this would come from environment/config
        return "https://api.54link.ng"
    }
}

// MARK: - Auth Manager Stub

class AuthManager {
    static let shared = AuthManager()
    var accessToken: String?
    
    private init() {}
}

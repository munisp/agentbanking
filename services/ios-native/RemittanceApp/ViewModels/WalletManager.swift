import Foundation
import Combine
import SwiftUI

@MainActor
class WalletManager: ObservableObject {
    @Published var balances: [CurrencyBalance] = []
    @Published var virtualIBANs: [VirtualIBAN] = []
    @Published var transactions: [Transaction] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var totalBalanceUSD: Double = 0.0
    
    private let apiClient = APIClient.shared
    private var cancellables = Set<AnyCancellable>()
    private var currentPage = 1
    private var hasMorePages = true
    
    // MARK: - Balances
    
    func loadBalances() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        
        do {
            let response: BalancesResponse = try await apiClient.request(.walletBalances)
            balances = response.data
            totalBalanceUSD = balances.reduce(0) { $0 + $1.usdEquivalent }
        } catch let error as APIError {
            errorMessage = error.errorDescription
        } catch {
            errorMessage = "Failed to load balances"
        }
    }
    
    func getBalance(for currency: String) -> CurrencyBalance? {
        return balances.first { $0.currency == currency }
    }
    
    // MARK: - Virtual IBANs
    
    func loadVirtualIBANs() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        
        do {
            let response: VirtualIBANsResponse = try await apiClient.request(.virtualIBANs)
            virtualIBANs = response.data
        } catch let error as APIError {
            errorMessage = error.errorDescription
        } catch {
            errorMessage = "Failed to load virtual IBANs"
        }
    }
    
    // MARK: - Transactions
    
    func loadTransactions(refresh: Bool = false) async {
        if refresh {
            currentPage = 1
            hasMorePages = true
            transactions = []
        }
        
        guard hasMorePages else { return }
        
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        
        do {
            let response: TransactionsResponse = try await apiClient.request(
                .transactions,
                parameters: [
                    "page": currentPage,
                    "limit": 20
                ]
            )
            
            if refresh {
                transactions = response.data.transactions
            } else {
                transactions.append(contentsOf: response.data.transactions)
            }
            
            hasMorePages = response.data.pagination.currentPage < response.data.pagination.totalPages
            if hasMorePages {
                currentPage += 1
            }
            
        } catch let error as APIError {
            errorMessage = error.errorDescription
        } catch {
            errorMessage = "Failed to load transactions"
        }
    }
    
    func loadMoreTransactions() async {
        await loadTransactions(refresh: false)
    }
    
    func getTransaction(id: String) async -> TransactionDetail? {
        do {
            let response: TransactionDetailResponse = try await apiClient.request(.transaction(id))
            return response.data
        } catch {
            errorMessage = "Failed to load transaction details"
            return nil
        }
    }
    
    func filterTransactions(type: String? = nil, status: String? = nil, startDate: String? = nil, endDate: String? = nil) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        
        var parameters: [String: Any] = ["page": 1, "limit": 20]
        if let type = type { parameters["type"] = type }
        if let status = status { parameters["status"] = status }
        if let startDate = startDate { parameters["startDate"] = startDate }
        if let endDate = endDate { parameters["endDate"] = endDate }
        
        do {
            let response: TransactionsResponse = try await apiClient.request(
                .transactions,
                parameters: parameters
            )
            transactions = response.data.transactions
            currentPage = 1
            hasMorePages = response.data.pagination.currentPage < response.data.pagination.totalPages
        } catch let error as APIError {
            errorMessage = error.errorDescription
        } catch {
            errorMessage = "Failed to filter transactions"
        }
    }
    
    // MARK: - Add Funds
    
    func addFunds(amount: Double, currency: String, paymentMethod: String, paymentDetails: [String: Any]) async -> AddFundsData? {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        
        do {
            let request = AddFundsRequest(
                amount: amount,
                currency: currency,
                paymentMethod: paymentMethod,
                paymentDetails: paymentDetails
            )
            
            let response: AddFundsResponse = try await apiClient.request(
                .addFunds,
                method: .post,
                parameters: request.toDictionary()
            )
            
            // Reload balances after adding funds
            await loadBalances()
            
            return response.data
        } catch let error as APIError {
            errorMessage = error.errorDescription
            return nil
        } catch {
            errorMessage = "Failed to add funds"
            return nil
        }
    }
    
    // MARK: - Withdraw
    
    func withdraw(amount: Double, currency: String, destinationAccount: String, destinationBank: String) async -> WithdrawData? {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        
        do {
            let request = WithdrawRequest(
                amount: amount,
                currency: currency,
                destinationAccount: destinationAccount,
                destinationBank: destinationBank
            )
            
            let response: WithdrawResponse = try await apiClient.request(
                .withdraw,
                method: .post,
                parameters: request.toDictionary()
            )
            
            // Reload balances after withdrawal
            await loadBalances()
            
            return response.data
        } catch let error as APIError {
            errorMessage = error.errorDescription
            return nil
        } catch {
            errorMessage = "Failed to process withdrawal"
            return nil
        }
    }
    
    // MARK: - Statement
    
    func getStatement(startDate: String, endDate: String, format: String = "pdf") async -> String? {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        
        do {
            let response: StatementResponse = try await apiClient.request(
                .statement,
                parameters: [
                    "startDate": startDate,
                    "endDate": endDate,
                    "format": format
                ]
            )
            return response.data.downloadUrl
        } catch let error as APIError {
            errorMessage = error.errorDescription
            return nil
        } catch {
            errorMessage = "Failed to generate statement"
            return nil
        }
    }
}

// MARK: - Supporting Models

struct CurrencyBalance: Codable, Identifiable {
    let currency: String
    let currencyName: String
    let currencySymbol: String
    let amount: Double
    let availableAmount: Double
    let pendingAmount: Double
    let usdEquivalent: Double
    
    var id: String { currency }
    
    var formattedAmount: String {
        return String(format: "%@ %.2f", currencySymbol, amount)
    }
    
    var formattedAvailable: String {
        return String(format: "%@ %.2f", currencySymbol, availableAmount)
    }
}

struct VirtualIBAN: Codable, Identifiable {
    let id: String
    let currency: String
    let iban: String
    let bic: String
    let bankName: String
    let accountHolderName: String
    let status: String
}

struct Transaction: Codable, Identifiable {
    let id: String
    let type: String
    let status: String
    let amount: Double
    let currency: String
    let recipient: String?
    let sender: String?
    let description: String?
    let fee: Double
    let exchangeRate: Double?
    let createdAt: String
    let completedAt: String?
    
    var statusColor: Color {
        switch status.lowercased() {
        case "completed": return .green
        case "pending": return .orange
        case "failed": return .red
        case "cancelled": return .gray
        default: return .blue
        }
    }
    
    var typeIcon: String {
        switch type.lowercased() {
        case "sent": return "arrow.up.circle.fill"
        case "received": return "arrow.down.circle.fill"
        case "exchange": return "arrow.left.arrow.right.circle.fill"
        case "fee": return "dollarsign.circle.fill"
        default: return "circle.fill"
        }
    }
}

struct TransactionDetail: Codable {
    let id: String
    let type: String
    let status: String
    let amount: Double
    let currency: String
    let recipient: RecipientDetail?
    let sender: SenderDetail?
    let description: String?
    let fee: Double
    let exchangeRate: Double?
    let paymentSystem: String
    let reference: String
    let createdAt: String
    let completedAt: String?
    let timeline: [TransactionTimeline]
}

struct RecipientDetail: Codable {
    let name: String
    let accountNumber: String
    let bankName: String
    let country: String
}

struct SenderDetail: Codable {
    let name: String
    let accountNumber: String
    let bankName: String
    let country: String
}

struct TransactionTimeline: Codable, Identifiable {
    let status: String
    let timestamp: String
    let message: String
    
    var id: String { timestamp }
}

struct AddFundsRequest: Encodable {
    let amount: Double
    let currency: String
    let paymentMethod: String
    let paymentDetails: [String: Any]
    
    func toDictionary() -> [String: Any] {
        return [
            "amount": amount,
            "currency": currency,
            "paymentMethod": paymentMethod,
            "paymentDetails": paymentDetails
        ]
    }
}

struct WithdrawRequest: Encodable {
    let amount: Double
    let currency: String
    let destinationAccount: String
    let destinationBank: String
}

struct BalancesResponse: Decodable {
    let success: Bool
    let data: [CurrencyBalance]
}

struct VirtualIBANsResponse: Decodable {
    let success: Bool
    let data: [VirtualIBAN]
}

struct TransactionsResponse: Decodable {
    let success: Bool
    let data: TransactionsPaginatedData
}

struct TransactionsPaginatedData: Decodable {
    let transactions: [Transaction]
    let pagination: Pagination
}

struct Pagination: Decodable {
    let currentPage: Int
    let totalPages: Int
    let totalItems: Int
    let itemsPerPage: Int
}

struct TransactionDetailResponse: Decodable {
    let success: Bool
    let data: TransactionDetail
}

struct AddFundsResponse: Decodable {
    let success: Bool
    let data: AddFundsData
}

struct AddFundsData: Decodable {
    let transactionId: String
    let paymentUrl: String?
    let instructions: String?
}

struct WithdrawResponse: Decodable {
    let success: Bool
    let data: WithdrawData
}

struct WithdrawData: Decodable {
    let transactionId: String
    let estimatedCompletionTime: String
}

struct StatementResponse: Decodable {
    let success: Bool
    let data: StatementData
}

struct StatementData: Decodable {
    let downloadUrl: String
    let expiresAt: String
}

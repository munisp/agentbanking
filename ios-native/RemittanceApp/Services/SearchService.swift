import Foundation
import Combine

// MARK: - Search Index Types
enum SearchIndex: String, Codable, CaseIterable {
    case transactions
    case users
    case beneficiaries
    case disputes
    case auditLogs = "audit_logs"
    case kyc
    case wallets
    case cards
    case bills
    case airtime
}

// MARK: - Search Request Models
struct SearchQuery: Codable {
    let query: String
    let index: [String]?
    let filters: [String: String]?
    let sort: SearchSort?
    let pagination: SearchPagination?
    let highlight: Bool
    let aggregations: [String]?
    
    init(
        query: String,
        index: [SearchIndex]? = nil,
        filters: [String: String]? = nil,
        sort: SearchSort? = nil,
        pagination: SearchPagination? = nil,
        highlight: Bool = true,
        aggregations: [String]? = nil
    ) {
        self.query = query
        self.index = index?.map { $0.rawValue }
        self.filters = filters
        self.sort = sort
        self.pagination = pagination
        self.highlight = highlight
        self.aggregations = aggregations
    }
}

struct SearchSort: Codable {
    let field: String
    let order: String
    
    init(field: String, order: String = "desc") {
        self.field = field
        self.order = order
    }
}

struct SearchPagination: Codable {
    let page: Int
    let size: Int
    
    init(page: Int = 1, size: Int = 20) {
        self.page = page
        self.size = size
    }
}

// MARK: - Search Response Models
struct SearchResponse<T: Codable>: Codable {
    let hits: [SearchHit<T>]
    let total: Int
    let page: Int
    let size: Int
    let took: Int
    let aggregations: [String: [AggregationBucket]]?
}

struct SearchHit<T: Codable>: Codable {
    let id: String
    let index: String
    let score: Float
    let source: T
    let highlight: [String: [String]]?
    
    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case index = "_index"
        case score = "_score"
        case source = "_source"
        case highlight
    }
}

struct AggregationBucket: Codable {
    let key: String
    let count: Int
    
    enum CodingKeys: String, CodingKey {
        case key
        case count = "doc_count"
    }
}

// MARK: - Domain-specific Result Types
struct TransactionSearchResult: Codable, Identifiable {
    let id: String
    let reference: String
    let type: String
    let amount: Double
    let currency: String
    let status: String
    let description: String
    let createdAt: String
    let senderId: String?
    let recipientId: String?
    
    enum CodingKeys: String, CodingKey {
        case id, reference, type, amount, currency, status, description
        case createdAt = "created_at"
        case senderId = "sender_id"
        case recipientId = "recipient_id"
    }
}

struct BeneficiarySearchResult: Codable, Identifiable {
    let id: String
    let name: String
    let accountNumber: String
    let bankCode: String
    let bankName: String
    let country: String
    let currency: String
    let createdAt: String
    
    enum CodingKeys: String, CodingKey {
        case id, name, country, currency
        case accountNumber = "account_number"
        case bankCode = "bank_code"
        case bankName = "bank_name"
        case createdAt = "created_at"
    }
}

struct DisputeSearchResult: Codable, Identifiable {
    let id: String
    let transactionId: String
    let type: String
    let status: String
    let description: String
    let createdAt: String
    let resolvedAt: String?
    
    enum CodingKeys: String, CodingKey {
        case id, type, status, description
        case transactionId = "transaction_id"
        case createdAt = "created_at"
        case resolvedAt = "resolved_at"
    }
}

struct AuditLogSearchResult: Codable, Identifiable {
    let id: String
    let action: String
    let category: String
    let userId: String
    let resourceType: String
    let resourceId: String
    let details: String
    let ipAddress: String
    let timestamp: String
    
    enum CodingKeys: String, CodingKey {
        case id, action, category, details, timestamp
        case userId = "user_id"
        case resourceType = "resource_type"
        case resourceId = "resource_id"
        case ipAddress = "ip_address"
    }
}

struct SearchSuggestion: Codable, Identifiable {
    var id: String { text }
    let text: String
    let score: Float
    let index: String
}

struct RecentSearch: Codable, Identifiable {
    var id: String { query + (index ?? "") }
    let query: String
    let index: String?
    let timestamp: String
}

// MARK: - Search Service
class SearchService: ObservableObject {
    static let shared = SearchService()
    
    private let baseURL: String
    private var authToken: String?
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder
    
    @Published var isLoading = false
    @Published var error: Error?
    
    init(
        baseURL: String = "https://api.remittance.com/api/search",
        authToken: String? = nil
    ) {
        self.baseURL = baseURL
        self.authToken = authToken
        
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 60
        self.session = URLSession(configuration: config)
        
        self.decoder = JSONDecoder()
        self.encoder = JSONEncoder()
    }
    
    func setAuthToken(_ token: String) {
        self.authToken = token
    }
    
    // MARK: - Unified Search
    func search<T: Codable>(query: SearchQuery) async throws -> SearchResponse<T> {
        let url = URL(string: "\(baseURL)/unified")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        request.httpBody = try encoder.encode(query)
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw SearchError.requestFailed
        }
        
        return try decoder.decode(SearchResponse<T>.self, from: data)
    }
    
    // MARK: - Transaction Search
    func searchTransactions(
        query: String,
        filters: [String: String]? = nil,
        pagination: SearchPagination = SearchPagination()
    ) async throws -> SearchResponse<TransactionSearchResult> {
        let searchQuery = SearchQuery(
            query: query,
            index: [.transactions],
            filters: filters,
            pagination: pagination
        )
        
        let url = URL(string: "\(baseURL)/transactions")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        request.httpBody = try encoder.encode(searchQuery)
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw SearchError.requestFailed
        }
        
        return try decoder.decode(SearchResponse<TransactionSearchResult>.self, from: data)
    }
    
    // MARK: - Beneficiary Search
    func searchBeneficiaries(
        query: String,
        filters: [String: String]? = nil,
        pagination: SearchPagination = SearchPagination()
    ) async throws -> SearchResponse<BeneficiarySearchResult> {
        let searchQuery = SearchQuery(
            query: query,
            index: [.beneficiaries],
            filters: filters,
            pagination: pagination
        )
        
        let url = URL(string: "\(baseURL)/beneficiaries")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        request.httpBody = try encoder.encode(searchQuery)
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw SearchError.requestFailed
        }
        
        return try decoder.decode(SearchResponse<BeneficiarySearchResult>.self, from: data)
    }
    
    // MARK: - Dispute Search
    func searchDisputes(
        query: String,
        filters: [String: String]? = nil,
        pagination: SearchPagination = SearchPagination()
    ) async throws -> SearchResponse<DisputeSearchResult> {
        let searchQuery = SearchQuery(
            query: query,
            index: [.disputes],
            filters: filters,
            pagination: pagination
        )
        
        let url = URL(string: "\(baseURL)/disputes")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        request.httpBody = try encoder.encode(searchQuery)
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw SearchError.requestFailed
        }
        
        return try decoder.decode(SearchResponse<DisputeSearchResult>.self, from: data)
    }
    
    // MARK: - Audit Log Search
    func searchAuditLogs(
        query: String,
        filters: [String: String]? = nil,
        pagination: SearchPagination = SearchPagination()
    ) async throws -> SearchResponse<AuditLogSearchResult> {
        let searchQuery = SearchQuery(
            query: query,
            index: [.auditLogs],
            filters: filters,
            pagination: pagination
        )
        
        let url = URL(string: "\(baseURL)/audit-logs")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        request.httpBody = try encoder.encode(searchQuery)
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw SearchError.requestFailed
        }
        
        return try decoder.decode(SearchResponse<AuditLogSearchResult>.self, from: data)
    }
    
    // MARK: - Suggestions
    func getSuggestions(query: String, index: SearchIndex? = nil) async throws -> [SearchSuggestion] {
        var urlComponents = URLComponents(string: "\(baseURL)/suggestions")!
        urlComponents.queryItems = [URLQueryItem(name: "q", value: query)]
        if let index = index {
            urlComponents.queryItems?.append(URLQueryItem(name: "index", value: index.rawValue))
        }
        
        var request = URLRequest(url: urlComponents.url!)
        request.httpMethod = "GET"
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw SearchError.requestFailed
        }
        
        return try decoder.decode([SearchSuggestion].self, from: data)
    }
    
    // MARK: - Recent Searches
    func getRecentSearches() async throws -> [RecentSearch] {
        let url = URL(string: "\(baseURL)/recent")!
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw SearchError.requestFailed
        }
        
        return try decoder.decode([RecentSearch].self, from: data)
    }
    
    func saveRecentSearch(query: String, index: SearchIndex? = nil) async throws {
        let url = URL(string: "\(baseURL)/recent")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        var body: [String: String] = ["query": query]
        if let index = index {
            body["index"] = index.rawValue
        }
        request.httpBody = try encoder.encode(body)
        
        let (_, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw SearchError.requestFailed
        }
    }
    
    func clearRecentSearches() async throws {
        let url = URL(string: "\(baseURL)/recent")!
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        let (_, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw SearchError.requestFailed
        }
    }
}

// MARK: - Search Errors
enum SearchError: Error, LocalizedError {
    case requestFailed
    case invalidResponse
    case decodingFailed
    case networkUnavailable
    
    var errorDescription: String? {
        switch self {
        case .requestFailed:
            return "Search request failed"
        case .invalidResponse:
            return "Invalid response from server"
        case .decodingFailed:
            return "Failed to decode search results"
        case .networkUnavailable:
            return "Network unavailable"
        }
    }
}

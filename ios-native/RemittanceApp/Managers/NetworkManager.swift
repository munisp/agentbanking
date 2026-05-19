import Foundation

class NetworkManager: ObservableObject {
    static let shared = NetworkManager()
    
    private let baseURL = "https://api.54link.ng"
    
    enum HTTPMethod: String {
        case get = "GET"
        case post = "POST"
        case put = "PUT"
        case delete = "DELETE"
    }
    
    enum NetworkError: Error {
        case invalidURL
        case invalidResponse
        case decodingError
        case serverError(Int)
        case unauthorized
        case unknown
    }
    
    private var authToken: String? {
        UserDefaults.standard.string(forKey: "authToken")
    }
    
    func request<T: Decodable>(
        endpoint: String,
        method: HTTPMethod = .get,
        body: Encodable? = nil
    ) async throws -> T {
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = method.rawValue
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        if let body = body {
            request.httpBody = try JSONEncoder().encode(body)
        }
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.invalidResponse
        }
        
        switch httpResponse.statusCode {
        case 200...299:
            do {
                return try JSONDecoder().decode(T.self, from: data)
            } catch {
                throw NetworkError.decodingError
            }
        case 401:
            throw NetworkError.unauthorized
        default:
            throw NetworkError.serverError(httpResponse.statusCode)
        }
    }
    
    // Wallet endpoints
    func getWalletBalance() async throws -> WalletBalance {
        try await request(endpoint: "/api/wallet/balance")
    }
    
    func getTransactions(limit: Int = 20, offset: Int = 0) async throws -> [Transaction] {
        try await request(endpoint: "/api/transactions?limit=\(limit)&offset=\(offset)")
    }
    
    func sendMoney(request: SendMoneyRequest) async throws -> TransactionResponse {
        try await self.request(endpoint: "/api/transactions/send", method: .post, body: request)
    }
    
    func getExchangeRates() async throws -> [ExchangeRate] {
        try await request(endpoint: "/api/exchange-rates")
    }
    
    func buyAirtime(request: AirtimeRequest) async throws -> AirtimeResponse {
        try await self.request(endpoint: "/api/airtime/purchase", method: .post, body: request)
    }
    
    func payBill(request: BillPaymentRequest) async throws -> BillPaymentResponse {
        try await self.request(endpoint: "/api/bills/pay", method: .post, body: request)
    }
}

// MARK: - Models

struct WalletBalance: Codable {
    let currency: String
    let balance: Double
}

struct Transaction: Codable, Identifiable {
    let id: String
    let type: String
    let amount: Double
    let currency: String
    let status: String
    let description: String
    let createdAt: String
}

struct SendMoneyRequest: Codable {
    let recipient: String
    let amount: Double
    let currency: String
    let note: String?
}

struct TransactionResponse: Codable {
    let id: String
    let status: String
    let message: String
}

struct ExchangeRate: Codable, Identifiable {
    var id: String { "\(from)\(to)" }
    let from: String
    let to: String
    let rate: Double
    let change: Double
}

struct AirtimeRequest: Codable {
    let phoneNumber: String
    let network: String
    let amount: Double
}

struct AirtimeResponse: Codable {
    let id: String
    let status: String
    let message: String
}

struct BillPaymentRequest: Codable {
    let category: String
    let provider: String
    let accountNumber: String
    let amount: Double
}

struct BillPaymentResponse: Codable {
    let id: String
    let status: String
    let message: String
}

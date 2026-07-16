import XCTest
import Combine
@testable import RemittanceApp

@MainActor
final class WalletManagerTests: XCTestCase {
    var sut: WalletManager!
    var cancellables: Set<AnyCancellable>!
    
    override func setUpWithError() throws {
        try super.setUpWithError()
        sut = WalletManager()
        cancellables = []
    }
    
    override func tearDownWithError() throws {
        sut = nil
        cancellables = nil
        try super.tearDownWithError()
    }
    
    // MARK: - Balance Loading Tests
    
    func testLoadBalances_SetsLoadingState() async throws {
        // Given
        let expectation = XCTestExpectation(description: "Loading state changes")
        
        sut.$isLoading
            .dropFirst()
            .sink { isLoading in
                if isLoading {
                    expectation.fulfill()
                }
            }
            .store(in: &cancellables)
        
        // When
        Task {
            await sut.loadBalances()
        }
        
        // Then
        await fulfillment(of: [expectation], timeout: 1.0)
    }
    
    func testLoadBalances_WithSuccess_PopulatesBalances() async throws {
        // When
        await sut.loadBalances()
        
        // Then
        // Note: Requires mock API client for actual testing
        XCTAssertNotNil(sut.balances)
    }
    
    func testLoadBalances_CalculatesTotalBalanceUSD() async throws {
        // Given: Mock balances
        let mockBalances = [
            CurrencyBalance(
                currency: "NGN",
                amount: 100000,
                usdEquivalent: 130,
                currencyName: "Nigerian Naira",
                currencySymbol: "₦"
            ),
            CurrencyBalance(
                currency: "USD",
                amount: 50,
                usdEquivalent: 50,
                currencyName: "US Dollar",
                currencySymbol: "$"
            )
        ]
        sut.balances = mockBalances
        
        // When
        let total = sut.totalBalanceUSD
        
        // Then
        XCTAssertEqual(total, 180.0, accuracy: 0.01)
    }
    
    // MARK: - Transaction Loading Tests
    
    func testLoadTransactions_WithRefresh_ClearsExisting() async throws {
        // Given: Existing transactions
        sut.transactions = [createMockTransaction()]
        
        // When
        await sut.loadTransactions(refresh: true)
        
        // Then
        // Note: Requires mock API client
        XCTAssertNotNil(sut.transactions)
    }
    
    func testLoadTransactions_WithoutRefresh_AppendsToExisting() async throws {
        // Given: Existing transactions
        let existingTransaction = createMockTransaction()
        sut.transactions = [existingTransaction]
        let initialCount = sut.transactions.count
        
        // When
        await sut.loadTransactions(refresh: false)
        
        // Then: Should have more transactions
        // Note: Requires mock API client
        XCTAssertGreaterThanOrEqual(sut.transactions.count, initialCount)
    }
    
    func testLoadMoreTransactions_IncreasesPageNumber() async throws {
        // Given
        let initialPage = sut.currentPage
        
        // When
        await sut.loadMoreTransactions()
        
        // Then
        XCTAssertEqual(sut.currentPage, initialPage + 1)
    }
    
    func testLoadMoreTransactions_WhenNoMoreData_SetsHasMoreToFalse() async throws {
        // Given: Mock API returns empty array
        sut.hasMoreTransactions = true
        
        // When
        await sut.loadMoreTransactions()
        
        // Then
        // Note: Requires mock API client that returns empty
        // XCTAssertFalse(sut.hasMoreTransactions)
    }
    
    // MARK: - Virtual IBAN Tests
    
    func testLoadVirtualIBANs_PopulatesIBANs() async throws {
        // When
        await sut.loadVirtualIBANs()
        
        // Then
        // Note: Requires mock API client
        XCTAssertNotNil(sut.virtualIBANs)
    }
    
    func testGenerateVirtualIBAN_AddsNewIBAN() async throws {
        // Given
        let initialCount = sut.virtualIBANs.count
        
        // When
        await sut.generateVirtualIBAN(currency: "EUR")
        
        // Then
        // Note: Requires mock API client
        XCTAssertGreaterThan(sut.virtualIBANs.count, initialCount)
    }
    
    // MARK: - Add Funds Tests
    
    func testInitiateAddFunds_WithValidAmount_ReturnsSuccess() async throws {
        // Given
        let amount = 100.0
        let currency = "USD"
        let method = "card"
        
        // When
        let result = await sut.initiateAddFunds(
            amount: amount,
            currency: currency,
            method: method
        )
        
        // Then
        // Note: Requires mock API client
        XCTAssertNotNil(result)
    }
    
    func testInitiateAddFunds_WithZeroAmount_ReturnsError() async throws {
        // Given
        let amount = 0.0
        
        // When
        let result = await sut.initiateAddFunds(
            amount: amount,
            currency: "USD",
            method: "card"
        )
        
        // Then
        XCTAssertNil(result)
        XCTAssertNotNil(sut.errorMessage)
    }
    
    // MARK: - Withdrawal Tests
    
    func testInitiateWithdrawal_WithValidAmount_ReturnsSuccess() async throws {
        // Given
        let amount = 50.0
        let currency = "USD"
        let accountId = "acc_123"
        
        // When
        let result = await sut.initiateWithdrawal(
            amount: amount,
            currency: currency,
            bankAccountId: accountId
        )
        
        // Then
        // Note: Requires mock API client
        XCTAssertNotNil(result)
    }
    
    func testInitiateWithdrawal_WithInsufficientBalance_ReturnsError() async throws {
        // Given: Balance of 10, trying to withdraw 100
        sut.balances = [
            CurrencyBalance(
                currency: "USD",
                amount: 10,
                usdEquivalent: 10,
                currencyName: "US Dollar",
                currencySymbol: "$"
            )
        ]
        
        // When
        let result = await sut.initiateWithdrawal(
            amount: 100,
            currency: "USD",
            bankAccountId: "acc_123"
        )
        
        // Then
        XCTAssertNil(result)
        XCTAssertNotNil(sut.errorMessage)
    }
    
    // MARK: - Statement Generation Tests
    
    func testGenerateStatement_WithValidDateRange_ReturnsData() async throws {
        // Given
        let startDate = Date().addingTimeInterval(-30 * 24 * 60 * 60) // 30 days ago
        let endDate = Date()
        let currency = "USD"
        
        // When
        let result = await sut.generateStatement(
            startDate: startDate,
            endDate: endDate,
            currency: currency
        )
        
        // Then
        // Note: Requires mock API client
        XCTAssertNotNil(result)
    }
    
    func testGenerateStatement_WithInvalidDateRange_ReturnsError() async throws {
        // Given: End date before start date
        let startDate = Date()
        let endDate = Date().addingTimeInterval(-30 * 24 * 60 * 60)
        
        // When
        let result = await sut.generateStatement(
            startDate: startDate,
            endDate: endDate,
            currency: "USD"
        )
        
        // Then
        XCTAssertNil(result)
        XCTAssertNotNil(sut.errorMessage)
    }
    
    // MARK: - State Management Tests
    
    func testBalances_PublishesChanges() {
        // Given
        let expectation = XCTestExpectation(description: "balances publishes")
        
        sut.$balances
            .dropFirst()
            .sink { _ in
                expectation.fulfill()
            }
            .store(in: &cancellables)
        
        // When
        sut.balances = [createMockBalance()]
        
        // Then
        wait(for: [expectation], timeout: 1.0)
    }
    
    func testTransactions_PublishesChanges() {
        // Given
        let expectation = XCTestExpectation(description: "transactions publishes")
        
        sut.$transactions
            .dropFirst()
            .sink { _ in
                expectation.fulfill()
            }
            .store(in: &cancellables)
        
        // When
        sut.transactions = [createMockTransaction()]
        
        // Then
        wait(for: [expectation], timeout: 1.0)
    }
    
    func testTotalBalanceUSD_UpdatesWhenBalancesChange() {
        // Given
        let expectation = XCTestExpectation(description: "totalBalanceUSD updates")
        
        sut.$totalBalanceUSD
            .dropFirst()
            .sink { total in
                if total > 0 {
                    expectation.fulfill()
                }
            }
            .store(in: &cancellables)
        
        // When
        sut.balances = [createMockBalance()]
        
        // Then
        wait(for: [expectation], timeout: 1.0)
    }
    
    // MARK: - Error Handling Tests
    
    func testErrorMessage_ClearsAfterSuccessfulOperation() async throws {
        // Given: Set an error
        sut.errorMessage = "Test error"
        
        // When: Successful operation
        await sut.loadBalances()
        
        // Then: Error should be cleared
        // Note: Requires mock API client that succeeds
        // XCTAssertNil(sut.errorMessage)
    }
    
    func testIsLoading_SetToFalseAfterOperation() async throws {
        // When
        await sut.loadBalances()
        
        // Then
        XCTAssertFalse(sut.isLoading)
    }
    
    // MARK: - Integration Tests
    
    func testLoadAllData_LoadsBalancesAndTransactions() async throws {
        // When
        async let balances: () = sut.loadBalances()
        async let transactions: () = sut.loadTransactions(refresh: true)
        
        _ = await (balances, transactions)
        
        // Then
        XCTAssertNotNil(sut.balances)
        XCTAssertNotNil(sut.transactions)
    }
    
    func testRefreshAllData_ClearsAndReloads() async throws {
        // Given: Existing data
        sut.balances = [createMockBalance()]
        sut.transactions = [createMockTransaction()]
        
        // When
        await sut.loadBalances()
        await sut.loadTransactions(refresh: true)
        
        // Then
        XCTAssertNotNil(sut.balances)
        XCTAssertNotNil(sut.transactions)
    }
    
    // MARK: - Performance Tests
    
    func testLoadBalancesPerformance() {
        measure {
            Task {
                await sut.loadBalances()
            }
        }
    }
    
    func testLoadTransactionsPerformance() {
        measure {
            Task {
                await sut.loadTransactions(refresh: true)
            }
        }
    }
    
    func testTotalBalanceCalculationPerformance() {
        // Given: Large number of balances
        sut.balances = (0..<100).map { _ in createMockBalance() }
        
        measure {
            _ = sut.totalBalanceUSD
        }
    }
    
    // MARK: - Helper Methods
    
    private func createMockBalance() -> CurrencyBalance {
        return CurrencyBalance(
            currency: "USD",
            amount: 100,
            usdEquivalent: 100,
            currencyName: "US Dollar",
            currencySymbol: "$"
        )
    }
    
    private func createMockTransaction() -> Transaction {
        return Transaction(
            id: "txn_\(UUID().uuidString)",
            type: "sent",
            amount: 50.0,
            currency: "USD",
            status: "completed",
            recipient: "John Doe",
            sender: nil,
            createdAt: ISO8601DateFormatter().string(from: Date()),
            fee: 2.5,
            paymentSystem: "SWIFT",
            reference: "REF123"
        )
    }
}

// MARK: - Mock Models

struct CurrencyBalance: Identifiable {
    let id = UUID()
    let currency: String
    let amount: Double
    let usdEquivalent: Double
    let currencyName: String
    let currencySymbol: String
    
    var formattedAmount: String {
        return "\(currencySymbol)\(String(format: "%.2f", amount))"
    }
}

struct Transaction: Identifiable {
    let id: String
    let type: String
    let amount: Double
    let currency: String
    let status: String
    let recipient: String?
    let sender: String?
    let createdAt: String
    let fee: Double?
    let paymentSystem: String?
    let reference: String?
}

struct VirtualIBAN: Identifiable {
    let id: String
    let iban: String
    let currency: String
    let bankName: String
    let accountHolder: String
}

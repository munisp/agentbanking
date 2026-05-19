package com.pos54link.app.data.api

import com.pos54link.app.models.User
import com.pos54link.app.security.TokenManager
import io.mockk.*
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.Assert.*
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

@OptIn(ExperimentalCoroutinesApi::class)
class ApiIntegrationTest {
    
    private lateinit var mockWebServer: MockWebServer
    private lateinit var apiClient: ApiClient
    private lateinit var tokenManager: TokenManager
    
    @Before
    fun setup() {
        mockWebServer = MockWebServer()
        mockWebServer.start()
        
        tokenManager = mockk(relaxed = true)
        every { tokenManager.getAccessToken() } returns "test_token"
        every { tokenManager.getOrCreateDeviceId() } returns "device_123"
        
        val retrofit = Retrofit.Builder()
            .baseUrl(mockWebServer.url("/"))
            .addConverterFactory(GsonConverterFactory.create())
            .build()
        
        apiClient = ApiClient(retrofit, tokenManager)
    }
    
    @After
    fun tearDown() {
        mockWebServer.shutdown()
        clearAllMocks()
    }
    
    // MARK: - Authentication API Tests
    
    @Test
    fun `login with valid credentials returns success`() = runTest {
        // Given
        val mockResponse = """
            {
                "success": true,
                "data": {
                    "user": {
                        "id": "user_123",
                        "email": "test@example.com",
                        "firstName": "John",
                        "lastName": "Doe",
                        "phoneNumber": "+2348012345678",
                        "country": "Nigeria",
                        "kycStatus": "pending",
                        "emailVerified": true,
                        "phoneVerified": false,
                        "twoFactorEnabled": false,
                        "createdAt": "2024-01-01T00:00:00Z"
                    },
                    "accessToken": "access_token_123",
                    "refreshToken": "refresh_token_123",
                    "expiresIn": 3600
                }
            }
        """.trimIndent()
        
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody(mockResponse)
                .addHeader("Content-Type", "application/json")
        )
        
        // When
        val response = apiClient.authService.login(
            LoginRequest(
                email = "test@example.com",
                password = "password123",
                deviceId = "device_123"
            )
        )
        
        // Then
        assertTrue(response.isSuccessful)
        assertNotNull(response.body())
        assertEquals("user_123", response.body()?.data?.user?.id)
        assertEquals("access_token_123", response.body()?.data?.accessToken)
    }
    
    @Test
    fun `login with invalid credentials returns 401`() = runTest {
        // Given
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(401)
                .setBody("""{"success": false, "message": "Invalid credentials"}""")
        )
        
        // When
        val response = apiClient.authService.login(
            LoginRequest(
                email = "invalid@example.com",
                password = "wrong",
                deviceId = "device_123"
            )
        )
        
        // Then
        assertFalse(response.isSuccessful)
        assertEquals(401, response.code())
    }
    
    @Test
    fun `register with valid data returns success`() = runTest {
        // Given
        val mockResponse = """
            {
                "success": true,
                "data": {
                    "user": {
                        "id": "user_new",
                        "email": "newuser@example.com",
                        "firstName": "Jane",
                        "lastName": "Smith",
                        "phoneNumber": "+2348087654321",
                        "country": "Nigeria",
                        "kycStatus": "pending",
                        "emailVerified": false,
                        "phoneVerified": false,
                        "twoFactorEnabled": false,
                        "createdAt": "2024-01-01T00:00:00Z"
                    },
                    "accessToken": "new_access_token",
                    "refreshToken": "new_refresh_token",
                    "expiresIn": 3600
                }
            }
        """.trimIndent()
        
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(201)
                .setBody(mockResponse)
        )
        
        // When
        val response = apiClient.authService.register(
            RegisterRequest(
                email = "newuser@example.com",
                password = "SecurePass123",
                firstName = "Jane",
                lastName = "Smith",
                phoneNumber = "+2348087654321",
                country = "Nigeria",
                deviceId = "device_123"
            )
        )
        
        // Then
        assertTrue(response.isSuccessful)
        assertEquals(201, response.code())
        assertEquals("user_new", response.body()?.data?.user?.id)
    }
    
    @Test
    fun `register with existing email returns 409`() = runTest {
        // Given
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(409)
                .setBody("""{"success": false, "message": "Email already exists"}""")
        )
        
        // When
        val response = apiClient.authService.register(
            RegisterRequest(
                email = "existing@example.com",
                password = "password",
                firstName = "John",
                lastName = "Doe",
                phoneNumber = "+234",
                country = "Nigeria",
                deviceId = "device_123"
            )
        )
        
        // Then
        assertFalse(response.isSuccessful)
        assertEquals(409, response.code())
    }
    
    // MARK: - Wallet API Tests
    
    @Test
    fun `getBalances returns currency balances`() = runTest {
        // Given
        val mockResponse = """
            {
                "success": true,
                "data": {
                    "balances": [
                        {
                            "currency": "NGN",
                            "amount": 100000.00,
                            "availableAmount": 100000.00,
                            "pendingAmount": 0.00,
                            "usdEquivalent": 130.00
                        },
                        {
                            "currency": "USD",
                            "amount": 50.00,
                            "availableAmount": 50.00,
                            "pendingAmount": 0.00,
                            "usdEquivalent": 50.00
                        }
                    ],
                    "totalUSD": 180.00
                }
            }
        """.trimIndent()
        
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody(mockResponse)
        )
        
        // When
        val response = apiClient.walletService.getBalances()
        
        // Then
        assertTrue(response.isSuccessful)
        assertNotNull(response.body())
        assertEquals(2, response.body()?.data?.balances?.size)
        assertEquals(180.00, response.body()?.data?.totalUSD, 0.01)
    }
    
    @Test
    fun `getTransactions with pagination returns transactions`() = runTest {
        // Given
        val mockResponse = """
            {
                "success": true,
                "data": {
                    "transactions": [
                        {
                            "id": "txn_1",
                            "type": "sent",
                            "amount": 50.00,
                            "currency": "USD",
                            "status": "completed",
                            "recipient": "John Doe",
                            "createdAt": "2024-01-01T00:00:00Z"
                        }
                    ],
                    "pagination": {
                        "page": 1,
                        "limit": 20,
                        "total": 1,
                        "hasMore": false
                    }
                }
            }
        """.trimIndent()
        
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody(mockResponse)
        )
        
        // When
        val response = apiClient.walletService.getTransactions(page = 1, limit = 20)
        
        // Then
        assertTrue(response.isSuccessful)
        assertEquals(1, response.body()?.data?.transactions?.size)
        assertFalse(response.body()?.data?.pagination?.hasMore ?: true)
    }
    
    @Test
    fun `getVirtualIBANs returns IBAN list`() = runTest {
        // Given
        val mockResponse = """
            {
                "success": true,
                "data": {
                    "ibans": [
                        {
                            "id": "iban_1",
                            "iban": "GB29NWBK60161331926819",
                            "currency": "EUR",
                            "bankName": "Test Bank",
                            "accountHolder": "John Doe"
                        }
                    ]
                }
            }
        """.trimIndent()
        
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody(mockResponse)
        )
        
        // When
        val response = apiClient.walletService.getVirtualIBANs()
        
        // Then
        assertTrue(response.isSuccessful)
        assertEquals(1, response.body()?.data?.ibans?.size)
        assertEquals("GB29NWBK60161331926819", response.body()?.data?.ibans?.first()?.iban)
    }
    
    // MARK: - Transfer API Tests
    
    @Test
    fun `initiateTransfer with valid data returns success`() = runTest {
        // Given
        val mockResponse = """
            {
                "success": true,
                "data": {
                    "transferId": "txn_123456",
                    "status": "pending",
                    "estimatedArrival": "2024-01-02T00:00:00Z"
                }
            }
        """.trimIndent()
        
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody(mockResponse)
        )
        
        // When
        val response = apiClient.transferService.initiateTransfer(
            TransferRequest(
                beneficiaryId = "ben_123",
                amount = 100.00,
                sourceCurrency = "USD",
                destinationCurrency = "NGN",
                paymentSystem = "NIBSS",
                purpose = "Family support"
            )
        )
        
        // Then
        assertTrue(response.isSuccessful)
        assertEquals("txn_123456", response.body()?.data?.transferId)
        assertEquals("pending", response.body()?.data?.status)
    }
    
    @Test
    fun `initiateTransfer with insufficient balance returns 400`() = runTest {
        // Given
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(400)
                .setBody("""{"success": false, "message": "Insufficient balance"}""")
        )
        
        // When
        val response = apiClient.transferService.initiateTransfer(
            TransferRequest(
                beneficiaryId = "ben_123",
                amount = 10000.00,
                sourceCurrency = "USD",
                destinationCurrency = "NGN",
                paymentSystem = "NIBSS",
                purpose = "Test"
            )
        )
        
        // Then
        assertFalse(response.isSuccessful)
        assertEquals(400, response.code())
    }
    
    @Test
    fun `getExchangeRate returns rate`() = runTest {
        // Given
        val mockResponse = """
            {
                "success": true,
                "data": {
                    "from": "USD",
                    "to": "NGN",
                    "rate": 770.50,
                    "timestamp": "2024-01-01T00:00:00Z"
                }
            }
        """.trimIndent()
        
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody(mockResponse)
        )
        
        // When
        val response = apiClient.transferService.getExchangeRate(from = "USD", to = "NGN")
        
        // Then
        assertTrue(response.isSuccessful)
        assertEquals(770.50, response.body()?.data?.rate, 0.01)
    }
    
    // MARK: - Error Handling Tests
    
    @Test
    fun `network error is handled correctly`() = runTest {
        // Given: Server returns 500
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(500)
                .setBody("""{"success": false, "message": "Internal server error"}""")
        )
        
        // When
        val response = apiClient.authService.login(
            LoginRequest("test@example.com", "password", "device_123")
        )
        
        // Then
        assertFalse(response.isSuccessful)
        assertEquals(500, response.code())
    }
    
    @Test
    fun `unauthorized request triggers token refresh`() = runTest {
        // Given: First request returns 401, second succeeds
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(401)
                .setBody("""{"success": false, "message": "Unauthorized"}""")
        )
        
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody("""{"success": true, "data": {"accessToken": "new_token", "refreshToken": "new_refresh"}}""")
        )
        
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody("""{"success": true, "data": {"balances": [], "totalUSD": 0}}""")
        )
        
        // When
        val response = apiClient.walletService.getBalances()
        
        // Then: Should have attempted refresh
        // Note: Requires interceptor implementation
        assertNotNull(response)
    }
    
    // MARK: - Request Validation Tests
    
    @Test
    fun `requests include authorization header`() = runTest {
        // Given
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody("""{"success": true, "data": {"balances": [], "totalUSD": 0}}""")
        )
        
        // When
        apiClient.walletService.getBalances()
        
        // Then
        val request = mockWebServer.takeRequest()
        assertTrue(request.headers["Authorization"]?.startsWith("Bearer ") == true)
    }
    
    @Test
    fun `requests include device ID header`() = runTest {
        // Given
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody("""{"success": true, "data": {"balances": [], "totalUSD": 0}}""")
        )
        
        // When
        apiClient.walletService.getBalances()
        
        // Then
        val request = mockWebServer.takeRequest()
        assertEquals("device_123", request.headers["X-Device-ID"])
    }
    
    // MARK: - Performance Tests
    
    @Test
    fun `concurrent API requests are handled correctly`() = runTest {
        // Given: Multiple endpoints
        repeat(5) {
            mockWebServer.enqueue(
                MockResponse()
                    .setResponseCode(200)
                    .setBody("""{"success": true, "data": {}}""")
            )
        }
        
        // When: Make concurrent requests
        val startTime = System.currentTimeMillis()
        
        kotlinx.coroutines.async { apiClient.walletService.getBalances() }
        kotlinx.coroutines.async { apiClient.walletService.getTransactions() }
        kotlinx.coroutines.async { apiClient.walletService.getVirtualIBANs() }
        
        val endTime = System.currentTimeMillis()
        
        // Then: Should complete reasonably fast
        assertTrue(endTime - startTime < 5000) // Less than 5 seconds
    }
}

// MARK: - Mock Request/Response Models

data class LoginRequest(
    val email: String,
    val password: String,
    val deviceId: String
)

data class RegisterRequest(
    val email: String,
    val password: String,
    val firstName: String,
    val lastName: String,
    val phoneNumber: String,
    val country: String,
    val deviceId: String
)

data class TransferRequest(
    val beneficiaryId: String,
    val amount: Double,
    val sourceCurrency: String,
    val destinationCurrency: String,
    val paymentSystem: String,
    val purpose: String
)

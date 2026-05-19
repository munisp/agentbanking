package com.pos54link.app.viewmodels

import com.pos54link.app.data.api.*
import com.pos54link.app.models.User
import com.pos54link.app.security.BiometricAuthManager
import com.pos54link.app.security.TokenManager
import io.mockk.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.Assert.*
import retrofit2.Response

@OptIn(ExperimentalCoroutinesApi::class)
class AuthViewModelTest {
    
    private lateinit var viewModel: AuthViewModel
    private lateinit var apiClient: ApiClient
    private lateinit var tokenManager: TokenManager
    private lateinit var biometricManager: BiometricAuthManager
    
    private val testDispatcher = StandardTestDispatcher()
    
    @Before
    fun setup() {
        Dispatchers.setMain(testDispatcher)
        
        apiClient = mockk(relaxed = true)
        tokenManager = mockk(relaxed = true)
        biometricManager = mockk(relaxed = true)
        
        every { biometricManager.isBiometricAvailable() } returns true
        every { tokenManager.isBiometricRegistered() } returns false
        
        viewModel = AuthViewModel(apiClient, tokenManager, biometricManager)
    }
    
    @After
    fun tearDown() {
        Dispatchers.resetMain()
        clearAllMocks()
    }
    
    // MARK: - Session Management Tests
    
    @Test
    fun `loadSession with valid token sets authenticated`() = runTest {
        // Given
        every { tokenManager.hasValidSession() } returns true
        val mockUser = createMockUser()
        val mockResponse = Response.success(
            ProfileDataResponse(
                success = true,
                data = UserProfile(
                    id = mockUser.id,
                    email = mockUser.email,
                    firstName = mockUser.firstName,
                    lastName = mockUser.lastName,
                    phoneNumber = mockUser.phoneNumber,
                    country = mockUser.country,
                    kycStatus = mockUser.kycStatus,
                    emailVerified = mockUser.emailVerified,
                    phoneVerified = mockUser.phoneVerified,
                    twoFactorEnabled = mockUser.twoFactorEnabled,
                    createdAt = mockUser.createdAt
                )
            )
        )
        coEvery { apiClient.profileService.getProfile() } returns mockResponse
        
        // When
        viewModel.loadSession()
        advanceUntilIdle()
        
        // Then
        assertTrue(viewModel.isAuthenticated.value)
        assertNotNull(viewModel.currentUser.value)
        assertEquals(mockUser.email, viewModel.currentUser.value?.email)
    }
    
    @Test
    fun `loadSession without token sets unauthenticated`() = runTest {
        // Given
        every { tokenManager.hasValidSession() } returns false
        
        // When
        viewModel.loadSession()
        advanceUntilIdle()
        
        // Then
        assertFalse(viewModel.isAuthenticated.value)
        assertNull(viewModel.currentUser.value)
    }
    
    @Test
    fun `loadSession with invalid token clears session`() = runTest {
        // Given
        every { tokenManager.hasValidSession() } returns true
        coEvery { apiClient.profileService.getProfile() } throws Exception("Unauthorized")
        
        // When
        viewModel.loadSession()
        advanceUntilIdle()
        
        // Then
        assertFalse(viewModel.isAuthenticated.value)
        verify { tokenManager.clearAll() }
    }
    
    // MARK: - Login Tests
    
    @Test
    fun `login with valid credentials sets authenticated`() = runTest {
        // Given
        val email = "test@example.com"
        val password = "password123"
        val mockUser = createMockUser()
        val mockResponse = Response.success(
            AuthDataResponse(
                success = true,
                data = AuthData(
                    user = mockUser,
                    accessToken = "access_token",
                    refreshToken = "refresh_token",
                    expiresIn = 3600
                )
            )
        )
        coEvery { apiClient.authService.login(any()) } returns mockResponse
        every { tokenManager.getOrCreateDeviceId() } returns "device_123"
        
        // When
        viewModel.login(email, password)
        advanceUntilIdle()
        
        // Then
        assertTrue(viewModel.isAuthenticated.value)
        assertEquals(mockUser.email, viewModel.currentUser.value?.email)
        verify { tokenManager.saveAccessToken("access_token") }
        verify { tokenManager.saveRefreshToken("refresh_token") }
        verify { tokenManager.saveUserId(mockUser.id) }
    }
    
    @Test
    fun `login with invalid credentials sets error`() = runTest {
        // Given
        val email = "invalid@example.com"
        val password = "wrong"
        coEvery { apiClient.authService.login(any()) } returns Response.error(401, mockk(relaxed = true))
        every { tokenManager.getOrCreateDeviceId() } returns "device_123"
        
        // When
        viewModel.login(email, password)
        advanceUntilIdle()
        
        // Then
        assertFalse(viewModel.isAuthenticated.value)
        assertNotNull(viewModel.errorMessage.value)
    }
    
    @Test
    fun `login sets loading state`() = runTest {
        // Given
        val email = "test@example.com"
        val password = "password123"
        every { tokenManager.getOrCreateDeviceId() } returns "device_123"
        coEvery { apiClient.authService.login(any()) } coAnswers {
            delay(100)
            Response.success(mockk(relaxed = true))
        }
        
        // When
        viewModel.login(email, password)
        
        // Then
        assertTrue(viewModel.isLoading.value)
        
        advanceUntilIdle()
        assertFalse(viewModel.isLoading.value)
    }
    
    // MARK: - Registration Tests
    
    @Test
    fun `register with valid data creates account`() = runTest {
        // Given
        val email = "newuser@example.com"
        val password = "SecurePass123"
        val firstName = "John"
        val lastName = "Doe"
        val phoneNumber = "+2348012345678"
        val country = "Nigeria"
        
        val mockUser = createMockUser()
        val mockResponse = Response.success(
            AuthDataResponse(
                success = true,
                data = AuthData(
                    user = mockUser,
                    accessToken = "access_token",
                    refreshToken = "refresh_token",
                    expiresIn = 3600
                )
            )
        )
        coEvery { apiClient.authService.register(any()) } returns mockResponse
        every { tokenManager.getOrCreateDeviceId() } returns "device_123"
        
        // When
        viewModel.register(email, password, firstName, lastName, phoneNumber, country)
        advanceUntilIdle()
        
        // Then
        assertTrue(viewModel.isAuthenticated.value)
        assertNotNull(viewModel.currentUser.value)
    }
    
    @Test
    fun `register with existing email sets error`() = runTest {
        // Given
        coEvery { apiClient.authService.register(any()) } returns Response.error(409, mockk(relaxed = true))
        every { tokenManager.getOrCreateDeviceId() } returns "device_123"
        
        // When
        viewModel.register("existing@example.com", "password", "John", "Doe", "+234", "Nigeria")
        advanceUntilIdle()
        
        // Then
        assertFalse(viewModel.isAuthenticated.value)
        assertNotNull(viewModel.errorMessage.value)
    }
    
    // MARK: - Logout Tests
    
    @Test
    fun `logout clears authentication`() = runTest {
        // Given
        viewModel.login("test@example.com", "password")
        coEvery { apiClient.authService.logout() } returns Response.success(mockk(relaxed = true))
        
        // When
        viewModel.logout()
        advanceUntilIdle()
        
        // Then
        assertFalse(viewModel.isAuthenticated.value)
        assertNull(viewModel.currentUser.value)
        verify { tokenManager.clearAll() }
    }
    
    @Test
    fun `logout clears data even if API call fails`() = runTest {
        // Given
        coEvery { apiClient.authService.logout() } throws Exception("Network error")
        
        // When
        viewModel.logout()
        advanceUntilIdle()
        
        // Then
        assertFalse(viewModel.isAuthenticated.value)
        verify { tokenManager.clearAll() }
    }
    
    // MARK: - Biometric Tests
    
    @Test
    fun `biometric availability is checked on init`() {
        // Then
        verify { biometricManager.isBiometricAvailable() }
        assertTrue(viewModel.isBiometricAvailable.value)
    }
    
    @Test
    fun `disableBiometric clears biometric data`() {
        // When
        viewModel.disableBiometric()
        
        // Then
        verify { tokenManager.clearBiometricPublicKey() }
        assertFalse(viewModel.isBiometricEnabled.value)
    }
    
    // MARK: - Password Reset Tests
    
    @Test
    fun `forgotPassword with valid email returns success`() = runTest {
        // Given
        val email = "test@example.com"
        coEvery { apiClient.authService.forgotPassword(any()) } returns Response.success(mockk(relaxed = true))
        
        // When
        val result = viewModel.forgotPassword(email)
        advanceUntilIdle()
        
        // Then
        assertTrue(result)
        assertNull(viewModel.errorMessage.value)
    }
    
    @Test
    fun `forgotPassword with invalid email returns error`() = runTest {
        // Given
        val email = "invalid@example.com"
        coEvery { apiClient.authService.forgotPassword(any()) } returns Response.error(404, mockk(relaxed = true))
        
        // When
        val result = viewModel.forgotPassword(email)
        advanceUntilIdle()
        
        // Then
        assertFalse(result)
        assertNotNull(viewModel.errorMessage.value)
    }
    
    // MARK: - Error Handling Tests
    
    @Test
    fun `clearError clears error message`() {
        // Given
        viewModel.login("invalid", "wrong")
        
        // When
        viewModel.clearError()
        
        // Then
        assertNull(viewModel.errorMessage.value)
    }
    
    // MARK: - State Flow Tests
    
    @Test
    fun `isAuthenticated emits changes`() = runTest {
        // Given
        val values = mutableListOf<Boolean>()
        val job = launch {
            viewModel.isAuthenticated.collect { values.add(it) }
        }
        
        // When
        viewModel.login("test@example.com", "password")
        advanceUntilIdle()
        
        // Then
        assertTrue(values.size > 1)
        job.cancel()
    }
    
    @Test
    fun `isLoading emits changes`() = runTest {
        // Given
        val values = mutableListOf<Boolean>()
        val job = launch {
            viewModel.isLoading.collect { values.add(it) }
        }
        
        // When
        viewModel.login("test@example.com", "password")
        advanceUntilIdle()
        
        // Then
        assertTrue(values.contains(true))
        assertTrue(values.contains(false))
        job.cancel()
    }
    
    // MARK: - Integration Tests
    
    @Test
    fun `full login-logout flow works correctly`() = runTest {
        // Given
        val mockUser = createMockUser()
        val loginResponse = Response.success(
            AuthDataResponse(
                success = true,
                data = AuthData(
                    user = mockUser,
                    accessToken = "access_token",
                    refreshToken = "refresh_token",
                    expiresIn = 3600
                )
            )
        )
        coEvery { apiClient.authService.login(any()) } returns loginResponse
        coEvery { apiClient.authService.logout() } returns Response.success(mockk(relaxed = true))
        every { tokenManager.getOrCreateDeviceId() } returns "device_123"
        
        // When: Login
        viewModel.login("test@example.com", "password")
        advanceUntilIdle()
        
        // Then: Should be authenticated
        assertTrue(viewModel.isAuthenticated.value)
        
        // When: Logout
        viewModel.logout()
        advanceUntilIdle()
        
        // Then: Should be unauthenticated
        assertFalse(viewModel.isAuthenticated.value)
        assertNull(viewModel.currentUser.value)
    }
    
    // MARK: - Helper Methods
    
    private fun createMockUser() = User(
        id = "user_123",
        email = "test@example.com",
        firstName = "John",
        lastName = "Doe",
        phoneNumber = "+2348012345678",
        country = "Nigeria",
        kycStatus = "pending",
        emailVerified = true,
        phoneVerified = false,
        twoFactorEnabled = false,
        createdAt = "2024-01-01T00:00:00Z"
    )
}

// Mock response data classes
data class AuthDataResponse(
    val success: Boolean,
    val data: AuthData
)

data class AuthData(
    val user: User,
    val accessToken: String,
    val refreshToken: String,
    val expiresIn: Int
)

data class ProfileDataResponse(
    val success: Boolean,
    val data: UserProfile
)

package com.pos54link.app.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pos54link.app.data.api.*
import com.pos54link.app.models.User
import com.pos54link.app.security.BiometricAuthManager
import com.pos54link.app.security.BiometricResult
import com.pos54link.app.security.TokenManager
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import timber.log.Timber
import javax.inject.Inject

@HiltViewModel
class AuthViewModel @Inject constructor(
    private val apiClient: ApiClient,
    private val tokenManager: TokenManager,
    private val biometricManager: BiometricAuthManager
) : ViewModel() {
    
    private val _isAuthenticated = MutableStateFlow(false)
    val isAuthenticated: StateFlow<Boolean> = _isAuthenticated.asStateFlow()
    
    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()
    
    private val _currentUser = MutableStateFlow<User?>(null)
    val currentUser: StateFlow<User?> = _currentUser.asStateFlow()
    
    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()
    
    private val _isBiometricAvailable = MutableStateFlow(false)
    val isBiometricAvailable: StateFlow<Boolean> = _isBiometricAvailable.asStateFlow()
    
    private val _isBiometricEnabled = MutableStateFlow(false)
    val isBiometricEnabled: StateFlow<Boolean> = _isBiometricEnabled.asStateFlow()
    
    init {
        checkBiometricAvailability()
    }
    
    // MARK: - Session Management
    
    fun loadSession() {
        viewModelScope.launch {
            _isLoading.value = true
            
            try {
                // Check if we have valid tokens
                val hasSession = tokenManager.hasValidSession()
                if (!hasSession) {
                    _isAuthenticated.value = false
                    _isLoading.value = false
                    return@launch
                }
                
                // Verify token by fetching user profile
                val response = apiClient.profileService.getProfile()
                if (response.isSuccessful && response.body() != null) {
                    _currentUser.value = response.body()!!.data.toUser()
                    _isAuthenticated.value = true
                    _isBiometricEnabled.value = tokenManager.isBiometricRegistered()
                } else {
                    // Token invalid, clear session
                    tokenManager.clearAll()
                    _isAuthenticated.value = false
                }
            } catch (e: Exception) {
                Timber.e(e, "Failed to load session")
                tokenManager.clearAll()
                _isAuthenticated.value = false
            } finally {
                _isLoading.value = false
            }
        }
    }
    
    // MARK: - Authentication
    
    fun login(email: String, password: String) {
        viewModelScope.launch {
            _isLoading.value = true
            _errorMessage.value = null
            
            try {
                val deviceId = tokenManager.getOrCreateDeviceId()
                val deviceName = android.os.Build.MODEL
                
                val request = LoginRequest(
                    email = email,
                    password = password,
                    deviceId = deviceId,
                    deviceName = deviceName
                )
                
                val response = apiClient.authService.login(request)
                
                if (response.isSuccessful && response.body() != null) {
                    val authResponse = response.body()!!
                    
                    // Save tokens
                    tokenManager.saveAccessToken(authResponse.data.accessToken)
                    tokenManager.saveRefreshToken(authResponse.data.refreshToken)
                    tokenManager.saveUserId(authResponse.data.user.id)
                    
                    _currentUser.value = authResponse.data.user
                    _isAuthenticated.value = true
                } else {
                    _errorMessage.value = "Login failed. Please check your credentials."
                }
            } catch (e: Exception) {
                Timber.e(e, "Login failed")
                _errorMessage.value = "Login failed. Please try again."
            } finally {
                _isLoading.value = false
            }
        }
    }
    
    fun register(
        email: String,
        password: String,
        firstName: String,
        lastName: String,
        phoneNumber: String,
        country: String
    ) {
        viewModelScope.launch {
            _isLoading.value = true
            _errorMessage.value = null
            
            try {
                val deviceId = tokenManager.getOrCreateDeviceId()
                val deviceName = android.os.Build.MODEL
                
                val request = RegisterRequest(
                    email = email,
                    password = password,
                    firstName = firstName,
                    lastName = lastName,
                    phoneNumber = phoneNumber,
                    country = country,
                    deviceId = deviceId,
                    deviceName = deviceName
                )
                
                val response = apiClient.authService.register(request)
                
                if (response.isSuccessful && response.body() != null) {
                    val authResponse = response.body()!!
                    
                    // Save tokens
                    tokenManager.saveAccessToken(authResponse.data.accessToken)
                    tokenManager.saveRefreshToken(authResponse.data.refreshToken)
                    tokenManager.saveUserId(authResponse.data.user.id)
                    
                    _currentUser.value = authResponse.data.user
                    _isAuthenticated.value = true
                } else {
                    _errorMessage.value = "Registration failed. Please try again."
                }
            } catch (e: Exception) {
                Timber.e(e, "Registration failed")
                _errorMessage.value = "Registration failed. Please try again."
            } finally {
                _isLoading.value = false
            }
        }
    }
    
    fun logout() {
        viewModelScope.launch {
            _isLoading.value = true
            
            try {
                // Call logout endpoint
                apiClient.authService.logout()
            } catch (e: Exception) {
                Timber.e(e, "Logout API call failed")
                // Continue with local logout even if API call fails
            }
            
            // Clear local data
            tokenManager.clearAll()
            _currentUser.value = null
            _isAuthenticated.value = false
            _isBiometricEnabled.value = false
            _isLoading.value = false
        }
    }
    
    // MARK: - Biometric Authentication
    
    private fun checkBiometricAvailability() {
        _isBiometricAvailable.value = biometricManager.isBiometricAvailable()
        _isBiometricEnabled.value = tokenManager.isBiometricRegistered()
    }
    
    suspend fun enableBiometric(activity: androidx.fragment.app.FragmentActivity): Boolean {
        if (!_isBiometricAvailable.value) {
            _errorMessage.value = "Biometric authentication is not available on this device"
            return false
        }
        
        _isLoading.value = true
        _errorMessage.value = null
        
        return try {
            // Authenticate with biometric first
            val result = biometricManager.authenticate(
                activity = activity,
                title = "Enable Biometric Login",
                subtitle = "Authenticate to enable biometric login",
                description = "Use your fingerprint or face to quickly log in"
            )
            
            when (result) {
                is BiometricResult.Success -> {
                    // Generate key pair (simplified - in production use Android Keystore)
                    val publicKey = "generated_public_key_${System.currentTimeMillis()}"
                    
                    // Register with server
                    val deviceId = tokenManager.getOrCreateDeviceId()
                    val request = BiometricRegisterRequest(
                        publicKey = publicKey,
                        deviceId = deviceId
                    )
                    
                    val response = apiClient.authService.registerBiometric(request)
                    
                    if (response.isSuccessful) {
                        tokenManager.saveBiometricPublicKey(publicKey)
                        _isBiometricEnabled.value = true
                        true
                    } else {
                        _errorMessage.value = "Failed to register biometric authentication"
                        false
                    }
                }
                is BiometricResult.Error -> {
                    _errorMessage.value = result.errorMessage
                    false
                }
                is BiometricResult.Cancelled -> {
                    _errorMessage.value = "Biometric authentication cancelled"
                    false
                }
            }
        } catch (e: Exception) {
            Timber.e(e, "Failed to enable biometric")
            _errorMessage.value = "Failed to enable biometric authentication"
            false
        } finally {
            _isLoading.value = false
        }
    }
    
    suspend fun loginWithBiometric(activity: androidx.fragment.app.FragmentActivity): Boolean {
        if (!_isBiometricEnabled.value) {
            _errorMessage.value = "Biometric authentication is not enabled"
            return false
        }
        
        _isLoading.value = true
        _errorMessage.value = null
        
        return try {
            val result = biometricManager.authenticate(
                activity = activity,
                title = "Biometric Login",
                subtitle = "Use your biometric to log in",
                description = "Authenticate to access your account"
            )
            
            when (result) {
                is BiometricResult.Success -> {
                    // In production, sign a challenge from server
                    val deviceId = tokenManager.getOrCreateDeviceId()
                    val signature = "signed_challenge_${System.currentTimeMillis()}"
                    
                    val request = BiometricVerifyRequest(
                        signature = signature,
                        challenge = "server_challenge",
                        deviceId = deviceId
                    )
                    
                    val response = apiClient.authService.verifyBiometric(request)
                    
                    if (response.isSuccessful && response.body() != null) {
                        val authResponse = response.body()!!
                        
                        tokenManager.saveAccessToken(authResponse.data.accessToken)
                        tokenManager.saveRefreshToken(authResponse.data.refreshToken)
                        tokenManager.saveUserId(authResponse.data.user.id)
                        
                        _currentUser.value = authResponse.data.user
                        _isAuthenticated.value = true
                        true
                    } else {
                        _errorMessage.value = "Biometric authentication failed"
                        false
                    }
                }
                is BiometricResult.Error -> {
                    _errorMessage.value = result.errorMessage
                    false
                }
                is BiometricResult.Cancelled -> {
                    false
                }
            }
        } catch (e: Exception) {
            Timber.e(e, "Biometric login failed")
            _errorMessage.value = "Biometric authentication failed"
            false
        } finally {
            _isLoading.value = false
        }
    }
    
    fun disableBiometric() {
        tokenManager.clearBiometricPublicKey()
        _isBiometricEnabled.value = false
    }
    
    // MARK: - Password Reset
    
    suspend fun forgotPassword(email: String): Boolean {
        _isLoading.value = true
        _errorMessage.value = null
        
        return try {
            val request = ForgotPasswordRequest(email = email)
            val response = apiClient.authService.forgotPassword(request)
            
            if (response.isSuccessful) {
                true
            } else {
                _errorMessage.value = "Failed to send password reset email"
                false
            }
        } catch (e: Exception) {
            Timber.e(e, "Forgot password failed")
            _errorMessage.value = "Failed to send password reset email"
            false
        } finally {
            _isLoading.value = false
        }
    }
    
    fun clearError() {
        _errorMessage.value = null
    }
}

// Extension to convert UserProfile to User
private fun com.pos54link.app.data.api.UserProfile.toUser(): User {
    return User(
        id = id,
        email = email,
        firstName = firstName,
        lastName = lastName,
        phoneNumber = phoneNumber,
        country = country,
        kycStatus = kycStatus,
        emailVerified = emailVerified,
        phoneVerified = phoneVerified,
        twoFactorEnabled = twoFactorEnabled,
        createdAt = createdAt
    )
}

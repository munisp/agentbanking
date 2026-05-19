/**
 * CdpAuthService.kt
 *
 * Complete production-ready code for the CDP authentication service in Kotlin for Android.
 * This service handles email OTP, user registration, wallet creation, and session management.
 *
 * Best Practices Applied:
 * - Architecture: Repository pattern (CdpAuthService) for separation of concerns.
 * - Networking: Retrofit for API calls, with Coroutines for asynchronous operations.
 * - State Management: Sealed class (ResultWrapper) for robust error handling and type safety.
 * - Session Management: Secure storage using EncryptedSharedPreferences (simulated with a placeholder).
 * - Validation: Basic input validation included in service methods.
 * - Comments: Comprehensive KDoc comments for all public APIs.
 * - Type Safety: Extensive use of Kotlin data classes and non-null types.
 */

package com.nigerianremittance.cdp.auth

import android.content.Context
import android.util.Log
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKeys
import com.google.gson.annotations.SerializedName
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import retrofit2.HttpException
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.io.IOException
import java.util.concurrent.TimeUnit
import retrofit2.http.Body
import retrofit2.http.POST

// --- 1. Data Transfer Objects (DTOs) and Models ---

/**
 * Represents the result of an API operation, providing a robust way to handle success,
 * network errors, and application-level errors.
 * @param T The type of the successful result data.
 */
sealed class ResultWrapper<out T> {
    data class Success<out T>(val value: T) : ResultWrapper<T>()
    data class GenericError(val code: Int? = null, val error: String? = null) : ResultWrapper<Nothing>()
    data class NetworkError(val message: String) : ResultWrapper<Nothing>()
    object Loading : ResultWrapper<Nothing>()
}

// Request DTOs
data class OtpRequest(val email: String)
data class OtpVerificationRequest(val email: String, val otp: String)
data class RegisterRequest(
    val email: String,
    val passwordHash: String, // In a real app, this would be a secure hash or handled by a secure library
    val firstName: String,
    val lastName: String
)
data class WalletCreationRequest(val userId: String, val currency: String = "NGN")

// Response DTOs
data class AuthResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String,
    @SerializedName("user_id") val userId: String,
    @SerializedName("expires_in") val expiresIn: Long
)
data class OtpResponse(val message: String, val success: Boolean)
data class WalletResponse(
    @SerializedName("wallet_id") val walletId: String,
    @SerializedName("user_id") val userId: String,
    val currency: String
)

// --- 2. Retrofit API Interface ---

interface CdpAuthApi {
    @POST("auth/otp/send")
    suspend fun sendOtp(@Body request: OtpRequest): Response<OtpResponse>

    @POST("auth/otp/verify")
    suspend fun verifyOtp(@Body request: OtpVerificationRequest): Response<AuthResponse>

    @POST("auth/register")
    suspend fun register(@Body request: RegisterRequest): Response<AuthResponse>

    @POST("wallet/create")
    suspend fun createWallet(@Body request: WalletCreationRequest): Response<WalletResponse>

    @POST("auth/refresh")
    suspend fun refreshToken(@Body request: RefreshTokenRequest): Response<AuthResponse>
}

data class RefreshTokenRequest(
    @SerializedName("refresh_token") val refreshToken: String
)

// --- 3. Session Manager (Secure Storage) ---

/**
 * Manages the secure storage and retrieval of authentication tokens.
 * In a real application, this would use AndroidX Security Crypto for EncryptedSharedPreferences.
 */
class SessionManager(context: Context) {
    private val TAG = "SessionManager"
    private val PREFS_NAME = "cdp_auth_prefs"
    private val ACCESS_TOKEN_KEY = "access_token"
    private val REFRESH_TOKEN_KEY = "refresh_token"
    private val USER_ID_KEY = "user_id"

    // Placeholder for EncryptedSharedPreferences setup
    private val masterKeyAlias = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC)
    private val sharedPrefs = EncryptedSharedPreferences.create(
        PREFS_NAME,
        masterKeyAlias,
        context,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    /**
     * Saves the authentication tokens and user ID.
     */
    fun saveAuthData(authResponse: AuthResponse) {
        sharedPrefs.edit().apply {
            putString(ACCESS_TOKEN_KEY, authResponse.accessToken)
            putString(REFRESH_TOKEN_KEY, authResponse.refreshToken)
            putString(USER_ID_KEY, authResponse.userId)
            apply()
        }
        Log.d(TAG, "Auth data saved for user: ${authResponse.userId}")
    }

    /**
     * Retrieves the current access token.
     */
    fun getAccessToken(): String? = sharedPrefs.getString(ACCESS_TOKEN_KEY, null)

    /**
     * Retrieves the current refresh token.
     */
    fun getRefreshToken(): String? = sharedPrefs.getString(REFRESH_TOKEN_KEY, null)

    /**
     * Retrieves the current user ID.
     */
    fun getUserId(): String? = sharedPrefs.getString(USER_ID_KEY, null)

    /**
     * Clears all session data on logout.
     */
    fun clearSession() {
        sharedPrefs.edit().clear().apply()
        Log.d(TAG, "Session cleared.")
    }

    /**
     * Checks if a user is currently logged in.
     */
    fun isLoggedIn(): Boolean = getAccessToken() != null
}

// --- 4. Main Service/Repository Implementation ---

/**
 * The main service class for all CDP authentication and wallet operations.
 * It encapsulates the API calls, session management, and error handling logic.
 *
 * @property api The Retrofit API interface.
 * @property sessionManager The manager for secure session storage.
 */
class CdpAuthService(
    private val api: CdpAuthApi,
    private val sessionManager: SessionManager
) {
    companion object {
        private const val BASE_URL = "https://api.54link.ng/cdp/v1/"
        private const val TAG = "CdpAuthService"

        /**
         * Factory method to create an instance of CdpAuthService.
         */
        fun create(context: Context, baseUrl: String = BASE_URL): CdpAuthService {
            val client = OkHttpClient.Builder()
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                // Add an Interceptor here for logging or adding the Authorization header
                .build()

            val retrofit = Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build()

            val api = retrofit.create(CdpAuthApi::class.java)
            val sessionManager = SessionManager(context)
            return CdpAuthService(api, sessionManager)
        }
    }

    /**
     * Generic safe API call wrapper to handle exceptions and map them to [ResultWrapper].
     * @param call The suspend function representing the API call.
     */
    private suspend fun <T> safeApiCall(call: suspend () -> Response<T>): ResultWrapper<T> {
        return withContext(Dispatchers.IO) {
            try {
                val response = call.invoke()
                if (response.isSuccessful) {
                    val body = response.body()
                    if (body != null) {
                        ResultWrapper.Success(body)
                    } else {
                        // Handle empty body case for successful response (e.g., 204 No Content)
                        @Suppress("UNCHECKED_CAST")
                        ResultWrapper.Success(Unit as T) // Return Unit for successful empty response
                    }
                } else {
                    val errorBody = response.errorBody()?.string()
                    val errorMessage = errorBody ?: "Unknown error"
                    Log.e(TAG, "API Error ${response.code()}: $errorMessage")
                    ResultWrapper.GenericError(response.code(), errorMessage)
                }
            } catch (e: HttpException) {
                Log.e(TAG, "HTTP Exception: ${e.message()}", e)
                ResultWrapper.GenericError(e.code(), e.message())
            } catch (e: IOException) {
                Log.e(TAG, "Network Error: ${e.message}", e)
                ResultWrapper.NetworkError("Please check your internet connection.")
            } catch (e: Exception) {
                Log.e(TAG, "Unknown Exception: ${e.message}", e)
                ResultWrapper.GenericError(null, "An unexpected error occurred.")
            }
        }
    }

    // --- 5. Service Methods (Business Logic) ---

    /**
     * Initiates the OTP process by sending a code to the user's email.
     * @param email The user's email address.
     * @return A [ResultWrapper] indicating success or failure.
     */
    suspend fun sendOtp(email: String): ResultWrapper<OtpResponse> {
        if (email.isBlank() || !android.util.Patterns.EMAIL_ADDRESS.matcher(email).matches()) {
            return ResultWrapper.GenericError(error = "Invalid email format.")
        }
        return safeApiCall { api.sendOtp(OtpRequest(email)) }
    }

    /**
     * Verifies the OTP and completes the login/registration process, saving the session.
     * @param email The user's email address.
     * @param otp The one-time password received by the user.
     * @return A [ResultWrapper] containing the [AuthResponse] on success.
     */
    suspend fun verifyOtpAndLogin(email: String, otp: String): ResultWrapper<AuthResponse> {
        if (otp.length != 6) { // Assuming a 6-digit OTP
            return ResultWrapper.GenericError(error = "OTP must be 6 digits.")
        }

        val result = safeApiCall { api.verifyOtp(OtpVerificationRequest(email, otp)) }

        if (result is ResultWrapper.Success) {
            sessionManager.saveAuthData(result.value)
        }
        return result
    }

    /**
     * Registers a new user with their details.
     * @param request The registration details.
     * @return A [ResultWrapper] containing the [AuthResponse] on success.
     */
    suspend fun registerUser(request: RegisterRequest): ResultWrapper<AuthResponse> {
        // Basic validation
        if (request.passwordHash.length < 8) {
            return ResultWrapper.GenericError(error = "Password must be at least 8 characters.")
        }
        if (request.firstName.isBlank() || request.lastName.isBlank()) {
            return ResultWrapper.GenericError(error = "First and last name are required.")
        }

        val result = safeApiCall { api.register(request) }

        if (result is ResultWrapper.Success) {
            sessionManager.saveAuthData(result.value)
        }
        return result
    }

    /**
     * Creates a new wallet for the authenticated user.
     * @param currency The currency for the new wallet (defaults to NGN).
     * @return A [ResultWrapper] containing the [WalletResponse] on success.
     */
    suspend fun createWallet(currency: String = "NGN"): ResultWrapper<WalletResponse> {
        val userId = sessionManager.getUserId()
        if (userId == null) {
            return ResultWrapper.GenericError(code = 401, error = "User not authenticated. Please log in.")
        }

        val request = WalletCreationRequest(userId = userId, currency = currency)
        return safeApiCall { api.createWallet(request) }
    }

    /**
     * Attempts to refresh the access token using the stored refresh token.
     * @return A [ResultWrapper] containing the new [AuthResponse] on success.
     */
    suspend fun refreshAccessToken(): ResultWrapper<AuthResponse> {
        val refreshToken = sessionManager.getRefreshToken()
        if (refreshToken == null) {
            return ResultWrapper.GenericError(code = 401, error = "No refresh token available.")
        }

        val result = safeApiCall { api.refreshToken(RefreshTokenRequest(refreshToken)) }

        if (result is ResultWrapper.Success) {
            sessionManager.saveAuthData(result.value)
        } else if (result is ResultWrapper.GenericError && result.code == 401) {
            // Refresh token is invalid or expired, force logout
            sessionManager.clearSession()
        }
        return result
    }

    /**
     * Logs out the current user by clearing the session data.
     */
    fun logout() {
        sessionManager.clearSession()
    }

    /**
     * Exposes the session manager's login status.
     */
    fun isUserLoggedIn(): Boolean = sessionManager.isLoggedIn()

    /**
     * Exposes the session manager's current user ID.
     */
    fun getCurrentUserId(): String? = sessionManager.getUserId()
}

// --- 6. Example Usage (For context, not part of the service file) ---
/*
// In your Application class or a DI module:
val cdpAuthService = CdpAuthService.create(applicationContext)

// In a ViewModel:
class AuthViewModel(private val service: CdpAuthService) : ViewModel() {
    private val _otpState = MutableStateFlow<ResultWrapper<OtpResponse>>(ResultWrapper.Loading)
    val otpState: StateFlow<ResultWrapper<OtpResponse>> = _otpState

    fun sendOtp(email: String) {
        viewModelScope.launch {
            _otpState.value = ResultWrapper.Loading
            _otpState.value = service.sendOtp(email)
        }
    }

    // ... other functions for verifyOtpAndLogin, registerUser, etc.
}
*/
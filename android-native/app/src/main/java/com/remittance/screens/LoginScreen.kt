// ===================================================================================
// FILE 1: src/main/kotlin/cdp/CdpAuthService.kt (API Service and Data Models)
// ===================================================================================
package com.nigerianremittance.cdp

import retrofit2.http.Body
import retrofit2.http.POST
import kotlinx.coroutines.delay

// --- Data Models ---

/**
 * Request body for the initial OTP request.
 * @property email The user's email address.
 */
data class OtpRequest(
    val email: String
)

/**
 * Request body for the OTP verification step.
 * @property email The user's email address.
 * @property otp The one-time password received by the user.
 */
data class OtpVerificationRequest(
    val email: String,
    val otp: String
)

/**
 * Response body for a successful OTP verification.
 * @property accessToken The JWT access token for subsequent API calls.
 * @property refreshToken The token used to refresh the access token.
 * @property userId The unique identifier for the user.
 */
data class AuthTokenResponse(
    val accessToken: String,
    val refreshToken: String,
    val userId: String
)

/**
 * Generic API error response model.
 * @property code A unique error code.
 * @property message A human-readable error message.
 */
data class ErrorResponse(
    val code: String,
    val message: String
)

// --- API Service Interface (Simulated Retrofit) ---

/**
 * Interface for the Customer Data Platform (CDP) Authentication API.
 * This simulates a Retrofit service interface.
 */
interface CdpAuthService {

    /**
     * Requests a One-Time Password (OTP) to be sent to the provided email.
     */
    @POST("api/v1/auth/otp/request")
    suspend fun requestOtp(@Body request: OtpRequest)

    /**
     * Verifies the provided OTP and exchanges it for an authentication token.
     */
    @POST("api/v1/auth/otp/verify")
    suspend fun verifyOtp(@Body request: OtpVerificationRequest): AuthTokenResponse
}

// --- Mock Implementation for Testing and Demonstration ---

/**
 * A mock implementation of the CdpAuthService for local development and testing.
 * In a real application, this would be replaced by a Retrofit or Ktor implementation.
 * This mock simulates network delay and basic OTP logic for demonstration.
 */
class MockCdpAuthService : CdpAuthService {
    // Simulate a simple in-memory store for OTPs
    private val otpStore = mutableMapOf<String, String>()

    override suspend fun requestOtp(request: OtpRequest) {
        // Simulate network delay
        delay(1000)

        if (request.email.isBlank() || !request.email.contains("@")) {
            throw Exception("Invalid email format.")
        }

        // Simulate OTP generation (e.g., a 6-digit code)
        val generatedOtp = (100000..999999).random().toString()
        otpStore[request.email] = generatedOtp

        // In a real app, this would trigger an email/SMS send
        println("MOCK: OTP for ${request.email} is $generatedOtp")
    }

    override suspend fun verifyOtp(request: OtpVerificationRequest): AuthTokenResponse {
        // Simulate network delay
        delay(1500)

        val storedOtp = otpStore[request.email]

        if (storedOtp == null) {
            throw Exception("Email not found or OTP not requested.")
        }

        if (storedOtp != request.otp) {
            throw Exception("Invalid OTP provided.")
        }

        // OTP is valid, remove it and return tokens
        otpStore.remove(request.email)
        return AuthTokenResponse(
            accessToken = "mock_jwt_access_token_${request.email}",
            refreshToken = "mock_jwt_refresh_token_${request.email}",
            userId = "user_${request.email.hashCode()}"
        )
    }
}

// ===================================================================================
// FILE 2: src/main/kotlin/viewmodel/LoginViewModel.kt (ViewModel and State Management)
// ===================================================================================
package com.nigerianremittance.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.nigerianremittance.cdp.AuthTokenResponse
import com.nigerianremittance.cdp.CdpAuthService
import com.nigerianremittance.cdp.MockCdpAuthService
import com.nigerianremittance.cdp.OtpRequest
import com.nigerianremittance.cdp.OtpVerificationRequest
import com.nigerianremittance.ui.AuthStep
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.regex.Pattern

/**
 * Data class representing the entire UI state for the Login Screen.
 * It is designed to be immutable for safe state management with StateFlow.
 *
 * @property email The current value of the email input field.
 * @property otp The current value of the OTP input field.
 * @property isEmailValid True if the email passes basic validation.
 * @property isOtpValid True if the OTP passes basic validation.
 * @property emailError The error message for the email field, or null if valid.
 * @property otpError The error message for the OTP field, or null if valid.
 * @property isLoading True if an API call is in progress.
 * @property message A general success or error message to display to the user.
 * @property isError True if the general message is an error.
 * @property currentStep The current step in the authentication flow (EmailInput or OtpInput).
 * @property isAuthenticated True if the user has successfully logged in.
 * @property authToken The authentication token received upon successful login.
 */
data class LoginUiState(
    val email: String = "",
    val otp: String = "",
    val isEmailValid: Boolean = false,
    val isOtpValid: Boolean = false,
    val emailError: String? = null,
    val otpError: String? = null,
    val isLoading: Boolean = false,
    val message: String = "",
    val isError: Boolean = false,
    val currentStep: AuthStep = AuthStep.EmailInput,
    val isAuthenticated: Boolean = false,
    val authToken: AuthTokenResponse? = null
)

/**
 * ViewModel for the Login Screen, handling all business logic and state changes.
 *
 * @param authService The service responsible for communicating with the CDP authentication API.
 */
class LoginViewModel(
    private val authService: CdpAuthService = MockCdpAuthService() // Use Mock for demonstration
) : ViewModel() {

    // Backing property to update the state internally
    private val _uiState = MutableStateFlow(LoginUiState())

    // Publicly exposed StateFlow for the UI to observe
    val uiState: StateFlow<LoginUiState> = _uiState

    // Regex for basic email validation
    private val emailPattern: Pattern = Pattern.compile(
        "^[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,6}$",
        Pattern.CASE_INSENSITIVE
    )

    /**
     * Updates the email input and performs validation.
     */
    fun onEmailChange(newEmail: String) {
        _uiState.update { currentState ->
            val isValid = emailPattern.matcher(newEmail).matches()
            currentState.copy(
                email = newEmail,
                isEmailValid = isValid,
                emailError = if (newEmail.isNotEmpty() && !isValid) "Invalid email format" else null,
                message = "", // Clear previous messages on input change
                isError = false
            )
        }
    }

    /**
     * Updates the OTP input and performs validation (must be 6 digits).
     */
    fun onOtpChange(newOtp: String) {
        // Only allow up to 6 digits
        val filteredOtp = newOtp.filter { it.isDigit() }.take(6)

        _uiState.update { currentState ->
            val isValid = filteredOtp.length == 6
            currentState.copy(
                otp = filteredOtp,
                isOtpValid = isValid,
                otpError = if (filteredOtp.isNotEmpty() && !isValid) "OTP must be 6 digits" else null,
                message = "", // Clear previous messages on input change
                isError = false
            )
        }
    }

    /**
     * Initiates the request for an OTP to the provided email.
     */
    fun onRequestOtp() {
        if (!_uiState.value.isEmailValid) {
            _uiState.update { it.copy(emailError = "Please enter a valid email address.") }
            return
        }

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, message = "Requesting OTP...", isError = false) }
            try {
                authService.requestOtp(OtpRequest(email = _uiState.value.email))
                _uiState.update { currentState ->
                    currentState.copy(
                        isLoading = false,
                        currentStep = AuthStep.OtpInput,
                        message = "OTP sent to ${currentState.email}. Please check your inbox.",
                        isError = false,
                        otp = "", // Clear previous OTP input
                        otpError = null
                    )
                }
            } catch (e: Exception) {
                // Proper error handling for network or API-specific errors
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        message = "Failed to request OTP: ${e.message}",
                        isError = true
                    )
                }
            }
        }
    }

    /**
     * Verifies the provided OTP with the server.
     */
    fun onVerifyOtp() {
        if (!_uiState.value.isOtpValid) {
            _uiState.update { it.copy(otpError = "Please enter the 6-digit OTP.") }
            return
        }

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, message = "Verifying OTP...", isError = false) }
            try {
                val response = authService.verifyOtp(
                    OtpVerificationRequest(
                        email = _uiState.value.email,
                        otp = _uiState.value.otp
                    )
                )
                // Successful login
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        isAuthenticated = true,
                        authToken = response,
                        message = "Login successful! Welcome back.",
                        isError = false
                    )
                }
                // In a real app, navigate to the main screen here
                println("Authentication successful: ${response.accessToken}")

            } catch (e: Exception) {
                // Proper error handling for network or API-specific errors
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        message = "Verification failed: ${e.message}",
                        isError = true
                    )
                }
            }
        }
    }

    /**
     * Resends the OTP by calling the request API again.
     */
    fun onResendOtp() {
        // Simply re-run the request OTP logic
        onRequestOtp()
    }

    /**
     * Resets the flow back to the email input step.
     */
    fun onBackToEmail() {
        _uiState.update { currentState ->
            currentState.copy(
                currentStep = AuthStep.EmailInput,
                otp = "",
                otpError = null,
                message = "",
                isError = false,
                isLoading = false
            )
        }
    }
}

// ===================================================================================
// FILE 3: src/main/kotlin/ui/LoginScreen.kt (Jetpack Compose UI)
// ===================================================================================
package com.nigerianremittance.ui

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.ExperimentalAnimationApi
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.nigerianremittance.R // Assuming R is generated with string resources
import com.nigerianremittance.viewmodel.LoginUiState

// Define a sealed class to represent the different authentication steps
sealed class AuthStep {
    object EmailInput : AuthStep()
    object OtpInput : AuthStep()
}

/**
 * Main composable for the CDP Email OTP Login Screen.
 * It handles the state transition between email input and OTP input.
 *
 * @param uiState The current state of the UI, provided by the ViewModel.
 * @param onEmailChange Callback for when the email input changes.
 * @param onOtpChange Callback for when the OTP input changes.
 * @param onRequestOtp Click handler for the "Request OTP" button.
 * @param onVerifyOtp Click handler for the "Verify OTP" button.
 * @param onResendOtp Click handler for the "Resend OTP" button.
 * @param onBackToEmail Click handler for the "Back to Email" button.
 */
@OptIn(ExperimentalAnimationApi::class)
@Composable
fun LoginScreen(
    uiState: LoginUiState,
    onEmailChange: (String) -> Unit,
    onOtpChange: (String) -> Unit,
    onRequestOtp: () -> Unit,
    onVerifyOtp: () -> Unit,
    onResendOtp: () -> Unit,
    onBackToEmail: () -> Unit,
) {
    Scaffold(
        topBar = {
            // In a real app, use stringResource(R.string.login_title)
            TopAppBar(title = { Text(R.string.login_title) })
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            // Animated content to smoothly transition between the two steps
            AnimatedContent(
                targetState = uiState.currentStep,
                label = "AuthStepTransition"
            ) { targetStep ->
                when (targetStep) {
                    AuthStep.EmailInput -> EmailInputStep(
                        uiState = uiState,
                        onEmailChange = onEmailChange,
                        onRequestOtp = onRequestOtp
                    )
                    AuthStep.OtpInput -> OtpInputStep(
                        uiState = uiState,
                        onOtpChange = onOtpChange,
                        onVerifyOtp = onVerifyOtp,
                        onResendOtp = onResendOtp,
                        onBackToEmail = onBackToEmail
                    )
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Global Error/Success Message Display
            if (uiState.message.isNotEmpty()) {
                val isError = uiState.isError
                Text(
                    text = uiState.message,
                    color = if (isError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth()
                )
            }
        }
    }
}

/**
 * Composable for the initial email input step.
 */
@Composable
private fun EmailInputStep(
    uiState: LoginUiState,
    onEmailChange: (String) -> Unit,
    onRequestOtp: () -> Unit
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            // In a real app, use stringResource(R.string.email_input_prompt)
            text = R.string.email_input_prompt,
            style = MaterialTheme.typography.headlineSmall,
            modifier = Modifier.padding(bottom = 16.dp)
        )

        OutlinedTextField(
            value = uiState.email,
            onValueChange = onEmailChange,
            // In a real app, use stringResource(R.string.email_label)
            label = { Text(R.string.email_label) },
            isError = uiState.emailError != null,
            supportingText = {
                if (uiState.emailError != null) {
                    Text(text = uiState.emailError)
                }
            },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            enabled = !uiState.isLoading // Disable input while loading
        )

        Spacer(modifier = Modifier.height(24.dp))

        Button(
            onClick = onRequestOtp,
            enabled = uiState.isEmailValid && !uiState.isLoading,
            modifier = Modifier.fillMaxWidth()
        ) {
            if (uiState.isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(24.dp),
                    color = MaterialTheme.colorScheme.onPrimary
                )
            } else {
                // In a real app, use stringResource(R.string.request_otp_button)
                Text(R.string.request_otp_button)
            }
        }
    }
}

/**
 * Composable for the OTP input and verification step.
 */
@Composable
private fun OtpInputStep(
    uiState: LoginUiState,
    onOtpChange: (String) -> Unit,
    onVerifyOtp: () -> Unit,
    onResendOtp: () -> Unit,
    onBackToEmail: () -> Unit
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            // In a real app, use stringResource(R.string.otp_input_prompt, uiState.email)
            text = String.format(R.string.otp_input_prompt, uiState.email),
            style = MaterialTheme.typography.headlineSmall,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(bottom = 16.dp)
        )

        OutlinedTextField(
            value = uiState.otp,
            onValueChange = onOtpChange,
            // In a real app, use stringResource(R.string.otp_label)
            label = { Text(R.string.otp_label) },
            isError = uiState.otpError != null,
            supportingText = {
                if (uiState.otpError != null) {
                    Text(text = uiState.otpError)
                }
            },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            enabled = !uiState.isLoading // Disable input while loading
        )

        Spacer(modifier = Modifier.height(24.dp))

        Button(
            onClick = onVerifyOtp,
            enabled = uiState.isOtpValid && !uiState.isLoading,
            modifier = Modifier.fillMaxWidth()
        ) {
            if (uiState.isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(24.dp),
                    color = MaterialTheme.colorScheme.onPrimary
                )
            } else {
                // In a real app, use stringResource(R.string.verify_otp_button)
                Text(R.string.verify_otp_button)
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Resend and Back buttons
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            TextButton(onClick = onBackToEmail, enabled = !uiState.isLoading) {
                // In a real app, use stringResource(R.string.back_to_email_button)
                Text(R.string.back_to_email_button)
            }
            TextButton(onClick = onResendOtp, enabled = !uiState.isLoading) {
                // In a real app, use stringResource(R.string.resend_otp_button)
                Text(R.string.resend_otp_button)
            }
        }
    }
}

// --- Mock R.string for Preview/Standalone Compilation ---

/**
 * A mock R.string object for preview purposes and to allow the code to compile
 * without a full Android project setup. In a real project, this would be
 * replaced by the generated R class and actual string resources.
 */
object R {
    object string {
        const val login_title = "Secure Login"
        const val email_input_prompt = "Enter your email to receive a One-Time Password."
        const val email_label = "Email Address"
        const val request_otp_button = "Request OTP"
        const val otp_input_prompt = "Enter the 6-digit code sent to %s"
        const val otp_label = "One-Time Password"
        const val verify_otp_button = "Verify OTP"
        const val resend_otp_button = "Resend Code"
        const val back_to_email_button = "Change Email"
    }
    // Helper properties to simulate stringResource behavior in a mock environment
    val string.login_title: String get() = string.login_title
    val string.email_input_prompt: String get() = string.email_input_prompt
    val string.email_label: String get() = string.email_label
    val string.request_otp_button: String get() = string.request_otp_button
    val string.otp_input_prompt: String get() = string.otp_input_prompt
    val string.otp_label: String get() = string.otp_label
    val string.verify_otp_button: String get() = string.verify_otp_button
    val string.resend_otp_button: String get() = string.resend_otp_button
    val string.back_to_email_button: String get() = string.back_to_email_button
}

// Mock LoginUiState for preview
val mockEmailState = LoginUiState(
    email = "user@example.com",
    isEmailValid = true,
    currentStep = AuthStep.EmailInput,
    isLoading = false,
    message = "Welcome back!"
)

val mockOtpState = LoginUiState(
    email = "user@example.com",
    currentStep = AuthStep.OtpInput,
    isLoading = true,
    message = "Sending OTP...",
    otp = "123456",
    isOtpValid = true
)

@Preview(showBackground = true)
@Composable
fun PreviewLoginScreenEmail() {
    // Assuming a custom theme is applied here
    MaterialTheme {
        LoginScreen(
            uiState = mockEmailState,
            onEmailChange = {},
            onOtpChange = {},
            onRequestOtp = {},
            onVerifyOtp = {},
            onResendOtp = {},
            onBackToEmail = {}
        )
    }
}

@Preview(showBackground = true)
@Composable
fun PreviewLoginScreenOtp() {
    // Assuming a custom theme is applied here
    MaterialTheme {
        LoginScreen(
            uiState = mockOtpState,
            onEmailChange = {},
            onOtpChange = {},
            onRequestOtp = {},
            onVerifyOtp = {},
            onResendOtp = {},
            onBackToEmail = {}
        )
    }
}

// ===================================================================================
// FILE 4: src/main/kotlin/MainActivity.kt (Integration/Entry Point)
// ===================================================================================
package com.nigerianremittance

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import com.nigerianremittance.ui.LoginScreen
import com.nigerianremittance.viewmodel.LoginViewModel

/**
 * Main Activity for the Nigerian Remittance Platform.
 * This serves as the entry point and integrates the Login UI with the ViewModel.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            // Assuming a custom theme is defined, using MaterialTheme as a placeholder
            MaterialTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    // Instantiate the ViewModel using the Hilt/ViewModel factory pattern
                    // For simplicity, we use the default viewModel() here.
                    val viewModel: LoginViewModel = viewModel()
                    val uiState by viewModel.uiState.collectAsState()

                    // The LoginScreen is the main composable for the authentication flow
                    LoginScreen(
                        uiState = uiState,
                        onEmailChange = viewModel::onEmailChange,
                        onOtpChange = viewModel::onOtpChange,
                        onRequestOtp = viewModel::onRequestOtp,
                        onVerifyOtp = viewModel::onVerifyOtp,
                        onResendOtp = viewModel::onResendOtp,
                        onBackToEmail = viewModel::onBackToEmail
                    )

                    // TODO: Add navigation logic here once isAuthenticated is true
                    if (uiState.isAuthenticated) {
                        // Example: Navigate to Home Screen
                        // Log.d("MainActivity", "User authenticated: ${uiState.authToken?.userId}")
                    }
                }
            }
        }
    }
}

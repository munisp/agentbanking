package com.pos54link.screens

import android.content.Context
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pos54link.R // Placeholder for string resources
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

// --- 1. State Management (BiometricAuthScreenState) ---

data class BiometricAuthScreenState(
    val isLoading: Boolean = false,
    val isBiometricAvailable: Boolean = false,
    val isBiometricSetup: Boolean = false,
    val authStatusMessage: String = "Tap to set up Biometric Authentication",
    val errorMessage: String? = null,
    val lastAuthSuccess: Boolean = false
)

// --- 2. Repository (BiometricAuthRepository) ---

interface IBiometricAuthRepository {
    suspend fun checkBiometricCapability(context: Context): Int
    suspend fun saveBiometricSetupStatus(isSetup: Boolean)
    suspend fun performPaymentGatewaySetup(gateway: String): Result<String>
    suspend fun syncOfflineData(): Result<Unit>
}

class BiometricAuthRepository : IBiometricAuthRepository {
    // Placeholder for Retrofit, Room, and payment gateway integration
    // In a real app, this would handle API calls (Retrofit) and local DB access (Room)

    /**
     * Checks if biometric hardware is available and configured.
     * @return BiometricManager.BIOMETRIC_SUCCESS, BIOMETRIC_ERROR_NO_HARDWARE, etc.
     */
    override suspend fun checkBiometricCapability(context: Context): Int {
        val biometricManager = BiometricManager.from(context)
        return biometricManager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.DEVICE_CREDENTIAL)
    }

    /**
     * Placeholder to save the setup status to SharedPreferences or Room.
     */
    override suspend fun saveBiometricSetupStatus(isSetup: Boolean) {
        // Implementation for saving setup status (e.g., to Room or DataStore)
        // For now, it's a no-op placeholder
        println("Saving biometric setup status: $isSetup")
    }

    /**
     * Placeholder for payment gateway setup (e.g., API call via Retrofit).
     */
    override suspend fun performPaymentGatewaySetup(gateway: String): Result<String> {
        // Retrofit integration would go here
        return Result.success("Setup successful for $gateway")
    }

    /**
     * Placeholder for syncing offline data (e.g., Room DB operations).
     */
    override suspend fun syncOfflineData(): Result<Unit> {
        // Room DB operations for offline mode would go here
        return Result.success(Unit)
    }
}

// --- 3. ViewModel (BiometricAuthViewModel) ---

class BiometricAuthViewModel(
    private val repository: IBiometricAuthRepository = BiometricAuthRepository()
) : ViewModel() {

    private val _state = MutableStateFlow(BiometricAuthScreenState())
    val state: StateFlow<BiometricAuthScreenState> = _state.asStateFlow()

    init {
        // Initialize with a check for biometric capability (requires context, so we'll call it from the Composable's LaunchedEffect)
        // Or, if using Hilt, we could pass ApplicationContext here. For simplicity, we'll rely on the Composable for the initial check.
    }

    /**
     * Updates the biometric capability status in the state.
     */
    fun updateBiometricCapability(capability: Int) {
        val isAvailable = capability == BiometricManager.BIOMETRIC_SUCCESS
        _state.value = _state.value.copy(
            isBiometricAvailable = isAvailable,
            authStatusMessage = when (capability) {
                BiometricManager.BIOMETRIC_SUCCESS -> "Biometric authentication is ready."
                BiometricManager.BIOMETRIC_ERROR_NO_HARDWARE -> "No biometric hardware detected."
                BiometricManager.BIOMETRIC_ERROR_NONE_ENROLLED -> "No biometrics enrolled. Please enroll in settings."
                else -> "Biometric check failed with code: $capability"
            },
            errorMessage = if (isAvailable) null else "Biometric setup required."
        )
    }

    /**
     * Handles the result of the biometric authentication attempt.
     */
    fun handleAuthResult(success: Boolean, error: String? = null) {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = false)
            if (success) {
                _state.value = _state.value.copy(
                    isBiometricSetup = true,
                    lastAuthSuccess = true,
                    authStatusMessage = "Biometric setup successful! Authentication granted.",
                    errorMessage = null
                )
                repository.saveBiometricSetupStatus(true)
                // Trigger background tasks like payment gateway setup and offline sync
                triggerPostAuthTasks()
            } else {
                _state.value = _state.value.copy(
                    lastAuthSuccess = false,
                    authStatusMessage = "Biometric authentication failed.",
                    errorMessage = error
                )
            }
        }
    }

    /**
     * Triggers placeholder tasks that should run after successful biometric setup.
     */
    private fun triggerPostAuthTasks() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true)
            // Placeholder for multiple payment gateway setup
            val gateways = listOf("Paystack", "Flutterwave", "Interswitch")
            gateways.forEach { gateway ->
                repository.performPaymentGatewaySetup(gateway)
                    .onFailure {
                        _state.value = _state.value.copy(errorMessage = "Failed to set up $gateway: ${it.message}")
                    }
            }

            // Placeholder for offline data sync
            repository.syncOfflineData()
                .onFailure {
                    _state.value = _state.value.copy(errorMessage = "Failed to sync offline data: ${it.message}")
                }

            _state.value = _state.value.copy(isLoading = false)
        }
    }

    /**
     * Initiates the biometric prompt flow.
     */
    fun startBiometricSetup(activity: FragmentActivity) {
        if (!_state.value.isBiometricAvailable) {
            _state.value = _state.value.copy(errorMessage = "Biometric authentication is not available or set up on this device.")
            return
        }

        _state.value = _state.value.copy(isLoading = true, errorMessage = null)

        val executor = ContextCompat.getMainExecutor(activity)
        val biometricPrompt = BiometricPrompt(activity, executor,
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    super.onAuthenticationError(errorCode, errString)
                    handleAuthResult(false, "Auth Error ($errorCode): $errString")
                }

                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    super.onAuthenticationSucceeded(result)
                    handleAuthResult(true)
                }

                override fun onAuthenticationFailed() {
                    super.onAuthenticationFailed()
                    // This is usually handled by the system UI, but we can log or update state if needed
                    // handleAuthResult(false, "Authentication failed.")
                }
            })

        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle("Biometric Authentication Setup")
            .setSubtitle("Use your fingerprint or face to enable quick login.")
            .setNegativeButtonText("Cancel")
            .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.DEVICE_CREDENTIAL)
            .build()

        biometricPrompt.authenticate(promptInfo)
    }

    /**
     * Checks biometric capability on initialization.
     */
    fun checkCapability(context: Context) {
        viewModelScope.launch {
            val capability = repository.checkBiometricCapability(context)
            updateBiometricCapability(capability)
        }
    }
}

// --- 4. Composable Screen (BiometricAuthScreen) ---

@Composable
fun BiometricAuthScreen(
    viewModel: BiometricAuthViewModel = BiometricAuthViewModel()
) {
    // R.string.app_name is a placeholder for a real string resource
    val screenTitle = "Biometric Setup"
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current
    val activity = context as? FragmentActivity

    // Initial check for biometric capability
    LaunchedEffect(Unit) {
        viewModel.checkCapability(context)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(screenTitle) },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    titleContentColor = MaterialTheme.colorScheme.primary,
                )
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(16.dp)
                .semantics { contentDescription = "Biometric Authentication Setup Screen" },
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            // Loading State
            if (state.isLoading) {
                CircularProgressIndicator(Modifier.padding(bottom = 16.dp))
                Text("Processing setup and syncing data...", style = MaterialTheme.typography.bodyLarge)
            }

            // Status Message
            Text(
                text = state.authStatusMessage,
                style = MaterialTheme.typography.headlineSmall,
                color = if (state.lastAuthSuccess) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.padding(bottom = 24.dp)
            )

            // Action Button
            Button(
                onClick = {
                    if (activity != null) {
                        viewModel.startBiometricSetup(activity)
                    } else {
                        viewModel.handleAuthResult(false, "Error: Could not find FragmentActivity context.")
                    }
                },
                enabled = !state.isLoading && state.isBiometricAvailable,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp)
                    .semantics { contentDescription = "Set up Biometric Authentication" }
            ) {
                Text(if (state.isBiometricSetup) "Re-authenticate" else "Set Up Biometrics")
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Error Message
            state.errorMessage?.let { error ->
                Card(
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        text = "Error: $error",
                        color = MaterialTheme.colorScheme.onErrorContainer,
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.padding(12.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(32.dp))

            // Accessibility/Documentation Note
            Text(
                text = "Note: This screen supports TalkBack accessibility and follows Material Design 3 guidelines.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f)
            )
        }
    }
}

// --- 5. Preview and Documentation ---

@Preview(showBackground = true)
@Composable
fun PreviewBiometricAuthScreen() {
    // Placeholder for a custom theme
    MaterialTheme {
        BiometricAuthScreen(
            viewModel = BiometricAuthViewModel(
                repository = object : IBiometricAuthRepository {
                    override suspend fun checkBiometricCapability(context: Context): Int = BiometricManager.BIOMETRIC_SUCCESS
                    override suspend fun saveBiometricSetupStatus(isSetup: Boolean) {}
                    override suspend fun performPaymentGatewaySetup(gateway: String): Result<String> = Result.success("Mock Success")
                    override suspend fun syncOfflineData(): Result<Unit> = Result.success(Unit)
                }
            )
        )
    }
}

/*
 * Documentation: BiometricAuthScreen.kt
 *
 * This file implements the Biometric Authentication Setup screen using Jetpack Compose and the MVVM pattern.
 *
 * Architecture:
 * - BiometricAuthScreenState: Data class holding the UI state (loading, availability, messages).
 * - IBiometricAuthRepository/BiometricAuthRepository: Handles data logic, including checking biometric capability,
 *   saving setup status, and placeholder functions for Retrofit (payment gateway setup) and Room (offline sync).
 * - BiometricAuthViewModel: Manages the state flow, business logic, and orchestrates the BiometricPrompt.
 *   It uses a coroutine scope (viewModelScope) for all suspend functions.
 * - BiometricAuthScreen: The Composable function that observes the ViewModel state and renders the UI.
 *
 * Key Integrations:
 * 1. BiometricPrompt: Integrated within the ViewModel's `startBiometricSetup` function, requiring a `FragmentActivity` context.
 *    The result is handled via `AuthenticationCallback` and passed back to the ViewModel's `handleAuthResult`.
 * 2. MVVM/State: Uses `StateFlow` for robust state management.
 * 3. Repository Pattern: Provides abstraction for data sources (API/DB/BiometricManager).
 * 4. Error/Loading States: Handled by `isLoading` and `errorMessage` in the state.
 * 5. Accessibility: Uses `Modifier.semantics` for content descriptions (TalkBack support).
 * 6. Material Design 3: Uses `Scaffold`, `TopAppBarDefaults`, `Button`, and `Card` with MaterialTheme colors.
 * 7. Placeholder Integrations:
 *    - Retrofit: Mocked in `performPaymentGatewaySetup`.
 *    - Room: Mocked in `syncOfflineData`.
 *    - Payment Gateways (Paystack, Flutterwave, Interswitch): Mocked setup in `triggerPostAuthTasks`.
 *
 * Dependencies (Required in build.gradle.kts):
 * - androidx.compose.ui
 * - androidx.compose.material3
 * - androidx.lifecycle.viewmodel.compose
 * - androidx.lifecycle.viewmodel.ktx
 * - androidx.biometric:biometric-ktx
 * - kotlinx-coroutines-core/android
 * - androidx.fragment:fragment-ktx (for FragmentActivity casting)
 * - Retrofit (for real API calls)
 * - Room (for real offline mode)
 */

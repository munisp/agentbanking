package com.pos54link.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pos54link.R // Assuming R.string.app_name and other resources exist
import com.pos54link.data.local.PinSetupDao // Assuming Room DAO
import com.pos54link.data.local.PinSetupDatabase // Assuming Room Database
import com.pos54link.data.model.PinSetupRequest
import com.pos54link.data.remote.AuthService // Assuming Retrofit Service
import com.pos54link.data.repository.PinSetupRepository
import com.pos54link.domain.PinStrengthValidator
import com.pos54link.domain.PinStrengthValidator.PinStrength
import com.pos54link.ui.theme.AppTheme // Assuming a custom theme
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.io.IOException

// --- 1. Data Layer (Stubs) ---

/**
 * Data class representing the PIN setup state.
 */
data class PinSetupState(
    val pin: String = "",
    val confirmPin: String = "",
    val pinStrength: PinStrength = PinStrength.WEAK,
    val pinError: String? = null,
    val confirmPinError: String? = null,
    val isLoading: Boolean = false,
    val isSuccess: Boolean = false,
    val error: String? = null,
    val isBiometricAvailable: Boolean = false,
    val isOfflineMode: Boolean = false,
    val selectedPaymentGateway: String = "Paystack"
)

/**
 * Stub for Retrofit Service.
 */
interface AuthService {
    suspend fun setupPin(request: PinSetupRequest): retrofit2.Response<Unit>
}

/**
 * Stub for Room DAO.
 */
interface PinSetupDao {
    suspend fun savePinLocally(pin: String)
}

/**
 * Stub for Room Database.
 */
abstract class PinSetupDatabase {
    abstract fun pinSetupDao(): PinSetupDao
}

/**
 * Stub for PinSetupRequest.
 */
data class PinSetupRequest(val pin: String)

// --- 2. Domain Layer (Validator) ---

/**
 * Domain logic for PIN strength validation.
 */
object PinStrengthValidator {
    enum class PinStrength {
        WEAK, MEDIUM, STRONG
    }

    fun validate(pin: String): PinStrength {
        return when {
            pin.length < 6 -> PinStrength.WEAK
            pin.all { it.isDigit() } && pin.length >= 6 -> PinStrength.MEDIUM
            pin.length >= 8 && pin.any { it.isLetter() } -> PinStrength.STRONG
            else -> PinStrength.WEAK
        }
    }
}

// --- 3. Data Layer (Repository) ---

/**
 * Repository to handle data operations, abstracting local (Room) and remote (Retrofit) sources.
 */
class PinSetupRepository(
    private val authService: AuthService,
    private val pinSetupDao: PinSetupDao
) {
    /**
     * Attempts to set up the PIN remotely, falling back to local storage on failure.
     */
    suspend fun setupPin(pin: String) {
        try {
            val response = authService.setupPin(PinSetupRequest(pin))
            if (!response.isSuccessful) {
                throw HttpException(response)
            }
            // Success, no need to save locally unless for caching
        } catch (e: IOException) {
            // Network error, save locally for offline mode
            pinSetupDao.savePinLocally(pin)
            throw e // Re-throw to inform ViewModel of the network issue
        } catch (e: HttpException) {
            // API error
            throw e
        }
    }

    /**
     * Stub for biometric check. In a real app, this would use BiometricManager.
     */
    fun checkBiometricAvailability(): Boolean {
        // Placeholder for actual biometric check logic
        return true
    }
}

// --- 4. Presentation Layer (ViewModel) ---

/**
 * ViewModel for the PinSetupScreen, handling business logic and state.
 */
class PinSetupViewModel(
    private val repository: PinSetupRepository
) : ViewModel() {

    private val _state = MutableStateFlow(PinSetupState())
    val state: StateFlow<PinSetupState> = _state.asStateFlow()

    init {
        _state.update { it.copy(isBiometricAvailable = repository.checkBiometricAvailability()) }
    }

    /**
     * Updates the PIN field and performs real-time validation.
     */
    fun onPinChange(newPin: String) {
        _state.update { currentState ->
            val strength = PinStrengthValidator.validate(newPin)
            val error = if (newPin.length > 0 && strength == PinStrength.WEAK) {
                "PIN is too weak. Try a longer or more complex PIN."
            } else if (newPin.length > 10) {
                "PIN cannot exceed 10 digits."
            } else {
                null
            }
            currentState.copy(
                pin = newPin,
                pinStrength = strength,
                pinError = error,
                confirmPinError = if (currentState.confirmPin.isNotEmpty() && currentState.confirmPin != newPin) "PINs do not match." else null
            )
        }
    }

    /**
     * Updates the Confirm PIN field and performs real-time validation.
     */
    fun onConfirmPinChange(newConfirmPin: String) {
        _state.update { currentState ->
            val error = if (newConfirmPin.isNotEmpty() && newConfirmPin != currentState.pin) {
                "PINs do not match."
            } else {
                null
            }
            currentState.copy(
                confirmPin = newConfirmPin,
                confirmPinError = error
            )
        }
    }

    /**
     * Handles the PIN setup submission.
     */
    fun setupPin() {
        val currentState = _state.value

        // Final validation before submission
        if (currentState.pin.isEmpty() || currentState.confirmPin.isEmpty()) {
            _state.update { it.copy(pinError = "PIN is required.", confirmPinError = "Confirmation is required.") }
            return
        }
        if (currentState.pin != currentState.confirmPin) {
            _state.update { it.copy(confirmPinError = "PINs do not match.") }
            return
        }
        if (currentState.pinStrength == PinStrength.WEAK) {
            _state.update { it.copy(pinError = "PIN strength is too weak.") }
            return
        }

        _state.update { it.copy(isLoading = true, error = null) }

        viewModelScope.launch {
            try {
                repository.setupPin(currentState.pin)
                _state.update { it.copy(isLoading = false, isSuccess = true) }
            } catch (e: IOException) {
                // Network error, offline mode engaged
                _state.update {
                    it.copy(
                        isLoading = false,
                        error = "Network error. PIN saved locally for offline sync.",
                        isOfflineMode = true
                    )
                }
            } catch (e: HttpException) {
                // API error
                _state.update {
                    it.copy(
                        isLoading = false,
                        error = "Setup failed: ${e.message()}"
                    )
                }
            } catch (e: Exception) {
                // General error
                _state.update {
                    it.copy(
                        isLoading = false,
                        error = "An unexpected error occurred."
                    )
                }
            }
        }
    }

    /**
     * Stub for initiating biometric authentication.
     */
    fun startBiometricAuth(onSuccess: () -> Unit, onFailure: () -> Unit) {
        // In a real app, this would launch BiometricPrompt
        // For now, we simulate success
        onSuccess()
    }

    /**
     * Updates the selected payment gateway.
     */
    fun onPaymentGatewaySelected(gateway: String) {
        _state.update { it.copy(selectedPaymentGateway = gateway) }
    }
}

// --- 5. Presentation Layer (UI) ---

/**
 * The main Composable function for the PIN Setup Screen.
 */
@Composable
fun PinSetupScreen(
    viewModel: PinSetupViewModel = viewModel(
        factory = PinSetupViewModelFactory(
            repository = PinSetupRepository(
                authService = object : AuthService {
                    override suspend fun setupPin(request: PinSetupRequest): retrofit2.Response<Unit> {
                        // Simulate API call success
                        kotlinx.coroutines.delay(1000)
                        return retrofit2.Response.success(Unit)
                    }
                },
                pinSetupDao = object : PinSetupDao {
                    override suspend fun savePinLocally(pin: String) {
                        // Simulate Room save
                        println("PIN saved locally: $pin")
                    }
                }
            )
        )
    )
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current

    Scaffold(
        topBar = {
            TopAppBar(title = { Text(stringResource(R.string.pin_setup_title)) })
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = stringResource(R.string.pin_setup_description),
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.padding(bottom = 24.dp)
            )

            PinInputField(
                value = state.pin,
                onValueChange = viewModel::onPinChange,
                label = stringResource(R.string.pin_label),
                isError = state.pinError != null,
                errorMessage = state.pinError,
                strength = state.pinStrength
            )

            Spacer(modifier = Modifier.height(16.dp))

            PinInputField(
                value = state.confirmPin,
                onValueChange = viewModel::onConfirmPinChange,
                label = stringResource(R.string.confirm_pin_label),
                isError = state.confirmPinError != null,
                errorMessage = state.confirmPinError,
                strength = null // No strength indicator for confirm field
            )

            Spacer(modifier = Modifier.height(24.dp))

            PaymentGatewaySelector(
                selectedGateway = state.selectedPaymentGateway,
                onGatewaySelected = viewModel::onPaymentGatewaySelected
            )

            Spacer(modifier = Modifier.height(24.dp))

            if (state.isLoading) {
                CircularProgressIndicator(Modifier.semantics { contentDescription = "Loading" })
            } else if (state.error != null) {
                Text(
                    text = state.error!!,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.semantics { contentDescription = "Error message: ${state.error}" }
                )
            } else if (state.isSuccess) {
                Text(
                    text = stringResource(R.string.pin_setup_success),
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.semantics { contentDescription = "PIN setup successful" }
                )
            }

            Spacer(modifier = Modifier.height(24.dp))

            Button(
                onClick = viewModel::setupPin,
                enabled = !state.isLoading && state.pinError == null && state.confirmPinError == null && state.pin.isNotEmpty() && state.confirmPin.isNotEmpty(),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp)
                    .semantics { contentDescription = "Set PIN button" }
            ) {
                Text(stringResource(R.string.set_pin_button))
            }

            if (state.isBiometricAvailable) {
                Spacer(modifier = Modifier.height(16.dp))
                OutlinedButton(
                    onClick = {
                        // In a real app, this would trigger the BiometricPrompt flow
                        viewModel.startBiometricAuth(
                            onSuccess = { /* Handle success, e.g., navigate */ },
                            onFailure = { /* Handle failure, e.g., show message */ }
                        )
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(56.dp)
                        .semantics { contentDescription = "Use Biometrics button" }
                ) {
                    Text(stringResource(R.string.use_biometrics_button))
                }
            }

            if (state.isOfflineMode) {
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    text = stringResource(R.string.offline_mode_warning),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.tertiary,
                    modifier = Modifier.semantics { contentDescription = "Offline mode warning" }
                )
            }
        }
    }
}

/**
 * Custom Composable for PIN input with strength validation and error display.
 */
@Composable
fun PinInputField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    isError: Boolean,
    errorMessage: String?,
    strength: PinStrengthValidator.PinStrength?
) {
    var passwordVisible by rememberSaveable { mutableStateOf(false) }

    Column(modifier = Modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = value,
            onValueChange = onValueChange,
            label = { Text(label) },
            isError = isError,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
            visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
            trailingIcon = {
                val image = if (passwordVisible)
                    Icons.Filled.Visibility
                else Icons.Filled.VisibilityOff

                val description = if (passwordVisible) "Hide PIN" else "Show PIN"

                IconButton(onClick = { passwordVisible = !passwordVisible }) {
                    Icon(imageVector = image, contentDescription = description)
                }
            },
            modifier = Modifier
                .fillMaxWidth()
                .semantics { contentDescription = label }
        )

        if (isError && errorMessage != null) {
            Text(
                text = errorMessage,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(start = 16.dp, top = 4.dp)
            )
        } else if (strength != null) {
            PinStrengthIndicator(strength = strength)
        }
    }
}

/**
 * Composable to display the PIN strength visually.
 */
@Composable
fun PinStrengthIndicator(strength: PinStrengthValidator.PinStrength) {
    val (text, color) = when (strength) {
        PinStrength.WEAK -> Pair("Weak", MaterialTheme.colorScheme.error)
        PinStrength.MEDIUM -> Pair("Medium", MaterialTheme.colorScheme.tertiary)
        PinStrength.STRONG -> Pair("Strong", MaterialTheme.colorScheme.primary)
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 16.dp, top = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = "Strength: $text",
            color = color,
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.semantics { contentDescription = "PIN strength is $text" }
        )
        Spacer(modifier = Modifier.width(8.dp))
        LinearProgressIndicator(
            progress = when (strength) {
                PinStrength.WEAK -> 0.3f
                PinStrength.MEDIUM -> 0.6f
                PinStrength.STRONG -> 1.0f
            },
            color = color,
            modifier = Modifier
                .width(100.dp)
                .semantics { contentDescription = "PIN strength progress bar" }
        )
    }
}

/**
 * Composable for selecting a payment gateway.
 */
@Composable
fun PaymentGatewaySelector(
    selectedGateway: String,
    onGatewaySelected: (String) -> Unit
) {
    val gateways = listOf("Paystack", "Flutterwave", "Interswitch")
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = stringResource(R.string.select_gateway_label),
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(bottom = 8.dp)
        )
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            gateways.forEach { gateway ->
                FilterChip(
                    selected = selectedGateway == gateway,
                    onClick = { onGatewaySelected(gateway) },
                    label = { Text(gateway) },
                    modifier = Modifier.semantics { contentDescription = "Select $gateway payment gateway" }
                )
            }
        }
    }
}

// --- 6. ViewModel Factory (for dependency injection) ---

/**
 * Factory to create the PinSetupViewModel with dependencies.
 */
class PinSetupViewModelFactory(
    private val repository: PinSetupRepository
) : androidx.lifecycle.ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(PinSetupViewModel::class.java)) {
            return PinSetupViewModel(repository) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}

// --- 7. Preview (Stubs for resources) ---

// Assuming these resources exist in res/values/strings.xml
// For the purpose of this file, we define them as constants for the preview
private object R {
    object string {
        const val pin_setup_title = "Create Your PIN"
        const val pin_setup_description = "Set a secure PIN for your transactions."
        const val pin_label = "New PIN"
        const val confirm_pin_label = "Confirm PIN"
        const val set_pin_button = "Set PIN"
        const val use_biometrics_button = "Use Biometrics"
        const val pin_setup_success = "PIN setup successful!"
        const val offline_mode_warning = "Offline mode: PIN saved locally. Will sync on next connection."
        const val select_gateway_label = "Select Primary Payment Gateway"
    }
}

@Preview(showBackground = true)
@Composable
fun PreviewPinSetupScreen() {
    AppTheme {
        PinSetupScreen(
            viewModel = PinSetupViewModel(
                repository = PinSetupRepository(
                    authService = object : AuthService {
                        override suspend fun setupPin(request: PinSetupRequest): retrofit2.Response<Unit> {
                            return retrofit2.Response.success(Unit)
                        }
                    },
                    pinSetupDao = object : PinSetupDao {
                        override suspend fun savePinLocally(pin: String) {}
                    }
                )
            )
        )
    }
}

package com.pos54link.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
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
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pos54link.R // Assuming R.string. and R.drawable. are available
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

// --- 1. Data Models ---

/**
 * Data class representing the user's settings preferences.
 */
data class UserSettings(
    val isDarkMode: Boolean = false,
    val language: String = "English",
    val isPushNotificationsEnabled: Boolean = true,
    val defaultCurrency: String = "NGN",
    val isBiometricAuthEnabled: Boolean = false,
    val paymentGateway: String = "Paystack"
)

/**
 * Sealed class to represent the state of the settings screen.
 */
sealed class SettingsState {
    data object Loading : SettingsState()
    data class Success(val settings: UserSettings) : SettingsState()
    data class Error(val message: String) : SettingsState()
}

// --- 2. Repository (Mocked) ---

/**
 * Repository for handling data operations related to user settings.
 * In a real app, this would integrate with Retrofit (API) and Room (DB).
 */
class SettingsRepository {
    // Mock API service interface (Retrofit)
    interface SettingsApiService {
        suspend fun fetchSettings(): UserSettings
        suspend fun updateSettings(settings: UserSettings): UserSettings
    }

    // Mock Room DAO interface
    interface SettingsDao {
        suspend fun getSettings(): UserSettings?
        suspend fun saveSettings(settings: UserSettings)
    }

    // Mock implementations
    private val mockApiService = object : SettingsApiService {
        private var currentSettings = UserSettings()
        override suspend fun fetchSettings(): UserSettings {
            delay(500) // Simulate network delay
            return currentSettings
        }

        override suspend fun updateSettings(settings: UserSettings): UserSettings {
            delay(500) // Simulate network delay
            currentSettings = settings
            return currentSettings
        }
    }

    private val mockDao = object : SettingsDao {
        private var cachedSettings: UserSettings? = null
        override suspend fun getSettings(): UserSettings? {
            return cachedSettings
        }

        override suspend fun saveSettings(settings: UserSettings) {
            cachedSettings = settings
        }
    }

    /**
     * Fetches settings, prioritizing local cache (offline mode) and falling back to API.
     */
    suspend fun getSettings(): UserSettings {
        // 1. Try Room (Offline Mode)
        val localSettings = mockDao.getSettings()
        if (localSettings != null) return localSettings

        // 2. Try Retrofit (API Call)
        return try {
            val apiSettings = mockApiService.fetchSettings()
            mockDao.saveSettings(apiSettings) // Cache successful fetch
            apiSettings
        } catch (e: Exception) {
            // In a real app, handle network errors more gracefully
            throw IllegalStateException("Failed to fetch settings from API and no local data available.")
        }
    }

    /**
     * Updates settings locally and remotely.
     */
    suspend fun updateSettings(settings: UserSettings): UserSettings {
        // 1. Update API
        val updatedSettings = mockApiService.updateSettings(settings)
        // 2. Update Room
        mockDao.saveSettings(updatedSettings)
        return updatedSettings
    }
}

// --- 3. ViewModel ---

/**
 * ViewModel to manage the state and business logic for the SettingsScreen.
 */
class SettingsViewModel(
    private val repository: SettingsRepository = SettingsRepository()
) : ViewModel() {

    private val _state = MutableStateFlow<SettingsState>(SettingsState.Loading)
    val state: StateFlow<SettingsState> = _state.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    // Form validation state (e.g., for a password change form)
    private val _passwordInput = MutableStateFlow("")
    val passwordInput: StateFlow<String> = _passwordInput.asStateFlow()

    private val _passwordError = MutableStateFlow<String?>(null)
    val passwordError: StateFlow<String?> = _passwordError.asStateFlow()

    init {
        loadSettings()
    }

    fun loadSettings() {
        viewModelScope.launch {
            _state.value = SettingsState.Loading
            try {
                val settings = repository.getSettings()
                _state.value = SettingsState.Success(settings)
            } catch (e: Exception) {
                _state.value = SettingsState.Error(e.message ?: "An unknown error occurred.")
            }
        }
    }

    fun updateSetting(transform: (UserSettings) -> UserSettings) {
        val currentState = _state.value
        if (currentState is SettingsState.Success) {
            val newSettings = transform(currentState.settings)
            _state.value = SettingsState.Success(newSettings) // Optimistic update

            viewModelScope.launch {
                try {
                    repository.updateSettings(newSettings)
                } catch (e: Exception) {
                    // Rollback optimistic update and show error
                    _state.value = currentState // Revert to previous state
                    _errorMessage.value = "Failed to save setting: ${e.message}"
                }
            }
        }
    }

    fun onPasswordInputChange(newPassword: String) {
        _passwordInput.value = newPassword
        validatePassword(newPassword)
    }

    private fun validatePassword(password: String) {
        _passwordError.value = when {
            password.isEmpty() -> "Password cannot be empty"
            password.length < 8 -> "Password must be at least 8 characters"
            !password.contains(Regex("[A-Z]")) -> "Must contain an uppercase letter"
            else -> null
        }
    }

    fun clearError() {
        _errorMessage.value = null
    }
}

// --- 4. Composable UI ---

/**
 * Main Composable function for the Settings Screen.
 */
@Composable
fun SettingsScreen(
    viewModel: SettingsViewModel = viewModel(),
    onBack: () -> Unit = {}
) {
    val state by viewModel.state.collectAsState()
    val errorMessage by viewModel.errorMessage.collectAsState()
    val context = LocalContext.current

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back"
                        )
                    }
                }
            )
        },
        snackbarHost = {
            if (errorMessage != null) {
                SnackbarHost(hostState = remember { SnackbarHostState() }) {
                    Snackbar(
                        action = {
                            TextButton(onClick = viewModel::clearError) {
                                Text("Dismiss")
                            }
                        }
                    ) {
                        Text(errorMessage!!)
                    }
                }
            }
        }
    ) { paddingValues ->
        when (state) {
            is SettingsState.Loading -> LoadingState(Modifier.padding(paddingValues))
            is SettingsState.Error -> ErrorState(
                (state as SettingsState.Error).message,
                viewModel::loadSettings,
                Modifier.padding(paddingValues)
            )
            is SettingsState.Success -> SettingsContent(
                settings = (state as SettingsState.Success).settings,
                viewModel = viewModel,
                modifier = Modifier.padding(paddingValues)
            )
        }
    }
}

@Composable
fun LoadingState(modifier: Modifier = Modifier) {
    Box(
        modifier = modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        CircularProgressIndicator(
            Modifier.semantics { contentDescription = "Loading settings" }
        )
    }
}

@Composable
fun ErrorState(
    message: String,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            text = "Error: $message",
            color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.titleMedium
        )
        Spacer(Modifier.height(16.dp))
        Button(onClick = onRetry) {
            Text("Retry")
        }
    }
}

@Composable
fun SettingsContent(
    settings: UserSettings,
    viewModel: SettingsViewModel,
    modifier: Modifier = Modifier
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(vertical = 8.dp)
    ) {
        // --- App Settings ---
        item { SettingsHeader("App Preferences") }
        item {
            SwitchSettingItem(
                icon = Icons.Default.DarkMode,
                title = "Dark Mode",
                description = "Toggle between light and dark themes",
                checked = settings.isDarkMode,
                onCheckedChange = { isChecked ->
                    viewModel.updateSetting { it.copy(isDarkMode = isChecked) }
                }
            )
        }
        item {
            ClickableSettingItem(
                icon = Icons.Default.Language,
                title = "Language",
                description = settings.language,
                onClick = { /* Navigate to Language selection screen */ }
            )
        }

        // --- Security Settings ---
        item { SettingsHeader("Security") }
        item {
            SwitchSettingItem(
                icon = Icons.Default.Fingerprint,
                title = "Biometric Authentication",
                description = "Use fingerprint or face ID to log in (BiometricPrompt integration)",
                checked = settings.isBiometricAuthEnabled,
                onCheckedChange = { isChecked ->
                    // In a real app, this would trigger BiometricPrompt setup
                    viewModel.updateSetting { it.copy(isBiometricAuthEnabled = isChecked) }
                }
            )
        }
        item {
            ClickableSettingItem(
                icon = Icons.Default.Lock,
                title = "Change Password",
                description = "Update your account password",
                onClick = { /* Show Change Password Dialog/Screen */ }
            )
        }
        item { PasswordValidationForm(viewModel) }


        // --- Notifications ---
        item { SettingsHeader("Notifications") }
        item {
            SwitchSettingItem(
                icon = Icons.Default.Notifications,
                title = "Push Notifications",
                description = "Receive alerts and updates",
                checked = settings.isPushNotificationsEnabled,
                onCheckedChange = { isChecked ->
                    viewModel.updateSetting { it.copy(isPushNotificationsEnabled = isChecked) }
                }
            )
        }

        // --- Payment & Remittance ---
        item { SettingsHeader("Payment & Remittance") }
        item {
            ClickableSettingItem(
                icon = Icons.Default.AttachMoney,
                title = "Default Currency",
                description = settings.defaultCurrency,
                onClick = { /* Show Currency selection dialog */ }
            )
        }
        item {
            ClickableSettingItem(
                icon = Icons.Default.Payment,
                title = "Payment Gateway",
                description = "Current: ${settings.paymentGateway} (Paystack, Flutterwave, Interswitch)",
                onClick = { /* Show Payment Gateway selection dialog */ }
            )
        }
    }
}

@Composable
fun SettingsHeader(title: String) {
    Text(
        text = title,
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 12.dp)
            .semantics { contentDescription = "$title section header" }
    )
    Divider()
}

@Composable
fun SwitchSettingItem(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    description: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onCheckedChange(!checked) }
            .padding(16.dp)
            .semantics(mergeDescendants = true) {
                contentDescription = "$title. $description. Currently ${if (checked) "enabled" else "disabled"}"
            },
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            icon,
            contentDescription = null, // Icon is decorative, description is on the Row
            modifier = Modifier.size(24.dp)
        )
        Spacer(Modifier.width(16.dp))
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(description, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            modifier = Modifier.semantics { contentDescription = "Toggle $title" }
        )
    }
}

@Composable
fun ClickableSettingItem(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    description: String,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(16.dp)
            .semantics(mergeDescendants = true) {
                contentDescription = "$title. Current value: $description. Tap to change."
            },
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            icon,
            contentDescription = null, // Icon is decorative
            modifier = Modifier.size(24.dp)
        )
        Spacer(Modifier.width(16.dp))
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(description, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Icon(
            Icons.Default.ChevronRight,
            contentDescription = null, // Decorative
            tint = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
fun PasswordValidationForm(viewModel: SettingsViewModel) {
    val password by viewModel.passwordInput.collectAsState()
    val passwordError by viewModel.passwordError.collectAsState()

    Column(modifier = Modifier.padding(16.dp)) {
        OutlinedTextField(
            value = password,
            onValueChange = viewModel::onPasswordInputChange,
            label = { Text("New Password") },
            isError = passwordError != null,
            supportingText = {
                if (passwordError != null) {
                    Text(
                        modifier = Modifier.semantics { contentDescription = "Password error: $passwordError" },
                        text = passwordError!!,
                        color = MaterialTheme.colorScheme.error
                    )
                } else {
                    Text("Enter a new secure password")
                }
            },
            trailingIcon = {
                if (passwordError != null) {
                    Icon(Icons.Filled.Error, "error", tint = MaterialTheme.colorScheme.error)
                }
            },
            modifier = Modifier
                .fillMaxWidth()
                .semantics { contentDescription = "New Password input field" }
        )
        Spacer(Modifier.height(8.dp))
        Button(
            onClick = { /* Implement password change logic */ },
            enabled = passwordError == null && password.isNotEmpty(),
            modifier = Modifier.align(Alignment.End)
        ) {
            Text("Save Password")
        }
    }
}

// --- 5. Preview ---

@Preview(showBackground = true)
@Composable
fun PreviewSettingsScreen() {
    // Note: In a real preview, you'd wrap this in your app's theme
    SettingsScreen(
        viewModel = SettingsViewModel(SettingsRepository()),
        onBack = {}
    )
}

// --- 6. Dependencies and Resources (Conceptual) ---

/*
// Dependencies required in build.gradle.kts (app module):
// Jetpack Compose & Material 3
implementation("androidx.compose.ui:ui")
implementation("androidx.compose.material3:material3")
// ViewModel and LiveData/StateFlow
implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0")
implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
// Coroutines
implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
// Retrofit (Mocked, but needed for real implementation)
implementation("com.squareup.retrofit2:retrofit:2.9.0")
implementation("com.squareup.retrofit2:converter-gson:2.9.0")
// Room (Mocked, but needed for real implementation)
implementation("androidx.room:room-runtime:2.6.1")
ksp("androidx.room:room-compiler:2.6.1")
implementation("androidx.room:room-ktx:2.6.1")
// Biometric (for BiometricPrompt)
implementation("androidx.biometric:biometric-ktx:1.2.0-alpha05")
*/

/*
// Conceptual R.string resources:
// R.string.settings_title = "Settings"
// R.string.header_app_preferences = "App Preferences"
// R.string.title_dark_mode = "Dark Mode"
// R.string.desc_dark_mode = "Toggle between light and dark themes"
// ... and so on for all titles and descriptions
*/

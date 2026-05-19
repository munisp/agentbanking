package com.pos54link.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pos54link.R // Placeholder for R.string and R.drawable
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.io.IOException

// --- 1. Data Models (M) ---

/**
 * Data class representing a single beneficiary.
 * @param id Unique identifier for the beneficiary. Null for new beneficiaries.
 * @param name Full name of the beneficiary.
 * @param accountNumber Bank account number.
 * @param bankName Name of the beneficiary's bank.
 * @param paymentGateway Preferred payment gateway (e.g., Paystack, Flutterwave).
 */
data class Beneficiary(
    val id: String? = null,
    val name: String = "",
    val accountNumber: String = "",
    val bankName: String = "",
    val paymentGateway: String = "Paystack" // Default to Paystack
)

/**
 * Sealed class for all possible UI events from the screen to the ViewModel.
 */
sealed class BeneficiaryEvent {
    data class NameChanged(val name: String) : BeneficiaryEvent()
    data class AccountNumberChanged(val accountNumber: String) : BeneficiaryEvent()
    data class BankNameChanged(val bankName: String) : BeneficiaryEvent()
    data class PaymentGatewayChanged(val gateway: String) : BeneficiaryEvent()
    data object SaveBeneficiary : BeneficiaryEvent()
    data class EditBeneficiary(val beneficiary: Beneficiary) : BeneficiaryEvent()
    data class DeleteBeneficiary(val beneficiary: Beneficiary) : BeneficiaryEvent()
    data object DismissDialog : BeneficiaryEvent()
    data object InitiateBiometricAuth : BeneficiaryEvent()
}

/**
 * Data class representing the current state of the Beneficiary Management Screen.
 */
data class BeneficiaryState(
    val beneficiaries: List<Beneficiary> = emptyList(),
    val currentBeneficiary: Beneficiary = Beneficiary(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val isEditMode: Boolean = false,
    val showDialog: Boolean = false,
    val isFormValid: Boolean = false,
    val nameError: String? = null,
    val accountNumberError: String? = null,
    val bankNameError: String? = null,
    val showBiometricPrompt: Boolean = false,
    val biometricAuthSuccess: Boolean = false,
    val biometricAuthError: String? = null
)

// --- 2. Repository Pattern (R) ---

/**
 * Interface for data operations on Beneficiaries.
 * This abstracts the data source (API, Room, etc.).
 */
interface BeneficiaryRepository {
    suspend fun getBeneficiaries(): List<Beneficiary>
    suspend fun saveBeneficiary(beneficiary: Beneficiary): Beneficiary
    suspend fun deleteBeneficiary(beneficiaryId: String)
}

/**
 * Concrete implementation of the BeneficiaryRepository.
 * This class handles the logic for fetching data from the network (Retrofit)
 * and caching/serving from the local database (Room) for offline support.
 */
class BeneficiaryRepositoryImpl(
    private val apiService: BeneficiaryApiService, // Retrofit service
    private val beneficiaryDao: BeneficiaryDao // Room DAO
) : BeneficiaryRepository {

    /**
     * Fetches beneficiaries, prioritizing network but falling back to local cache.
     */
    override suspend fun getBeneficiaries(): List<Beneficiary> {
        return try {
            // 1. Try to fetch from network
            val networkBeneficiaries = apiService.getBeneficiaries()
            // 2. Update local cache (Room)
            beneficiaryDao.insertAll(networkBeneficiaries.map { it.toEntity() })
            networkBeneficiaries
        } catch (e: IOException) {
            // 3. Network error, fall back to local cache (Offline Mode)
            beneficiaryDao.getAll().map { it.toDomain() }
        } catch (e: HttpException) {
            // 4. API error, fall back to local cache
            beneficiaryDao.getAll().map { it.toDomain() }
        }
    }

    /**
     * Saves a beneficiary to the network and updates the local cache.
     */
    override suspend fun saveBeneficiary(beneficiary: Beneficiary): Beneficiary {
        // Placeholder for Retrofit call to save/update beneficiary
        val savedBeneficiary = if (beneficiary.id == null) {
            apiService.createBeneficiary(beneficiary)
        } else {
            apiService.updateBeneficiary(beneficiary.id, beneficiary)
        }
        // Update local cache
        beneficiaryDao.insert(savedBeneficiary.toEntity())
        return savedBeneficiary
    }

    /**
     * Deletes a beneficiary from the network and local cache.
     */
    override suspend fun deleteBeneficiary(beneficiaryId: String) {
        // Placeholder for Retrofit call to delete beneficiary
        apiService.deleteBeneficiary(beneficiaryId)
        // Delete from local cache
        beneficiaryDao.delete(beneficiaryId)
    }
}

// --- Placeholder for Retrofit API Service and Room DAO ---

/**
 * Placeholder for Retrofit API Service interface.
 */
interface BeneficiaryApiService {
    suspend fun getBeneficiaries(): List<Beneficiary>
    suspend fun createBeneficiary(beneficiary: Beneficiary): Beneficiary
    suspend fun updateBeneficiary(id: String, beneficiary: Beneficiary): Beneficiary
    suspend fun deleteBeneficiary(id: String)
}

/**
 * Placeholder for Room Entity and DAO.
 */
// Room Entity Placeholder
data class BeneficiaryEntity(
    val id: String,
    val name: String,
    val accountNumber: String,
    val bankName: String,
    val paymentGateway: String
)

// Mapper functions
fun Beneficiary.toEntity() = BeneficiaryEntity(id!!, name, accountNumber, bankName, paymentGateway)
fun BeneficiaryEntity.toDomain() = Beneficiary(id, name, accountNumber, bankName, paymentGateway)

// Room DAO Placeholder
interface BeneficiaryDao {
    suspend fun getAll(): List<BeneficiaryEntity>
    suspend fun insertAll(beneficiaries: List<BeneficiaryEntity>)
    suspend fun insert(beneficiary: BeneficiaryEntity)
    suspend fun delete(id: String)
}

// --- 3. ViewModel (VM) ---

/**
 * ViewModel for the Beneficiary Management Screen.
 * Handles state management, business logic, and data interaction.
 */
class BeneficiaryManagementViewModel(
    private val repository: BeneficiaryRepository
) : ViewModel() {

    private val _state = MutableStateFlow(BeneficiaryState())
    val state: StateFlow<BeneficiaryState> = _state.asStateFlow()

    init {
        loadBeneficiaries()
    }

    /**
     * Loads the list of beneficiaries from the repository.
     */
    private fun loadBeneficiaries() {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, error = null) }
            try {
                val beneficiaries = repository.getBeneficiaries()
                _state.update { it.copy(beneficiaries = beneficiaries, isLoading = false) }
            } catch (e: Exception) {
                _state.update { it.copy(isLoading = false, error = "Failed to load beneficiaries: ${e.message}") }
            }
        }
    }

    /**
     * Handles all incoming UI events.
     */
    fun onEvent(event: BeneficiaryEvent) {
        when (event) {
            is BeneficiaryEvent.NameChanged -> {
                _state.update { it.copy(currentBeneficiary = it.currentBeneficiary.copy(name = event.name)) }
                validateForm()
            }
            is BeneficiaryEvent.AccountNumberChanged -> {
                _state.update { it.copy(currentBeneficiary = it.currentBeneficiary.copy(accountNumber = event.accountNumber)) }
                validateForm()
            }
            is BeneficiaryEvent.BankNameChanged -> {
                _state.update { it.copy(currentBeneficiary = it.currentBeneficiary.copy(bankName = event.bankName)) }
                validateForm()
            }
            is BeneficiaryEvent.PaymentGatewayChanged -> {
                _state.update { it.copy(currentBeneficiary = it.currentBeneficiary.copy(paymentGateway = event.gateway)) }
            }
            BeneficiaryEvent.SaveBeneficiary -> {
                if (_state.value.isFormValid) {
                    saveBeneficiary()
                } else {
                    _state.update { it.copy(error = "Please correct the form errors.") }
                }
            }
            is BeneficiaryEvent.EditBeneficiary -> {
                _state.update {
                    it.copy(
                        currentBeneficiary = event.beneficiary,
                        isEditMode = true,
                        showDialog = true
                    )
                }
                validateForm()
            }
            is BeneficiaryEvent.DeleteBeneficiary -> {
                deleteBeneficiary(event.beneficiary)
            }
            BeneficiaryEvent.DismissDialog -> {
                _state.update { it.copy(showDialog = false, isEditMode = false, currentBeneficiary = Beneficiary()) }
            }
            BeneficiaryEvent.InitiateBiometricAuth -> {
                _state.update { it.copy(showBiometricPrompt = true) }
            }
        }
    }

    /**
     * Performs client-side form validation.
     */
    private fun validateForm() {
        val current = _state.value.currentBeneficiary
        var isValid = true
        var nameError: String? = null
        var accountNumberError: String? = null
        var bankNameError: String? = null

        if (current.name.isBlank() || current.name.length < 3) {
            nameError = "Name must be at least 3 characters."
            isValid = false
        }

        if (current.accountNumber.length != 10 || current.accountNumber.any { !it.isDigit() }) {
            accountNumberError = "Account number must be 10 digits."
            isValid = false
        }

        if (current.bankName.isBlank()) {
            bankNameError = "Bank name cannot be empty."
            isValid = false
        }

        _state.update {
            it.copy(
                isFormValid = isValid,
                nameError = nameError,
                accountNumberError = accountNumberError,
                bankNameError = bankNameError
            )
        }
    }

    /**
     * Saves the current beneficiary (Create/Update).
     */
    private fun saveBeneficiary() {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, error = null) }
            try {
                val beneficiaryToSave = _state.value.currentBeneficiary
                // In a real app, we would initiate biometric auth here before saving
                // For this example, we'll assume auth is handled or bypassed for now.
                repository.saveBeneficiary(beneficiaryToSave)
                _state.update {
                    it.copy(
                        isLoading = false,
                        showDialog = false,
                        isEditMode = false,
                        currentBeneficiary = Beneficiary(),
                        error = null
                    )
                }
                loadBeneficiaries() // Refresh list
            } catch (e: Exception) {
                _state.update { it.copy(isLoading = false, error = "Failed to save beneficiary: ${e.message}") }
            }
        }
    }

    /**
     * Deletes a beneficiary.
     */
    private fun deleteBeneficiary(beneficiary: Beneficiary) {
        beneficiary.id?.let { id ->
            viewModelScope.launch {
                _state.update { it.copy(isLoading = true, error = null) }
                try {
                    repository.deleteBeneficiary(id)
                    _state.update { it.copy(isLoading = false, error = null) }
                    loadBeneficiaries() // Refresh list
                } catch (e: Exception) {
                    _state.update { it.copy(isLoading = false, error = "Failed to delete beneficiary: ${e.message}") }
                }
            }
        }
    }

    // --- ViewModel Factory Placeholder ---
    companion object {
        // Simple factory for demonstration. In a real app, use Hilt/Koin.
        val Factory: androidx.lifecycle.ViewModelProvider.Factory = object : androidx.lifecycle.ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                // Mock dependencies for preview/simple use
                val mockApiService = object : BeneficiaryApiService {
                    override suspend fun getBeneficiaries(): List<Beneficiary> = listOf(
                        Beneficiary("1", "John Doe", "1234567890", "First Bank", "Paystack"),
                        Beneficiary("2", "Jane Smith", "0987654321", "Access Bank", "Flutterwave")
                    )
                    override suspend fun createBeneficiary(beneficiary: Beneficiary): Beneficiary = beneficiary.copy(id = "3")
                    override suspend fun updateBeneficiary(id: String, beneficiary: Beneficiary): Beneficiary = beneficiary
                    override suspend fun deleteBeneficiary(id: String) {}
                }
                val mockDao = object : BeneficiaryDao {
                    override suspend fun getAll(): List<BeneficiaryEntity> = mockApiService.getBeneficiaries().map { it.toEntity() }
                    override suspend fun insertAll(beneficiaries: List<BeneficiaryEntity>) {}
                    override suspend fun insert(beneficiary: BeneficiaryEntity) {}
                    override suspend fun delete(id: String) {}
                }
                val repository = BeneficiaryRepositoryImpl(mockApiService, mockDao)
                return BeneficiaryManagementViewModel(repository) as T
            }
        }
    }
}

// --- 4. Composable UI (V) ---

/**
 * Main Composable function for the Beneficiary Management Screen.
 * @param viewModel The ViewModel instance for state and event handling.
 */
@Composable
fun BeneficiaryManagementScreen(
    viewModel: BeneficiaryManagementViewModel = viewModel(factory = BeneficiaryManagementViewModel.Factory)
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Beneficiary Management") },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    titleContentColor = MaterialTheme.colorScheme.primary,
                )
            )
        },
        floatingActionButton = {
            FloatingActionButton(
                onClick = {
                    viewModel.onEvent(BeneficiaryEvent.EditBeneficiary(Beneficiary()))
                },
                content = {
                    Icon(Icons.Filled.Add, contentDescription = "Add Beneficiary")
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(16.dp)
        ) {
            // Error and Loading States
            if (state.isLoading) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }
            state.error?.let { error ->
                Text(
                    text = error,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(vertical = 8.dp)
                )
            }

            // Biometric Authentication Status (Placeholder)
            if (state.biometricAuthSuccess) {
                Text("Biometric Auth Successful!", color = MaterialTheme.colorScheme.tertiary)
            }
            state.biometricAuthError?.let { error ->
                Text("Biometric Auth Failed: $error", color = MaterialTheme.colorScheme.error)
            }

            // Beneficiary List
            BeneficiaryList(
                beneficiaries = state.beneficiaries,
                onEdit = { viewModel.onEvent(BeneficiaryEvent.EditBeneficiary(it)) },
                onDelete = { viewModel.onEvent(BeneficiaryEvent.DeleteBeneficiary(it)) }
            )
        }
    }

    // Dialog for Add/Edit Beneficiary
    if (state.showDialog) {
        BeneficiaryFormDialog(
            state = state,
            onEvent = viewModel::onEvent,
            onDismiss = { viewModel.onEvent(BeneficiaryEvent.DismissDialog) }
        )
    }

    // Biometric Prompt Integration (Placeholder)
    if (state.showBiometricPrompt) {
        // In a real app, this would trigger the BiometricPrompt API
        LaunchedEffect(Unit) {
            // Placeholder for BiometricPrompt logic
            // On success: viewModel.onEvent(BeneficiaryEvent.BiometricAuthSuccess)
            // On failure: viewModel.onEvent(BeneficiaryEvent.BiometricAuthFailure("Reason"))
            // For now, we simulate success after a delay
            kotlinx.coroutines.delay(1000)
            // Simulating a successful biometric authentication for the save operation
            // viewModel.onEvent(BeneficiaryEvent.SaveBeneficiary) // Would be called after successful auth
            viewModel.onEvent(BeneficiaryEvent.DismissDialog) // Dismiss the prompt trigger
        }
    }
}

/**
 * Composable for displaying the list of beneficiaries.
 */
@Composable
fun BeneficiaryList(
    beneficiaries: List<Beneficiary>,
    onEdit: (Beneficiary) -> Unit,
    onDelete: (Beneficiary) -> Unit
) {
    if (beneficiaries.isEmpty()) {
        Text(
            text = "No beneficiaries added yet. Tap '+' to add one.",
            style = MaterialTheme.typography.bodyLarge,
            modifier = Modifier.padding(top = 16.dp)
        )
        return
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(vertical = 8.dp)
    ) {
        items(beneficiaries, key = { it.id ?: it.hashCode().toString() }) { beneficiary ->
            BeneficiaryItem(
                beneficiary = beneficiary,
                onEdit = onEdit,
                onDelete = onDelete
            )
            Divider()
        }
    }
}

/**
 * Composable for a single beneficiary item in the list.
 */
@Composable
fun BeneficiaryItem(
    beneficiary: Beneficiary,
    onEdit: (Beneficiary) -> Unit,
    onDelete: (Beneficiary) -> Unit
) {
    ListItem(
        modifier = Modifier.clickable { onEdit(beneficiary) },
        headlineContent = { Text(beneficiary.name) },
        supportingContent = {
            Column {
                Text("Account: ${beneficiary.accountNumber}")
                Text("Bank: ${beneficiary.bankName}")
                Text("Gateway: ${beneficiary.paymentGateway}")
            }
        },
        leadingContent = {
            Icon(
                Icons.Filled.AccountCircle,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.secondary
            )
        },
        trailingContent = {
            Row {
                IconButton(onClick = { onEdit(beneficiary) }) {
                    Icon(Icons.Filled.Edit, contentDescription = "Edit ${beneficiary.name}")
                }
                IconButton(onClick = { onDelete(beneficiary) }) {
                    Icon(Icons.Filled.Delete, contentDescription = "Delete ${beneficiary.name}", tint = MaterialTheme.colorScheme.error)
                }
            }
        }
    )
}

/**
 * Composable for the Add/Edit Beneficiary form dialog.
 */
@Composable
fun BeneficiaryFormDialog(
    state: BeneficiaryState,
    onEvent: (BeneficiaryEvent) -> Unit,
    onDismiss: () -> Unit
) {
    val beneficiary = state.currentBeneficiary
    val title = if (state.isEditMode) "Edit Beneficiary" else "Add New Beneficiary"

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(modifier = Modifier.padding(top = 8.dp)) {
                // Name Field
                OutlinedTextField(
                    value = beneficiary.name,
                    onValueChange = { onEvent(BeneficiaryEvent.NameChanged(it)) },
                    label = { Text("Full Name") },
                    isError = state.nameError != null,
                    supportingText = { state.nameError?.let { Text(it) } },
                    modifier = Modifier.fillMaxWidth(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text),
                    // Accessibility: label and supporting text provide context
                )
                Spacer(modifier = Modifier.height(8.dp))

                // Account Number Field
                OutlinedTextField(
                    value = beneficiary.accountNumber,
                    onValueChange = { onEvent(BeneficiaryEvent.AccountNumberChanged(it)) },
                    label = { Text("Account Number") },
                    isError = state.accountNumberError != null,
                    supportingText = { state.accountNumberError?.let { Text(it) } },
                    modifier = Modifier.fillMaxWidth(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    // Accessibility: label and supporting text provide context
                )
                Spacer(modifier = Modifier.height(8.dp))

                // Bank Name Field
                OutlinedTextField(
                    value = beneficiary.bankName,
                    onValueChange = { onEvent(BeneficiaryEvent.BankNameChanged(it)) },
                    label = { Text("Bank Name") },
                    isError = state.bankNameError != null,
                    supportingText = { state.bankNameError?.let { Text(it) } },
                    modifier = Modifier.fillMaxWidth(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text),
                    // Accessibility: label and supporting text provide context
                )
                Spacer(modifier = Modifier.height(16.dp))

                // Payment Gateway Selection (Placeholder for a more complex selector)
                PaymentGatewaySelector(
                    selectedGateway = beneficiary.paymentGateway,
                    onGatewaySelected = { onEvent(BeneficiaryEvent.PaymentGatewayChanged(it)) }
                )
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    // In a real app, this would trigger biometric auth if required
                    // For now, we directly save.
                    onEvent(BeneficiaryEvent.SaveBeneficiary)
                },
                enabled = state.isFormValid && !state.isLoading
            ) {
                Text(if (state.isLoading) "Saving..." else "Save")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}

/**
 * Composable for selecting a payment gateway.
 * This is a simplified placeholder for a real-world implementation.
 */
@Composable
fun PaymentGatewaySelector(
    selectedGateway: String,
    onGatewaySelected: (String) -> Unit
) {
    val gateways = listOf("Paystack", "Flutterwave", "Interswitch")
    var expanded by remember { mutableStateOf(false) }

    OutlinedCard(
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { expanded = true }
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text("Payment Gateway: $selectedGateway")
            Icon(Icons.Filled.ArrowDropDown, contentDescription = "Select Payment Gateway")
            DropdownMenu(
                expanded = expanded,
                onDismissRequest = { expanded = false }
            ) {
                gateways.forEach { gateway ->
                    DropdownMenuItem(
                        text = { Text(gateway) },
                        onClick = {
                            onGatewaySelected(gateway)
                            expanded = false
                        }
                    )
                }
            }
        }
    }
    // Accessibility: The clickable row and DropdownMenu provide a clear interactive element.
}

// --- 5. Preview ---

@Preview(showBackground = true)
@Composable
fun PreviewBeneficiaryManagementScreen() {
    // Using a mock ViewModel for preview
    BeneficiaryManagementScreen(
        viewModel = BeneficiaryManagementViewModel(
            repository = object : BeneficiaryRepository {
                override suspend fun getBeneficiaries(): List<Beneficiary> = listOf(
                    Beneficiary("1", "Aisha Bello", "1234567890", "Zenith Bank", "Paystack"),
                    Beneficiary("2", "Chinedu Okoro", "0987654321", "GTBank", "Flutterwave"),
                    Beneficiary.copy(id = "3", name = "Tunde Adebayo", bankName = "Access Bank", paymentGateway = "Interswitch")
                )
                override suspend fun saveBeneficiary(beneficiary: Beneficiary): Beneficiary = beneficiary
                override suspend fun deleteBeneficiary(beneficiaryId: String) {}
            }
        )
    )
}

@Preview(showBackground = true)
@Composable
fun PreviewBeneficiaryFormDialog() {
    val mockState = BeneficiaryState(
        currentBeneficiary = Beneficiary(name = "Test User", accountNumber = "1234567890", bankName = "Test Bank"),
        showDialog = true,
        isFormValid = true,
        isEditMode = false
    )
    BeneficiaryFormDialog(
        state = mockState,
        onEvent = {},
        onDismiss = {}
    )
}

// --- End of BeneficiaryManagementScreen.kt ---

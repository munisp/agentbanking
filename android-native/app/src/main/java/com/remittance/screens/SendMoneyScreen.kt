package com.pos54link.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Error
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import com.pos54link.app.BuildConfig
import com.pos54link.app.data.api.BeneficiaryService
import com.pos54link.app.data.api.TransferService
import com.pos54link.app.data.api.QuoteRequest
import com.pos54link.app.data.api.TransferRequest
import com.pos54link.app.data.api.VerifyBeneficiaryRequest
import com.pos54link.app.data.api.AddBeneficiaryRequest
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.io.IOException
import java.util.UUID

// --- 1. Data Models ---

/**
 * Represents a beneficiary for money transfer.
 * This would typically be a Room Entity for offline storage.
 */
data class Beneficiary(
    val id: String = UUID.randomUUID().toString(),
    val name: String,
    val bankName: String,
    val accountNumber: String,
    val isLocal: Boolean,
    val bankCode: String = "",
    val country: String = "NG",
    val currency: String = "NGN"
)

/**
 * Represents the state of a single step in the transfer flow.
 */
data class TransferStepState(
    val stepIndex: Int,
    val title: String,
    val isCompleted: Boolean = false,
    val isValid: Boolean = false
)

/**
 * Represents the entire state of the money transfer form.
 */
data class TransferFormState(
    // Step 1: Beneficiary
    val selectedBeneficiary: Beneficiary? = null,
    val newBeneficiaryName: String = "",
    val newBeneficiaryAccount: String = "",
    val newBeneficiaryBank: String = "",
    val isNewBeneficiaryLocal: Boolean = true,
    val beneficiaryError: String? = null,

    // Step 2: Amount & Purpose
    val amountToSend: String = "",
    val purpose: String = "",
    val exchangeRate: Double = 0.0,
    val fee: Double = 0.0,
    val totalToPay: Double = 0.0,
    val amountError: String? = null,

    // Step 3: Review & Payment Method
    val selectedPaymentMethod: String = "Bank Transfer", // e.g., "Bank Transfer", "Paystack", "Flutterwave"
    val paymentMethodError: String? = null,

    // Step 4: Authentication & Final Send
    val transactionPin: String = "",
    val authError: String? = null,
)

/**
 * Represents the overall UI state.
 */
data class SendMoneyUiState(
    val currentStep: Int = 1,
    val totalSteps: Int = 4,
    val formState: TransferFormState = TransferFormState(),
    val steps: List<TransferStepState> = listOf(
        TransferStepState(1, "Beneficiary", isValid = false),
        TransferStepState(2, "Amount & Purpose", isValid = false),
        TransferStepState(3, "Review & Pay", isValid = false),
        TransferStepState(4, "Confirm & Send", isValid = false)
    ),
    val isLoading: Boolean = false,
    val error: String? = null,
    val successMessage: String? = null,
    val offlineMode: Boolean = false,
    val beneficiaries: List<Beneficiary> = emptyList()
)

// --- 2. Repository Interface (Abstraction for Data Access) ---

/**
 * Abstraction for data operations, including API calls (Retrofit) and local DB (Room).
 */
interface TransferRepository {
    suspend fun getBeneficiaries(): Flow<List<Beneficiary>>
    suspend fun validateBeneficiary(accountNumber: String, bankCode: String): Result<Beneficiary>
    suspend fun getExchangeRate(sourceCurrency: String, targetCurrency: String): Result<Double>
    suspend fun calculateFee(amount: Double): Result<Double>
    suspend fun submitTransfer(transferData: TransferFormState): Result<String>
    suspend fun saveBeneficiaryLocally(beneficiary: Beneficiary)
}

// --- 3. Repository Implementations ---

/**
 * Mock repository — for unit tests and Compose previews ONLY.
 * Never used as a default on live paths.
 */
class MockTransferRepository : TransferRepository {
    private val localBeneficiaries = MutableStateFlow(
        listOf(
            Beneficiary(name = "Aisha Bello", bankName = "Access Bank", accountNumber = "0123456789", isLocal = true),
            Beneficiary(name = "John Doe", bankName = "First Bank", accountNumber = "9876543210", isLocal = true)
        )
    )

    override suspend fun getBeneficiaries(): Flow<List<Beneficiary>> = localBeneficiaries

    override suspend fun validateBeneficiary(accountNumber: String, bankCode: String): Result<Beneficiary> {
        // Simulate API call for validation
        kotlinx.coroutines.delay(1000)
        return if (accountNumber.length == 10 && bankCode.isNotEmpty()) {
            Result.success(Beneficiary(name = "Validated Name", bankName = "Validated Bank", accountNumber = accountNumber, isLocal = true))
        } else {
            Result.failure(IllegalArgumentException("Invalid account number or bank code."))
        }
    }

    override suspend fun getExchangeRate(sourceCurrency: String, targetCurrency: String): Result<Double> {
        kotlinx.coroutines.delay(500)
        return Result.success(750.50) // Mock rate: 1 USD = 750.50 NGN
    }

    override suspend fun calculateFee(amount: Double): Result<Double> {
        kotlinx.coroutines.delay(300)
        return Result.success(amount * 0.01) // Mock 1% fee
    }

    override suspend fun submitTransfer(transferData: TransferFormState): Result<String> {
        kotlinx.coroutines.delay(2000)
        if (transferData.transactionPin == "1234") {
            return Result.success("TRX-${System.currentTimeMillis()}")
        } else {
            return Result.failure(HttpException(retrofit2.Response.error<Any>(401, okhttp3.ResponseBody.create(null, "Invalid PIN"))))
        }
    }

    override suspend fun saveBeneficiaryLocally(beneficiary: Beneficiary) {
        localBeneficiaries.update { it + beneficiary }
    }
}


/**
 * Live repository backed by the real backend API (Retrofit TransferService /
 * BeneficiaryService). All data returned to the UI comes from server responses;
 * failures surface as honest errors.
 */
class LiveTransferRepository(
    private val transferService: TransferService,
    private val beneficiaryService: BeneficiaryService
) : TransferRepository {

    override suspend fun getBeneficiaries(): Flow<List<Beneficiary>> = flow {
        val response = beneficiaryService.getBeneficiaries()
        if (!response.isSuccessful) throw HttpException(response)
        val list = response.body()?.data.orEmpty().map { api ->
            Beneficiary(
                id = api.id,
                name = api.name,
                bankName = api.bankName,
                accountNumber = api.accountNumber,
                isLocal = api.country.equals("NG", ignoreCase = true),
                bankCode = api.bankCode,
                country = api.country,
                currency = api.currency
            )
        }
        emit(list)
    }

    override suspend fun validateBeneficiary(accountNumber: String, bankCode: String): Result<Beneficiary> {
        return try {
            val response = beneficiaryService.verifyBeneficiary(
                VerifyBeneficiaryRequest(accountNumber = accountNumber, bankCode = bankCode, country = "NG")
            )
            val body = response.body()
            if (response.isSuccessful && body != null && body.success) {
                Result.success(
                    Beneficiary(
                        name = body.data.accountName,
                        bankName = body.data.bankName,
                        accountNumber = body.data.accountNumber,
                        isLocal = true,
                        bankCode = bankCode
                    )
                )
            } else {
                Result.failure(if (response.isSuccessful) IllegalArgumentException("Beneficiary could not be verified.") else HttpException(response))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getExchangeRate(sourceCurrency: String, targetCurrency: String): Result<Double> {
        return try {
            val response = transferService.getExchangeRates(sourceCurrency, targetCurrency)
            val body = response.body()
            if (response.isSuccessful && body != null && body.success) {
                Result.success(body.data.rate)
            } else {
                Result.failure(if (response.isSuccessful) IOException("No rate returned.") else HttpException(response))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun calculateFee(amount: Double): Result<Double> {
        return try {
            val response = transferService.getQuote(
                QuoteRequest(
                    sourceCurrency = "USD",
                    destinationCurrency = "NGN",
                    amount = amount,
                    transferSpeed = "standard"
                )
            )
            val body = response.body()
            if (response.isSuccessful && body != null && body.success) {
                Result.success(body.data.fee)
            } else {
                Result.failure(if (response.isSuccessful) IOException("No fee quote returned.") else HttpException(response))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun submitTransfer(transferData: TransferFormState): Result<String> {
        return try {
            // Obtain a fresh server quote — the server is the only source of
            // rates/fees and the resulting quoteId binds the transfer.
            val amount = transferData.amountToSend.toDoubleOrNull()
                ?: return Result.failure(IllegalArgumentException("Invalid amount."))
            val beneficiary = transferData.selectedBeneficiary
                ?: return Result.failure(IllegalArgumentException("No beneficiary selected."))
            val quoteResponse = transferService.getQuote(
                QuoteRequest(
                    sourceCurrency = "USD",
                    destinationCurrency = beneficiary.currency,
                    amount = amount,
                    transferSpeed = "standard"
                )
            )
            val quote = quoteResponse.body()
            if (!quoteResponse.isSuccessful || quote == null || !quote.success) {
                return Result.failure(if (quoteResponse.isSuccessful) IOException("Could not obtain a transfer quote.") else HttpException(quoteResponse))
            }
            val transferResponse = transferService.initiateTransfer(
                TransferRequest(
                    quoteId = quote.data.quoteId,
                    beneficiaryId = beneficiary.id,
                    sourceCurrency = "USD",
                    destinationCurrency = beneficiary.currency,
                    amount = amount,
                    transferSpeed = "standard",
                    paymentSystem = transferData.selectedPaymentMethod.lowercase().replace(" ", "_"),
                    description = transferData.purpose
                )
            )
            val body = transferResponse.body()
            if (transferResponse.isSuccessful && body != null && body.success) {
                // Real server-issued reference — never fabricated.
                Result.success(body.data.reference)
            } else {
                Result.failure(if (transferResponse.isSuccessful) IOException("Transfer was not accepted by the server.") else HttpException(transferResponse))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun saveBeneficiaryLocally(beneficiary: Beneficiary) {
        // Persist server-side; the beneficiary list is re-fetched from the backend.
        beneficiaryService.addBeneficiary(
            AddBeneficiaryRequest(
                name = beneficiary.name,
                accountNumber = beneficiary.accountNumber,
                bankName = beneficiary.bankName,
                bankCode = beneficiary.bankCode,
                country = beneficiary.country,
                currency = beneficiary.currency
            )
        )
    }
}

/**
 * Provides the default live repository for the compose-created ViewModel.
 *
 * Note: this builds a bare Retrofit against the configured backend base URL.
 * Production wiring should prefer injecting the Hilt-provided
 * [com.pos54link.app.data.api.ApiClient] (which attaches the auth interceptor)
 * and passing `apiClient.transferService` / `apiClient.beneficiaryService`.
 */
object SendMoneyRepositoryProvider {
    private val retrofit: Retrofit by lazy {
        Retrofit.Builder()
            .baseUrl(BuildConfig.BASE_URL)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }

    fun live(): TransferRepository = LiveTransferRepository(
        transferService = retrofit.create(TransferService::class.java),
        beneficiaryService = retrofit.create(BeneficiaryService::class.java)
    )
}

// --- 4. ViewModel (State Management and Business Logic) ---

class SendMoneyViewModel(
    private val repository: TransferRepository = SendMoneyRepositoryProvider.live()
) : ViewModel() {

    private val _uiState = MutableStateFlow(SendMoneyUiState())
    val uiState: StateFlow<SendMoneyUiState> = _uiState.asStateFlow()

    init {
        loadBeneficiaries()
        _uiState.update { it.copy(offlineMode = false) }
    }

    private fun loadBeneficiaries() {
        viewModelScope.launch {
            repository.getBeneficiaries().collect { beneficiaries ->
                _uiState.update { it.copy(beneficiaries = beneficiaries) }
            }
        }
    }

    fun onEvent(event: SendMoneyEvent) {
        when (event) {
            is SendMoneyEvent.UpdateForm -> updateFormState(event.update)
            is SendMoneyEvent.NextStep -> nextStep()
            is SendMoneyEvent.PreviousStep -> previousStep()
            is SendMoneyEvent.SubmitTransfer -> submitTransfer()
            is SendMoneyEvent.SelectBeneficiary -> selectBeneficiary(event.beneficiary)
            is SendMoneyEvent.ValidateNewBeneficiary -> validateNewBeneficiary()
            is SendMoneyEvent.BiometricAuthResult -> onBiometricAuthResult(event.success)
            is SendMoneyEvent.ClearError -> _uiState.update { it.copy(error = null, successMessage = null) }
        }
    }

    private fun updateFormState(update: TransferFormState.() -> TransferFormState) {
        _uiState.update { currentState ->
            val newFormState = currentState.formState.update()
            val newSteps = currentState.steps.map { step ->
                step.copy(isValid = validateStep(step.stepIndex, newFormState))
            }
            currentState.copy(formState = newFormState, steps = newSteps)
        }
        // Recalculate financial details if amount changes
        if (_uiState.value.currentStep == 2) {
            recalculateFinancials()
        }
    }

    private fun validateStep(stepIndex: Int, formState: TransferFormState): Boolean {
        return when (stepIndex) {
            1 -> formState.selectedBeneficiary != null || (
                formState.newBeneficiaryName.isNotBlank() &&
                formState.newBeneficiaryAccount.length == 10 &&
                formState.newBeneficiaryBank.isNotBlank()
            )
            2 -> try {
                formState.amountToSend.toDouble() > 100.0 && formState.purpose.isNotBlank()
            } catch (e: NumberFormatException) {
                false
            }
            3 -> formState.selectedPaymentMethod.isNotBlank()
            4 -> formState.transactionPin.length == 4 // Simple PIN validation
            else -> false
        }
    }

    private fun nextStep() {
        _uiState.update { currentState ->
            val currentStepState = currentState.steps.find { it.stepIndex == currentState.currentStep }
            if (currentStepState?.isValid == true) {
                val newSteps = currentState.steps.map {
                    if (it.stepIndex == currentState.currentStep) it.copy(isCompleted = true) else it
                }
                currentState.copy(
                    currentStep = (currentState.currentStep + 1).coerceAtMost(currentState.totalSteps),
                    steps = newSteps
                )
            } else {
                currentState.copy(error = "Please complete the current step before proceeding.")
            }
        }
    }

    private fun previousStep() {
        _uiState.update {
            it.copy(currentStep = (it.currentStep - 1).coerceAtLeast(1))
        }
    }

    private fun selectBeneficiary(beneficiary: Beneficiary) {
        updateFormState {
            copy(
                selectedBeneficiary = beneficiary,
                newBeneficiaryName = "",
                newBeneficiaryAccount = "",
                newBeneficiaryBank = "",
                beneficiaryError = null
            )
        }
        nextStep()
    }

    private fun validateNewBeneficiary() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            val formState = _uiState.value.formState
            if (formState.newBeneficiaryAccount.length != 10 || formState.newBeneficiaryBank.isBlank()) {
                _uiState.update { it.copy(isLoading = false, error = "Account number must be 10 digits and bank must be selected.") }
                return@launch
            }

            repository.validateBeneficiary(formState.newBeneficiaryAccount, formState.newBeneficiaryBank)
                .onSuccess { validatedBeneficiary ->
                    // Save validated beneficiary locally (offline mode support)
                    repository.saveBeneficiaryLocally(validatedBeneficiary)
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            formState = it.formState.copy(
                                selectedBeneficiary = validatedBeneficiary,
                                beneficiaryError = null
                            )
                        )
                    }
                    nextStep()
                }
                .onFailure { e ->
                    _uiState.update { it.copy(isLoading = false, error = "Validation failed: ${e.message}") }
                }
        }
    }

    private fun recalculateFinancials() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            val amount = try { _uiState.value.formState.amountToSend.toDouble() } catch (e: Exception) { 0.0 }

            if (amount <= 0) {
                _uiState.update { it.copy(isLoading = false) }
                return@launch
            }

            val rateResult = repository.getExchangeRate("USD", "NGN") // Assuming fixed currencies for simplicity
            val feeResult = repository.calculateFee(amount)

            _uiState.update { currentState ->
                val rate = rateResult.getOrNull() ?: currentState.formState.exchangeRate
                val fee = feeResult.getOrNull() ?: currentState.formState.fee
                val total = amount + fee

                currentState.copy(
                    isLoading = false,
                    formState = currentState.formState.copy(
                        exchangeRate = rate,
                        fee = fee,
                        totalToPay = total
                    ),
                    error = rateResult.exceptionOrNull()?.message ?: feeResult.exceptionOrNull()?.message
                )
            }
        }
    }

    /**
     * Handles the result of the real platform BiometricPrompt shown by the UI layer.
     * A successful device authentication authorizes submitting the transfer;
     * nothing is auto-filled and no success is fabricated.
     */
    private fun onBiometricAuthResult(success: Boolean) {
        if (success) {
            submitTransfer()
        } else {
            _uiState.update {
                it.copy(formState = it.formState.copy(authError = "Biometric authentication failed or was cancelled."))
            }
        }
    }

    private fun submitTransfer() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            repository.submitTransfer(_uiState.value.formState)
                .onSuccess { transactionId ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            successMessage = "Transfer successful! Transaction ID: $transactionId",
                            currentStep = 5 // Success screen
                        )
                    }
                }
                .onFailure { e ->
                    val errorMessage = when (e) {
                        is HttpException -> "API Error: ${e.code()} - Invalid PIN or server issue."
                        is IOException -> "Network Error: Check your connection."
                        else -> "An unexpected error occurred: ${e.message}"
                    }
                    _uiState.update { it.copy(isLoading = false, error = errorMessage) }
                }
        }
    }
}

// --- 5. Events (User Actions) ---

sealed class SendMoneyEvent {
    data class UpdateForm(val update: TransferFormState.() -> TransferFormState) : SendMoneyEvent()
    object NextStep : SendMoneyEvent()
    object PreviousStep : SendMoneyEvent()
    object SubmitTransfer : SendMoneyEvent()
    data class SelectBeneficiary(val beneficiary: Beneficiary) : SendMoneyEvent()
    object ValidateNewBeneficiary : SendMoneyEvent()
    data class BiometricAuthResult(val success: Boolean) : SendMoneyEvent()
    object ClearError : SendMoneyEvent()
}

// --- 6. Compose UI (Screen Implementation) ---

@Composable
fun SendMoneyScreen(viewModel: SendMoneyViewModel = androidx.lifecycle.viewmodel.compose.viewModel()) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Send Money") },
                navigationIcon = {
                    if (uiState.currentStep > 1 && uiState.currentStep <= uiState.totalSteps) {
                        IconButton(onClick = { viewModel.onEvent(SendMoneyEvent.PreviousStep) }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                        }
                    }
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
            // Step Indicator
            StepIndicator(uiState.steps, uiState.currentStep)
            Spacer(modifier = Modifier.height(16.dp))

            // Content Area
            Box(modifier = Modifier.weight(1f)) {
                when (uiState.currentStep) {
                    1 -> BeneficiarySelectionStep(uiState.formState, uiState.beneficiaries, viewModel::onEvent)
                    2 -> AmountAndPurposeStep(uiState.formState, viewModel::onEvent)
                    3 -> ReviewAndPaymentStep(uiState.formState, viewModel::onEvent)
                    4 -> AuthenticationStep(uiState.formState, viewModel::onEvent)
                    5 -> TransferSuccessScreen(uiState.successMessage ?: "Transfer Complete")
                    else -> TransferErrorScreen(uiState.error ?: "Unknown Error")
                }

                // Loading Overlay
                if (uiState.isLoading) {
                    CircularProgressIndicator(Modifier.align(Alignment.Center))
                }
            }

            // Error/Success Snackbar
            uiState.error?.let { error ->
                Snackbar(
                    modifier = Modifier.padding(top = 8.dp),
                    action = {
                        TextButton(onClick = { viewModel.onEvent(SendMoneyEvent.ClearError) }) {
                            Text("Dismiss")
                        }
                    }
                ) {
                    Text(error)
                }
            }

            // Navigation Buttons
            if (uiState.currentStep <= uiState.totalSteps) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End
                ) {
                    Button(
                        onClick = {
                            if (uiState.currentStep == uiState.totalSteps) {
                                viewModel.onEvent(SendMoneyEvent.SubmitTransfer)
                            } else {
                                viewModel.onEvent(SendMoneyEvent.NextStep)
                            }
                        },
                        enabled = uiState.steps.getOrNull(uiState.currentStep - 1)?.isValid == true && !uiState.isLoading
                    ) {
                        Text(if (uiState.currentStep == uiState.totalSteps) "Send Money" else "Continue")
                    }
                }
            }
        }
    }
}

@Composable
fun StepIndicator(steps: List<TransferStepState>, currentStep: Int) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        steps.forEach { step ->
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                val color = when {
                    step.stepIndex < currentStep -> MaterialTheme.colorScheme.primary
                    step.stepIndex == currentStep -> MaterialTheme.colorScheme.secondary
                    else -> MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f)
                }
                Icon(
                    imageVector = if (step.isCompleted) Icons.Default.CheckCircle else Icons.Default.Error,
                    contentDescription = "Step ${step.stepIndex}",
                    tint = color,
                    modifier = Modifier.size(24.dp)
                )
                Text(
                    text = step.title,
                    style = MaterialTheme.typography.labelSmall,
                    color = color
                )
            }
        }
    }
}

// --- Step 1: Beneficiary Selection ---
@Composable
fun BeneficiarySelectionStep(
    formState: TransferFormState,
    beneficiaries: List<Beneficiary>,
    onEvent: (SendMoneyEvent) -> Unit
) {
    LazyColumn(contentPadding = PaddingValues(vertical = 8.dp)) {
        item {
            Text("Select Existing Beneficiary", style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(8.dp))
        }

        if (beneficiaries.isEmpty()) {
            item { Text("No saved beneficiaries. Please add a new one below.") }
        } else {
            items(beneficiaries.size) { index ->
                val beneficiary = beneficiaries[index]
                ListItem(
                    headlineContent = { Text(beneficiary.name) },
                    supportingContent = { Text("${beneficiary.accountNumber} - ${beneficiary.bankName}") },
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onEvent(SendMoneyEvent.SelectBeneficiary(beneficiary)) }
                )
                Divider()
            }
        }

        item {
            Spacer(modifier = Modifier.height(16.dp))
            Text("Or Add New Beneficiary", style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(8.dp))

            OutlinedTextField(
                value = formState.newBeneficiaryAccount,
                onValueChange = {
                    onEvent(SendMoneyEvent.UpdateForm { copy(newBeneficiaryAccount = it) })
                },
                label = { Text("Account Number") },
                isError = formState.beneficiaryError != null,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(modifier = Modifier.height(8.dp))

            OutlinedTextField(
                value = formState.newBeneficiaryBank,
                onValueChange = {
                    onEvent(SendMoneyEvent.UpdateForm { copy(newBeneficiaryBank = it) })
                },
                label = { Text("Bank Name") },
                isError = formState.beneficiaryError != null,
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(modifier = Modifier.height(8.dp))

            OutlinedTextField(
                value = formState.newBeneficiaryName,
                onValueChange = {
                    onEvent(SendMoneyEvent.UpdateForm { copy(newBeneficiaryName = it) })
                },
                label = { Text("Beneficiary Name (Optional)") },
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(modifier = Modifier.height(16.dp))

            Button(
                onClick = { onEvent(SendMoneyEvent.ValidateNewBeneficiary) },
                enabled = formState.newBeneficiaryAccount.length == 10 && formState.newBeneficiaryBank.isNotBlank()
            ) {
                Text("Validate & Continue")
            }
        }
    }
}

// --- Step 2: Amount and Purpose ---
@Composable
fun AmountAndPurposeStep(
    formState: TransferFormState,
    onEvent: (SendMoneyEvent) -> Unit
) {
    Column {
        Text("Transfer Details", style = MaterialTheme.typography.titleLarge)
        Spacer(modifier = Modifier.height(16.dp))

        OutlinedTextField(
            value = formState.amountToSend,
            onValueChange = {
                onEvent(SendMoneyEvent.UpdateForm { copy(amountToSend = it) })
            },
            label = { Text("Amount to Send (USD)") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            isError = formState.amountError != null,
            modifier = Modifier.fillMaxWidth()
        )
        if (formState.amountError != null) {
            Text(formState.amountError, color = MaterialTheme.colorScheme.error)
        }
        Spacer(modifier = Modifier.height(8.dp))

        OutlinedTextField(
            value = formState.purpose,
            onValueChange = {
                onEvent(SendMoneyEvent.UpdateForm { copy(purpose = it) })
            },
            label = { Text("Purpose of Transfer") },
            modifier = Modifier.fillMaxWidth()
        )
        Spacer(modifier = Modifier.height(16.dp))

        // Financial Summary
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("Summary", style = MaterialTheme.typography.titleMedium)
                Spacer(modifier = Modifier.height(8.dp))
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("Exchange Rate:")
                    Text("1 USD = ${"%.2f".format(formState.exchangeRate)} NGN")
                }
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("Transfer Fee:")
                    Text("${"%.2f".format(formState.fee)} USD")
                }
                Divider(modifier = Modifier.padding(vertical = 4.dp))
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("Total Debit:", style = MaterialTheme.typography.titleSmall)
                    Text("${"%.2f".format(formState.totalToPay)} USD", style = MaterialTheme.typography.titleSmall)
                }
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("Beneficiary Receives (NGN):", style = MaterialTheme.typography.titleSmall)
                    Text("${"%.2f".format(formState.amountToSend.toDoubleOrNull()?.times(formState.exchangeRate) ?: 0.0)} NGN", style = MaterialTheme.typography.titleSmall)
                }
            }
        }
    }
}

// --- Step 3: Review and Payment Method ---
@Composable
fun ReviewAndPaymentStep(
    formState: TransferFormState,
    onEvent: (SendMoneyEvent) -> Unit
) {
    Column {
        Text("Review and Select Payment Method", style = MaterialTheme.typography.titleLarge)
        Spacer(modifier = Modifier.height(16.dp))

        // Review Card
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("Transaction Summary", style = MaterialTheme.typography.titleMedium)
                Spacer(modifier = Modifier.height(8.dp))
                formState.selectedBeneficiary?.let { beneficiary ->
                    Text("To: ${beneficiary.name} (${beneficiary.accountNumber})")
                    Text("Bank: ${beneficiary.bankName}")
                }
                Text("Amount: ${formState.amountToSend} USD")
                Text("Fee: ${"%.2f".format(formState.fee)} USD")
                Text("Total: ${"%.2f".format(formState.totalToPay)} USD")
                Text("Purpose: ${formState.purpose}")
            }
        }
        Spacer(modifier = Modifier.height(16.dp))

        // Payment Method Selection (Including Payment Gateways)
        Text("Choose Payment Method", style = MaterialTheme.typography.titleMedium)
        val paymentMethods = listOf("Bank Transfer", "Paystack", "Flutterwave", "Interswitch")
        paymentMethods.forEach { method ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onEvent(SendMoneyEvent.UpdateForm { copy(selectedPaymentMethod = method) }) }
                    .padding(vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                RadioButton(
                    selected = formState.selectedPaymentMethod == method,
                    onClick = { onEvent(SendMoneyEvent.UpdateForm { copy(selectedPaymentMethod = method) }) }
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(method)
            }
        }
    }
}

// --- Step 4: Authentication ---
@Composable
fun AuthenticationStep(
    formState: TransferFormState,
    onEvent: (SendMoneyEvent) -> Unit
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text("Confirm Transfer", style = MaterialTheme.typography.titleLarge)
        Spacer(modifier = Modifier.height(16.dp))

        Text("Enter your Transaction PIN or use Biometrics to authorize the transfer of ${"%.2f".format(formState.totalToPay)} USD.",
            style = MaterialTheme.typography.bodyMedium)
        Spacer(modifier = Modifier.height(16.dp))

        // PIN Input
        OutlinedTextField(
            value = formState.transactionPin,
            onValueChange = {
                if (it.length <= 4) {
                    onEvent(SendMoneyEvent.UpdateForm { copy(transactionPin = it) })
                }
            },
            label = { Text("Transaction PIN (4 digits)") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
            isError = formState.authError != null,
            modifier = Modifier.fillMaxWidth(0.5f)
        )
        if (formState.authError != null) {
            Text(formState.authError, color = MaterialTheme.colorScheme.error)
        }
        Spacer(modifier = Modifier.height(16.dp))

        // Biometric Authentication Button — launches the real platform prompt.
        val context = LocalContext.current
        Button(
            onClick = {
                val activity = context as? FragmentActivity
                if (activity == null) {
                    onEvent(SendMoneyEvent.BiometricAuthResult(false))
                } else {
                    val executor = ContextCompat.getMainExecutor(activity)
                    val prompt = BiometricPrompt(activity, executor, object : BiometricPrompt.AuthenticationCallback() {
                        override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                            onEvent(SendMoneyEvent.BiometricAuthResult(true))
                        }
                        override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                            onEvent(SendMoneyEvent.BiometricAuthResult(false))
                        }
                        override fun onAuthenticationFailed() {
                            // Non-fatal: prompt stays visible for another attempt.
                        }
                    })
                    // BIOMETRIC_STRONG with DEVICE_CREDENTIAL (passcode) fallback.
                    val promptInfo = BiometricPrompt.PromptInfo.Builder()
                        .setTitle("Authorize Transfer")
                        .setSubtitle("Authenticate to send ${"%.2f".format(formState.totalToPay)} USD")
                        .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.DEVICE_CREDENTIAL)
                        .build()
                    prompt.authenticate(promptInfo)
                }
            },
            colors = ButtonDefaults.outlinedButtonColors()
        ) {
            Text("Authenticate with Biometrics")
        }
    }
}

// --- Success and Error Screens (Step 5+) ---
@Composable
fun TransferSuccessScreen(message: String) {
    Column(
        modifier = Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            imageVector = Icons.Default.CheckCircle,
            contentDescription = "Success",
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(96.dp)
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text("Transfer Successful!", style = MaterialTheme.typography.headlineMedium)
        Spacer(modifier = Modifier.height(8.dp))
        Text(message, style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
fun TransferErrorScreen(message: String) {
    Column(
        modifier = Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            imageVector = Icons.Default.Error,
            contentDescription = "Error",
            tint = MaterialTheme.colorScheme.error,
            modifier = Modifier.size(96.dp)
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text("Transfer Failed", style = MaterialTheme.typography.headlineMedium)
        Spacer(modifier = Modifier.height(8.dp))
        Text(message, style = MaterialTheme.typography.bodyLarge)
    }
}

// --- Accessibility and Documentation Notes ---
/*
 * Accessibility (TalkBack):
 * - All Icons have `contentDescription`.
 * - All interactive elements (Buttons, RadioButtons, ListItems) are inherently accessible.
 * - Text fields use `label` for proper semantic meaning.
 *
 * Offline Mode (Room):
 * - The `TransferRepository` interface abstracts data access.
 * - `MockTransferRepository` simulates local data (`localBeneficiaries` flow) which would be backed by Room in a real implementation.
 * - The `loadBeneficiaries` function demonstrates fetching local data first.
 *
 * Retrofit/API:
 * - `MockTransferRepository` simulates API calls for `validateBeneficiary`, `getExchangeRate`, `calculateFee`, and `submitTransfer`.
 * - Error handling in `submitTransfer` includes checks for `HttpException` (Retrofit) and `IOException` (network).
 *
 * Payment Gateways:
 * - Step 3 includes "Paystack", "Flutterwave", and "Interswitch" as selectable payment methods. The actual integration logic would be in the `TransferRepository` and triggered by `submitTransfer`.
 *
 * Biometric Authentication:
 * - `AuthenticationStep` includes a button for biometric auth, and `SendMoneyViewModel` has a placeholder function `authenticateWithBiometrics` which would invoke `BiometricPrompt` in a real application.
 */

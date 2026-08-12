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

package com.pos54link.app.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import com.pos54link.app.data.api.*
import com.pos54link.app.security.IdempotencyKeyGenerator

data class TransactionUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val successRef: String? = null,
    val agentFloat: Double? = null,
    val dailyUsed: Double? = null,
    val dailyLimit: Double? = null,
    val fee: Double? = null,
    val commission: Double? = null,
    val tier: String? = null
)

@HiltViewModel
class TransactionViewModel @Inject constructor(
    private val transactionService: TransactionService
) : ViewModel() {

    private val _uiState = MutableStateFlow(TransactionUiState())
    val uiState: StateFlow<TransactionUiState> = _uiState.asStateFlow()

    fun processCashIn(customerPhone: String, amount: Double, narration: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null, successRef = null)

            // Pre-flight: check float balance
            val floatError = checkFloatSufficiency(amount)
            if (floatError != null) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = floatError)
                return@launch
            }

            val idempotencyKey = IdempotencyKeyGenerator.generate()
            try {
                val response = transactionService.cashIn(
                    idempotencyKey = idempotencyKey,
                    request = CashInRequest(
                        json = CashInInput(
                            customerPhone = customerPhone,
                            amount = amount,
                            narration = narration
                        )
                    )
                )
                val body = response.body()
                if (response.isSuccessful && body != null) {
                    val result = body.result.data.json
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        successRef = result.reference,
                        fee = result.fee,
                        commission = result.commission
                    )
                    refreshFloat()
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Transaction failed (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = e.message ?: "Transaction failed"
                )
            }
        }
    }

    fun processCashOut(customerPhone: String, amount: Double, withdrawalCode: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null, successRef = null)

            // Pre-flight: check float balance (cash out debits agent float)
            val floatError = checkFloatSufficiency(amount)
            if (floatError != null) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = floatError)
                return@launch
            }

            val idempotencyKey = IdempotencyKeyGenerator.generate()
            try {
                val response = transactionService.cashOut(
                    idempotencyKey = idempotencyKey,
                    request = CashOutRequest(
                        json = CashOutInput(
                            customerPhone = customerPhone,
                            amount = amount,
                            withdrawalCode = withdrawalCode
                        )
                    )
                )
                val body = response.body()
                if (response.isSuccessful && body != null) {
                    val result = body.result.data.json
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        successRef = result.reference,
                        fee = result.fee,
                        commission = result.commission
                    )
                    refreshFloat()
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Transaction failed (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = e.message ?: "Transaction failed"
                )
            }
        }
    }

    fun processBillPayment(category: String, provider: String, customerRef: String, amount: Double) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null, successRef = null)

            val idempotencyKey = IdempotencyKeyGenerator.generate()
            try {
                val response = transactionService.billPayment(
                    idempotencyKey = idempotencyKey,
                    request = BillPaymentRequest(
                        json = BillPaymentInput(
                            category = category,
                            provider = provider,
                            customerRef = customerRef,
                            amount = amount
                        )
                    )
                )
                val body = response.body()
                if (response.isSuccessful && body != null) {
                    val result = body.result.data.json
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        successRef = result.reference,
                        fee = result.fee,
                        commission = result.commission
                    )
                    refreshFloat()
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Payment failed (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = e.message ?: "Payment failed"
                )
            }
        }
    }

    fun requestPinPadVerification(
        phone: String,
        amount: Double,
        onVerified: () -> Unit,
        onFailed: () -> Unit
    ) {
        viewModelScope.launch {
            try {
                val response = transactionService.verifyPinPad(
                    PinVerifyRequest(json = PinVerifyInput(phone = phone, amount = amount))
                )
                val body = response.body()
                if (response.isSuccessful && body?.result?.data?.json?.verified == true) {
                    onVerified()
                } else {
                    onFailed()
                }
            } catch (e: Exception) {
                onFailed()
            }
        }
    }

    fun loadAgentFloat() {
        viewModelScope.launch {
            try {
                val response = transactionService.getAgentFloat()
                val body = response.body()
                if (response.isSuccessful && body != null) {
                    val result = body.result.data.json
                    _uiState.value = _uiState.value.copy(
                        agentFloat = result.floatBalance,
                        dailyUsed = result.dailyUsed,
                        dailyLimit = result.dailyLimit,
                        tier = result.tier
                    )
                }
            } catch (e: Exception) {
                // Non-critical — ignore
            }
        }
    }

    fun clearSuccess() {
        _uiState.value = _uiState.value.copy(successRef = null, fee = null, commission = null)
    }

    private fun checkFloatSufficiency(amount: Double): String? {
        val currentFloat = _uiState.value.agentFloat ?: return null // Can't validate if not loaded
        if (amount > currentFloat) {
            return "Insufficient float balance. Available: ₦${String.format("%,.0f", currentFloat)}, Required: ₦${String.format("%,.0f", amount)}"
        }
        // CBN daily limit check
        val dailyUsed = _uiState.value.dailyUsed ?: 0.0
        val dailyLimit = _uiState.value.dailyLimit ?: Double.MAX_VALUE
        if (dailyUsed + amount > dailyLimit) {
            val remaining = dailyLimit - dailyUsed
            return "Would exceed CBN daily limit of ₦${String.format("%,.0f", dailyLimit)}. Remaining: ₦${String.format("%,.0f", remaining.coerceAtLeast(0.0))}"
        }
        return null
    }

    private fun refreshFloat() {
        loadAgentFloat()
    }
}

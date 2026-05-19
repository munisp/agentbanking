package com.pos54link.app.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import com.pos54link.app.data.api.TransactionService

data class TransactionUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val successRef: String? = null,
    val agentFloat: Double? = null
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
            try {
                val result = transactionService.cashIn(
                    customerPhone = customerPhone,
                    amount = amount,
                    narration = narration
                )
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    successRef = result.reference
                )
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
            try {
                val result = transactionService.cashOut(
                    customerPhone = customerPhone,
                    amount = amount,
                    withdrawalCode = withdrawalCode
                )
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    successRef = result.reference
                )
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
            try {
                val result = transactionService.billPayment(
                    category = category,
                    provider = provider,
                    customerRef = customerRef,
                    amount = amount
                )
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    successRef = result.reference
                )
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
                val verified = transactionService.verifyPinPad(phone = phone, amount = amount)
                if (verified) onVerified() else onFailed()
            } catch (e: Exception) {
                onFailed()
            }
        }
    }

    fun loadAgentFloat() {
        viewModelScope.launch {
            try {
                val float = transactionService.getAgentFloat()
                _uiState.value = _uiState.value.copy(agentFloat = float)
            } catch (e: Exception) {
                // Non-critical — ignore
            }
        }
    }

    fun clearSuccess() {
        _uiState.value = _uiState.value.copy(successRef = null)
    }
}

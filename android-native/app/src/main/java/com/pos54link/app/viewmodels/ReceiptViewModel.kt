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
import com.pos54link.app.ui.screens.PrintState

data class ReceiptData(
    val reference: String,
    val date: String,
    val time: String,
    val transactionType: String,
    val customerPhone: String,
    val amount: String,
    val fee: String,
    val total: String,
    val status: String,
    val agentName: String,
    val agentCode: String,
    val terminalId: String,
    val simSlot: String
)

@HiltViewModel
class ReceiptViewModel @Inject constructor(
    private val transactionService: TransactionService
) : ViewModel() {

    private val _receipt = MutableStateFlow<ReceiptData?>(null)
    val receipt: StateFlow<ReceiptData?> = _receipt.asStateFlow()

    private val _printState = MutableStateFlow(PrintState.IDLE)
    val printState: StateFlow<PrintState> = _printState.asStateFlow()

    fun loadReceipt(transactionRef: String) {
        viewModelScope.launch {
            try {
                val tx = transactionService.getTransaction(transactionRef)
                _receipt.value = ReceiptData(
                    reference = tx.reference,
                    date = tx.date,
                    time = tx.time,
                    transactionType = tx.type,
                    customerPhone = tx.customerPhone,
                    amount = tx.amount,
                    fee = tx.fee,
                    total = tx.total,
                    status = tx.status,
                    agentName = tx.agentName,
                    agentCode = tx.agentCode,
                    terminalId = tx.terminalId,
                    simSlot = tx.simSlot
                )
            } catch (e: Exception) {
                // Handle error
            }
        }
    }

    fun printReceipt(transactionRef: String) {
        viewModelScope.launch {
            _printState.value = PrintState.PRINTING
            try {
                transactionService.printReceipt(transactionRef)
                _printState.value = PrintState.DONE
            } catch (e: Exception) {
                _printState.value = PrintState.ERROR
            }
        }
    }

    fun sendSmsReceipt(transactionRef: String) {
        viewModelScope.launch {
            try {
                transactionService.sendSmsReceipt(transactionRef)
            } catch (e: Exception) {
                // Non-critical
            }
        }
    }

    fun shareWhatsApp(transactionRef: String) {
        viewModelScope.launch {
            try {
                transactionService.shareWhatsApp(transactionRef)
            } catch (e: Exception) {
                // Non-critical
            }
        }
    }
}

package com.pos54link.app.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pos54link.app.models.CurrencyBalance
import com.pos54link.app.models.Transaction
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class WalletViewModel @Inject constructor() : ViewModel() {

    private val _balances = MutableStateFlow<List<CurrencyBalance>>(emptyList())
    val balances: StateFlow<List<CurrencyBalance>> = _balances.asStateFlow()

    private val _transactions = MutableStateFlow<List<Transaction>>(emptyList())
    val transactions: StateFlow<List<Transaction>> = _transactions.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _totalBalanceUSD = MutableStateFlow(0.0)
    val totalBalanceUSD: StateFlow<Double> = _totalBalanceUSD.asStateFlow()

    fun loadBalances() {
        viewModelScope.launch {
            _isLoading.value = true
            // API call to load balances
            _isLoading.value = false
        }
    }

    fun loadTransactions() {
        viewModelScope.launch {
            _isLoading.value = true
            // API call to load transactions
            _isLoading.value = false
        }
    }
}

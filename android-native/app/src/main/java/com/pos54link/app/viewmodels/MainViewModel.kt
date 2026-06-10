package com.pos54link.app.viewmodels

import android.net.Uri
import androidx.lifecycle.ViewModel
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject

@HiltViewModel
class MainViewModel @Inject constructor() : ViewModel() {

    private val _networkStatus = MutableStateFlow(true)
    val networkStatus: StateFlow<Boolean> = _networkStatus.asStateFlow()

    fun handleDeepLink(uri: Uri) {
        // Handle deep link navigation based on URI path
    }

    fun updateNetworkStatus(isConnected: Boolean) {
        _networkStatus.value = isConnected
    }
}

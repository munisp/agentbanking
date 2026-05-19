package com.pos54link.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.pos54link.app.viewmodels.TransactionViewModel

/**
 * Cash-Out Screen — PAX A920
 * Agent dispenses cash to customer who has initiated a withdrawal.
 * Requires PIN verification on the PAX PIN pad before disbursement.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CashOutScreen(
    onSuccess: (transactionRef: String) -> Unit,
    onBack: () -> Unit,
    viewModel: TransactionViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    var customerPhone by remember { mutableStateOf("") }
    var amount by remember { mutableStateOf("") }
    var withdrawalCode by remember { mutableStateOf("") }
    var pinPadState by remember { mutableStateOf(PinPadState.IDLE) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Cash Out") },
                navigationIcon = {
                    IconButton(onClick = onBack) { Text("←") }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            OutlinedTextField(
                value = customerPhone,
                onValueChange = { customerPhone = it },
                label = { Text("Customer Phone") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )

            OutlinedTextField(
                value = withdrawalCode,
                onValueChange = { withdrawalCode = it },
                label = { Text("Withdrawal Code (from customer's app)") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )

            OutlinedTextField(
                value = amount,
                onValueChange = { amount = it.filter { c -> c.isDigit() || c == '.' } },
                label = { Text("Amount (NGN)") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                modifier = Modifier.fillMaxWidth(),
                prefix = { Text("₦") },
                singleLine = true
            )

            // PIN pad status indicator
            when (pinPadState) {
                PinPadState.IDLE -> {}
                PinPadState.WAITING -> {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer)
                    ) {
                        Row(
                            modifier = Modifier.padding(16.dp),
                            horizontalArrangement = Arrangement.spacedBy(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            CircularProgressIndicator(modifier = Modifier.size(24.dp))
                            Text("Waiting for customer PIN on PIN pad...")
                        }
                    }
                }
                PinPadState.VERIFIED -> {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
                    ) {
                        Row(modifier = Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("✓", color = MaterialTheme.colorScheme.primary)
                            Text("PIN verified — ready to dispense cash")
                        }
                    }
                }
                PinPadState.FAILED -> {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)
                    ) {
                        Row(modifier = Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("✗", color = MaterialTheme.colorScheme.error)
                            Text("PIN verification failed")
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.weight(1f))

            // Agent float check
            if (uiState.agentFloat != null) {
                val floatAmount = uiState.agentFloat!!
                val requestedAmount = amount.toDoubleOrNull() ?: 0.0
                if (floatAmount < requestedAmount) {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)
                    ) {
                        Text(
                            "Insufficient float. Available: ₦${floatAmount}",
                            modifier = Modifier.padding(12.dp),
                            color = MaterialTheme.colorScheme.onErrorContainer
                        )
                    }
                }
            }

            if (pinPadState == PinPadState.IDLE || pinPadState == PinPadState.FAILED) {
                Button(
                    onClick = {
                        pinPadState = PinPadState.WAITING
                        viewModel.requestPinPadVerification(
                            phone = customerPhone,
                            amount = amount.toDoubleOrNull() ?: 0.0,
                            onVerified = { pinPadState = PinPadState.VERIFIED },
                            onFailed = { pinPadState = PinPadState.FAILED }
                        )
                    },
                    modifier = Modifier.fillMaxWidth().height(56.dp),
                    enabled = customerPhone.isNotEmpty() && amount.isNotEmpty() && withdrawalCode.isNotEmpty()
                ) {
                    Text("Request PIN Verification")
                }
            }

            if (pinPadState == PinPadState.VERIFIED) {
                Button(
                    onClick = {
                        viewModel.processCashOut(
                            customerPhone = customerPhone,
                            amount = amount.toDoubleOrNull() ?: 0.0,
                            withdrawalCode = withdrawalCode
                        )
                    },
                    modifier = Modifier.fillMaxWidth().height(56.dp),
                    enabled = !uiState.isLoading,
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.tertiary)
                ) {
                    if (uiState.isLoading) {
                        CircularProgressIndicator(modifier = Modifier.size(24.dp))
                    } else {
                        Text("Dispense ₦${amount}", style = MaterialTheme.typography.titleMedium)
                    }
                }
            }

            uiState.error?.let { error ->
                Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
        }
    }

    LaunchedEffect(uiState.successRef) {
        uiState.successRef?.let { ref -> onSuccess(ref) }
    }
}

enum class PinPadState { IDLE, WAITING, VERIFIED, FAILED }

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
 * Cash-In Screen — PAX A920
 * Allows agent to receive cash from customer and credit their mobile wallet.
 * Supports NFC tap, QR scan, and manual account entry.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CashInScreen(
    onSuccess: (transactionRef: String) -> Unit,
    onBack: () -> Unit,
    viewModel: TransactionViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    var customerPhone by remember { mutableStateOf("") }
    var amount by remember { mutableStateOf("") }
    var narration by remember { mutableStateOf("") }
    var inputMethod by remember { mutableStateOf(InputMethod.MANUAL) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Cash In") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        // Back arrow
                        Text("←")
                    }
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
            // Input method selector
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                InputMethod.entries.forEach { method ->
                    FilterChip(
                        selected = inputMethod == method,
                        onClick = { inputMethod = method },
                        label = { Text(method.label) }
                    )
                }
            }

            when (inputMethod) {
                InputMethod.MANUAL -> {
                    OutlinedTextField(
                        value = customerPhone,
                        onValueChange = { customerPhone = it },
                        label = { Text("Customer Phone / Account") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )
                }
                InputMethod.NFC -> {
                    Card(
                        modifier = Modifier.fillMaxWidth().height(120.dp),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
                    ) {
                        Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
                            Text("Tap customer's NFC card...", style = MaterialTheme.typography.bodyLarge)
                        }
                    }
                }
                InputMethod.QR -> {
                    Card(
                        modifier = Modifier.fillMaxWidth().height(120.dp),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)
                    ) {
                        Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
                            Text("Scan customer QR code...", style = MaterialTheme.typography.bodyLarge)
                        }
                    }
                }
            }

            OutlinedTextField(
                value = amount,
                onValueChange = { amount = it.filter { c -> c.isDigit() || c == '.' } },
                label = { Text("Amount (NGN)") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                modifier = Modifier.fillMaxWidth(),
                prefix = { Text("₦") },
                singleLine = true
            )

            OutlinedTextField(
                value = narration,
                onValueChange = { narration = it },
                label = { Text("Narration (optional)") },
                modifier = Modifier.fillMaxWidth(),
                maxLines = 2
            )

            // Amount quick-select buttons
            Text("Quick amounts:", style = MaterialTheme.typography.labelMedium)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                listOf("500", "1000", "2000", "5000", "10000").forEach { quickAmount ->
                    AssistChip(
                        onClick = { amount = quickAmount },
                        label = { Text("₦$quickAmount") }
                    )
                }
            }

            Spacer(modifier = Modifier.weight(1f))

            // Summary card
            if (amount.isNotEmpty() && customerPhone.isNotEmpty()) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Transaction Summary", style = MaterialTheme.typography.titleSmall)
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("Customer"); Text(customerPhone)
                        }
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("Amount"); Text("₦${amount}")
                        }
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("Fee"); Text("₦0.00")
                        }
                        Divider()
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("Total", style = MaterialTheme.typography.titleSmall)
                            Text("₦${amount}", style = MaterialTheme.typography.titleSmall)
                        }
                    }
                }
            }

            Button(
                onClick = {
                    viewModel.processCashIn(
                        customerPhone = customerPhone,
                        amount = amount.toDoubleOrNull() ?: 0.0,
                        narration = narration
                    )
                },
                modifier = Modifier.fillMaxWidth().height(56.dp),
                enabled = customerPhone.isNotEmpty() && amount.isNotEmpty() && !uiState.isLoading
            ) {
                if (uiState.isLoading) {
                    CircularProgressIndicator(modifier = Modifier.size(24.dp), color = MaterialTheme.colorScheme.onPrimary)
                } else {
                    Text("Process Cash In", style = MaterialTheme.typography.titleMedium)
                }
            }

            uiState.error?.let { error ->
                Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
        }
    }

    LaunchedEffect(uiState.successRef) {
        uiState.successRef?.let { ref ->
            onSuccess(ref)
        }
    }
}

enum class InputMethod(val label: String) {
    MANUAL("Manual"),
    NFC("NFC"),
    QR("QR Code")
}

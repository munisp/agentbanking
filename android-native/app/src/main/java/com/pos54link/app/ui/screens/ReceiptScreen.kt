package com.pos54link.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.pos54link.app.viewmodels.ReceiptViewModel

/**
 * Receipt Screen — PAX A920
 * Displays transaction receipt and provides print / SMS / WhatsApp share options.
 * Triggers ESC/POS print via the PAX thermal printer HAL.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReceiptScreen(
    transactionRef: String,
    onNewTransaction: () -> Unit,
    onHome: () -> Unit,
    viewModel: ReceiptViewModel = hiltViewModel()
) {
    val receipt by viewModel.receipt.collectAsState()
    val printState by viewModel.printState.collectAsState()

    LaunchedEffect(transactionRef) {
        viewModel.loadReceipt(transactionRef)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Receipt") },
                actions = {
                    IconButton(onClick = onHome) { Text("🏠") }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Success indicator
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
            ) {
                Column(
                    modifier = Modifier.padding(24.dp).fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text("✓", style = MaterialTheme.typography.displayMedium, color = MaterialTheme.colorScheme.primary)
                    Text("Transaction Successful", style = MaterialTheme.typography.titleLarge)
                }
            }

            Spacer(Modifier.height(16.dp))

            // Receipt body
            receipt?.let { r ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier
                            .padding(16.dp)
                            .verticalScroll(rememberScrollState()),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        // Header
                        Text(
                            "54LINK POS SERVICES",
                            style = MaterialTheme.typography.titleMedium,
                            fontFamily = FontFamily.Monospace,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.fillMaxWidth()
                        )
                        Text(
                            r.agentName,
                            style = MaterialTheme.typography.bodySmall,
                            fontFamily = FontFamily.Monospace,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.fillMaxWidth()
                        )
                        Text(
                            r.agentCode,
                            style = MaterialTheme.typography.bodySmall,
                            fontFamily = FontFamily.Monospace,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.fillMaxWidth()
                        )

                        Divider()

                        // Transaction details
                        ReceiptRow("Date", r.date)
                        ReceiptRow("Time", r.time)
                        ReceiptRow("Ref", r.reference)
                        ReceiptRow("Type", r.transactionType)
                        ReceiptRow("Customer", r.customerPhone)

                        Divider()

                        ReceiptRow("Amount", "₦${r.amount}")
                        ReceiptRow("Fee", "₦${r.fee}")
                        ReceiptRow("Total", "₦${r.total}")

                        Divider()

                        ReceiptRow("Status", r.status)
                        ReceiptRow("Terminal", r.terminalId)
                        ReceiptRow("SIM", r.simSlot)

                        Divider()

                        Text(
                            "Thank you for using 54Link",
                            style = MaterialTheme.typography.bodySmall,
                            fontFamily = FontFamily.Monospace,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.fillMaxWidth()
                        )
                        Text(
                            "Support: 0800-54LINK",
                            style = MaterialTheme.typography.bodySmall,
                            fontFamily = FontFamily.Monospace,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                }
            } ?: run {
                CircularProgressIndicator()
            }

            Spacer(Modifier.weight(1f))

            // Action buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                OutlinedButton(
                    onClick = { viewModel.printReceipt(transactionRef) },
                    modifier = Modifier.weight(1f),
                    enabled = printState != PrintState.PRINTING
                ) {
                    when (printState) {
                        PrintState.IDLE -> Text("🖨️ Print")
                        PrintState.PRINTING -> {
                            CircularProgressIndicator(modifier = Modifier.size(16.dp))
                            Spacer(Modifier.width(8.dp))
                            Text("Printing...")
                        }
                        PrintState.DONE -> Text("✓ Printed")
                        PrintState.ERROR -> Text("⚠ Retry Print")
                    }
                }

                OutlinedButton(
                    onClick = { viewModel.sendSmsReceipt(transactionRef) },
                    modifier = Modifier.weight(1f)
                ) { Text("📱 SMS") }

                OutlinedButton(
                    onClick = { viewModel.shareWhatsApp(transactionRef) },
                    modifier = Modifier.weight(1f)
                ) { Text("💬 WhatsApp") }
            }

            Spacer(Modifier.height(12.dp))

            Button(
                onClick = onNewTransaction,
                modifier = Modifier.fillMaxWidth().height(56.dp)
            ) { Text("New Transaction") }
        }
    }
}

@Composable
private fun ReceiptRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(label, style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Monospace)
        Text(value, style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Monospace)
    }
}

enum class PrintState { IDLE, PRINTING, DONE, ERROR }

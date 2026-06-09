package com.pos54link.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/**
 * Terminal Leasing Screen
 *
 * Maps to backend: terminalLeasing.ts
 * Features:
 *   - View active/overdue leases with payment schedule
 *   - Make lease payments (recordPayment)
 *   - Track remaining balance, missed payments, next due date
 *   - Lease types: standard, premium, rent-to-own
 *   - Insurance cost display if included
 *   - Payment day validation (1-28)
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TerminalLeasingScreen(onBack: () -> Unit) {
    val leases = remember {
        listOf(
            LeaseInfo(
                id = "LSE-001", terminalId = "TRM-PAX-001", type = "rent_to_own",
                status = "active", monthlyRate = 15000.0, totalPaid = 90000.0,
                duration = 24, monthsRemaining = 18, missedPayments = 0,
                nextPaymentDue = "2026-06-01", includesInsurance = true,
                insuranceRate = 1500.0, deposit = 25000.0
            ),
            LeaseInfo(
                id = "LSE-002", terminalId = "TRM-SUN-002", type = "standard",
                status = "overdue", monthlyRate = 10000.0, totalPaid = 30000.0,
                duration = 12, monthsRemaining = 9, missedPayments = 2,
                nextPaymentDue = "2026-05-01", includesInsurance = false,
                insuranceRate = 0.0, deposit = 15000.0
            ),
        )
    }

    var showPaymentDialog by remember { mutableStateOf(false) }
    var selectedLease by remember { mutableStateOf<LeaseInfo?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Terminal Leasing") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") } }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier.padding(padding).fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            items(leases) { lease ->
                LeaseCard(lease, onPay = {
                    selectedLease = lease
                    showPaymentDialog = true
                })
            }
        }
    }

    if (showPaymentDialog && selectedLease != null) {
        PaymentDialog(
            lease = selectedLease!!,
            onDismiss = { showPaymentDialog = false },
            onPay = { /* call recordPayment API with idempotencyKey */ showPaymentDialog = false }
        )
    }
}

@Composable
private fun LeaseCard(lease: LeaseInfo, onPay: () -> Unit) {
    val statusColor = when (lease.status) {
        "active" -> Color(0xFF16A34A)
        "overdue" -> Color(0xFFDC2626)
        "suspended" -> Color(0xFFF59E0B)
        "completed" -> Color(0xFF6366F1)
        else -> Color.Gray
    }

    val totalCost = (lease.monthlyRate + lease.insuranceRate) * lease.duration + lease.deposit
    val remaining = totalCost - lease.totalPaid

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(lease.id, fontWeight = FontWeight.Bold)
                    Text(
                        "Terminal: ${lease.terminalId}",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.Gray
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Surface(color = statusColor.copy(alpha = 0.1f), shape = MaterialTheme.shapes.small) {
                        Text(
                            lease.status.uppercase(),
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                            color = statusColor,
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Text(
                        lease.type.replace("_", " ").replaceFirstChar { it.uppercase() },
                        style = MaterialTheme.typography.labelSmall,
                        color = Color.Gray
                    )
                }
            }

            HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp))

            // Payment details
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text("Monthly", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                    Text("₦${String.format("%,.0f", lease.monthlyRate)}", fontWeight = FontWeight.Medium)
                }
                Column {
                    Text("Paid", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                    Text("₦${String.format("%,.0f", lease.totalPaid)}", fontWeight = FontWeight.Medium)
                }
                Column {
                    Text("Remaining", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                    Text("₦${String.format("%,.0f", remaining)}", fontWeight = FontWeight.Medium, color = Color(0xFFDC2626))
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Progress bar
            LinearProgressIndicator(
                progress = { (lease.totalPaid / totalCost).toFloat().coerceIn(0f, 1f) },
                modifier = Modifier.fillMaxWidth().height(8.dp),
                color = Color(0xFF16A34A),
                trackColor = Color(0xFFE5E7EB)
            )

            Spacer(modifier = Modifier.height(8.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(
                    "${lease.monthsRemaining} months remaining",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray
                )
                if (lease.missedPayments > 0) {
                    Text(
                        "${lease.missedPayments} missed payments",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color(0xFFDC2626),
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            if (lease.includesInsurance) {
                Text(
                    "Insurance: ₦${String.format("%,.0f", lease.insuranceRate)}/mo",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color(0xFF6366F1)
                )
            }

            Spacer(modifier = Modifier.height(8.dp))
            Text("Next payment: ${lease.nextPaymentDue}", style = MaterialTheme.typography.bodySmall)

            Spacer(modifier = Modifier.height(8.dp))
            Button(
                onClick = onPay,
                modifier = Modifier.fillMaxWidth(),
                enabled = lease.status in listOf("active", "overdue")
            ) { Text("Make Payment") }
        }
    }
}

@Composable
private fun PaymentDialog(lease: LeaseInfo, onDismiss: () -> Unit, onPay: () -> Unit) {
    var amount by remember { mutableStateOf(String.format("%.0f", lease.monthlyRate + lease.insuranceRate)) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Lease Payment — ${lease.id}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Terminal: ${lease.terminalId}")
                Text("Monthly: ₦${String.format("%,.0f", lease.monthlyRate + lease.insuranceRate)}")
                OutlinedTextField(
                    value = amount,
                    onValueChange = { amount = it.filter { c -> c.isDigit() || c == '.' } },
                    label = { Text("Payment Amount (NGN)") },
                    prefix = { Text("₦") },
                    modifier = Modifier.fillMaxWidth()
                )
            }
        },
        confirmButton = {
            Button(onClick = onPay) { Text("Pay") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        }
    )
}

private data class LeaseInfo(
    val id: String,
    val terminalId: String,
    val type: String,
    val status: String,
    val monthlyRate: Double,
    val totalPaid: Double,
    val duration: Int,
    val monthsRemaining: Int,
    val missedPayments: Int,
    val nextPaymentDue: String,
    val includesInsurance: Boolean,
    val insuranceRate: Double,
    val deposit: Double
)

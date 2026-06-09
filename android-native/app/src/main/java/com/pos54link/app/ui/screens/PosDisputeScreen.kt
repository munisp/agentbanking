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
 * POS Dispute Screen
 *
 * Maps to backend: posDispute.ts
 * Features:
 *   - View agent's disputes (open, investigating, resolved, rejected, escalated)
 *   - File new dispute with reason enum and evidence
 *   - SLA indicators (auto-escalation after 72h)
 *   - Status transitions enforced via state machine
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PosDisputeScreen(onBack: () -> Unit) {
    var showFileDialog by remember { mutableStateOf(false) }
    var selectedTab by remember { mutableIntStateOf(0) }
    val tabs = listOf("All", "Open", "Investigating", "Resolved", "Escalated")

    val disputes = remember {
        mutableStateListOf(
            DisputeItem("DSP-001", "wrong_amount", "open", "₦5,000 vs ₦3,000", "2026-05-18", 24),
            DisputeItem("DSP-002", "failed_but_debited", "investigating", "TXN debited but failed", "2026-05-16", 72),
            DisputeItem("DSP-003", "duplicate_charge", "resolved", "Double charge refunded", "2026-05-10", 0),
            DisputeItem("DSP-004", "unauthorized", "escalated", "Unauthorized transaction", "2026-05-14", 120),
        )
    }

    val filtered = when (selectedTab) {
        1 -> disputes.filter { it.status == "open" }
        2 -> disputes.filter { it.status == "investigating" }
        3 -> disputes.filter { it.status == "resolved" }
        4 -> disputes.filter { it.status == "escalated" }
        else -> disputes
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Disputes") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") } }
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { showFileDialog = true }) {
                Icon(Icons.Default.Add, "File Dispute")
            }
        }
    ) { padding ->
        Column(modifier = Modifier.padding(padding)) {
            // Stats
            Row(
                modifier = Modifier.fillMaxWidth().padding(16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                val open = disputes.count { it.status == "open" }
                val investigating = disputes.count { it.status == "investigating" }
                val escalated = disputes.count { it.status == "escalated" }
                StatChip("Open: $open", Color(0xFFF59E0B), Modifier.weight(1f))
                StatChip("Investigating: $investigating", Color(0xFF3B82F6), Modifier.weight(1f))
                StatChip("Escalated: $escalated", Color(0xFFDC2626), Modifier.weight(1f))
            }

            // Tabs
            ScrollableTabRow(selectedTabIndex = selectedTab) {
                tabs.forEachIndexed { index, title ->
                    Tab(selected = selectedTab == index, onClick = { selectedTab = index }, text = { Text(title) })
                }
            }

            // List
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(filtered) { dispute ->
                    DisputeCard(dispute)
                }
            }
        }
    }

    if (showFileDialog) {
        FileDisputeDialog(onDismiss = { showFileDialog = false })
    }
}

@Composable
private fun DisputeCard(dispute: DisputeItem) {
    val statusColor = when (dispute.status) {
        "open" -> Color(0xFFF59E0B)
        "investigating" -> Color(0xFF3B82F6)
        "resolved" -> Color(0xFF10B981)
        "rejected" -> Color(0xFF6B7280)
        "escalated" -> Color(0xFFDC2626)
        else -> Color.Gray
    }

    val slaBreached = dispute.hoursOpen > 72

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = if (slaBreached) CardDefaults.cardColors(containerColor = Color(0xFFFEF2F2))
        else CardDefaults.cardColors()
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(dispute.reference, fontWeight = FontWeight.Bold)
                    Text(
                        dispute.reason.replace("_", " ").replaceFirstChar { it.uppercase() },
                        style = MaterialTheme.typography.bodySmall, color = Color.Gray
                    )
                }
                Surface(color = statusColor.copy(alpha = 0.1f), shape = MaterialTheme.shapes.small) {
                    Text(
                        dispute.status.uppercase(),
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        color = statusColor,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text(dispute.description, style = MaterialTheme.typography.bodyMedium)
            Spacer(modifier = Modifier.height(4.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(dispute.filedDate, style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                if (slaBreached) {
                    Text(
                        "SLA BREACHED (${dispute.hoursOpen}h)",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color(0xFFDC2626),
                        fontWeight = FontWeight.Bold
                    )
                } else if (dispute.hoursOpen > 48) {
                    Text(
                        "SLA: ${72 - dispute.hoursOpen}h remaining",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color(0xFFF59E0B)
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun FileDisputeDialog(onDismiss: () -> Unit) {
    var transactionRef by remember { mutableStateOf("") }
    var selectedReason by remember { mutableStateOf("wrong_amount") }
    var description by remember { mutableStateOf("") }
    var expanded by remember { mutableStateOf(false) }

    val reasons = listOf(
        "wrong_amount", "failed_but_debited", "duplicate_charge",
        "unauthorized", "service_not_received", "other"
    )

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("File Dispute") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = transactionRef,
                    onValueChange = { transactionRef = it },
                    label = { Text("Transaction Reference") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
                ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
                    OutlinedTextField(
                        value = selectedReason.replace("_", " ").replaceFirstChar { it.uppercase() },
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("Reason") },
                        modifier = Modifier.fillMaxWidth().menuAnchor(),
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) }
                    )
                    ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                        reasons.forEach { reason ->
                            DropdownMenuItem(
                                text = { Text(reason.replace("_", " ").replaceFirstChar { it.uppercase() }) },
                                onClick = { selectedReason = reason; expanded = false }
                            )
                        }
                    }
                }
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = { Text("Description") },
                    modifier = Modifier.fillMaxWidth(),
                    maxLines = 3
                )
            }
        },
        confirmButton = {
            Button(onClick = { /* call fileDispute API */ onDismiss() }) { Text("Submit") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        }
    )
}

@Composable
private fun StatChip(text: String, color: Color, modifier: Modifier = Modifier) {
    Card(modifier = modifier, colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.1f))) {
        Text(
            text,
            modifier = Modifier.padding(8.dp).fillMaxWidth(),
            color = color,
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.Bold
        )
    }
}

private data class DisputeItem(
    val reference: String,
    val reason: String,
    val status: String,
    val description: String,
    val filedDate: String,
    val hoursOpen: Int
)

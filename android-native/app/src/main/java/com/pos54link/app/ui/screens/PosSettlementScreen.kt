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
 * POS Batch Settlement Screen
 *
 * Maps to backend: posBatchSettlement.ts
 * Features:
 *   - View settlement batches (pending, processing, settled, reconciled)
 *   - Trigger new settlement batch creation
 *   - View settlement stats (total volume, fees, net payout)
 *   - Status-based filtering with color-coded badges
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PosSettlementScreen(onBack: () -> Unit) {
    var selectedTab by remember { mutableIntStateOf(0) }
    val tabs = listOf("All", "Pending", "Processing", "Settled")

    var batches by remember {
        mutableStateOf(
            listOf(
                SettlementBatch("BATCH-001", "pending", 45, 125_000.0, 3_750.0, "2026-05-19"),
                SettlementBatch("BATCH-002", "processing", 32, 89_500.0, 2_685.0, "2026-05-18"),
                SettlementBatch("BATCH-003", "settled", 67, 230_000.0, 6_900.0, "2026-05-17"),
            )
        )
    }

    val filtered = when (selectedTab) {
        1 -> batches.filter { it.status == "pending" }
        2 -> batches.filter { it.status == "processing" }
        3 -> batches.filter { it.status == "settled" }
        else -> batches
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settlement") },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") }
                },
                actions = {
                    IconButton(onClick = { /* refresh */ }) { Icon(Icons.Default.Refresh, "Refresh") }
                }
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { /* trigger createBatch with idempotencyKey */ }) {
                Icon(Icons.Default.Add, "New Batch")
            }
        }
    ) { padding ->
        Column(modifier = Modifier.padding(padding)) {
            // Stats summary
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                StatCard("Today's Volume", "₦444,500", Color(0xFF2563EB), Modifier.weight(1f))
                StatCard("Total Fees", "₦13,335", Color(0xFFDC2626), Modifier.weight(1f))
                StatCard("Net Payout", "₦431,165", Color(0xFF16A34A), Modifier.weight(1f))
            }

            // Tabs
            TabRow(selectedTabIndex = selectedTab) {
                tabs.forEachIndexed { index, title ->
                    Tab(
                        selected = selectedTab == index,
                        onClick = { selectedTab = index },
                        text = { Text(title) }
                    )
                }
            }

            // Batch list
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(filtered) { batch ->
                    SettlementBatchCard(batch)
                }
            }
        }
    }
}

@Composable
private fun SettlementBatchCard(batch: SettlementBatch) {
    val statusColor = when (batch.status) {
        "pending" -> Color(0xFFF59E0B)
        "processing" -> Color(0xFF3B82F6)
        "settled" -> Color(0xFF10B981)
        "reconciled" -> Color(0xFF6366F1)
        else -> Color.Gray
    }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(batch.reference, fontWeight = FontWeight.Bold)
                Surface(
                    color = statusColor.copy(alpha = 0.1f),
                    shape = MaterialTheme.shapes.small
                ) {
                    Text(
                        batch.status.uppercase(),
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        color = statusColor,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text("Transactions", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                    Text("${batch.transactionCount}", fontWeight = FontWeight.Medium)
                }
                Column {
                    Text("Total Amount", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                    Text("₦${String.format("%,.0f", batch.totalAmount)}", fontWeight = FontWeight.Medium)
                }
                Column {
                    Text("Fees", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                    Text("₦${String.format("%,.0f", batch.fees)}", fontWeight = FontWeight.Medium)
                }
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(batch.date, style = MaterialTheme.typography.bodySmall, color = Color.Gray)
        }
    }
}

@Composable
private fun StatCard(label: String, value: String, color: Color, modifier: Modifier = Modifier) {
    Card(modifier = modifier) {
        Column(
            modifier = Modifier.padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(value, fontWeight = FontWeight.Bold, color = color)
            Text(label, style = MaterialTheme.typography.labelSmall, color = Color.Gray)
        }
    }
}

private data class SettlementBatch(
    val reference: String,
    val status: String,
    val transactionCount: Int,
    val totalAmount: Double,
    val fees: Double,
    val date: String
)

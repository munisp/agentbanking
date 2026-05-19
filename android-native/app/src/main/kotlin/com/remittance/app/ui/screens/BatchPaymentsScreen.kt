package com.pos54link.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import java.text.SimpleDateFormat
import java.util.*

data class PaymentBatch(
    val batchId: String,
    val name: String,
    val status: String,
    val totalAmount: Double,
    val currency: String,
    val totalPayments: Int,
    val completedPayments: Int,
    val failedPayments: Int,
    val progressPercent: Int,
    val createdAt: Long,
    val recurrence: String
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BatchPaymentsScreen(
    onNavigateBack: () -> Unit
) {
    var batches by remember { mutableStateOf<List<PaymentBatch>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var selectedTab by remember { mutableStateOf(0) }

    LaunchedEffect(Unit) {
        delay(500)
        batches = listOf(
            PaymentBatch("batch-001", "January Payroll", "COMPLETED", 5000000.0, "NGN", 50, 50, 0, 100, 
                System.currentTimeMillis() - 86400000 * 7, "MONTHLY"),
            PaymentBatch("batch-002", "Vendor Payments Q1", "PROCESSING", 2500000.0, "NGN", 25, 15, 2, 60,
                System.currentTimeMillis() - 3600000, "ONCE"),
            PaymentBatch("batch-003", "Contractor Fees", "PENDING", 1200000.0, "NGN", 12, 0, 0, 0,
                System.currentTimeMillis() - 1800000, "ONCE")
        )
        loading = false
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Batch Payments") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { }) {
                        Icon(Icons.Default.Add, contentDescription = "New Batch")
                    }
                }
            )
        }
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            TabRow(selectedTabIndex = selectedTab) {
                Tab(selected = selectedTab == 0, onClick = { selectedTab = 0 }, text = { Text("Batches") })
                Tab(selected = selectedTab == 1, onClick = { selectedTab = 1 }, text = { Text("Scheduled") })
            }

            if (loading) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    items(batches) { batch ->
                        BatchCard(batch)
                    }
                }
            }
        }
    }
}

@Composable
private fun BatchCard(batch: PaymentBatch) {
    val statusColor = when (batch.status) {
        "COMPLETED" -> Color(0xFF4CAF50)
        "PROCESSING" -> Color(0xFF2196F3)
        "PENDING" -> Color(0xFFFFC107)
        "FAILED" -> Color(0xFFF44336)
        else -> Color.Gray
    }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(batch.name, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                    Text(
                        SimpleDateFormat("MMM dd, yyyy", Locale.getDefault()).format(Date(batch.createdAt)),
                        fontSize = 12.sp, color = Color.Gray
                    )
                }
                Surface(
                    shape = RoundedCornerShape(16.dp),
                    color = statusColor.copy(alpha = 0.1f)
                ) {
                    Text(
                        batch.status,
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
                        color = statusColor,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Medium
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text("Total Amount", fontSize = 12.sp, color = Color.Gray)
                    Text("${batch.currency} ${String.format("%,.0f", batch.totalAmount)}", fontWeight = FontWeight.Bold)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text("Payments", fontSize = 12.sp, color = Color.Gray)
                    Text("${batch.completedPayments}/${batch.totalPayments}", fontWeight = FontWeight.Bold)
                }
            }

            if (batch.status == "PROCESSING") {
                Spacer(modifier = Modifier.height(8.dp))
                LinearProgressIndicator(
                    progress = batch.progressPercent / 100f,
                    modifier = Modifier.fillMaxWidth().height(4.dp)
                )
            }

            if (batch.status == "PENDING") {
                Spacer(modifier = Modifier.height(8.dp))
                Button(
                    onClick = { },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4CAF50))
                ) {
                    Text("Process Batch")
                }
            }
        }
    }
}

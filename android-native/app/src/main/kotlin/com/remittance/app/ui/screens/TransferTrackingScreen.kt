package com.pos54link.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import java.text.SimpleDateFormat
import java.util.*

data class TrackingEvent(
    val state: String,
    val timestamp: Long,
    val description: String,
    val location: String? = null
)

data class TransferTrackingData(
    val transferId: String,
    val trackingId: String,
    val currentState: String,
    val progressPercent: Int,
    val senderName: String,
    val recipientName: String,
    val amount: Double,
    val currency: String,
    val destinationCurrency: String,
    val destinationAmount: Double,
    val corridor: String,
    val createdAt: Long,
    val estimatedCompletion: Long,
    val events: List<TrackingEvent>
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TransferTrackingScreen(
    transferId: String,
    onNavigateBack: () -> Unit
) {
    var tracking by remember { mutableStateOf<TransferTrackingData?>(null) }
    var loading by remember { mutableStateOf(true) }

    val transferStates = listOf(
        "INITIATED" to "Transfer Initiated",
        "PENDING" to "Pending",
        "RESERVED" to "Funds Reserved",
        "IN_NETWORK" to "In Network",
        "AT_DESTINATION" to "At Destination",
        "COMPLETED" to "Completed"
    )

    LaunchedEffect(transferId) {
        delay(500)
        tracking = TransferTrackingData(
            transferId = transferId,
            trackingId = "TRK-${transferId.take(8).uppercase()}",
            currentState = "IN_NETWORK",
            progressPercent = 60,
            senderName = "John Doe",
            recipientName = "Jane Smith",
            amount = 500.0,
            currency = "GBP",
            destinationCurrency = "NGN",
            destinationAmount = 975250.0,
            corridor = "MOJALOOP",
            createdAt = System.currentTimeMillis() - 3600000,
            estimatedCompletion = System.currentTimeMillis() + 1800000,
            events = listOf(
                TrackingEvent("INITIATED", System.currentTimeMillis() - 3600000, "Transfer initiated"),
                TrackingEvent("PENDING", System.currentTimeMillis() - 3500000, "Awaiting verification"),
                TrackingEvent("RESERVED", System.currentTimeMillis() - 3000000, "Funds reserved"),
                TrackingEvent("IN_NETWORK", System.currentTimeMillis() - 1800000, "Processing via Mojaloop", "Lagos Hub")
            )
        )
        loading = false
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Transfer Tracking") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { padding ->
        if (loading) {
            Box(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator()
            }
        } else {
            tracking?.let { data ->
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    item {
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primary)
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Column {
                                        Text("Sending", color = Color.White.copy(alpha = 0.7f), fontSize = 12.sp)
                                        Text("${data.currency} ${String.format("%,.2f", data.amount)}", 
                                            color = Color.White, fontWeight = FontWeight.Bold, fontSize = 20.sp)
                                    }
                                    Column(horizontalAlignment = Alignment.End) {
                                        Text("Receiving", color = Color.White.copy(alpha = 0.7f), fontSize = 12.sp)
                                        Text("${data.destinationCurrency} ${String.format("%,.0f", data.destinationAmount)}", 
                                            color = Color.White, fontWeight = FontWeight.Bold, fontSize = 20.sp)
                                    }
                                }
                                Spacer(modifier = Modifier.height(16.dp))
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Column {
                                        Text("From", color = Color.White.copy(alpha = 0.7f), fontSize = 12.sp)
                                        Text(data.senderName, color = Color.White, fontWeight = FontWeight.Medium)
                                    }
                                    Column(horizontalAlignment = Alignment.End) {
                                        Text("To", color = Color.White.copy(alpha = 0.7f), fontSize = 12.sp)
                                        Text(data.recipientName, color = Color.White, fontWeight = FontWeight.Medium)
                                    }
                                }
                            }
                        }
                    }

                    item {
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text("Progress", fontWeight = FontWeight.Medium)
                                    Text("${data.progressPercent}%", color = MaterialTheme.colorScheme.primary)
                                }
                                Spacer(modifier = Modifier.height(8.dp))
                                LinearProgressIndicator(
                                    progress = data.progressPercent / 100f,
                                    modifier = Modifier.fillMaxWidth().height(8.dp).clip(RoundedCornerShape(4.dp))
                                )
                            }
                        }
                    }

                    item {
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text("Transfer Status", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                                Spacer(modifier = Modifier.height(16.dp))
                                
                                val currentIndex = transferStates.indexOfFirst { it.first == data.currentState }
                                
                                transferStates.forEachIndexed { index, (state, label) ->
                                    val isCompleted = index < currentIndex
                                    val isCurrent = index == currentIndex
                                    val event = data.events.find { it.state == state }
                                    
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        verticalAlignment = Alignment.Top
                                    ) {
                                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                            Box(
                                                modifier = Modifier
                                                    .size(32.dp)
                                                    .clip(CircleShape)
                                                    .background(
                                                        when {
                                                            isCompleted -> Color(0xFF4CAF50)
                                                            isCurrent -> MaterialTheme.colorScheme.primary
                                                            else -> Color.LightGray
                                                        }
                                                    ),
                                                contentAlignment = Alignment.Center
                                            ) {
                                                if (isCompleted) {
                                                    Icon(Icons.Default.Check, contentDescription = null, 
                                                        tint = Color.White, modifier = Modifier.size(16.dp))
                                                } else {
                                                    Text("${index + 1}", color = Color.White, fontSize = 12.sp)
                                                }
                                            }
                                            if (index < transferStates.size - 1) {
                                                Box(
                                                    modifier = Modifier
                                                        .width(2.dp)
                                                        .height(40.dp)
                                                        .background(if (isCompleted) Color(0xFF4CAF50) else Color.LightGray)
                                                )
                                            }
                                        }
                                        Spacer(modifier = Modifier.width(12.dp))
                                        Column(modifier = Modifier.weight(1f)) {
                                            Text(
                                                label,
                                                fontWeight = if (isCurrent) FontWeight.Bold else FontWeight.Normal,
                                                color = if (index > currentIndex) Color.Gray else Color.Unspecified
                                            )
                                            event?.let {
                                                Text(
                                                    SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date(it.timestamp)),
                                                    fontSize = 12.sp,
                                                    color = Color.Gray
                                                )
                                                it.location?.let { loc ->
                                                    Text(loc, fontSize = 12.sp, color = Color.Gray)
                                                }
                                            }
                                            Spacer(modifier = Modifier.height(if (index < transferStates.size - 1) 24.dp else 0.dp))
                                        }
                                    }
                                }
                            }
                        }
                    }

                    item {
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text("Transfer Details", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                                Spacer(modifier = Modifier.height(12.dp))
                                DetailRow("Tracking ID", data.trackingId)
                                DetailRow("Payment Network", data.corridor)
                                DetailRow("Created", SimpleDateFormat("MMM dd, yyyy HH:mm", Locale.getDefault()).format(Date(data.createdAt)))
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(label, color = Color.Gray)
        Text(value, fontWeight = FontWeight.Medium)
    }
}

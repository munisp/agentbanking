package com.pos54link.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowBack
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

data class FXAlert(
    val alertId: String,
    val sourceCurrency: String,
    val destinationCurrency: String,
    val alertType: String,
    val thresholdValue: Double,
    val currentValue: Double,
    val status: String
)

data class LoyaltySummary(
    val tier: String,
    val tierIcon: String,
    val availablePoints: Int,
    val totalPoints: Int,
    val feeDiscount: Int,
    val cashbackPercent: Double,
    val freeTransfersPerMonth: Int,
    val nextTier: String?,
    val pointsToNextTier: Int
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FXAlertsScreen(
    onNavigateBack: () -> Unit
) {
    var alerts by remember { mutableStateOf<List<FXAlert>>(emptyList()) }
    var loyalty by remember { mutableStateOf<LoyaltySummary?>(null) }
    var loading by remember { mutableStateOf(true) }
    var selectedTab by remember { mutableStateOf(0) }

    LaunchedEffect(Unit) {
        delay(500)
        alerts = listOf(
            FXAlert("alert-001", "GBP", "NGN", "RATE_ABOVE", 2000.0, 1950.50, "ACTIVE"),
            FXAlert("alert-002", "USD", "NGN", "RATE_BELOW", 1500.0, 1535.00, "ACTIVE"),
            FXAlert("alert-003", "EUR", "NGN", "RATE_ABOVE", 1700.0, 1680.25, "TRIGGERED")
        )
        loyalty = LoyaltySummary(
            tier = "GOLD",
            tierIcon = "🥇",
            availablePoints = 3750,
            totalPoints = 5250,
            feeDiscount = 10,
            cashbackPercent = 0.25,
            freeTransfersPerMonth = 3,
            nextTier = "PLATINUM",
            pointsToNextTier = 19750
        )
        loading = false
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("FX Alerts & Rewards") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            TabRow(selectedTabIndex = selectedTab) {
                Tab(selected = selectedTab == 0, onClick = { selectedTab = 0 }, 
                    text = { Text("🔔 Alerts") })
                Tab(selected = selectedTab == 1, onClick = { selectedTab = 1 }, 
                    text = { Text("🎁 Rewards") })
            }

            if (loading) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            } else {
                when (selectedTab) {
                    0 -> AlertsTab(alerts)
                    1 -> LoyaltyTab(loyalty)
                }
            }
        }
    }
}

@Composable
private fun AlertsTab(alerts: List<FXAlert>) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Get notified when rates hit your target", color = Color.Gray, fontSize = 14.sp)
                Button(onClick = { }) {
                    Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("New Alert")
                }
            }
        }

        items(alerts) { alert ->
            AlertCard(alert)
        }
    }
}

@Composable
private fun AlertCard(alert: FXAlert) {
    val statusColor = when (alert.status) {
        "ACTIVE" -> Color(0xFF4CAF50)
        "TRIGGERED" -> Color(0xFF2196F3)
        "EXPIRED" -> Color.Gray
        else -> Color.Gray
    }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("💱", fontSize = 24.sp)
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text("${alert.sourceCurrency}/${alert.destinationCurrency}", fontWeight = FontWeight.Bold)
                        Text(
                            if (alert.alertType == "RATE_ABOVE") "Alert when above ${String.format("%,.2f", alert.thresholdValue)}"
                            else "Alert when below ${String.format("%,.2f", alert.thresholdValue)}",
                            fontSize = 12.sp, color = Color.Gray
                        )
                    }
                }
                Surface(
                    shape = RoundedCornerShape(16.dp),
                    color = statusColor.copy(alpha = 0.1f)
                ) {
                    Text(
                        alert.status,
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
                        color = statusColor,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Medium
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Current: ", color = Color.Gray, fontSize = 14.sp)
                Text(String.format("%,.2f", alert.currentValue), fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.width(8.dp))
                if (alert.alertType == "RATE_ABOVE") {
                    if (alert.currentValue >= alert.thresholdValue) {
                        Text("(Target reached!)", color = Color(0xFF4CAF50), fontSize = 12.sp)
                    } else {
                        Text("(${String.format("%,.2f", alert.thresholdValue - alert.currentValue)} to go)", 
                            color = Color.Gray, fontSize = 12.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun LoyaltyTab(loyalty: LoyaltySummary?) {
    loyalty?.let { data ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF8E1))
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(data.tierIcon, fontSize = 32.sp)
                                Spacer(modifier = Modifier.width(12.dp))
                                Column {
                                    Text("${data.tier} Member", fontWeight = FontWeight.Bold, fontSize = 20.sp,
                                        color = Color(0xFFFF8F00))
                                }
                            }
                            Column(horizontalAlignment = Alignment.End) {
                                Text("${data.availablePoints}", fontWeight = FontWeight.Bold, fontSize = 24.sp)
                                Text("Available Points", fontSize = 12.sp, color = Color.Gray)
                            }
                        }

                        data.nextTier?.let { nextTier ->
                            Spacer(modifier = Modifier.height(16.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(data.tier, fontSize = 12.sp)
                                Text(nextTier, fontSize = 12.sp)
                            }
                            Spacer(modifier = Modifier.height(4.dp))
                            LinearProgressIndicator(
                                progress = data.totalPoints.toFloat() / (data.totalPoints + data.pointsToNextTier),
                                modifier = Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(3.dp))
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text("${data.pointsToNextTier} points to $nextTier", fontSize = 12.sp, color = Color.Gray)
                        }
                    }
                }
            }

            item {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Your Benefits", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                        Spacer(modifier = Modifier.height(12.dp))
                        BenefitRow("✓", "${data.feeDiscount}% fee discount")
                        BenefitRow("✓", "${data.cashbackPercent}% cashback")
                        BenefitRow("✓", "${data.freeTransfersPerMonth} free transfers/month")
                    }
                }
            }

            item {
                Button(
                    onClick = { },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4CAF50))
                ) {
                    Text("Redeem Points")
                }
            }
        }
    }
}

@Composable
private fun BenefitRow(icon: String, text: String) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(icon, color = Color(0xFF4CAF50))
        Spacer(modifier = Modifier.width(8.dp))
        Text(text)
    }
}

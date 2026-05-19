package com.pos54link.screens

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
import androidx.compose.ui.unit.dp

data class ExchangeRate(
    val from: String,
    val to: String,
    val rate: Double,
    val change: Double,
    val trending: TrendDirection
)

enum class TrendDirection {
    UP, DOWN
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ExchangeRatesScreen() {
    val rates = remember {
        listOf(
            ExchangeRate("USD", "NGN", 1550.00, 2.5, TrendDirection.UP),
            ExchangeRate("USD", "GHS", 12.50, -0.8, TrendDirection.DOWN),
            ExchangeRate("USD", "KES", 145.30, 1.2, TrendDirection.UP),
            ExchangeRate("EUR", "NGN", 1680.00, 3.1, TrendDirection.UP),
            ExchangeRate("GBP", "NGN", 1950.00, 1.8, TrendDirection.UP)
        )
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Exchange Rates") },
                actions = {
                    IconButton(onClick = { }) {
                        Icon(Icons.Default.Refresh, "Refresh")
                    }
                }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            item {
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.primaryContainer
                    )
                ) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(Icons.Default.Info, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text(
                            text = "Rates updated every 5 minutes",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }
            
            items(rates) { rate ->
                ExchangeRateCard(rate = rate)
            }
        }
    }
}

@Composable
fun ExchangeRateCard(rate: ExchangeRate) {
    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = "${rate.from}/${rate.to}",
                    style = MaterialTheme.typography.titleMedium
                )
                Text(
                    text = String.format("%.2f", rate.rate),
                    style = MaterialTheme.typography.headlineMedium
                )
            }
            
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Icon(
                    imageVector = if (rate.trending == TrendDirection.UP) 
                        Icons.Default.TrendingUp else Icons.Default.TrendingDown,
                    contentDescription = null,
                    tint = if (rate.trending == TrendDirection.UP) Color.Green else Color.Red
                )
                Text(
                    text = String.format("%.1f%%", kotlin.math.abs(rate.change)),
                    color = if (rate.trending == TrendDirection.UP) Color.Green else Color.Red,
                    style = MaterialTheme.typography.titleMedium
                )
            }
        }
    }
}

package com.pos54link.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

data class WalletTransaction(
    val type: TransactionType,
    val amount: Double,
    val counterparty: String,
    val date: String
)

enum class TransactionType {
    SENT, RECEIVED
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WalletScreen() {
    var showBalance by remember { mutableStateOf(true) }
    val balance = 2450.00
    
    val transactions = remember {
        listOf(
            WalletTransaction(TransactionType.RECEIVED, 500.0, "John Doe", "Nov 3, 2024"),
            WalletTransaction(TransactionType.SENT, 200.0, "Jane Smith", "Nov 2, 2024"),
            WalletTransaction(TransactionType.RECEIVED, 750.0, "Bob Johnson", "Nov 1, 2024")
        )
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("My Wallet") }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(200.dp)
                        .background(
                            brush = Brush.horizontalGradient(
                                colors = listOf(
                                    Color(0xFF9C27B0),
                                    Color(0xFF2196F3)
                                )
                            ),
                            shape = RoundedCornerShape(20.dp)
                        )
                        .padding(24.dp)
                ) {
                    Column(
                        modifier = Modifier.fillMaxSize(),
                        verticalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Column {
                                Text(
                                    text = "Total Balance",
                                    color = Color.White.copy(alpha = 0.8f),
                                    style = MaterialTheme.typography.bodyMedium
                                )
                                Spacer(Modifier.height(8.dp))
                                Text(
                                    text = if (showBalance) String.format("$%.2f", balance) else "••••••",
                                    color = Color.White,
                                    style = MaterialTheme.typography.headlineLarge
                                )
                            }
                            IconButton(onClick = { showBalance = !showBalance }) {
                                Icon(
                                    if (showBalance) Icons.Default.Visibility else Icons.Default.VisibilityOff,
                                    contentDescription = null,
                                    tint = Color.White
                                )
                            }
                        }
                        
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            Button(
                                onClick = { },
                                modifier = Modifier.weight(1f),
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = Color.White.copy(alpha = 0.2f)
                                )
                            ) {
                                Icon(Icons.Default.ArrowUpward, contentDescription = null)
                                Spacer(Modifier.width(4.dp))
                                Text("Send")
                            }
                            Button(
                                onClick = { },
                                modifier = Modifier.weight(1f),
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = Color.White.copy(alpha = 0.2f)
                                )
                            ) {
                                Icon(Icons.Default.ArrowDownward, contentDescription = null)
                                Spacer(Modifier.width(4.dp))
                                Text("Receive")
                            }
                        }
                    }
                }
            }
            
            item {
                Text(
                    text = "Recent Transactions",
                    style = MaterialTheme.typography.titleLarge
                )
            }
            
            items(transactions) { transaction ->
                TransactionItem(transaction = transaction)
            }
        }
    }
}

@Composable
fun TransactionItem(transaction: WalletTransaction) {
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
            Row(
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .size(44.dp)
                        .background(
                            color = if (transaction.type == TransactionType.RECEIVED) 
                                Color.Green.copy(alpha = 0.2f) else Color.Red.copy(alpha = 0.2f),
                            shape = CircleShape
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        if (transaction.type == TransactionType.RECEIVED) 
                            Icons.Default.ArrowDownward else Icons.Default.ArrowUpward,
                        contentDescription = null,
                        tint = if (transaction.type == TransactionType.RECEIVED) Color.Green else Color.Red
                    )
                }
                
                Column {
                    Text(
                        text = transaction.counterparty,
                        style = MaterialTheme.typography.titleMedium
                    )
                    Text(
                        text = transaction.date,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            
            Text(
                text = "${if (transaction.type == TransactionType.RECEIVED) "+" else "-"}$${String.format("%.2f", transaction.amount)}",
                style = MaterialTheme.typography.titleMedium,
                color = if (transaction.type == TransactionType.RECEIVED) Color.Green else Color.Red
            )
        }
    }
}

package com.pos54link.app.ui.screens

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pos54link.app.models.CurrencyBalance
import com.pos54link.app.models.Transaction
import com.pos54link.app.viewmodels.WalletViewModel
import com.google.accompanist.swiperefresh.SwipeRefresh
import com.google.accompanist.swiperefresh.rememberSwipeRefreshState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    onNavigateToSendMoney: () -> Unit,
    onNavigateToTransactions: () -> Unit,
    onNavigateToWallet: () -> Unit,
    onNavigateToProfile: () -> Unit,
    viewModel: WalletViewModel = hiltViewModel()
) {
    val balances by viewModel.balances.collectAsStateWithLifecycle()
    val transactions by viewModel.transactions.collectAsStateWithLifecycle()
    val isLoading by viewModel.isLoading.collectAsStateWithLifecycle()
    val totalBalanceUSD by viewModel.totalBalanceUSD.collectAsStateWithLifecycle()
    
    var balanceVisible by remember { mutableStateOf(true) }
    
    LaunchedEffect(Unit) {
        viewModel.loadBalances()
        viewModel.loadTransactions()
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Dashboard") },
                actions = {
                    IconButton(onClick = { /* Notifications */ }) {
                        Badge(
                            containerColor = MaterialTheme.colorScheme.error
                        ) {
                            Icon(Icons.Default.Notifications, contentDescription = "Notifications")
                        }
                    }
                    IconButton(onClick = onNavigateToProfile) {
                        Icon(Icons.Default.AccountCircle, contentDescription = "Profile")
                    }
                }
            )
        }
    ) { padding ->
        SwipeRefresh(
            state = rememberSwipeRefreshState(isLoading),
            onRefresh = {
                viewModel.loadBalances()
                viewModel.loadTransactions()
            },
            modifier = Modifier.padding(padding)
        ) {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(24.dp)
            ) {
                // Total Balance Card
                item {
                    TotalBalanceCard(
                        totalBalance = totalBalanceUSD,
                        balanceVisible = balanceVisible,
                        onToggleVisibility = { balanceVisible = !balanceVisible },
                        isLoading = isLoading && balances.isEmpty()
                    )
                }
                
                // Quick Actions
                item {
                    QuickActionsSection(
                        onSendMoney = onNavigateToSendMoney,
                        onAddFunds = { /* Add funds */ },
                        onScanQR = { /* Scan QR */ },
                        onExchange = { /* Exchange */ }
                    )
                }
                
                // Currency Balances
                item {
                    CurrencyBalancesSection(
                        balances = balances.take(3),
                        onSeeAll = onNavigateToWallet,
                        isLoading = isLoading
                    )
                }
                
                // Recent Transactions
                item {
                    RecentTransactionsSection(
                        transactions = transactions.take(5),
                        onSeeAll = onNavigateToTransactions,
                        onTransactionClick = { /* Navigate to detail */ },
                        isLoading = isLoading
                    )
                }
            }
        }
    }
}

@Composable
fun TotalBalanceCard(
    totalBalance: Double,
    balanceVisible: Boolean,
    onToggleVisibility: () -> Void,
    isLoading: Boolean
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(200.dp),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = Color.Transparent
        )
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    Brush.linearGradient(
                        colors = listOf(
                            MaterialTheme.colorScheme.primary,
                            MaterialTheme.colorScheme.secondary
                        )
                    )
                )
                .padding(24.dp)
        ) {
            Column(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.SpaceBetween
            ) {
                // Header
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = "Total Balance",
                            color = Color.White.copy(alpha = 0.8f),
                            fontSize = 14.sp
                        )
                        
                        Spacer(modifier = Modifier.height(8.dp))
                        
                        if (isLoading) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(24.dp),
                                color = Color.White
                            )
                        } else {
                            Text(
                                text = if (balanceVisible) "$${"%.2f".format(totalBalance)}" else "****",
                                color = Color.White,
                                fontSize = 36.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                    
                    IconButton(onClick = onToggleVisibility) {
                        Icon(
                            imageVector = if (balanceVisible) Icons.Default.Visibility else Icons.Default.VisibilityOff,
                            contentDescription = if (balanceVisible) "Hide balance" else "Show balance",
                            tint = Color.White.copy(alpha = 0.8f)
                        )
                    }
                }
                
                // Balance breakdown
                HorizontalDivider(color = Color.White.copy(alpha = 0.3f))
                
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    BalanceItem(
                        label = "Available",
                        amount = if (balanceVisible) "$${"%.2f".format(totalBalance)}" else "****"
                    )
                    
                    BalanceItem(
                        label = "Pending",
                        amount = if (balanceVisible) "$0.00" else "****"
                    )
                }
            }
        }
    }
}

@Composable
fun BalanceItem(label: String, amount: String) {
    Column {
        Text(
            text = label,
            color = Color.White.copy(alpha = 0.8f),
            fontSize = 12.sp
        )
        Text(
            text = amount,
            color = Color.White,
            fontSize = 14.sp,
            fontWeight = FontWeight.SemiBold
        )
    }
}

@Composable
fun QuickActionsSection(
    onSendMoney: () -> Unit,
    onAddFunds: () -> Unit,
    onScanQR: () -> Unit,
    onExchange: () -> Unit
) {
    Column {
        Text(
            text = "Quick Actions",
            fontSize = 18.sp,
            fontWeight = FontWeight.Bold
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            QuickActionButton(
                icon = Icons.Default.Send,
                label = "Send",
                color = MaterialTheme.colorScheme.primary,
                onClick = onSendMoney,
                modifier = Modifier.weight(1f)
            )
            
            Spacer(modifier = Modifier.width(12.dp))
            
            QuickActionButton(
                icon = Icons.Default.Add,
                label = "Add Funds",
                color = Color(0xFF4CAF50),
                onClick = onAddFunds,
                modifier = Modifier.weight(1f)
            )
            
            Spacer(modifier = Modifier.width(12.dp))
            
            QuickActionButton(
                icon = Icons.Default.QrCodeScanner,
                label = "Scan QR",
                color = Color(0xFFFF9800),
                onClick = onScanQR,
                modifier = Modifier.weight(1f)
            )
            
            Spacer(modifier = Modifier.width(12.dp))
            
            QuickActionButton(
                icon = Icons.Default.SwapHoriz,
                label = "Exchange",
                color = Color(0xFF9C27B0),
                onClick = onExchange,
                modifier = Modifier.weight(1f)
            )
        }
    }
}

@Composable
fun QuickActionButton(
    icon: ImageVector,
    label: String,
    color: Color,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier.clickable(onClick = onClick),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Box(
            modifier = Modifier
                .size(60.dp)
                .clip(CircleShape)
                .background(color.copy(alpha = 0.1f)),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = icon,
                contentDescription = label,
                tint = color,
                modifier = Modifier.size(28.dp)
            )
        }
        
        Spacer(modifier = Modifier.height(8.dp))
        
        Text(
            text = label,
            fontSize = 12.sp,
            color = MaterialTheme.colorScheme.onSurface
        )
    }
}

@Composable
fun CurrencyBalancesSection(
    balances: List<CurrencyBalance>,
    onSeeAll: () -> Unit,
    isLoading: Boolean
) {
    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "My Currencies",
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold
            )
            
            TextButton(onClick = onSeeAll) {
                Text("See All")
            }
        }
        
        Spacer(modifier = Modifier.height(16.dp))
        
        if (isLoading && balances.isEmpty()) {
            repeat(3) {
                CurrencyBalanceCardSkeleton()
                Spacer(modifier = Modifier.height(12.dp))
            }
        } else if (balances.isEmpty()) {
            EmptyStateCard(
                icon = Icons.Default.AccountBalance,
                title = "No Balances",
                message = "Add funds to get started"
            )
        } else {
            balances.forEach { balance ->
                CurrencyBalanceCard(balance)
                Spacer(modifier = Modifier.height(12.dp))
            }
        }
    }
}

@Composable
fun CurrencyBalanceCard(balance: CurrencyBalance) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Currency icon
                Box(
                    modifier = Modifier
                        .size(50.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.1f)),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = balance.currencySymbol,
                        fontSize = 20.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
                
                // Currency info
                Column {
                    Text(
                        text = balance.currencyName,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Medium
                    )
                    Text(
                        text = balance.currency,
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            
            // Amount
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    text = balance.formattedAmount,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.SemiBold
                )
                Text(
                    text = "≈ $${"%.2f".format(balance.usdEquivalent)}",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
fun CurrencyBalanceCardSkeleton() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Box(
                    modifier = Modifier
                        .size(50.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.1f))
                )
                
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Box(
                        modifier = Modifier
                            .width(100.dp)
                            .height(16.dp)
                            .background(MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.1f))
                    )
                    Box(
                        modifier = Modifier
                            .width(60.dp)
                            .height(12.dp)
                            .background(MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.1f))
                    )
                }
            }
        }
    }
}

@Composable
fun RecentTransactionsSection(
    transactions: List<Transaction>,
    onSeeAll: () -> Unit,
    onTransactionClick: (Transaction) -> Unit,
    isLoading: Boolean
) {
    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Recent Transactions",
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold
            )
            
            TextButton(onClick = onSeeAll) {
                Text("See All")
            }
        }
        
        Spacer(modifier = Modifier.height(16.dp))
        
        if (isLoading && transactions.isEmpty()) {
            repeat(5) {
                TransactionCardSkeleton()
                Spacer(modifier = Modifier.height(12.dp))
            }
        } else if (transactions.isEmpty()) {
            EmptyStateCard(
                icon = Icons.Default.SwapHoriz,
                title = "No Transactions",
                message = "Your transaction history will appear here"
            )
        } else {
            transactions.forEach { transaction ->
                TransactionCard(
                    transaction = transaction,
                    onClick = { onTransactionClick(transaction) }
                )
                Spacer(modifier = Modifier.height(12.dp))
            }
        }
    }
}

@Composable
fun TransactionCard(
    transaction: Transaction,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Transaction icon
                val (icon, color) = when (transaction.type.lowercase()) {
                    "sent" -> Icons.Default.ArrowUpward to Color.Red
                    "received" -> Icons.Default.ArrowDownward to Color.Green
                    else -> Icons.Default.SwapHoriz to Color.Gray
                }
                
                Box(
                    modifier = Modifier
                        .size(50.dp)
                        .clip(CircleShape)
                        .background(color.copy(alpha = 0.1f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = icon,
                        contentDescription = null,
                        tint = color
                    )
                }
                
                // Transaction info
                Column {
                    Text(
                        text = transaction.recipient ?: transaction.sender ?: "Transaction",
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Medium,
                        maxLines = 1
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(
                            text = "Today", // Simplified
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = "•",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = transaction.status.capitalize(),
                            fontSize = 12.sp,
                            color = when (transaction.status.lowercase()) {
                                "completed" -> Color.Green
                                "pending" -> Color.Orange
                                "failed" -> Color.Red
                                else -> Color.Gray
                            }
                        )
                    }
                }
            }
            
            // Amount
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    text = "${if (transaction.type.lowercase() == "sent") "-" else "+"}${transaction.currency} ${"%.2f".format(transaction.amount)}",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = if (transaction.type.lowercase() == "sent") Color.Red else Color.Green
                )
                transaction.fee?.let { fee ->
                    if (fee > 0) {
                        Text(
                            text = "Fee: ${transaction.currency} ${"%.2f".format(fee)}",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun TransactionCardSkeleton() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Box(
                    modifier = Modifier
                        .size(50.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.1f))
                )
                
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Box(
                        modifier = Modifier
                            .width(120.dp)
                            .height(16.dp)
                            .background(MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.1f))
                    )
                    Box(
                        modifier = Modifier
                            .width(80.dp)
                            .height(12.dp)
                            .background(MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.1f))
                    )
                }
            }
        }
    }
}

@Composable
fun EmptyStateCard(
    icon: ImageVector,
    title: String,
    message: String
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(40.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                modifier = Modifier.size(60.dp),
                tint = MaterialTheme.colorScheme.onSurfaceVariant
            )
            
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text(
                    text = title,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold
                )
                
                Text(
                    text = message,
                    fontSize = 14.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center
                )
            }
        }
    }
}

fun String.capitalize(): String {
    return this.replaceFirstChar { if (it.isLowerCase()) it.titlecase() else it.toString() }
}

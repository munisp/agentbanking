package com.pos54link.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

// Data classes
data class StablecoinBalance(
    val chain: String,
    val stablecoin: String,
    val balance: String,
    val pendingBalance: String = "0"
)

data class StablecoinTransaction(
    val id: String,
    val type: String,
    val chain: String,
    val stablecoin: String,
    val amount: String,
    val status: String,
    val createdAt: String,
    val txHash: String? = null
)

data class Chain(
    val id: String,
    val name: String,
    val symbol: String,
    val fee: String,
    val color: Color
)

data class Stablecoin(
    val id: String,
    val name: String,
    val symbol: String,
    val color: Color
)

// Chain and Stablecoin configurations
val chains = listOf(
    Chain("tron", "Tron", "TRX", "$1", Color(0xFFEF4444)),
    Chain("ethereum", "Ethereum", "ETH", "$5", Color(0xFF3B82F6)),
    Chain("solana", "Solana", "SOL", "$0.01", Color(0xFF8B5CF6)),
    Chain("polygon", "Polygon", "MATIC", "$0.10", Color(0xFF7C3AED)),
    Chain("bsc", "BNB Chain", "BNB", "$0.30", Color(0xFFEAB308))
)

val stablecoins = listOf(
    Stablecoin("usdt", "Tether", "USDT", Color(0xFF22C55E)),
    Stablecoin("usdc", "USD Coin", "USDC", Color(0xFF60A5FA)),
    Stablecoin("pyusd", "PayPal USD", "PYUSD", Color(0xFF2563EB)),
    Stablecoin("dai", "Dai", "DAI", Color(0xFFFACC15))
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StablecoinScreen(
    onNavigateBack: () -> Unit = {}
) {
    var selectedTab by remember { mutableStateOf(0) }
    val tabs = listOf("Wallet", "Send", "Receive", "Convert", "Buy/Sell")
    
    // Sample data
    val balances = remember {
        listOf(
            StablecoinBalance("tron", "usdt", "1,250.00", "50.00"),
            StablecoinBalance("ethereum", "usdc", "500.00"),
            StablecoinBalance("solana", "usdt", "200.00")
        )
    }
    
    val transactions = remember {
        listOf(
            StablecoinTransaction("1", "deposit", "tron", "usdt", "500.00", "completed", "2024-01-15"),
            StablecoinTransaction("2", "withdrawal", "ethereum", "usdc", "100.00", "confirming", "2024-01-14"),
            StablecoinTransaction("3", "conversion", "solana", "usdt", "200.00", "completed", "2024-01-13")
        )
    }
    
    val totalBalance = "1,950.00"
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Stablecoin Wallet") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color.Transparent
                )
            )
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            // Header with gradient
            item {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(
                            brush = Brush.horizontalGradient(
                                colors = listOf(Color(0xFF2563EB), Color(0xFF7C3AED))
                            )
                        )
                        .padding(24.dp)
                ) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            text = "Total Balance",
                            color = Color.White.copy(alpha = 0.8f),
                            fontSize = 14.sp
                        )
                        Text(
                            text = "$$totalBalance",
                            color = Color.White,
                            fontSize = 36.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.padding(top = 8.dp)
                        ) {
                            Icon(
                                Icons.Default.TrendingUp,
                                contentDescription = null,
                                tint = Color.White.copy(alpha = 0.8f),
                                modifier = Modifier.size(16.dp)
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                text = "ML-optimized rates active",
                                color = Color.White.copy(alpha = 0.8f),
                                fontSize = 12.sp
                            )
                        }
                        
                        // Quick Actions
                        Row(
                            horizontalArrangement = Arrangement.SpaceEvenly,
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(top = 24.dp)
                        ) {
                            QuickActionButton(
                                icon = Icons.Default.ArrowUpward,
                                label = "Send",
                                onClick = { selectedTab = 1 }
                            )
                            QuickActionButton(
                                icon = Icons.Default.ArrowDownward,
                                label = "Receive",
                                onClick = { selectedTab = 2 }
                            )
                            QuickActionButton(
                                icon = Icons.Default.SwapHoriz,
                                label = "Convert",
                                onClick = { selectedTab = 3 }
                            )
                            QuickActionButton(
                                icon = Icons.Default.Language,
                                label = "Buy/Sell",
                                onClick = { selectedTab = 4 }
                            )
                        }
                    }
                }
            }
            
            // Tabs
            item {
                ScrollableTabRow(
                    selectedTabIndex = selectedTab,
                    containerColor = MaterialTheme.colorScheme.surface,
                    edgePadding = 16.dp
                ) {
                    tabs.forEachIndexed { index, title ->
                        Tab(
                            selected = selectedTab == index,
                            onClick = { selectedTab = index },
                            text = { Text(title) }
                        )
                    }
                }
            }
            
            // Content based on selected tab
            when (selectedTab) {
                0 -> {
                    // Wallet Tab
                    item {
                        BalancesSection(balances)
                    }
                    item {
                        TransactionsSection(transactions)
                    }
                    item {
                        FeaturesSection()
                    }
                }
                1 -> {
                    // Send Tab
                    item {
                        SendSection()
                    }
                }
                2 -> {
                    // Receive Tab
                    item {
                        ReceiveSection()
                    }
                }
                3 -> {
                    // Convert Tab
                    item {
                        ConvertSection()
                    }
                }
                4 -> {
                    // Buy/Sell Tab
                    item {
                        RampSection()
                    }
                }
            }
            
            // Bottom spacing
            item {
                Spacer(modifier = Modifier.height(100.dp))
            }
        }
    }
}

@Composable
private fun QuickActionButton(
    icon: ImageVector,
    label: String,
    onClick: () -> Unit
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier
            .clip(RoundedCornerShape(12.dp))
            .clickable(onClick = onClick)
            .background(Color.White.copy(alpha = 0.2f))
            .padding(16.dp)
    ) {
        Icon(
            icon,
            contentDescription = label,
            tint = Color.White,
            modifier = Modifier.size(24.dp)
        )
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = label,
            color = Color.White,
            fontSize = 12.sp
        )
    }
}

@Composable
private fun BalancesSection(balances: List<StablecoinBalance>) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp),
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "Your Balances",
                fontWeight = FontWeight.SemiBold,
                fontSize = 18.sp
            )
            Spacer(modifier = Modifier.height(16.dp))
            
            balances.forEach { balance ->
                BalanceItem(balance)
                if (balance != balances.last()) {
                    Divider(modifier = Modifier.padding(vertical = 8.dp))
                }
            }
        }
    }
}

@Composable
private fun BalanceItem(balance: StablecoinBalance) {
    val stablecoin = stablecoins.find { it.id == balance.stablecoin }
    val chain = chains.find { it.id == balance.chain }
    
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .clip(CircleShape)
                    .background(stablecoin?.color ?: Color.Gray),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = stablecoin?.symbol?.take(1) ?: "?",
                    color = Color.White,
                    fontWeight = FontWeight.Bold
                )
            }
            Spacer(modifier = Modifier.width(12.dp))
            Column {
                Text(
                    text = stablecoin?.symbol ?: balance.stablecoin.uppercase(),
                    fontWeight = FontWeight.Medium
                )
                Text(
                    text = chain?.name ?: balance.chain,
                    fontSize = 12.sp,
                    color = Color.Gray
                )
            }
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(
                text = "$${balance.balance}",
                fontWeight = FontWeight.SemiBold
            )
            if (balance.pendingBalance != "0") {
                Text(
                    text = "+$${balance.pendingBalance} pending",
                    fontSize = 12.sp,
                    color = Color(0xFFEAB308)
                )
            }
        }
    }
}

@Composable
private fun TransactionsSection(transactions: List<StablecoinTransaction>) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp),
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "Recent Transactions",
                fontWeight = FontWeight.SemiBold,
                fontSize = 18.sp
            )
            Spacer(modifier = Modifier.height(16.dp))
            
            transactions.forEach { tx ->
                TransactionItem(tx)
                if (tx != transactions.last()) {
                    Divider(modifier = Modifier.padding(vertical = 8.dp))
                }
            }
        }
    }
}

@Composable
private fun TransactionItem(tx: StablecoinTransaction) {
    val isDeposit = tx.type == "deposit"
    
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .clip(CircleShape)
                    .background(if (isDeposit) Color(0xFFDCFCE7) else Color(0xFFFEE2E2)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    if (isDeposit) Icons.Default.ArrowDownward else Icons.Default.ArrowUpward,
                    contentDescription = null,
                    tint = if (isDeposit) Color(0xFF22C55E) else Color(0xFFEF4444),
                    modifier = Modifier.size(20.dp)
                )
            }
            Spacer(modifier = Modifier.width(12.dp))
            Column {
                Text(
                    text = tx.type.replaceFirstChar { it.uppercase() },
                    fontWeight = FontWeight.Medium
                )
                Text(
                    text = tx.createdAt,
                    fontSize = 12.sp,
                    color = Color.Gray
                )
            }
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(
                text = "${if (isDeposit) "+" else "-"}$${tx.amount}",
                fontWeight = FontWeight.SemiBold,
                color = if (isDeposit) Color(0xFF22C55E) else Color(0xFFEF4444)
            )
            StatusChip(tx.status)
        }
    }
}

@Composable
private fun StatusChip(status: String) {
    val (backgroundColor, textColor) = when (status) {
        "completed" -> Color(0xFFDCFCE7) to Color(0xFF166534)
        "confirming" -> Color(0xFFFEF9C3) to Color(0xFF854D0E)
        "pending" -> Color(0xFFDBEAFE) to Color(0xFF1E40AF)
        "failed" -> Color(0xFFFEE2E2) to Color(0xFF991B1B)
        else -> Color(0xFFF3F4F6) to Color(0xFF4B5563)
    }
    
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = backgroundColor
    ) {
        Text(
            text = status,
            color = textColor,
            fontSize = 10.sp,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp)
        )
    }
}

@Composable
private fun FeaturesSection() {
    Column(modifier = Modifier.padding(16.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            FeatureCard(
                icon = Icons.Default.Bolt,
                title = "Instant Transfers",
                subtitle = "Send in seconds",
                color = Color(0xFFEAB308),
                modifier = Modifier.weight(1f)
            )
            FeatureCard(
                icon = Icons.Default.Shield,
                title = "Secure",
                subtitle = "Multi-chain security",
                color = Color(0xFF22C55E),
                modifier = Modifier.weight(1f)
            )
        }
        Spacer(modifier = Modifier.height(12.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            FeatureCard(
                icon = Icons.Default.TrendingUp,
                title = "ML Rates",
                subtitle = "AI-optimized timing",
                color = Color(0xFF3B82F6),
                modifier = Modifier.weight(1f)
            )
            FeatureCard(
                icon = Icons.Default.WifiOff,
                title = "Offline Ready",
                subtitle = "Queue when offline",
                color = Color(0xFF8B5CF6),
                modifier = Modifier.weight(1f)
            )
        }
    }
}

@Composable
private fun FeatureCard(
    icon: ImageVector,
    title: String,
    subtitle: String,
    color: Color,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Icon(
                icon,
                contentDescription = null,
                tint = color,
                modifier = Modifier.size(32.dp)
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = title,
                fontWeight = FontWeight.Medium
            )
            Text(
                text = subtitle,
                fontSize = 12.sp,
                color = Color.Gray
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SendSection() {
    var selectedChain by remember { mutableStateOf(chains[0]) }
    var selectedStablecoin by remember { mutableStateOf(stablecoins[0]) }
    var amount by remember { mutableStateOf("") }
    var address by remember { mutableStateOf("") }
    
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp),
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "Send Stablecoin",
                fontWeight = FontWeight.SemiBold,
                fontSize = 18.sp
            )
            Spacer(modifier = Modifier.height(16.dp))
            
            // Network Selection
            Text(text = "Network", fontSize = 14.sp, color = Color.Gray)
            Spacer(modifier = Modifier.height(8.dp))
            ChainSelector(
                chains = chains,
                selectedChain = selectedChain,
                onChainSelected = { selectedChain = it }
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            
            // Stablecoin Selection
            Text(text = "Stablecoin", fontSize = 14.sp, color = Color.Gray)
            Spacer(modifier = Modifier.height(8.dp))
            StablecoinSelector(
                stablecoins = stablecoins,
                selectedStablecoin = selectedStablecoin,
                onStablecoinSelected = { selectedStablecoin = it }
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            
            // Amount
            OutlinedTextField(
                value = amount,
                onValueChange = { amount = it },
                label = { Text("Amount") },
                prefix = { Text("$") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            
            // Address
            OutlinedTextField(
                value = address,
                onValueChange = { address = it },
                label = { Text("Recipient Address") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            // Fee info
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(text = "Network Fee", fontSize = 14.sp, color = Color.Gray)
                Text(text = selectedChain.fee, fontSize = 14.sp)
            }
            
            Spacer(modifier = Modifier.height(24.dp))
            
            Button(
                onClick = { /* Send transaction */ },
                modifier = Modifier.fillMaxWidth(),
                enabled = amount.isNotEmpty() && address.isNotEmpty()
            ) {
                Text("Send Now")
            }
        }
    }
}

@Composable
private fun ChainSelector(
    chains: List<Chain>,
    selectedChain: Chain,
    onChainSelected: (Chain) -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        chains.take(3).forEach { chain ->
            FilterChip(
                selected = chain == selectedChain,
                onClick = { onChainSelected(chain) },
                label = { Text(chain.name, fontSize = 12.sp) },
                modifier = Modifier.weight(1f)
            )
        }
    }
}

@Composable
private fun StablecoinSelector(
    stablecoins: List<Stablecoin>,
    selectedStablecoin: Stablecoin,
    onStablecoinSelected: (Stablecoin) -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        stablecoins.take(3).forEach { coin ->
            FilterChip(
                selected = coin == selectedStablecoin,
                onClick = { onStablecoinSelected(coin) },
                label = { Text(coin.symbol, fontSize = 12.sp) },
                modifier = Modifier.weight(1f)
            )
        }
    }
}

@Composable
private fun ReceiveSection() {
    val sampleAddresses = listOf(
        "tron" to "TN3W4H6rK2ce4vX9YnFQHwKENnHjoxb3m9",
        "ethereum" to "0x742d35Cc6634C0532925a3b844Bc9e7595f5bE21",
        "solana" to "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d"
    )
    
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp),
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "Receive Stablecoin",
                fontWeight = FontWeight.SemiBold,
                fontSize = 18.sp
            )
            Spacer(modifier = Modifier.height(16.dp))
            
            sampleAddresses.forEach { (chainId, address) ->
                val chain = chains.find { it.id == chainId }
                AddressCard(chain = chain, address = address)
                Spacer(modifier = Modifier.height(12.dp))
            }
        }
    }
    
    // Tips card
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFFEFF6FF))
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "Tips for Receiving",
                fontWeight = FontWeight.Medium,
                color = Color(0xFF1E40AF)
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "• Always verify the network matches the sender's\n• Tron (TRC20) has the lowest fees\n• Deposits are confirmed automatically",
                fontSize = 14.sp,
                color = Color(0xFF1E40AF)
            )
        }
    }
}

@Composable
private fun AddressCard(chain: Chain?, address: String) {
    val context = LocalContext.current
    
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = Color(0xFFF9FAFB)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = chain?.name ?: "Unknown",
                    fontWeight = FontWeight.Medium
                )
                IconButton(
                    onClick = {
                        // Copy to clipboard
                    },
                    modifier = Modifier.size(32.dp)
                ) {
                    Icon(
                        Icons.Default.ContentCopy,
                        contentDescription = "Copy",
                        modifier = Modifier.size(18.dp)
                    )
                }
            }
            Text(
                text = address,
                fontSize = 12.sp,
                color = Color.Gray,
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color.White, RoundedCornerShape(8.dp))
                    .padding(8.dp)
            )
            Text(
                text = "Supports: USDT, USDC",
                fontSize = 12.sp,
                color = Color.Gray,
                modifier = Modifier.padding(top = 8.dp)
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ConvertSection() {
    var fromChain by remember { mutableStateOf(chains[0]) }
    var fromStablecoin by remember { mutableStateOf(stablecoins[0]) }
    var toChain by remember { mutableStateOf(chains[1]) }
    var toStablecoin by remember { mutableStateOf(stablecoins[1]) }
    var amount by remember { mutableStateOf("") }
    var showQuote by remember { mutableStateOf(false) }
    
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp),
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "Convert Stablecoin",
                fontWeight = FontWeight.SemiBold,
                fontSize = 18.sp
            )
            Spacer(modifier = Modifier.height(16.dp))
            
            // From
            Text(text = "From", fontSize = 14.sp, color = Color.Gray)
            Spacer(modifier = Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StablecoinSelector(
                    stablecoins = stablecoins,
                    selectedStablecoin = fromStablecoin,
                    onStablecoinSelected = { fromStablecoin = it }
                )
            }
            
            Spacer(modifier = Modifier.height(16.dp))
            
            // Amount
            OutlinedTextField(
                value = amount,
                onValueChange = { 
                    amount = it
                    showQuote = false
                },
                label = { Text("Amount") },
                prefix = { Text("$") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            
            // Swap icon
            Box(
                modifier = Modifier.fillMaxWidth(),
                contentAlignment = Alignment.Center
            ) {
                IconButton(
                    onClick = {
                        val tempChain = fromChain
                        val tempCoin = fromStablecoin
                        fromChain = toChain
                        fromStablecoin = toStablecoin
                        toChain = tempChain
                        toStablecoin = tempCoin
                    }
                ) {
                    Icon(Icons.Default.SwapVert, contentDescription = "Swap")
                }
            }
            
            // To
            Text(text = "To", fontSize = 14.sp, color = Color.Gray)
            Spacer(modifier = Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StablecoinSelector(
                    stablecoins = stablecoins,
                    selectedStablecoin = toStablecoin,
                    onStablecoinSelected = { toStablecoin = it }
                )
            }
            
            Spacer(modifier = Modifier.height(16.dp))
            
            // Get Quote button
            if (!showQuote) {
                OutlinedButton(
                    onClick = { showQuote = true },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = amount.isNotEmpty()
                ) {
                    Text("Get Quote")
                }
            }
            
            // Quote display
            if (showQuote && amount.isNotEmpty()) {
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = Color(0xFFDCFCE7),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("You'll receive", color = Color.Gray)
                            Text(
                                "$$amount",
                                fontWeight = FontWeight.Bold,
                                fontSize = 18.sp
                            )
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("Rate", fontSize = 14.sp, color = Color.Gray)
                            Text("1 ${fromStablecoin.symbol} = 0.9998 ${toStablecoin.symbol}", fontSize = 14.sp)
                        }
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("Fee", fontSize = 14.sp, color = Color.Gray)
                            Text("$0.50", fontSize = 14.sp)
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                Icons.Default.TrendingUp,
                                contentDescription = null,
                                tint = Color(0xFF166534),
                                modifier = Modifier.size(14.dp)
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                "ML-optimized rate applied",
                                fontSize = 12.sp,
                                color = Color(0xFF166534)
                            )
                        }
                    }
                }
                
                Spacer(modifier = Modifier.height(16.dp))
            }
            
            Button(
                onClick = { /* Convert */ },
                modifier = Modifier.fillMaxWidth(),
                enabled = showQuote && amount.isNotEmpty()
            ) {
                Text("Convert Now")
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RampSection() {
    var isOnRamp by remember { mutableStateOf(true) }
    var selectedFiat by remember { mutableStateOf("NGN") }
    var amount by remember { mutableStateOf("") }
    var selectedStablecoin by remember { mutableStateOf(stablecoins[0]) }
    var selectedChain by remember { mutableStateOf(chains[0]) }
    
    val fiats = listOf(
        "NGN" to "Nigerian Naira",
        "USD" to "US Dollar",
        "EUR" to "Euro",
        "GBP" to "British Pound"
    )
    
    // Toggle
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp),
        shape = RoundedCornerShape(16.dp)
    ) {
        Column {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(8.dp)
            ) {
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = if (isOnRamp) MaterialTheme.colorScheme.primary else Color.Transparent,
                    modifier = Modifier
                        .weight(1f)
                        .clickable { isOnRamp = true }
                ) {
                    Text(
                        text = "Buy Stablecoin",
                        textAlign = TextAlign.Center,
                        color = if (isOnRamp) Color.White else Color.Gray,
                        fontWeight = FontWeight.Medium,
                        modifier = Modifier.padding(12.dp)
                    )
                }
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = if (!isOnRamp) MaterialTheme.colorScheme.primary else Color.Transparent,
                    modifier = Modifier
                        .weight(1f)
                        .clickable { isOnRamp = false }
                ) {
                    Text(
                        text = "Sell Stablecoin",
                        textAlign = TextAlign.Center,
                        color = if (!isOnRamp) Color.White else Color.Gray,
                        fontWeight = FontWeight.Medium,
                        modifier = Modifier.padding(12.dp)
                    )
                }
            }
            
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    text = if (isOnRamp) "Buy Stablecoin with Fiat" else "Sell Stablecoin for Fiat",
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 18.sp
                )
                Spacer(modifier = Modifier.height(16.dp))
                
                // Fiat selection
                Text(
                    text = if (isOnRamp) "Pay with" else "Receive in",
                    fontSize = 14.sp,
                    color = Color.Gray
                )
                Spacer(modifier = Modifier.height(8.dp))
                
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    fiats.take(3).forEach { (code, _) ->
                        FilterChip(
                            selected = code == selectedFiat,
                            onClick = { selectedFiat = code },
                            label = { Text(code, fontSize = 12.sp) },
                            modifier = Modifier.weight(1f)
                        )
                    }
                }
                
                Spacer(modifier = Modifier.height(16.dp))
                
                // Amount
                val currencySymbol = when (selectedFiat) {
                    "NGN" -> "₦"
                    "EUR" -> "€"
                    "GBP" -> "£"
                    else -> "$"
                }
                OutlinedTextField(
                    value = amount,
                    onValueChange = { amount = it },
                    label = { Text("Amount") },
                    prefix = { Text(currencySymbol) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
                
                Spacer(modifier = Modifier.height(16.dp))
                
                // Stablecoin selection
                Text(
                    text = if (isOnRamp) "Receive" else "Sell",
                    fontSize = 14.sp,
                    color = Color.Gray
                )
                Spacer(modifier = Modifier.height(8.dp))
                StablecoinSelector(
                    stablecoins = stablecoins,
                    selectedStablecoin = selectedStablecoin,
                    onStablecoinSelected = { selectedStablecoin = it }
                )
                
                Spacer(modifier = Modifier.height(16.dp))
                
                // Rate info
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = Color(0xFFF9FAFB)
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("Current Rate", fontSize = 14.sp, color = Color.Gray)
                            Text(
                                when (selectedFiat) {
                                    "NGN" -> "1 USDT = ₦1,650"
                                    "EUR" -> "1 USDT = €0.92"
                                    "GBP" -> "1 USDT = £0.79"
                                    else -> "1 USDT = $1.00"
                                },
                                fontSize = 14.sp
                            )
                        }
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("Fee", fontSize = 14.sp, color = Color.Gray)
                            Text("1%", fontSize = 14.sp)
                        }
                    }
                }
                
                Spacer(modifier = Modifier.height(24.dp))
                
                Button(
                    onClick = { /* Process ramp */ },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = amount.isNotEmpty()
                ) {
                    Text(if (isOnRamp) "Buy Now" else "Sell Now")
                }
            }
        }
    }
    
    // Payment methods
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "Payment Methods",
                fontWeight = FontWeight.Medium
            )
            Spacer(modifier = Modifier.height(12.dp))
            
            PaymentMethodItem(
                icon = Icons.Default.AccountBalance,
                title = "Bank Transfer",
                subtitle = "Instant for NGN, 1-2 days for others"
            )
            PaymentMethodItem(
                icon = Icons.Default.CreditCard,
                title = "Debit/Credit Card",
                subtitle = "Instant, 2.5% fee"
            )
            PaymentMethodItem(
                icon = Icons.Default.PhoneAndroid,
                title = "Mobile Money",
                subtitle = "M-Pesa, MTN MoMo, Airtel Money"
            )
        }
    }
}

@Composable
private fun PaymentMethodItem(
    icon: ImageVector,
    title: String,
    subtitle: String
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(40.dp)
                .clip(CircleShape)
                .background(Color(0xFFF3F4F6)),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                icon,
                contentDescription = null,
                tint = Color(0xFF4B5563),
                modifier = Modifier.size(20.dp)
            )
        }
        Spacer(modifier = Modifier.width(12.dp))
        Column {
            Text(text = title, fontWeight = FontWeight.Medium)
            Text(text = subtitle, fontSize = 12.sp, color = Color.Gray)
        }
    }
}

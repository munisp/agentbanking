package com.pos54link.app.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.text.NumberFormat
import java.util.*

// Data classes for FX transparency
data class ExchangeRate(
    val from: String,
    val to: String,
    val rate: Double,
    val lastUpdated: String,
    val provider: String
)

data class RateLock(
    val id: String,
    val rate: Double,
    val expiresAt: Long
)

data class FeeBreakdown(
    val transferFee: Double,
    val networkFee: Double,
    val totalFees: Double,
    val feePercentage: Double
)

data class DeliveryEstimate(
    val method: String,
    val estimatedTime: String,
    val available: Boolean
)

// Currency data
val CURRENCY_FLAGS = mapOf(
    "GBP" to "\uD83C\uDDEC\uD83C\uDDE7", "USD" to "\uD83C\uDDFA\uD83C\uDDF8",
    "EUR" to "\uD83C\uDDEA\uD83C\uDDFA", "NGN" to "\uD83C\uDDF3\uD83C\uDDEC",
    "GHS" to "\uD83C\uDDEC\uD83C\uDDED", "KES" to "\uD83C\uDDF0\uD83C\uDDEA"
)

val CURRENCY_SYMBOLS = mapOf(
    "GBP" to "£", "USD" to "$", "EUR" to "€", "NGN" to "₦", "GHS" to "₵", "KES" to "KSh"
)

val SOURCE_CURRENCIES = listOf("GBP", "USD", "EUR", "NGN")
val DESTINATION_CURRENCIES = listOf("NGN", "GHS", "KES", "USD", "GBP")

val MOCK_RATES = mapOf(
    "GBP" to mapOf("NGN" to 1950.50, "GHS" to 15.20, "KES" to 165.30, "USD" to 1.27),
    "USD" to mapOf("NGN" to 1535.00, "GHS" to 11.95, "KES" to 130.20, "GBP" to 0.79),
    "EUR" to mapOf("NGN" to 1680.25, "GHS" to 13.10, "KES" to 142.50, "GBP" to 0.86),
    "NGN" to mapOf("GHS" to 0.0078, "KES" to 0.085, "USD" to 0.00065, "GBP" to 0.00051)
)

val DELIVERY_METHODS = mapOf(
    "NGN" to listOf(
        DeliveryEstimate("bank_transfer", "Instant - 30 mins", true),
        DeliveryEstimate("mobile_money", "Instant", true),
        DeliveryEstimate("cash_pickup", "1 - 4 hours", true)
    ),
    "default" to listOf(DeliveryEstimate("bank_transfer", "1 - 2 business days", true))
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SendMoneyScreen(
    onNavigateBack: () -> Unit,
    isOnline: Boolean = true
) {
    val scope = rememberCoroutineScope()
    val numberFormat = NumberFormat.getNumberInstance(Locale.US)
    
    // Form state
    var currentStep by remember { mutableIntStateOf(1) }
    var recipient by remember { mutableStateOf("") }
    var recipientName by remember { mutableStateOf("") }
    var recipientType by remember { mutableStateOf("phone") }
    var amount by remember { mutableStateOf("") }
    var sourceCurrency by remember { mutableStateOf("GBP") }
    var destinationCurrency by remember { mutableStateOf("NGN") }
    var note by remember { mutableStateOf("") }
    var deliveryMethod by remember { mutableStateOf("bank_transfer") }
    var selectedBank by remember { mutableStateOf("") }
    
    // FX state
    var exchangeRate by remember { mutableStateOf<ExchangeRate?>(null) }
    var rateLock by remember { mutableStateOf<RateLock?>(null) }
    var isLoadingRate by remember { mutableStateOf(false) }
    var rateRefreshCountdown by remember { mutableIntStateOf(30) }
    var showRateHistory by remember { mutableStateOf(false) }
    
    // UI state
    var isSubmitting by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var successMessage by remember { mutableStateOf<String?>(null) }
    var pendingCount by remember { mutableIntStateOf(0) }
    
    // Calculate received amount
    val receivedAmount = remember(amount, exchangeRate, rateLock) {
        val amountValue = amount.toDoubleOrNull() ?: 0.0
        val rate = rateLock?.rate ?: exchangeRate?.rate ?: 0.0
        amountValue * rate
    }
    
    // Calculate fee breakdown
    val feeBreakdown = remember(amount, sourceCurrency, destinationCurrency, deliveryMethod) {
        val amountValue = amount.toDoubleOrNull() ?: 0.0
        if (amountValue <= 0) null
        else {
            val corridor = "$sourceCurrency-$destinationCurrency"
            val (fixed, percentage) = when (corridor) {
                "GBP-NGN" -> Pair(0.99, 0.5)
                "USD-NGN" -> Pair(2.99, 0.5)
                "EUR-NGN" -> Pair(1.99, 0.5)
                else -> Pair(50.0, 1.5)
            }
            val transferFee = fixed + (amountValue * percentage / 100)
            val networkFee = if (deliveryMethod == "cash_pickup") 2.00 else 0.0
            val totalFees = transferFee + networkFee
            FeeBreakdown(transferFee, networkFee, totalFees, (totalFees / amountValue) * 100)
        }
    }
    
    // Delivery estimates
    val deliveryEstimates = remember(destinationCurrency) {
        DELIVERY_METHODS[destinationCurrency] ?: DELIVERY_METHODS["default"]!!
    }
    
    // Fetch exchange rate
    fun fetchExchangeRate() {
        if (rateLock != null) return
        isLoadingRate = true
        scope.launch {
            delay(500)
            val rate = MOCK_RATES[sourceCurrency]?.get(destinationCurrency) ?: 1.0
            exchangeRate = ExchangeRate(sourceCurrency, destinationCurrency, rate, "Just now", "Market Rate")
            isLoadingRate = false
            rateRefreshCountdown = 30
        }
    }
    
    fun lockRate() {
        exchangeRate?.let { rate ->
            rateLock = RateLock("lock_${System.currentTimeMillis()}", rate.rate, System.currentTimeMillis() + 600000)
        }
    }
    
    fun unlockRate() {
        rateLock = null
        fetchExchangeRate()
    }
    
    fun submitTransfer() {
        isSubmitting = true
        scope.launch {
            delay(1500)
            if (!isOnline) {
                pendingCount++
                successMessage = "Transfer queued. Will sync when online."
            } else {
                successMessage = "Transfer successful! Ref: TXN${System.currentTimeMillis()}"
            }
            isSubmitting = false
            delay(2000)
            onNavigateBack()
        }
    }
    
    LaunchedEffect(sourceCurrency, destinationCurrency) { fetchExchangeRate() }
    
    LaunchedEffect(rateLock) {
        if (rateLock == null) {
            while (true) {
                delay(1000)
                rateRefreshCountdown--
                if (rateRefreshCountdown <= 0) fetchExchangeRate()
            }
        }
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Send Money") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    if (!isOnline) {
                        Surface(color = MaterialTheme.colorScheme.errorContainer, shape = RoundedCornerShape(16.dp)) {
                            Row(modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                                Box(modifier = Modifier.size(8.dp).clip(CircleShape).background(MaterialTheme.colorScheme.error))
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("Offline", style = MaterialTheme.typography.labelSmall)
                            }
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier.fillMaxSize().padding(paddingValues).verticalScroll(rememberScrollState())
        ) {
            // Pending banner
            AnimatedVisibility(visible = pendingCount > 0) {
                Surface(modifier = Modifier.fillMaxWidth().padding(16.dp), color = MaterialTheme.colorScheme.primaryContainer, shape = RoundedCornerShape(12.dp)) {
                    Row(modifier = Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Surface(shape = CircleShape, color = MaterialTheme.colorScheme.primary) {
                            Text(pendingCount.toString(), modifier = Modifier.padding(8.dp), color = MaterialTheme.colorScheme.onPrimary, fontWeight = FontWeight.Bold)
                        }
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text("Pending Transactions", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Medium)
                            Text("Will sync when online", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
            
            // Progress indicator
            Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                listOf("Recipient", "Amount", "Confirm").forEachIndexed { index, label ->
                    val stepNum = index + 1
                    val isCompleted = currentStep > stepNum
                    val isCurrent = currentStep == stepNum
                    
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Surface(shape = CircleShape, color = when { isCompleted -> MaterialTheme.colorScheme.primary; isCurrent -> MaterialTheme.colorScheme.primary; else -> MaterialTheme.colorScheme.surfaceVariant }, modifier = Modifier.size(40.dp)) {
                            Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
                                if (isCompleted) Icon(Icons.Default.Check, contentDescription = null, tint = MaterialTheme.colorScheme.onPrimary)
                                else Text(stepNum.toString(), color = if (isCurrent) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant, fontWeight = FontWeight.Bold)
                            }
                        }
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(label, style = MaterialTheme.typography.labelSmall, color = if (isCurrent) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    if (index < 2) Box(modifier = Modifier.weight(1f).height(2.dp).padding(horizontal = 8.dp).background(if (isCompleted) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant))
                }
            }
            
            // Error/Success messages
            AnimatedVisibility(visible = errorMessage != null) {
                Surface(modifier = Modifier.fillMaxWidth().padding(16.dp), color = MaterialTheme.colorScheme.errorContainer, shape = RoundedCornerShape(12.dp)) {
                    Row(modifier = Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Warning, contentDescription = null, tint = MaterialTheme.colorScheme.error)
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(errorMessage ?: "", modifier = Modifier.weight(1f))
                        IconButton(onClick = { errorMessage = null }) { Icon(Icons.Default.Close, contentDescription = "Dismiss") }
                    }
                }
            }
            
            AnimatedVisibility(visible = successMessage != null) {
                Surface(modifier = Modifier.fillMaxWidth().padding(16.dp), color = Color(0xFFE8F5E9), shape = RoundedCornerShape(12.dp)) {
                    Row(modifier = Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.CheckCircle, contentDescription = null, tint = Color(0xFF4CAF50))
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(successMessage ?: "", color = Color(0xFF1B5E20))
                    }
                }
            }
            
            // Step content
            when (currentStep) {
                1 -> RecipientStep(recipientType, { recipientType = it }, recipientName, { recipientName = it }, recipient, { recipient = it }, selectedBank, { selectedBank = it }, destinationCurrency, { destinationCurrency = it })
                2 -> AmountStep(amount, { amount = it }, sourceCurrency, { sourceCurrency = it }, destinationCurrency, receivedAmount, exchangeRate, rateLock, isLoadingRate, rateRefreshCountdown, showRateHistory, { showRateHistory = it }, { lockRate() }, { unlockRate() }, feeBreakdown, deliveryEstimates, deliveryMethod, { deliveryMethod = it }, note, { note = it }, numberFormat)
                3 -> ConfirmStep(amount, sourceCurrency, destinationCurrency, receivedAmount, recipientName, recipient, recipientType, exchangeRate, rateLock, deliveryMethod, deliveryEstimates, feeBreakdown, note, isOnline, numberFormat)
            }
            
            Spacer(modifier = Modifier.weight(1f))
            
            // Navigation buttons
            Row(modifier = Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                if (currentStep > 1) OutlinedButton(onClick = { currentStep-- }, modifier = Modifier.weight(1f)) { Text("Back") }
                else OutlinedButton(onClick = onNavigateBack, modifier = Modifier.weight(1f)) { Text("Cancel") }
                
                Button(
                    onClick = { if (currentStep < 3) currentStep++ else submitTransfer() },
                    modifier = Modifier.weight(1f),
                    enabled = when (currentStep) { 1 -> recipientName.isNotBlank() && recipient.length >= 5; 2 -> (amount.toDoubleOrNull() ?: 0.0) > 0 && exchangeRate != null; 3 -> !isSubmitting; else -> false }
                ) {
                    if (isSubmitting) { CircularProgressIndicator(modifier = Modifier.size(20.dp), color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp); Spacer(modifier = Modifier.width(8.dp)); Text("Processing...") }
                    else if (currentStep == 3) { Icon(Icons.Default.Send, contentDescription = null); Spacer(modifier = Modifier.width(8.dp)); Text("Send ${CURRENCY_SYMBOLS[sourceCurrency]}${numberFormat.format(amount.toDoubleOrNull() ?: 0.0)}") }
                    else Text("Continue")
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RecipientStep(recipientType: String, onRecipientTypeChange: (String) -> Unit, recipientName: String, onRecipientNameChange: (String) -> Unit, recipient: String, onRecipientChange: (String) -> Unit, selectedBank: String, onBankChange: (String) -> Unit, destinationCurrency: String, onDestinationCurrencyChange: (String) -> Unit) {
    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("Who are you sending to?", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(Triple("phone", "Phone", Icons.Default.Phone), Triple("email", "Email", Icons.Default.Email), Triple("bank", "Bank", Icons.Default.AccountBalance)).forEach { (type, label, icon) ->
                val isSelected = recipientType == type
                Surface(modifier = Modifier.weight(1f).clickable { onRecipientTypeChange(type) }, shape = RoundedCornerShape(12.dp), color = if (isSelected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant) {
                    Column(modifier = Modifier.padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(icon, contentDescription = null, tint = if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(label, style = MaterialTheme.typography.labelMedium, color = if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
        
        OutlinedTextField(value = recipientName, onValueChange = onRecipientNameChange, label = { Text("Recipient Name") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(value = recipient, onValueChange = onRecipientChange, label = { Text(when (recipientType) { "phone" -> "Phone Number"; "email" -> "Email Address"; else -> "Account Number" }) }, modifier = Modifier.fillMaxWidth(), singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = when (recipientType) { "phone" -> KeyboardType.Phone; "email" -> KeyboardType.Email; else -> KeyboardType.Number }))
        
        if (recipientType == "bank") {
            var expanded by remember { mutableStateOf(false) }
            val banks = listOf("Access Bank", "First Bank", "GTBank", "UBA", "Zenith Bank", "Stanbic IBTC", "Fidelity Bank")
            ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
                OutlinedTextField(value = selectedBank, onValueChange = {}, readOnly = true, label = { Text("Select Bank") }, trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) }, modifier = Modifier.fillMaxWidth().menuAnchor())
                ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                    banks.forEach { bank -> DropdownMenuItem(text = { Text(bank) }, onClick = { onBankChange(bank); expanded = false }) }
                }
            }
        }
        
        Text("Sending to", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            DESTINATION_CURRENCIES.take(4).forEach { currency ->
                val isSelected = destinationCurrency == currency
                Surface(modifier = Modifier.weight(1f).clickable { onDestinationCurrencyChange(currency) }, shape = RoundedCornerShape(12.dp), color = if (isSelected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant) {
                    Column(modifier = Modifier.padding(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(CURRENCY_FLAGS[currency] ?: "", fontSize = 24.sp)
                        Text(currency, style = MaterialTheme.typography.labelSmall, fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AmountStep(amount: String, onAmountChange: (String) -> Unit, sourceCurrency: String, onSourceCurrencyChange: (String) -> Unit, destinationCurrency: String, receivedAmount: Double, exchangeRate: ExchangeRate?, rateLock: RateLock?, isLoadingRate: Boolean, rateRefreshCountdown: Int, showRateHistory: Boolean, onShowRateHistoryChange: (Boolean) -> Unit, onLockRate: () -> Unit, onUnlockRate: () -> Unit, feeBreakdown: FeeBreakdown?, deliveryEstimates: List<DeliveryEstimate>, deliveryMethod: String, onDeliveryMethodChange: (String) -> Unit, note: String, onNoteChange: (String) -> Unit, numberFormat: NumberFormat) {
    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("How much are you sending?", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            var expanded by remember { mutableStateOf(false) }
            ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }, modifier = Modifier.width(120.dp)) {
                OutlinedTextField(value = "${CURRENCY_FLAGS[sourceCurrency]} $sourceCurrency", onValueChange = {}, readOnly = true, modifier = Modifier.menuAnchor(), trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) })
                ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                    SOURCE_CURRENCIES.forEach { currency -> DropdownMenuItem(text = { Text("${CURRENCY_FLAGS[currency]} $currency") }, onClick = { onSourceCurrencyChange(currency); expanded = false }) }
                }
            }
            OutlinedTextField(value = amount, onValueChange = onAmountChange, label = { Text("You send") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), modifier = Modifier.weight(1f), singleLine = true, prefix = { Text(CURRENCY_SYMBOLS[sourceCurrency] ?: "") })
        }
        
        Surface(modifier = Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.surfaceVariant, shape = RoundedCornerShape(12.dp)) {
            Row(modifier = Modifier.padding(16.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text("They receive", style = MaterialTheme.typography.bodyMedium)
                Text("${CURRENCY_SYMBOLS[destinationCurrency]}${numberFormat.format(receivedAmount)} $destinationCurrency", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
            }
        }
        
        // Exchange rate card
        Surface(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp), color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f)) {
            Column(modifier = Modifier.padding(16.dp)) {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text("Exchange Rate", style = MaterialTheme.typography.titleSmall)
                    if (isLoadingRate) CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                    else if (rateLock != null) Surface(color = Color(0xFF4CAF50), shape = RoundedCornerShape(12.dp)) { Row(modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Default.Lock, contentDescription = null, modifier = Modifier.size(12.dp), tint = Color.White); Spacer(modifier = Modifier.width(4.dp)); Text("Locked", style = MaterialTheme.typography.labelSmall, color = Color.White) } }
                    else Text("Refreshes in ${rateRefreshCountdown}s", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Spacer(modifier = Modifier.height(8.dp))
                Text("1 $sourceCurrency = ${exchangeRate?.rate?.let { String.format("%.4f", it) } ?: "---"} $destinationCurrency", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Spacer(modifier = Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (rateLock != null) OutlinedButton(onClick = onUnlockRate, colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)) { Text("Unlock") }
                    else Button(onClick = onLockRate, enabled = exchangeRate != null && !isLoadingRate) { Icon(Icons.Default.Lock, contentDescription = null, modifier = Modifier.size(16.dp)); Spacer(modifier = Modifier.width(4.dp)); Text("Lock Rate") }
                    OutlinedButton(onClick = { onShowRateHistoryChange(!showRateHistory) }) { Text(if (showRateHistory) "Hide" else "History") }
                }
                AnimatedVisibility(visible = showRateHistory) {
                    Column(modifier = Modifier.padding(top = 12.dp)) {
                        Text("7-Day Rate History", style = MaterialTheme.typography.labelMedium)
                        Spacer(modifier = Modifier.height(8.dp))
                        Row(modifier = Modifier.fillMaxWidth().height(60.dp), horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.Bottom) {
                            listOf(0.98, 0.99, 1.01, 0.97, 1.02, 0.99, 1.0).forEach { multiplier -> Box(modifier = Modifier.weight(1f).height((multiplier * 50).dp).clip(RoundedCornerShape(topStart = 4.dp, topEnd = 4.dp)).background(MaterialTheme.colorScheme.primary.copy(alpha = 0.7f))) }
                        }
                    }
                }
            }
        }
        
        // Fee breakdown
        feeBreakdown?.let { fees ->
            Surface(modifier = Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.surfaceVariant, shape = RoundedCornerShape(12.dp)) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Fee Breakdown", style = MaterialTheme.typography.titleSmall)
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { Text("Transfer fee", style = MaterialTheme.typography.bodySmall); Text("${CURRENCY_SYMBOLS[sourceCurrency]}${String.format("%.2f", fees.transferFee)}", style = MaterialTheme.typography.bodySmall) }
                    if (fees.networkFee > 0) Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { Text("Cash pickup fee", style = MaterialTheme.typography.bodySmall); Text("${CURRENCY_SYMBOLS[sourceCurrency]}${String.format("%.2f", fees.networkFee)}", style = MaterialTheme.typography.bodySmall) }
                    HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { Text("Total fees", style = MaterialTheme.typography.titleSmall); Text("${CURRENCY_SYMBOLS[sourceCurrency]}${String.format("%.2f", fees.totalFees)} (${String.format("%.1f", fees.feePercentage)}%)", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold) }
                }
            }
        }
        
        // Delivery method
        Text("Delivery Method", style = MaterialTheme.typography.titleMedium)
        deliveryEstimates.forEach { estimate ->
            val isSelected = deliveryMethod == estimate.method
            Surface(modifier = Modifier.fillMaxWidth().clickable(enabled = estimate.available) { onDeliveryMethodChange(estimate.method) }, shape = RoundedCornerShape(12.dp), color = if (isSelected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant) {
                Row(modifier = Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(when (estimate.method) { "bank_transfer" -> Icons.Default.AccountBalance; "mobile_money" -> Icons.Default.PhoneAndroid; else -> Icons.Default.LocalAtm }, contentDescription = null, tint = if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(modifier = Modifier.width(12.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(estimate.method.replace("_", " ").replaceFirstChar { it.uppercase() }, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                        Text(estimate.estimatedTime, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    if (isSelected) Icon(Icons.Default.CheckCircle, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                }
            }
        }
        
        OutlinedTextField(value = note, onValueChange = onNoteChange, label = { Text("Note (optional)") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
    }
}

@Composable
private fun ConfirmStep(amount: String, sourceCurrency: String, destinationCurrency: String, receivedAmount: Double, recipientName: String, recipient: String, recipientType: String, exchangeRate: ExchangeRate?, rateLock: RateLock?, deliveryMethod: String, deliveryEstimates: List<DeliveryEstimate>, feeBreakdown: FeeBreakdown?, note: String, isOnline: Boolean, numberFormat: NumberFormat) {
    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("Confirm Transfer", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        
        // Amount summary card
        Surface(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.primary) {
            Column(modifier = Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Text("You're sending", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.8f))
                Text("${CURRENCY_SYMBOLS[sourceCurrency]}${numberFormat.format(amount.toDoubleOrNull() ?: 0.0)}", style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onPrimary)
                Text(sourceCurrency, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.8f))
                Spacer(modifier = Modifier.height(16.dp))
                Icon(Icons.Default.ArrowDownward, contentDescription = null, tint = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.6f), modifier = Modifier.size(32.dp))
                Spacer(modifier = Modifier.height(16.dp))
                Text("$recipientName receives", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.8f))
                Text("${CURRENCY_SYMBOLS[destinationCurrency]}${numberFormat.format(receivedAmount)}", style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onPrimary)
                Text(destinationCurrency, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.8f))
            }
        }
        
        // Details
        Surface(modifier = Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.surfaceVariant, shape = RoundedCornerShape(12.dp)) {
            Column(modifier = Modifier.padding(16.dp)) {
                DetailRow("Recipient", recipientName)
                DetailRow(when (recipientType) { "phone" -> "Phone"; "email" -> "Email"; else -> "Account" }, recipient)
                DetailRow("Exchange Rate", "1 $sourceCurrency = ${String.format("%.4f", rateLock?.rate ?: exchangeRate?.rate ?: 0.0)} $destinationCurrency" + if (rateLock != null) " (Locked)" else "")
                DetailRow("Delivery Method", deliveryMethod.replace("_", " ").replaceFirstChar { it.uppercase() })
                DetailRow("Estimated Delivery", deliveryEstimates.find { it.method == deliveryMethod }?.estimatedTime ?: "-")
                DetailRow("Total Fees", "${CURRENCY_SYMBOLS[sourceCurrency]}${String.format("%.2f", feeBreakdown?.totalFees ?: 0.0)}")
                if (note.isNotBlank()) DetailRow("Note", note)
            }
        }
        
        // Total to pay
        Surface(modifier = Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.primaryContainer, shape = RoundedCornerShape(12.dp)) {
            Row(modifier = Modifier.padding(16.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text("Total to Pay", style = MaterialTheme.typography.titleMedium)
                Text("${CURRENCY_SYMBOLS[sourceCurrency]}${numberFormat.format((amount.toDoubleOrNull() ?: 0.0) + (feeBreakdown?.totalFees ?: 0.0))}", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
            }
        }
        
        // Offline warning
        if (!isOnline) {
            Surface(modifier = Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.errorContainer, shape = RoundedCornerShape(12.dp)) {
                Row(modifier = Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Warning, contentDescription = null, tint = MaterialTheme.colorScheme.error)
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text("You're currently offline", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Medium)
                        Text("This transfer will be queued and processed when you're back online.", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
    }
    HorizontalDivider()
}

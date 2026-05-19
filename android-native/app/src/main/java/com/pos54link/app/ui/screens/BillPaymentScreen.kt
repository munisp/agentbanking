package com.pos54link.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.pos54link.app.viewmodels.TransactionViewModel

data class BillCategory(
    val id: String,
    val name: String,
    val icon: String,
    val providers: List<String>
)

val BILL_CATEGORIES = listOf(
    BillCategory("electricity", "Electricity", "⚡", listOf("EKEDC", "IKEDC", "AEDC", "PHEDC", "EEDC", "KEDCO", "JEDC", "BEDC")),
    BillCategory("airtime", "Airtime", "📱", listOf("MTN", "Airtel", "Glo", "9mobile")),
    BillCategory("data", "Data Bundle", "🌐", listOf("MTN", "Airtel", "Glo", "9mobile")),
    BillCategory("cable", "Cable TV", "📺", listOf("DSTV", "GOtv", "StarTimes")),
    BillCategory("water", "Water Bill", "💧", listOf("Lagos Water", "Abuja Water", "Rivers Water")),
    BillCategory("internet", "Internet", "🔗", listOf("Spectranet", "Smile", "ipNX", "Swift")),
    BillCategory("insurance", "Insurance", "🛡️", listOf("AIICO", "Leadway", "AXA Mansard")),
    BillCategory("tax", "Tax / Levies", "🏛️", listOf("FIRS", "LIRS", "SIRS"))
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BillPaymentScreen(
    onSuccess: (transactionRef: String) -> Unit,
    onBack: () -> Unit,
    viewModel: TransactionViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    var selectedCategory by remember { mutableStateOf<BillCategory?>(null) }
    var selectedProvider by remember { mutableStateOf("") }
    var customerRef by remember { mutableStateOf("") }
    var amount by remember { mutableStateOf("") }
    var step by remember { mutableStateOf(BillStep.SELECT_CATEGORY) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(when (step) {
                        BillStep.SELECT_CATEGORY -> "Bill Payment"
                        BillStep.SELECT_PROVIDER -> selectedCategory?.name ?: "Select Provider"
                        BillStep.ENTER_DETAILS -> "Enter Details"
                        BillStep.CONFIRM -> "Confirm Payment"
                    })
                },
                navigationIcon = {
                    IconButton(onClick = {
                        when (step) {
                            BillStep.SELECT_CATEGORY -> onBack()
                            BillStep.SELECT_PROVIDER -> step = BillStep.SELECT_CATEGORY
                            BillStep.ENTER_DETAILS -> step = BillStep.SELECT_PROVIDER
                            BillStep.CONFIRM -> step = BillStep.ENTER_DETAILS
                        }
                    }) { Text("←") }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
        ) {
            when (step) {
                BillStep.SELECT_CATEGORY -> {
                    Text("Select bill type:", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(16.dp))
                    LazyVerticalGrid(
                        columns = GridCells.Fixed(2),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        items(BILL_CATEGORIES) { category ->
                            Card(
                                onClick = {
                                    selectedCategory = category
                                    step = BillStep.SELECT_PROVIDER
                                },
                                modifier = Modifier.fillMaxWidth().height(100.dp)
                            ) {
                                Column(
                                    modifier = Modifier.fillMaxSize(),
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                    verticalArrangement = Arrangement.Center
                                ) {
                                    Text(category.icon, style = MaterialTheme.typography.headlineMedium)
                                    Text(category.name, style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.Center)
                                }
                            }
                        }
                    }
                }

                BillStep.SELECT_PROVIDER -> {
                    Text("Select provider:", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(16.dp))
                    selectedCategory?.providers?.forEach { provider ->
                        Card(
                            onClick = {
                                selectedProvider = provider
                                step = BillStep.ENTER_DETAILS
                            },
                            modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)
                        ) {
                            Row(
                                modifier = Modifier.padding(16.dp).fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(provider, style = MaterialTheme.typography.bodyLarge)
                                Text("→")
                            }
                        }
                    }
                }

                BillStep.ENTER_DETAILS -> {
                    Text("$selectedProvider — ${selectedCategory?.name}", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(16.dp))
                    OutlinedTextField(
                        value = customerRef,
                        onValueChange = { customerRef = it },
                        label = { Text(when (selectedCategory?.id) {
                            "electricity" -> "Meter Number"
                            "airtime", "data" -> "Phone Number"
                            "cable" -> "Smart Card / IUC Number"
                            "water" -> "Account Number"
                            else -> "Customer Reference"
                        }) },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )
                    Spacer(Modifier.height(12.dp))
                    OutlinedTextField(
                        value = amount,
                        onValueChange = { amount = it.filter { c -> c.isDigit() || c == '.' } },
                        label = { Text("Amount (NGN)") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                        modifier = Modifier.fillMaxWidth(),
                        prefix = { Text("₦") },
                        singleLine = true
                    )
                    Spacer(Modifier.weight(1f))
                    Button(
                        onClick = { step = BillStep.CONFIRM },
                        modifier = Modifier.fillMaxWidth().height(56.dp),
                        enabled = customerRef.isNotEmpty() && amount.isNotEmpty()
                    ) { Text("Continue") }
                }

                BillStep.CONFIRM -> {
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("Payment Summary", style = MaterialTheme.typography.titleMedium)
                            Divider()
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Bill Type"); Text(selectedCategory?.name ?: "")
                            }
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Provider"); Text(selectedProvider)
                            }
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Reference"); Text(customerRef)
                            }
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Amount"); Text("₦$amount")
                            }
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Fee"); Text("₦50.00")
                            }
                            Divider()
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Total", style = MaterialTheme.typography.titleSmall)
                                Text("₦${(amount.toDoubleOrNull() ?: 0.0) + 50.0}", style = MaterialTheme.typography.titleSmall)
                            }
                        }
                    }
                    Spacer(Modifier.weight(1f))
                    Button(
                        onClick = {
                            viewModel.processBillPayment(
                                category = selectedCategory?.id ?: "",
                                provider = selectedProvider,
                                customerRef = customerRef,
                                amount = amount.toDoubleOrNull() ?: 0.0
                            )
                        },
                        modifier = Modifier.fillMaxWidth().height(56.dp),
                        enabled = !uiState.isLoading
                    ) {
                        if (uiState.isLoading) {
                            CircularProgressIndicator(modifier = Modifier.size(24.dp))
                        } else {
                            Text("Pay ₦${(amount.toDoubleOrNull() ?: 0.0) + 50.0}")
                        }
                    }
                    uiState.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                }
            }
        }
    }

    LaunchedEffect(uiState.successRef) {
        uiState.successRef?.let { ref -> onSuccess(ref) }
    }
}

enum class BillStep { SELECT_CATEGORY, SELECT_PROVIDER, ENTER_DETAILS, CONFIRM }

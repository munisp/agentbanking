package com.pos54link.app.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

// Data classes for Property KYC
data class PartyIdentity(
    var fullName: String = "",
    var dateOfBirth: String = "",
    var nationality: String = "Nigerian",
    var idType: String = "NATIONAL_ID",
    var idNumber: String = "",
    var idExpiryDate: String = "",
    var bvn: String = "",
    var nin: String = "",
    var address: String = "",
    var city: String = "",
    var state: String = "",
    var country: String = "Nigeria",
    var phone: String = "",
    var email: String = ""
)

data class SourceOfFunds(
    var primarySource: String = "EMPLOYMENT",
    var description: String = "",
    var employerName: String = "",
    var businessName: String = "",
    var annualIncome: String = ""
)

data class BankStatement(
    var fileName: String = "",
    var startDate: String = "",
    var endDate: String = "",
    var uploaded: Boolean = false
)

data class IncomeDocument(
    var documentType: String = "PAYSLIP",
    var fileName: String = "",
    var uploaded: Boolean = false
)

data class PurchaseAgreement(
    var fileName: String = "",
    var propertyAddress: String = "",
    var purchasePrice: String = "",
    var buyerName: String = "",
    var sellerName: String = "",
    var agreementDate: String = "",
    var uploaded: Boolean = false
)

val ID_TYPES = listOf(
    "NATIONAL_ID" to "National ID Card",
    "PASSPORT" to "International Passport",
    "DRIVERS_LICENSE" to "Driver's License",
    "VOTERS_CARD" to "Voter's Card",
    "NIN_SLIP" to "NIN Slip",
    "BVN" to "BVN"
)

val SOURCE_OF_FUNDS_OPTIONS = listOf(
    "EMPLOYMENT" to "Employment Income",
    "BUSINESS" to "Business Income",
    "SAVINGS" to "Personal Savings",
    "GIFT" to "Gift from Family/Friends",
    "LOAN" to "Bank Loan/Mortgage",
    "INHERITANCE" to "Inheritance",
    "INVESTMENT" to "Investment Returns",
    "SALE_OF_PROPERTY" to "Sale of Property",
    "OTHER" to "Other"
)

val INCOME_DOCUMENT_TYPES = listOf(
    "PAYSLIP" to "Payslip (Last 3 months)",
    "W2" to "W-2 Form",
    "PAYE" to "PAYE Records",
    "TAX_RETURN" to "Tax Return",
    "BUSINESS_REGISTRATION" to "Business Registration",
    "AUDITED_ACCOUNTS" to "Audited Accounts"
)

val NIGERIAN_STATES = listOf(
    "Lagos", "Abuja FCT", "Kano", "Rivers", "Oyo", "Kaduna", "Ogun", "Enugu",
    "Delta", "Anambra", "Edo", "Imo", "Kwara", "Osun", "Ekiti", "Ondo"
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PropertyKYCScreen(
    onNavigateBack: () -> Unit,
    isOnline: Boolean = true
) {
    val scope = rememberCoroutineScope()
    
    // Form state
    var currentStep by remember { mutableIntStateOf(1) }
    var buyerIdentity by remember { mutableStateOf(PartyIdentity()) }
    var sellerIdentity by remember { mutableStateOf(PartyIdentity()) }
    var sourceOfFunds by remember { mutableStateOf(SourceOfFunds()) }
    var bankStatements by remember { mutableStateOf(listOf(BankStatement())) }
    var incomeDocuments by remember { mutableStateOf(listOf(IncomeDocument())) }
    var purchaseAgreement by remember { mutableStateOf(PurchaseAgreement()) }
    
    // UI state
    var isSubmitting by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var successMessage by remember { mutableStateOf<String?>(null) }
    
    val steps = listOf(
        "Buyer KYC", "Seller KYC", "Source of Funds",
        "Bank Statements", "Income Docs", "Agreement", "Review"
    )
    
    fun submitKYC() {
        isSubmitting = true
        scope.launch {
            delay(2000)
            successMessage = "Property KYC submitted successfully! Reference: PKYC${System.currentTimeMillis()}"
            isSubmitting = false
            delay(2000)
            onNavigateBack()
        }
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Property Transaction KYC") },
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
            // Progress indicator
            Row(
                modifier = Modifier.fillMaxWidth().padding(16.dp),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                steps.forEachIndexed { index, label ->
                    val stepNum = index + 1
                    val isCompleted = currentStep > stepNum
                    val isCurrent = currentStep == stepNum
                    
                    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.weight(1f)) {
                        Surface(
                            shape = CircleShape,
                            color = when {
                                isCompleted -> MaterialTheme.colorScheme.primary
                                isCurrent -> MaterialTheme.colorScheme.primary
                                else -> MaterialTheme.colorScheme.surfaceVariant
                            },
                            modifier = Modifier.size(32.dp)
                        ) {
                            Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
                                if (isCompleted) {
                                    Icon(Icons.Default.Check, contentDescription = null, tint = MaterialTheme.colorScheme.onPrimary, modifier = Modifier.size(16.dp))
                                } else {
                                    Text(stepNum.toString(), color = if (isCurrent) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
                                }
                            }
                        }
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(label, style = MaterialTheme.typography.labelSmall, color = if (isCurrent) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
                    }
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
                1 -> PartyIdentityStep(title = "Buyer Information", identity = buyerIdentity, onIdentityChange = { buyerIdentity = it })
                2 -> PartyIdentityStep(title = "Seller Information", identity = sellerIdentity, onIdentityChange = { sellerIdentity = it })
                3 -> SourceOfFundsStep(sourceOfFunds = sourceOfFunds, onSourceChange = { sourceOfFunds = it })
                4 -> BankStatementsStep(statements = bankStatements, onStatementsChange = { bankStatements = it })
                5 -> IncomeDocumentsStep(documents = incomeDocuments, onDocumentsChange = { incomeDocuments = it })
                6 -> PurchaseAgreementStep(agreement = purchaseAgreement, onAgreementChange = { purchaseAgreement = it })
                7 -> ReviewStep(buyerIdentity, sellerIdentity, sourceOfFunds, bankStatements, incomeDocuments, purchaseAgreement)
            }
            
            Spacer(modifier = Modifier.weight(1f))
            
            // Navigation buttons
            Row(modifier = Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                if (currentStep > 1) {
                    OutlinedButton(onClick = { currentStep-- }, modifier = Modifier.weight(1f)) { Text("Back") }
                } else {
                    OutlinedButton(onClick = onNavigateBack, modifier = Modifier.weight(1f)) { Text("Cancel") }
                }
                
                Button(
                    onClick = { if (currentStep < 7) currentStep++ else submitKYC() },
                    modifier = Modifier.weight(1f),
                    enabled = !isSubmitting
                ) {
                    if (isSubmitting) {
                        CircularProgressIndicator(modifier = Modifier.size(20.dp), color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Submitting...")
                    } else if (currentStep == 7) {
                        Icon(Icons.Default.Send, contentDescription = null)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Submit KYC")
                    } else {
                        Text("Continue")
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PartyIdentityStep(title: String, identity: PartyIdentity, onIdentityChange: (PartyIdentity) -> Unit) {
    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Text("Please provide government-issued identification", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        
        OutlinedTextField(value = identity.fullName, onValueChange = { onIdentityChange(identity.copy(fullName = it)) }, label = { Text("Full Name (as on ID)") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(value = identity.dateOfBirth, onValueChange = { onIdentityChange(identity.copy(dateOfBirth = it)) }, label = { Text("Date of Birth (DD/MM/YYYY)") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        
        // ID Type dropdown
        var expandedIdType by remember { mutableStateOf(false) }
        ExposedDropdownMenuBox(expanded = expandedIdType, onExpandedChange = { expandedIdType = it }) {
            OutlinedTextField(value = ID_TYPES.find { it.first == identity.idType }?.second ?: "", onValueChange = {}, readOnly = true, label = { Text("ID Type") }, trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expandedIdType) }, modifier = Modifier.fillMaxWidth().menuAnchor())
            ExposedDropdownMenu(expanded = expandedIdType, onDismissRequest = { expandedIdType = false }) {
                ID_TYPES.forEach { (code, name) -> DropdownMenuItem(text = { Text(name) }, onClick = { onIdentityChange(identity.copy(idType = code)); expandedIdType = false }) }
            }
        }
        
        OutlinedTextField(value = identity.idNumber, onValueChange = { onIdentityChange(identity.copy(idNumber = it)) }, label = { Text("ID Number") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(value = identity.idExpiryDate, onValueChange = { onIdentityChange(identity.copy(idExpiryDate = it)) }, label = { Text("ID Expiry Date (DD/MM/YYYY)") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        
        HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
        Text("Nigerian Verification Numbers", style = MaterialTheme.typography.titleMedium)
        
        OutlinedTextField(value = identity.bvn, onValueChange = { onIdentityChange(identity.copy(bvn = it)) }, label = { Text("BVN (11 digits)") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(value = identity.nin, onValueChange = { onIdentityChange(identity.copy(nin = it)) }, label = { Text("NIN (11 digits)") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        
        HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
        Text("Contact Information", style = MaterialTheme.typography.titleMedium)
        
        OutlinedTextField(value = identity.address, onValueChange = { onIdentityChange(identity.copy(address = it)) }, label = { Text("Street Address") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(value = identity.city, onValueChange = { onIdentityChange(identity.copy(city = it)) }, label = { Text("City") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        
        var expandedState by remember { mutableStateOf(false) }
        ExposedDropdownMenuBox(expanded = expandedState, onExpandedChange = { expandedState = it }) {
            OutlinedTextField(value = identity.state, onValueChange = {}, readOnly = true, label = { Text("State") }, trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expandedState) }, modifier = Modifier.fillMaxWidth().menuAnchor())
            ExposedDropdownMenu(expanded = expandedState, onDismissRequest = { expandedState = false }) {
                NIGERIAN_STATES.forEach { state -> DropdownMenuItem(text = { Text(state) }, onClick = { onIdentityChange(identity.copy(state = state)); expandedState = false }) }
            }
        }
        
        OutlinedTextField(value = identity.phone, onValueChange = { onIdentityChange(identity.copy(phone = it)) }, label = { Text("Phone Number") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(value = identity.email, onValueChange = { onIdentityChange(identity.copy(email = it)) }, label = { Text("Email Address") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        
        // Upload ID document button
        Surface(modifier = Modifier.fillMaxWidth().clickable { }, color = MaterialTheme.colorScheme.primaryContainer, shape = RoundedCornerShape(12.dp)) {
            Row(modifier = Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Upload, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                Spacer(modifier = Modifier.width(12.dp))
                Column {
                    Text("Upload ID Document", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                    Text("PDF or image, max 10MB", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SourceOfFundsStep(sourceOfFunds: SourceOfFunds, onSourceChange: (SourceOfFunds) -> Unit) {
    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("Source of Funds", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Text("Declare the source of funds for this property purchase", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        
        var expanded by remember { mutableStateOf(false) }
        ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
            OutlinedTextField(value = SOURCE_OF_FUNDS_OPTIONS.find { it.first == sourceOfFunds.primarySource }?.second ?: "", onValueChange = {}, readOnly = true, label = { Text("Primary Source of Funds") }, trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) }, modifier = Modifier.fillMaxWidth().menuAnchor())
            ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                SOURCE_OF_FUNDS_OPTIONS.forEach { (code, name) -> DropdownMenuItem(text = { Text(name) }, onClick = { onSourceChange(sourceOfFunds.copy(primarySource = code)); expanded = false }) }
            }
        }
        
        OutlinedTextField(value = sourceOfFunds.description, onValueChange = { onSourceChange(sourceOfFunds.copy(description = it)) }, label = { Text("Description") }, placeholder = { Text("Provide details about your source of funds") }, modifier = Modifier.fillMaxWidth(), minLines = 3)
        
        if (sourceOfFunds.primarySource == "EMPLOYMENT") {
            OutlinedTextField(value = sourceOfFunds.employerName, onValueChange = { onSourceChange(sourceOfFunds.copy(employerName = it)) }, label = { Text("Employer Name") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        }
        
        if (sourceOfFunds.primarySource == "BUSINESS") {
            OutlinedTextField(value = sourceOfFunds.businessName, onValueChange = { onSourceChange(sourceOfFunds.copy(businessName = it)) }, label = { Text("Business Name") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        }
        
        OutlinedTextField(value = sourceOfFunds.annualIncome, onValueChange = { onSourceChange(sourceOfFunds.copy(annualIncome = it)) }, label = { Text("Annual Income (NGN)") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        
        Surface(modifier = Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.tertiaryContainer, shape = RoundedCornerShape(12.dp)) {
            Row(modifier = Modifier.padding(16.dp)) {
                Icon(Icons.Default.Info, contentDescription = null, tint = MaterialTheme.colorScheme.tertiary)
                Spacer(modifier = Modifier.width(12.dp))
                Text("This information is required for anti-money laundering compliance. All declarations will be verified.", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun BankStatementsStep(statements: List<BankStatement>, onStatementsChange: (List<BankStatement>) -> Unit) {
    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("Bank Statements", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Text("Upload at least 3 months of bank statements showing regular income", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        
        Surface(modifier = Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.primaryContainer, shape = RoundedCornerShape(12.dp)) {
            Column(modifier = Modifier.padding(16.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Description, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text("Requirements", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                        Text("Minimum 90 days coverage", style = MaterialTheme.typography.bodySmall)
                        Text("Must be within last 6 months", style = MaterialTheme.typography.bodySmall)
                        Text("PDF format preferred", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
        
        statements.forEachIndexed { index, statement ->
            Surface(modifier = Modifier.fillMaxWidth().clickable { }, color = if (statement.uploaded) Color(0xFFE8F5E9) else MaterialTheme.colorScheme.surfaceVariant, shape = RoundedCornerShape(12.dp)) {
                Row(modifier = Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(if (statement.uploaded) Icons.Default.CheckCircle else Icons.Default.Upload, contentDescription = null, tint = if (statement.uploaded) Color(0xFF4CAF50) else MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(modifier = Modifier.width(12.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(if (statement.uploaded) statement.fileName else "Upload Statement ${index + 1}", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                        Text(if (statement.uploaded) "${statement.startDate} - ${statement.endDate}" else "Tap to select file", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
        
        OutlinedButton(onClick = { onStatementsChange(statements + BankStatement()) }, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Default.Add, contentDescription = null)
            Spacer(modifier = Modifier.width(8.dp))
            Text("Add Another Statement")
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun IncomeDocumentsStep(documents: List<IncomeDocument>, onDocumentsChange: (List<IncomeDocument>) -> Unit) {
    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("Income Documents", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Text("Upload documents verifying your income (W-2, PAYE, payslips, etc.)", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        
        documents.forEachIndexed { index, document ->
            var expanded by remember { mutableStateOf(false) }
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
                    OutlinedTextField(value = INCOME_DOCUMENT_TYPES.find { it.first == document.documentType }?.second ?: "", onValueChange = {}, readOnly = true, label = { Text("Document Type") }, trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) }, modifier = Modifier.fillMaxWidth().menuAnchor())
                    ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                        INCOME_DOCUMENT_TYPES.forEach { (code, name) ->
                            DropdownMenuItem(text = { Text(name) }, onClick = {
                                val updated = documents.toMutableList()
                                updated[index] = document.copy(documentType = code)
                                onDocumentsChange(updated)
                                expanded = false
                            })
                        }
                    }
                }
                
                Surface(modifier = Modifier.fillMaxWidth().clickable { }, color = if (document.uploaded) Color(0xFFE8F5E9) else MaterialTheme.colorScheme.surfaceVariant, shape = RoundedCornerShape(12.dp)) {
                    Row(modifier = Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(if (document.uploaded) Icons.Default.CheckCircle else Icons.Default.Upload, contentDescription = null, tint = if (document.uploaded) Color(0xFF4CAF50) else MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(if (document.uploaded) document.fileName else "Tap to upload", style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        }
        
        OutlinedButton(onClick = { onDocumentsChange(documents + IncomeDocument()) }, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Default.Add, contentDescription = null)
            Spacer(modifier = Modifier.width(8.dp))
            Text("Add Another Document")
        }
    }
}

@Composable
private fun PurchaseAgreementStep(agreement: PurchaseAgreement, onAgreementChange: (PurchaseAgreement) -> Unit) {
    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("Purchase Agreement", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Text("Upload the signed purchase agreement with property details", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        
        Surface(modifier = Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.tertiaryContainer, shape = RoundedCornerShape(12.dp)) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("Agreement Requirements", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                Spacer(modifier = Modifier.height(8.dp))
                listOf("Buyer and seller names and addresses", "Property address and description", "Purchase price and payment terms", "Signatures of both parties", "Date of agreement").forEach { req ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(16.dp), tint = MaterialTheme.colorScheme.tertiary)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(req, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
        
        Surface(modifier = Modifier.fillMaxWidth().clickable { }, color = if (agreement.uploaded) Color(0xFFE8F5E9) else MaterialTheme.colorScheme.primaryContainer, shape = RoundedCornerShape(12.dp)) {
            Row(modifier = Modifier.padding(20.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(if (agreement.uploaded) Icons.Default.CheckCircle else Icons.Default.Upload, contentDescription = null, tint = if (agreement.uploaded) Color(0xFF4CAF50) else MaterialTheme.colorScheme.primary, modifier = Modifier.size(32.dp))
                Spacer(modifier = Modifier.width(16.dp))
                Column {
                    Text(if (agreement.uploaded) agreement.fileName else "Upload Purchase Agreement", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
                    Text("PDF format, max 25MB", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        
        HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
        Text("Property Details", style = MaterialTheme.typography.titleMedium)
        
        OutlinedTextField(value = agreement.propertyAddress, onValueChange = { onAgreementChange(agreement.copy(propertyAddress = it)) }, label = { Text("Property Address") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
        OutlinedTextField(value = agreement.purchasePrice, onValueChange = { onAgreementChange(agreement.copy(purchasePrice = it)) }, label = { Text("Purchase Price (NGN)") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(value = agreement.agreementDate, onValueChange = { onAgreementChange(agreement.copy(agreementDate = it)) }, label = { Text("Agreement Date (DD/MM/YYYY)") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
    }
}

@Composable
private fun ReviewStep(buyer: PartyIdentity, seller: PartyIdentity, sourceOfFunds: SourceOfFunds, statements: List<BankStatement>, incomeDocuments: List<IncomeDocument>, agreement: PurchaseAgreement) {
    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("Review & Submit", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Text("Please review all information before submitting", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        
        // Buyer summary
        ReviewSection(title = "Buyer Information", items = listOf("Name" to buyer.fullName, "ID Type" to (ID_TYPES.find { it.first == buyer.idType }?.second ?: ""), "ID Number" to buyer.idNumber, "BVN" to buyer.bvn, "Phone" to buyer.phone, "Email" to buyer.email))
        
        // Seller summary
        ReviewSection(title = "Seller Information", items = listOf("Name" to seller.fullName, "ID Type" to (ID_TYPES.find { it.first == seller.idType }?.second ?: ""), "ID Number" to seller.idNumber, "Phone" to seller.phone, "Email" to seller.email))
        
        // Source of funds summary
        ReviewSection(title = "Source of Funds", items = listOf("Primary Source" to (SOURCE_OF_FUNDS_OPTIONS.find { it.first == sourceOfFunds.primarySource }?.second ?: ""), "Annual Income" to "NGN ${sourceOfFunds.annualIncome}"))
        
        // Documents summary
        Surface(modifier = Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.surfaceVariant, shape = RoundedCornerShape(12.dp)) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("Documents", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                Spacer(modifier = Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Description, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("${statements.count { it.uploaded }} Bank Statements uploaded", style = MaterialTheme.typography.bodySmall)
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Description, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("${incomeDocuments.count { it.uploaded }} Income Documents uploaded", style = MaterialTheme.typography.bodySmall)
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(if (agreement.uploaded) Icons.Default.CheckCircle else Icons.Default.Warning, contentDescription = null, modifier = Modifier.size(16.dp), tint = if (agreement.uploaded) Color(0xFF4CAF50) else MaterialTheme.colorScheme.error)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(if (agreement.uploaded) "Purchase Agreement uploaded" else "Purchase Agreement pending", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        
        // Property summary
        if (agreement.propertyAddress.isNotBlank()) {
            ReviewSection(title = "Property Details", items = listOf("Address" to agreement.propertyAddress, "Purchase Price" to "NGN ${agreement.purchasePrice}", "Agreement Date" to agreement.agreementDate))
        }
        
        Surface(modifier = Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.primaryContainer, shape = RoundedCornerShape(12.dp)) {
            Row(modifier = Modifier.padding(16.dp)) {
                Icon(Icons.Default.Security, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                Spacer(modifier = Modifier.width(12.dp))
                Text("By submitting, you confirm that all information provided is accurate and complete. False declarations may result in transaction rejection.", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun ReviewSection(title: String, items: List<Pair<String, String>>) {
    Surface(modifier = Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.surfaceVariant, shape = RoundedCornerShape(12.dp)) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            Spacer(modifier = Modifier.height(8.dp))
            items.filter { it.second.isNotBlank() }.forEach { (label, value) ->
                Row(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
                }
            }
        }
    }
}

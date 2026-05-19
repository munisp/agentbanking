package com.pos54link.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * SupportScreen.kt
 * Help center with FAQs, contact support, and live chat
 * 
 * Features:
 * - FAQ section with expandable items
 * - Contact support options (email, phone, chat)
 * - Help articles and guides
 * - Live chat integration
 * - Ticket submission
 */

// MARK: - Data Models

data class FAQItem(
    val id: String,
    val question: String,
    val answer: String,
    val category: String
)

data class SupportOption(
    val id: String,
    val title: String,
    val description: String,
    val icon: ImageVector,
    val action: SupportAction
)

enum class SupportAction {
    EMAIL,
    PHONE,
    LIVE_CHAT,
    SUBMIT_TICKET
}

// MARK: - ViewModel

class SupportViewModel : ViewModel() {
    private val _uiState = MutableStateFlow<SupportUiState>(SupportUiState.Loading)
    val uiState: StateFlow<SupportUiState> = _uiState.asStateFlow()
    
    private val _expandedFAQs = MutableStateFlow<Set<String>>(emptySet())
    val expandedFAQs: StateFlow<Set<String>> = _expandedFAQs.asStateFlow()
    
    init {
        loadSupportData()
    }
    
    fun loadSupportData() {
        viewModelScope.launch {
            _uiState.value = SupportUiState.Loading
            try {
                kotlinx.coroutines.delay(500)
                
                val faqs = listOf(
                    FAQItem(
                        id = "1",
                        question = "How do I send money?",
                        answer = "To send money, tap on 'Send Money' from the dashboard, select or add a beneficiary, enter the amount, and confirm the transaction.",
                        category = "Transactions"
                    ),
                    FAQItem(
                        id = "2",
                        question = "What are the transaction limits?",
                        answer = "Transaction limits vary by account tier. Basic: ₦50,000/day, Silver: ₦200,000/day, Gold: ₦1,000,000/day, Platinum: Unlimited.",
                        category = "Limits"
                    ),
                    FAQItem(
                        id = "3",
                        question = "How long does KYC verification take?",
                        answer = "KYC verification typically takes 24-48 hours. You'll receive a notification once your verification is complete.",
                        category = "KYC"
                    ),
                    FAQItem(
                        id = "4",
                        question = "Which payment methods are supported?",
                        answer = "We support bank transfers, debit/credit cards, USSD, and mobile money through Paystack, Flutterwave, and Interswitch.",
                        category = "Payments"
                    ),
                    FAQItem(
                        id = "5",
                        question = "Is my money safe?",
                        answer = "Yes! We use bank-level encryption, secure storage, and are regulated by the CBN. All transactions are monitored for fraud.",
                        category = "Security"
                    )
                )
                
                val supportOptions = listOf(
                    SupportOption(
                        id = "email",
                        title = "Email Support",
                        description = "support@remittance.ng",
                        icon = Icons.Default.Email,
                        action = SupportAction.EMAIL
                    ),
                    SupportOption(
                        id = "phone",
                        title = "Call Us",
                        description = "+234 800 123 4567",
                        icon = Icons.Default.Phone,
                        action = SupportAction.PHONE
                    ),
                    SupportOption(
                        id = "chat",
                        title = "Live Chat",
                        description = "Chat with our support team",
                        icon = Icons.Default.Chat,
                        action = SupportAction.LIVE_CHAT
                    ),
                    SupportOption(
                        id = "ticket",
                        title = "Submit Ticket",
                        description = "Create a support ticket",
                        icon = Icons.Default.Create,
                        action = SupportAction.SUBMIT_TICKET
                    )
                )
                
                _uiState.value = SupportUiState.Success(faqs, supportOptions)
            } catch (e: Exception) {
                _uiState.value = SupportUiState.Error(e.message ?: "Failed to load support data")
            }
        }
    }
    
    fun toggleFAQ(faqId: String) {
        _expandedFAQs.value = if (_expandedFAQs.value.contains(faqId)) {
            _expandedFAQs.value - faqId
        } else {
            _expandedFAQs.value + faqId
        }
    }
    
    fun handleSupportAction(action: SupportAction) {
        // Implement support action handling
        when (action) {
            SupportAction.EMAIL -> {
                // Open email client
            }
            SupportAction.PHONE -> {
                // Initiate phone call
            }
            SupportAction.LIVE_CHAT -> {
                // Open live chat
            }
            SupportAction.SUBMIT_TICKET -> {
                // Navigate to ticket submission
            }
        }
    }
}

sealed class SupportUiState {
    object Loading : SupportUiState()
    data class Success(
        val faqs: List<FAQItem>,
        val supportOptions: List<SupportOption>
    ) : SupportUiState()
    data class Error(val message: String) : SupportUiState()
}

// MARK: - Composable Screen

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SupportScreen(
    viewModel: SupportViewModel = androidx.lifecycle.viewmodel.compose.viewModel(),
    onNavigateBack: () -> Unit = {}
) {
    val uiState by viewModel.uiState.collectAsState()
    val expandedFAQs by viewModel.expandedFAQs.collectAsState()
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Help & Support") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { paddingValues ->
        when (val state = uiState) {
            is SupportUiState.Loading -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(paddingValues),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator()
                }
            }
            is SupportUiState.Error -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(paddingValues),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            text = state.message,
                            color = MaterialTheme.colorScheme.error
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(onClick = { viewModel.loadSupportData() }) {
                            Text("Retry")
                        }
                    }
                }
            }
            is SupportUiState.Success -> {
                SupportContent(
                    faqs = state.faqs,
                    supportOptions = state.supportOptions,
                    expandedFAQs = expandedFAQs,
                    onToggleFAQ = { viewModel.toggleFAQ(it) },
                    onSupportAction = { viewModel.handleSupportAction(it) },
                    modifier = Modifier.padding(paddingValues)
                )
            }
        }
    }
}

@Composable
private fun SupportContent(
    faqs: List<FAQItem>,
    supportOptions: List<SupportOption>,
    expandedFAQs: Set<String>,
    onToggleFAQ: (String) -> Unit,
    onSupportAction: (SupportAction) -> Unit,
    modifier: Modifier = Modifier
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // Contact Support Options
        item {
            Text(
                text = "Contact Us",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold
            )
        }
        
        items(supportOptions) { option ->
            SupportOptionCard(
                option = option,
                onClick = { onSupportAction(option.action) }
            )
        }
        
        // FAQ Section
        item {
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "Frequently Asked Questions",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold
            )
        }
        
        items(faqs) { faq ->
            FAQCard(
                faq = faq,
                isExpanded = expandedFAQs.contains(faq.id),
                onToggle = { onToggleFAQ(faq.id) }
            )
        }
    }
}

@Composable
private fun SupportOptionCard(
    option: SupportOption,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = option.icon,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(40.dp)
            )
            Spacer(modifier = Modifier.width(16.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = option.title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = option.description,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Icon(
                imageVector = Icons.Default.KeyboardArrowRight,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun FAQCard(
    faq: FAQItem,
    isExpanded: Boolean,
    onToggle: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onToggle)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = faq.question,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.weight(1f)
                )
                Icon(
                    imageVector = if (isExpanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                    contentDescription = if (isExpanded) "Collapse" else "Expand"
                )
            }
            
            if (isExpanded) {
                Spacer(modifier = Modifier.height(12.dp))
                Divider()
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    text = faq.answer,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

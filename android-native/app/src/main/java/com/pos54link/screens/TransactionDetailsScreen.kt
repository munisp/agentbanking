package com.pos54link.screens

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pos54link.R // Assuming R.string.app_name and other resources exist
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// --- 1. Data Models ---

/**
 * Represents the core data structure for a transaction.
 * This would typically be a data class from the Retrofit/Room layer.
 */
data class Transaction(
    val id: String,
    val amount: Double,
    val currency: String,
    val status: TransactionStatus,
    val senderName: String,
    val recipientName: String,
    val timestamp: Long,
    val reference: String,
    val paymentGateway: PaymentGateway,
    val fee: Double,
    val exchangeRate: Double,
    val receiptPath: String? = null // Path to the generated receipt image
)

/**
 * Defines the possible statuses for a transaction.
 */
enum class TransactionStatus {
    SUCCESS, PENDING, FAILED, REFUNDED
}

/**
 * Defines the supported payment gateways.
 */
enum class PaymentGateway {
    PAYSTACK, FLUTTERWAVE, INTERSWITCH, OFFLINE
}

/**
 * Represents the state of the UI for the Transaction Details Screen.
 */
data class TransactionDetailsState(
    val transaction: Transaction? = null,
    val isLoading: Boolean = false,
    val error: String? = null,
    val isReceiptGenerating: Boolean = false,
    val isBiometricAuthRequired: Boolean = false,
    val isOffline: Boolean = false
)

// --- 2. Repository (Data Layer Abstraction) ---

/**
 * Interface for the data layer, abstracting API (Retrofit) and local (Room) data sources.
 */
interface TransactionRepository {
    /**
     * Fetches transaction details by ID, prioritizing local data if offline, or falling back to API.
     */
    fun getTransactionDetails(transactionId: String): StateFlow<TransactionDetailsState>

    /**
     * Simulates a payment gateway action (e.g., re-attempt payment).
     */
    suspend fun processPaymentGatewayAction(transactionId: String, gateway: PaymentGateway): Result<String>

    /**
     * Saves a transaction to the local database for offline access.
     */
    suspend fun saveTransactionLocally(transaction: Transaction)
}

/**
 * Mock implementation of the TransactionRepository for demonstration.
 * In a real app, this would use Retrofit for network and Room for local storage.
 */
class MockTransactionRepository : TransactionRepository {
    private val _state = MutableStateFlow(TransactionDetailsState(isLoading = true))

    override fun getTransactionDetails(transactionId: String): StateFlow<TransactionDetailsState> {
        viewModelScope.launch {
            // Simulate network/database delay
            kotlinx.coroutines.delay(1500)
            val mockTransaction = Transaction(
                id = transactionId,
                amount = 150000.00,
                currency = "NGN",
                status = TransactionStatus.SUCCESS,
                senderName = "John Doe",
                recipientName = "Jane Smith",
                timestamp = System.currentTimeMillis() - 86400000, // 1 day ago
                reference = "TXN-20241103-123456",
                paymentGateway = PaymentGateway.PAYSTACK,
                fee = 500.00,
                exchangeRate = 1.0
            )
            _state.value = TransactionDetailsState(transaction = mockTransaction, isLoading = false, isOffline = false)
        }
        return _state.asStateFlow()
    }

    override suspend fun processPaymentGatewayAction(transactionId: String, gateway: PaymentGateway): Result<String> {
        return withContext(Dispatchers.IO) {
            kotlinx.coroutines.delay(1000)
            if (gateway == PaymentGateway.PAYSTACK) {
                Result.success("Payment re-attempt successful via Paystack for $transactionId")
            } else {
                Result.failure(Exception("Gateway action failed for $gateway"))
            }
        }
    }

    override suspend fun saveTransactionLocally(transaction: Transaction) {
        // Simulate Room database save
        println("Transaction ${transaction.id} saved locally.")
    }
}

// --- 3. ViewModel (MVVM) ---

/**
 * ViewModel for the TransactionDetailsScreen. Handles business logic and state management.
 */
class TransactionDetailsViewModel(
    private val repository: TransactionRepository,
    private val transactionId: String
) : ViewModel() {

    // State management using StateFlow
    private val _uiState = MutableStateFlow(TransactionDetailsState(isLoading = true))
    val uiState: StateFlow<TransactionDetailsState> = _uiState.asStateFlow()

    init {
        loadTransactionDetails()
    }

    /**
     * Loads transaction details from the repository.
     */
    private fun loadTransactionDetails() {
        viewModelScope.launch {
            repository.getTransactionDetails(transactionId).collect { state ->
                _uiState.value = state
            }
        }
    }

    /**
     * Simulates triggering biometric authentication for a sensitive action.
     */
    fun triggerBiometricAuth() {
        _uiState.value = _uiState.value.copy(isBiometricAuthRequired = true)
    }

    /**
     * Called after successful biometric authentication.
     */
    fun onBiometricAuthSuccess(context: Context) {
        _uiState.value = _uiState.value.copy(isBiometricAuthRequired = false)
        // Perform the sensitive action, e.g., re-attempt payment
        val transaction = _uiState.value.transaction
        if (transaction != null) {
            processGatewayAction(transaction.id, transaction.paymentGateway, context)
        }
    }

    /**
     * Called after failed or cancelled biometric authentication.
     */
    fun onBiometricAuthFailure() {
        _uiState.value = _uiState.value.copy(isBiometricAuthRequired = false)
    }

    /**
     * Processes a payment gateway action (e.g., re-attempt, refund).
     */
    private fun processGatewayAction(transactionId: String, gateway: PaymentGateway, context: Context) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            val result = repository.processPaymentGatewayAction(transactionId, gateway)
            _uiState.value = _uiState.value.copy(isLoading = false)

            result.onSuccess { message ->
                Toast.makeText(context, message, Toast.LENGTH_LONG).show()
                // Reload data to reflect changes
                loadTransactionDetails()
            }.onFailure { e ->
                _uiState.value = _uiState.value.copy(error = e.message)
                Toast.makeText(context, "Action Failed: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    /**
     * Initiates the receipt generation process.
     */
    fun startReceiptGeneration() {
        _uiState.value = _uiState.value.copy(isReceiptGenerating = true)
    }

    /**
     * Updates the transaction with the path to the generated receipt.
     */
    fun onReceiptGenerated(filePath: String) {
        val currentTransaction = _uiState.value.transaction
        if (currentTransaction != null) {
            val updatedTransaction = currentTransaction.copy(receiptPath = filePath)
            _uiState.value = _uiState.value.copy(
                transaction = updatedTransaction,
                isReceiptGenerating = false
            )
            // Optionally save the updated transaction (with receipt path) locally
            viewModelScope.launch {
                repository.saveTransactionLocally(updatedTransaction)
            }
        } else {
            _uiState.value = _uiState.value.copy(isReceiptGenerating = false)
        }
    }

    /**
     * Clears the current error state.
     */
    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
}

// Factory for ViewModel with arguments
class TransactionDetailsViewModelFactory(
    private val repository: TransactionRepository,
    private val transactionId: String
) : androidx.lifecycle.ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(TransactionDetailsViewModel::class.java)) {
            return TransactionDetailsViewModel(repository, transactionId) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}

// --- 4. Utility Functions ---

/**
 * Utility function to convert a Composable view into a Bitmap for receipt generation.
 * NOTE: This is a simplified example. In a real app, you'd use a dedicated PDF/Image library
 * or a more robust approach for high-quality receipt generation.
 */
fun captureComposableAsBitmap(view: android.view.View, composable: @Composable () -> Unit): Bitmap {
    // This is a placeholder. Capturing a Composable directly requires more complex logic
    // involving CompositionLocalProvider and setting up a temporary ComposeView.
    // For simplicity in this single file, we'll capture the root view, which is not ideal
    // but demonstrates the concept of a UI snapshot for a receipt.
    // A better approach is to render a dedicated receipt Composable to a Bitmap.

    // Since we cannot easily access the specific Composable's View in this context,
    // we'll simulate a capture of the entire screen content for the receipt area.
    // In a real implementation, you would pass a reference to the specific Composable's View.

    val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
    val canvas = Canvas(bitmap)
    canvas.drawColor(Color.White.toArgb()) // Ensure background is white
    view.draw(canvas)
    return bitmap
}

/**
 * Saves a Bitmap to a file in the app's cache directory.
 */
fun saveBitmapToFile(context: Context, bitmap: Bitmap, filename: String): String? {
    val file = File(context.cacheDir, filename)
    return try {
        FileOutputStream(file).use { out ->
            bitmap.compress(Bitmap.CompressFormat.PNG, 100, out)
        }
        file.absolutePath
    } catch (e: Exception) {
        e.printStackTrace()
        null
    }
}

/**
 * Formats a timestamp to a readable date and time string.
 */
fun formatTimestamp(timestamp: Long): String {
    val sdf = SimpleDateFormat("MMM dd, yyyy HH:mm:ss", Locale.getDefault())
    return sdf.format(Date(timestamp))
}

// --- 5. UI Components (Jetpack Compose) ---

/**
 * Main screen Composable for displaying transaction details.
 *
 * @param transactionId The ID of the transaction to display.
 * @param viewModel The ViewModel instance.
 * @param onBackClicked Action to perform when the back button is clicked.
 */
@Composable
fun TransactionDetailsScreen(
    transactionId: String,
    viewModel: TransactionDetailsViewModel = viewModel(
        factory = TransactionDetailsViewModelFactory(MockTransactionRepository(), transactionId)
    ),
    onBackClicked: () -> Unit = {}
) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current

    // Handle Biometric Authentication requirement
    if (uiState.isBiometricAuthRequired) {
        // In a real app, this would launch a BiometricPrompt dialog
        // For simplicity, we simulate success immediately in this mock
        LaunchedEffect(Unit) {
            // Placeholder for actual BiometricPrompt launch
            Toast.makeText(context, "Biometric Auth Prompted (Simulated)", Toast.LENGTH_SHORT).show()
            // Simulate success after a short delay
            kotlinx.coroutines.delay(500)
            viewModel.onBiometricAuthSuccess(context)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Transaction Details") },
                navigationIcon = {
                    IconButton(onClick = onBackClicked) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.back_button_desc) // Assuming resource exists
                        )
                    }
                }
            )
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            when {
                uiState.isLoading -> LoadingState()
                uiState.error != null -> ErrorState(uiState.error, viewModel::clearError)
                uiState.transaction != null -> {
                    TransactionDetailsContent(
                        transaction = uiState.transaction,
                        onGenerateReceiptClicked = viewModel::startReceiptGeneration,
                        onGatewayActionClicked = viewModel::triggerBiometricAuth,
                        isReceiptGenerating = uiState.isReceiptGenerating,
                        isOffline = uiState.isOffline
                    )
                }
                else -> EmptyState()
            }
        }
    }
}

/**
 * Displays the main content of the transaction details.
 */
@Composable
fun TransactionDetailsContent(
    transaction: Transaction,
    onGenerateReceiptClicked: () -> Unit,
    onGatewayActionClicked: () -> Unit,
    isReceiptGenerating: Boolean,
    isOffline: Boolean
) {
    val scrollState = rememberScrollState()
    val context = LocalContext.current
    val view = LocalView.current // Used for capturing the composable

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(scrollState)
            .padding(16.dp)
            .semantics(mergeDescendants = true) {} // Merge all content for TalkBack
    ) {
        // Status Card
        StatusCard(transaction.status, isOffline)
        Spacer(modifier = Modifier.height(16.dp))

        // Receipt Content Area (The part we want to capture)
        ReceiptContent(transaction)

        Spacer(modifier = Modifier.height(24.dp))

        // Action Buttons
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            // Generate Receipt Button
            Button(
                onClick = onGenerateReceiptClicked,
                enabled = !isReceiptGenerating,
                modifier = Modifier.weight(1f).height(48.dp)
            ) {
                if (isReceiptGenerating) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(24.dp),
                        color = MaterialTheme.colorScheme.onPrimary,
                        strokeWidth = 2.dp
                    )
                } else {
                    Icon(Icons.Default.Receipt, contentDescription = "Generate Receipt")
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Generate Receipt")
                }
            }
            Spacer(modifier = Modifier.width(16.dp))

            // Payment Gateway Action Button (e.g., Re-attempt, Dispute)
            OutlinedButton(
                onClick = onGatewayActionClicked,
                modifier = Modifier.weight(1f).height(48.dp)
            ) {
                Icon(Icons.Default.Payment, contentDescription = "Payment Action")
                Spacer(modifier = Modifier.width(8.dp))
                Text("Re-attempt")
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Receipt Path Display (if generated)
        if (transaction.receiptPath != null) {
            Text(
                text = "Receipt saved to: ${transaction.receiptPath}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.secondary,
                modifier = Modifier.padding(vertical = 8.dp)
            )
        }

        // Biometric Auth Note for TalkBack
        Text(
            text = "Sensitive actions require biometric authentication.",
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.semantics { contentDescription = "Security note: Sensitive actions require biometric authentication." }
        )
    }
}

/**
 * Displays the core transaction details in a receipt-like format.
 */
@Composable
fun ReceiptContent(transaction: Transaction) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            // Header
            Text(
                text = "Transaction Receipt",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.align(Alignment.CenterHorizontally)
            )
            Spacer(modifier = Modifier.height(16.dp))
            Divider()
            Spacer(modifier = Modifier.height(16.dp))

            // Main Amount
            Text(
                text = "${transaction.currency} ${"%.2f".format(transaction.amount)}",
                style = MaterialTheme.typography.displaySmall,
                fontWeight = FontWeight.ExtraBold,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier
                    .align(Alignment.CenterHorizontally)
                    .semantics { contentDescription = "Amount: ${transaction.amount} ${transaction.currency}" }
            )
            Spacer(modifier = Modifier.height(24.dp))

            // Details List
            DetailRow("Reference", transaction.reference)
            DetailRow("Date & Time", formatTimestamp(transaction.timestamp))
            DetailRow("Sender", transaction.senderName)
            DetailRow("Recipient", transaction.recipientName)
            DetailRow("Gateway", transaction.paymentGateway.name)
            DetailRow("Fee", "${transaction.currency} ${"%.2f".format(transaction.fee)}")
            DetailRow("Exchange Rate", "%.4f".format(transaction.exchangeRate))
        }
    }
}

/**
 * A single row for displaying a detail item.
 */
@Composable
fun DetailRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.semantics { contentDescription = label }
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.semantics { contentDescription = value }
        )
    }
}

/**
 * Displays the transaction status in a colored chip.
 */
@Composable
fun StatusCard(status: TransactionStatus, isOffline: Boolean) {
    val (color, text, icon) = when (status) {
        TransactionStatus.SUCCESS -> Triple(Color(0xFF4CAF50), "Successful", Icons.Default.CheckCircle)
        TransactionStatus.PENDING -> Triple(Color(0xFFFFC107), "Pending", Icons.Default.Schedule)
        TransactionStatus.FAILED -> Triple(Color(0xFFF44336), "Failed", Icons.Default.Error)
        TransactionStatus.REFUNDED -> Triple(Color(0xFF2196F3), "Refunded", Icons.Default.Refresh)
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.1f)),
        border = BorderStroke(1.dp, color.copy(alpha = 0.5f))
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    icon,
                    contentDescription = "$text transaction status",
                    tint = color,
                    modifier = Modifier.size(24.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "$text Transaction",
                    color = color,
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp
                )
            }
            if (isOffline) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Default.CloudOff,
                        contentDescription = "Offline Mode",
                        tint = MaterialTheme.colorScheme.error,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = "Offline",
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.labelMedium
                    )
                }
            }
        }
    }
}

/**
 * Displays a loading indicator.
 */
@Composable
fun LoadingState() {
    Column(
        modifier = Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        CircularProgressIndicator(
            modifier = Modifier.semantics { contentDescription = "Loading transaction details" }
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text("Loading details...", style = MaterialTheme.typography.bodyLarge)
    }
}

/**
 * Displays an error message and a retry button.
 */
@Composable
fun ErrorState(message: String, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Error") },
        text = { Text(message) },
        confirmButton = {
            Button(onClick = onDismiss) {
                Text("Dismiss")
            }
        },
        modifier = Modifier.semantics { contentDescription = "Error dialog: $message" }
    )
}

/**
 * Displays an empty state when no transaction is found.
 */
@Composable
fun EmptyState() {
    Column(
        modifier = Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            Icons.Default.SearchOff,
            contentDescription = "No transaction found",
            modifier = Modifier.size(48.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text("Transaction not found.", style = MaterialTheme.typography.titleMedium)
    }
}

// --- 6. Preview ---

@Preview(showBackground = true)
@Composable
fun PreviewTransactionDetailsScreen() {
    // Mocking the screen with a dummy ID.
    // In a real app, you'd wrap this in your app's theme.
    MaterialTheme {
        TransactionDetailsScreen(transactionId = "TXN-12345")
    }
}

// --- 7. Dependencies and Resources (For documentation) ---

/*
 * Dependencies required for this screen:
 *
 * // Jetpack Compose & Material 3
 * implementation("androidx.compose.ui:ui")
 * implementation("androidx.compose.material3:material3")
 * implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0")
 *
 * // Coroutines & Flow
 * implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
 * implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
 *
 * // Retrofit (for real implementation)
 * implementation("com.squareup.retrofit2:retrofit:2.9.0")
 * implementation("com.squareup.retrofit2:converter-gson:2.9.0")
 *
 * // Room (for real implementation - Offline Mode)
 * implementation("androidx.room:room-runtime:2.6.1")
 * annotationProcessor("androidx.room:room-compiler:2.6.1")
 * // To use Kotlin annotation processing tool (kapt)
 * kapt("androidx.room:room-compiler:2.6.1")
 * implementation("androidx.room:room-ktx:2.6.1")
 *
 * // Biometrics
 * implementation("androidx.biometric:biometric-ktx:1.2.0-alpha05")
 *
 * // Payment Gateways (Placeholders for real SDKs)
 * // implementation("com.paystack:paystack-android:x.y.z")
 * // implementation("com.flutterwave.rave:rave-android:x.y.z")
 * // implementation("com.interswitch.payment:interswitch-sdk:x.y.z")
 *
 * // Resource strings assumed to exist:
 * // R.string.back_button_desc = "Back"
 */

/*
 * Features Implemented:
 * - Jetpack Compose UI (Material Design 3)
 * - MVVM Architecture (ViewModel, Repository)
 * - State Management (StateFlow)
 * - Data Models (Transaction, TransactionStatus, PaymentGateway)
 * - Mock Repository (Simulates Retrofit/Room integration)
 * - Loading and Error States (CircularProgressIndicator, AlertDialog)
 * - Receipt Generation Logic (Simulated UI capture to Bitmap/File)
 * - Biometric Authentication Trigger (Simulated BiometricPrompt launch)
 * - Offline Mode Indicator (StatusCard)
 * - Payment Gateway Action (Simulated re-attempt)
 * - Accessibility (Semantics for TalkBack)
 * - Proper documentation and comments
 */

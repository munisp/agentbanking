package com.pos54link.screens

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Color
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.zxing.BarcodeFormat
import com.google.zxing.qrcode.QRCodeWriter
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.util.UUID

// --- 1. Data Models and State Management ---

/**
 * Data class representing the user's account details for receiving money.
 */
data class AccountDetails(
    val accountName: String,
    val accountNumber: String,
    val bankName: String,
    val qrCodeData: String // Data to be encoded in the QR code
)

/**
 * Sealed class to represent the different states of the Receive Money screen.
 */
sealed class ReceiveMoneyState {
    object Loading : ReceiveMoneyState()
    data class Success(val details: AccountDetails) : ReceiveMoneyState()
    data class Error(val message: String) : ReceiveMoneyState()
    object Initial : ReceiveMoneyState()
}

/**
 * Sealed class to represent one-time events from the ViewModel to the UI.
 */
sealed class ReceiveMoneyEvent {
    data class ShowToast(val message: String) : ReceiveMoneyEvent()
    object TriggerBiometricPrompt : ReceiveMoneyEvent()
    object ShowShareSheet : ReceiveMoneyEvent()
}

// --- 2. Repository Pattern (Data Layer) ---

/**
 * Interface for the data layer, abstracting data sources (API, DB).
 */
interface ReceiveMoneyRepository {
    suspend fun fetchAccountDetails(): Result<AccountDetails>
    suspend fun saveAccountDetailsLocally(details: AccountDetails)
}

/**
 * Mock implementation of the Repository.
 * In a real app, this would handle Retrofit calls and Room database operations.
 */
class ReceiveMoneyRepositoryImpl : ReceiveMoneyRepository {
    // Mock data for demonstration
    private val mockAccountDetails = AccountDetails(
        accountName = "Aisha Bello",
        accountNumber = "0123456789",
        bankName = "First Nigerian Bank (FNB)",
        qrCodeData = "REMITTANCE|0123456789|FNB|AISHA_BELLO"
    )

    /**
     * Simulates fetching account details from a remote API (Retrofit).
     * Includes mock loading and error states.
     */
    override suspend fun fetchAccountDetails(): Result<AccountDetails> = withContext(Dispatchers.IO) {
        // Simulate network delay
        delay(1500)

        // Simulate success
        return@withContext Result.success(mockAccountDetails)

        // Uncomment to simulate error:
        // return@withContext Result.failure(Exception("Failed to fetch account details from server."))
    }

    /**
     * Simulates saving account details to a local database (Room).
     */
    override suspend fun saveAccountDetailsLocally(details: AccountDetails) = withContext(Dispatchers.IO) {
        // In a real app, this would be a Room DAO call:
        // accountDao.insert(details.toEntity())
        println("Room: Account details saved locally: ${details.accountNumber}")
    }
}

// --- 3. ViewModel (Presentation Layer) ---

class ReceiveMoneyViewModel(
    private val repository: ReceiveMoneyRepository = ReceiveMoneyRepositoryImpl()
) : ViewModel() {

    private val _state = MutableStateFlow<ReceiveMoneyState>(ReceiveMoneyState.Initial)
    val state: StateFlow<ReceiveMoneyState> = _state.asStateFlow()

    private val _event = MutableStateFlow<ReceiveMoneyEvent?>(null)
    val event: StateFlow<ReceiveMoneyEvent?> = _event.asStateFlow()

    init {
        loadAccountDetails()
    }

    /**
     * Fetches account details from the repository.
     */
    fun loadAccountDetails() {
        viewModelScope.launch {
            _state.value = ReceiveMoneyState.Loading
            val result = repository.fetchAccountDetails()

            result.onSuccess { details ->
                _state.value = ReceiveMoneyState.Success(details)
                // Offline mode integration: save successful fetch to local DB
                repository.saveAccountDetailsLocally(details)
            }.onFailure { e ->
                // Error handling: try to load from local DB if network fails
                // In a real app, this would be a separate Room call
                val localDetails = loadLocalAccountDetails()
                if (localDetails != null) {
                    _state.value = ReceiveMoneyState.Success(localDetails)
                    _event.value = ReceiveMoneyEvent.ShowToast("Network failed. Showing offline data.")
                } else {
                    _state.value = ReceiveMoneyState.Error(e.message ?: "An unknown error occurred.")
                }
            }
        }
    }

    /**
     * Mock function to simulate loading from Room database.
     */
    private suspend fun loadLocalAccountDetails(): AccountDetails? {
        // In a real app, this would be a Room DAO call:
        // return accountDao.getAccountDetails()?.toDomain()
        return null // For now, assume no local data on first load failure
    }

    /**
     * Handles the share action, first requiring biometric authentication for security.
     */
    fun onShareClicked() {
        // Biometric integration: Trigger prompt before sensitive action
        _event.value = ReceiveMoneyEvent.TriggerBiometricPrompt
    }

    /**
     * Called after successful biometric authentication.
     */
    fun onBiometricSuccess() {
        _event.value = ReceiveMoneyEvent.ShowShareSheet
    }

    /**
     * Called when the copy button is clicked.
     */
    fun onCopyClicked(text: String) {
        // In a real app, this would copy to clipboard
        _event.value = ReceiveMoneyEvent.ShowToast("Copied: $text")
    }

    /**
     * Consumes the one-time event.
     */
    fun consumeEvent() {
        _event.value = null
    }
}

// --- 4. Utility Functions ---

/**
 * Generates a QR code Bitmap from a string.
 */
fun generateQrCodeBitmap(content: String, size: Int = 512): Bitmap {
    val writer = QRCodeWriter()
    val bitMatrix = writer.encode(content, BarcodeFormat.QR_CODE, size, size)
    val width = bitMatrix.width
    val height = bitMatrix.height
    val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.RGB_565)
    for (x in 0 until width) {
        for (y in 0 until height) {
            bitmap.setPixel(x, y, if (bitMatrix.get(x, y)) Color.BLACK else Color.WHITE)
        }
    }
    return bitmap
}

/**
 * Saves a Bitmap to a temporary file and returns its Uri for sharing.
 */
fun saveBitmapToTempFile(context: Context, bitmap: Bitmap): Uri? {
    val cachePath = File(context.cacheDir, "images")
    cachePath.mkdirs()
    val file = File(cachePath, "${UUID.randomUUID()}.png")
    return try {
        val stream = FileOutputStream(file)
        bitmap.compress(Bitmap.CompressFormat.PNG, 100, stream)
        stream.close()
        Uri.fromFile(file)
    } catch (e: Exception) {
        e.printStackTrace()
        null
    }
}

// --- 5. Composable UI Components ---

@Composable
fun QrCodeDisplay(qrCodeData: String) {
    val bitmap by produceState<Bitmap?>(initialValue = null, qrCodeData) {
        value = withContext(Dispatchers.Default) {
            generateQrCodeBitmap(qrCodeData)
        }
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
    ) {
        Column(
            modifier = Modifier.padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = "Scan to Pay",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(bottom = 16.dp)
            )
            if (bitmap != null) {
                Image(
                    bitmap = bitmap!!.asImageBitmap(),
                    contentDescription = "QR Code for payment",
                    modifier = Modifier.size(200.dp)
                )
            } else {
                CircularProgressIndicator(modifier = Modifier.size(200.dp))
            }
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "This QR code contains your account details.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
fun AccountDetailsCard(details: AccountDetails, onCopyClicked: (String) -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            DetailRow(label = "Account Name", value = details.accountName, onCopyClicked = onCopyClicked)
            Divider(modifier = Modifier.padding(vertical = 8.dp))
            DetailRow(label = "Bank Name", value = details.bankName, onCopyClicked = onCopyClicked)
            Divider(modifier = Modifier.padding(vertical = 8.dp))
            DetailRow(label = "Account Number", value = details.accountNumber, onCopyClicked = onCopyClicked)
        }
    }
}

@Composable
fun DetailRow(label: String, value: String, onCopyClicked: (String) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column {
            Text(
                text = label,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                text = value,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium,
                modifier = Modifier.padding(top = 2.dp)
            )
        }
        IconButton(onClick = { onCopyClicked(value) }) {
            Icon(
                Icons.Default.ContentCopy,
                contentDescription = "Copy $label",
                tint = MaterialTheme.colorScheme.primary
            )
        }
    }
}

@Composable
fun ShareButton(onClick: () -> Unit) {
    Button(
        onClick = onClick,
        modifier = Modifier
            .fillMaxWidth()
            .height(56.dp)
            .padding(horizontal = 16.dp),
        contentPadding = PaddingValues(16.dp)
    ) {
        Icon(Icons.Default.Share, contentDescription = null)
        Spacer(modifier = Modifier.width(8.dp))
        Text("Share Account Details")
    }
}

@Composable
fun PaymentGatewayInfo() {
    Column(modifier = Modifier.padding(16.dp)) {
        Text(
            text = "Supported Payment Gateways",
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(bottom = 8.dp)
        )
        // Stub for payment gateway support
        Text(
            text = "Payments can be received via Paystack, Flutterwave, and Interswitch.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

// --- 6. Main Screen Composable ---

@Composable
fun ReceiveMoneyScreen(viewModel: ReceiveMoneyViewModel = androidx.lifecycle.viewmodel.compose.viewModel()) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    // Biometric Prompt Stub (Requires a FragmentActivity context in a real app)
    // For simplicity in a single file, we'll simulate the success callback.
    // In a real app, you'd use BiometricPrompt and handle the result in the Activity/Fragment.
    val showBiometricPrompt = remember { mutableStateOf(false) }

    // Share Launcher
    val shareLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) { /* Nothing to do on result */ }

    // Event Collector
    LaunchedEffect(Unit) {
        viewModel.event.collect { event ->
            when (event) {
                is ReceiveMoneyEvent.ShowToast -> {
                    scope.launch {
                        snackbarHostState.showSnackbar(event.message)
                    }
                }
                is ReceiveMoneyEvent.TriggerBiometricPrompt -> {
                    // In a real app, this would launch the BiometricPrompt.
                    // For this single file, we simulate success after a short delay.
                    showBiometricPrompt.value = true
                    scope.launch {
                        delay(500) // Simulate prompt time
                        viewModel.onBiometricSuccess()
                        showBiometricPrompt.value = false
                    }
                }
                is ReceiveMoneyEvent.ShowShareSheet -> {
                    if (state is ReceiveMoneyState.Success) {
                        val details = (state as ReceiveMoneyState.Success).details
                        val shareText = "Receive money from ${details.accountName} via:\n" +
                                "Bank: ${details.bankName}\n" +
                                "Account Number: ${details.accountNumber}\n" +
                                "QR Code Data: ${details.qrCodeData}"

                        // Generate QR code image for sharing
                        val qrBitmap = generateQrCodeBitmap(details.qrCodeData)
                        val imageUri = saveBitmapToTempFile(context, qrBitmap)

                        val shareIntent = Intent().apply {
                            action = Intent.ACTION_SEND
                            putExtra(Intent.EXTRA_TEXT, shareText)
                            if (imageUri != null) {
                                putExtra(Intent.EXTRA_STREAM, imageUri)
                                type = "image/png"
                                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                            } else {
                                type = "text/plain"
                            }
                        }
                        shareLauncher.launch(Intent.createChooser(shareIntent, "Share Account Details"))
                    }
                }
                null -> {}
            }
            viewModel.consumeEvent()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("Receive Money") })
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .verticalScroll(rememberScrollState()),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            when (state) {
                ReceiveMoneyState.Loading -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(Modifier.size(48.dp))
                    }
                }
                is ReceiveMoneyState.Success -> {
                    val details = (state as ReceiveMoneyState.Success).details
                    
                    // 1. QR Code Display
                    QrCodeDisplay(qrCodeData = details.qrCodeData)
                    
                    Spacer(modifier = Modifier.height(16.dp))

                    // 2. Account Details
                    AccountDetailsCard(details = details, onCopyClicked = viewModel::onCopyClicked)

                    Spacer(modifier = Modifier.height(24.dp))

                    // 3. Share Functionality
                    ShareButton(onClick = viewModel::onShareClicked)

                    Spacer(modifier = Modifier.height(16.dp))

                    // 4. Payment Gateway Info Stub
                    PaymentGatewayInfo()

                    // Accessibility Note: All composables use proper content descriptions and Material 3 semantics.
                }
                is ReceiveMoneyState.Error -> {
                    Column(
                        modifier = Modifier.fillMaxSize().padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        Text(
                            text = "Error: ${(state as ReceiveMoneyState.Error).message}",
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.titleMedium
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(onClick = viewModel::loadAccountDetails) {
                            Text("Retry Load")
                        }
                    }
                }
                ReceiveMoneyState.Initial -> {
                    // Initial state, will quickly transition to Loading
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text("Initializing...")
                    }
                }
            }
        }
    }
}

// --- 7. Preview ---

@Preview(showBackground = true)
@Composable
fun PreviewReceiveMoneyScreen() {
    // Note: In a real preview, you would provide a mock ViewModel instance
    // with a predefined state for better previewing.
    // Since this is a single file, we rely on the default ViewModel which loads data.
    MaterialTheme {
        ReceiveMoneyScreen(viewModel = ReceiveMoneyViewModel(ReceiveMoneyRepositoryImpl()))
    }
}

/*
 * Documentation and Comments:
 *
 * This file implements the ReceiveMoneyScreen using Jetpack Compose and the MVVM pattern.
 *
 * Architecture:
 * - UI: ReceiveMoneyScreen and supporting composables. Observes StateFlow from ViewModel.
 * - ViewModel: ReceiveMoneyViewModel. Manages UI state (ReceiveMoneyState) and one-time events (ReceiveMoneyEvent).
 * - Repository: ReceiveMoneyRepository (interface) and ReceiveMoneyRepositoryImpl (mock implementation).
 *   - Retrofit Integration: Simulated in ReceiveMoneyRepositoryImpl.fetchAccountDetails().
 *   - Room Integration (Offline Mode): Simulated in ReceiveMoneyRepositoryImpl.saveAccountDetailsLocally() and ViewModel's error handling.
 *
 * Key Features Implemented:
 * - QR Code Display: Uses generateQrCodeBitmap utility with zxing logic.
 * - Account Details: Displayed in AccountDetailsCard with a copy function stub.
 * - Share Functionality: Triggered by ShareButton, requires biometric authentication first.
 * - Biometric Authentication: Simulated via ReceiveMoneyEvent.TriggerBiometricPrompt and a delayed success callback.
 * - Error Handling/Loading: Managed by ReceiveMoneyState sealed class.
 * - Payment Gateways: Mentioned in PaymentGatewayInfo composable (stub).
 * - Material Design 3: Uses Material3 components (Card, Button, TopAppBar, etc.).
 * - Accessibility: Implemented via proper content descriptions (e.g., in Image and Icon composables).
 *
 * Dependencies required (to be added to build.gradle.kts (app)):
 * - androidx.compose.ui:ui
 * - androidx.compose.material3:material3
 * - androidx.lifecycle:lifecycle-viewmodel-compose
 * - androidx.lifecycle:lifecycle-runtime-ktx
 * - com.google.zxing:core (for QR code generation)
 * - androidx.activity:activity-compose
 * - kotlinx.coroutines:kotlinx-coroutines-core
 * - kotlinx.coroutines:kotlinx-coroutines-android
 * - com.squareup.retrofit2:retrofit (for real API calls)
 * - androidx.room:room-runtime (for real offline mode)
 * - androidx.biometric:biometric-ktx (for real biometric prompt)
 */

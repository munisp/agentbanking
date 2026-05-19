package com.pos54link.screens

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.net.Uri
import android.provider.MediaStore
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.room.*
import com.pos54link.R // Assuming R.string.kyc_title, R.string.upload_document, etc. are defined
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*
import java.io.File
import java.io.IOException

// --- 1. Data Layer Models (Entities, DTOs) ---

/**
 * Represents the status of the KYC verification process.
 */
enum class VerificationStatus {
    PENDING,
    IN_REVIEW,
    VERIFIED,
    REJECTED
}

/**
 * Represents a document type for KYC.
 */
enum class DocumentType(val displayName: String) {
    PASSPORT("International Passport"),
    DRIVERS_LICENSE("Driver's License"),
    NIN_SLIP("NIN Slip"),
    VOTERS_CARD("Voter's Card")
}

/**
 * Room Entity for storing KYC status locally (Offline Mode).
 */
@Entity(tableName = "kyc_status")
data class KycStatusEntity(
    @PrimaryKey val userId: String,
    val status: VerificationStatus,
    val lastUpdated: Long
)

/**
 * Data Transfer Object for API response.
 */
data class KycStatusDto(
    val status: String,
    val message: String,
    val requiredDocuments: List<String>? = null
)

/**
 * Data class for UI state management.
 */
data class KycState(
    val isLoading: Boolean = false,
    val status: VerificationStatus = VerificationStatus.PENDING,
    val statusMessage: String = "Please upload your documents to start verification.",
    val error: String? = null,
    val selectedDocumentType: DocumentType = DocumentType.PASSPORT,
    val documentUri: Uri? = null,
    val documentBitmap: Bitmap? = null,
    val isDocumentValid: Boolean = true,
    val validationError: String? = null,
    val isBiometricAuthRequired: Boolean = false,
    val paymentGatewayStatus: String = "Not Integrated"
)

// --- 2. Data Layer (API Service, Room DAO, Repository) ---

/**
 * Retrofit API Service Interface for KYC operations.
 */
interface KycApiService {
    @Multipart
    @POST("kyc/upload")
    suspend fun uploadDocument(
        @Part("document_type") documentType: String,
        @Part("file\"; filename=\"document.jpg\"") file: File
    ): KycStatusDto

    @GET("kyc/status")
    suspend fun getKycStatus(): KycStatusDto
}

/**
 * Room Data Access Object (DAO) for KYC status.
 */
@Dao
interface KycDao {
    @Query("SELECT * FROM kyc_status WHERE userId = :userId")
    fun getKycStatus(userId: String): Flow<KycStatusEntity?>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertKycStatus(status: KycStatusEntity)
}

/**
 * Room Database (Stub).
 */
@Database(entities = [KycStatusEntity::class], version = 1)
abstract class KycDatabase : RoomDatabase() {
    abstract fun kycDao(): KycDao
}

/**
 * Repository to handle data operations (API and Local DB).
 */
class KycRepository(
    private val apiService: KycApiService,
    private val kycDao: KycDao,
    private val userId: String = "user_123" // Placeholder
) {
    /**
     * Fetches KYC status from the network and caches it locally.
     */
    fun getKycStatusStream(): Flow<KycStatusEntity?> = kycDao.getKycStatus(userId)

    suspend fun refreshKycStatus() {
        try {
            val response = apiService.getKycStatus()
            val status = KycStatusEntity(
                userId = userId,
                status = VerificationStatus.valueOf(response.status.uppercase()),
                lastUpdated = System.currentTimeMillis()
            )
            kycDao.insertKycStatus(status)
        } catch (e: Exception) {
            // Handle network error, rely on cached data
            throw e
        }
    }

    suspend fun uploadDocument(documentType: DocumentType, file: File): KycStatusDto {
        return apiService.uploadDocument(documentType.name, file)
    }
}

// --- 3. ViewModel ---

class KYCVerificationViewModel(
    private val repository: KycRepository
) : ViewModel() {

    // State management with StateFlow
    private val _state = MutableStateFlow(KycState())
    val state: StateFlow<KycState> = _state.asStateFlow()

    init {
        // Observe local database for offline mode and status tracking
        viewModelScope.launch {
            repository.getKycStatusStream().collect { entity ->
                _state.update { currentState ->
                    currentState.copy(
                        status = entity?.status ?: VerificationStatus.PENDING,
                        statusMessage = when (entity?.status) {
                            VerificationStatus.VERIFIED -> "Your identity has been successfully verified."
                            VerificationStatus.IN_REVIEW -> "Your documents are currently under review."
                            VerificationStatus.REJECTED -> "Verification failed. Please re-upload documents."
                            else -> "Please upload your documents to start verification."
                        }
                    )
                }
            }
        }
        // Initial status refresh
        refreshStatus()
    }

    fun refreshStatus() {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, error = null) }
            try {
                repository.refreshKycStatus()
            } catch (e: Exception) {
                _state.update { it.copy(error = "Failed to fetch status: ${e.message}") }
            } finally {
                _state.update { it.copy(isLoading = false) }
            }
        }
    }

    fun onDocumentTypeSelected(type: DocumentType) {
        _state.update { it.copy(selectedDocumentType = type) }
    }

    fun onDocumentSelected(uri: Uri?, bitmap: Bitmap?) {
        _state.update { it.copy(documentUri = uri, documentBitmap = bitmap) }
        validateDocument(uri)
    }

    private fun validateDocument(uri: Uri?) {
        val isValid = uri != null // Simple validation: check if a file is selected
        _state.update {
            it.copy(
                isDocumentValid = isValid,
                validationError = if (isValid) null else "Please select a document to upload."
            )
        }
    }

    fun uploadDocument(context: Context) {
        val currentUri = _state.value.documentUri
        val currentType = _state.value.selectedDocumentType

        if (currentUri == null) {
            _state.update { it.copy(validationError = "No document selected for upload.") }
            return
        }

        _state.update { it.copy(isLoading = true, error = null) }

        viewModelScope.launch {
            try {
                // In a real app, you'd convert the Uri to a File or use a ContentResolver to get an InputStream
                // For this stub, we'll simulate file creation from the Uri (not production ready)
                val file = File(context.cacheDir, "kyc_doc_${System.currentTimeMillis()}.jpg")
                // In a real app, copy content from currentUri to 'file'
                // For now, we just use a placeholder file
                file.createNewFile()

                val response = repository.uploadDocument(currentType, file)
                // Update local status based on API response
                repository.refreshKycStatus()

                _state.update {
                    it.copy(
                        statusMessage = response.message,
                        documentUri = null,
                        documentBitmap = null
                    )
                }
            } catch (e: HttpException) {
                _state.update { it.copy(error = "Upload failed: ${e.response()?.errorBody()?.string()}") }
            } catch (e: IOException) {
                _state.update { it.copy(error = "Network error: ${e.message}") }
            } catch (e: Exception) {
                _state.update { it.copy(error = "An unexpected error occurred: ${e.message}") }
            } finally {
                _state.update { it.copy(isLoading = false) }
            }
        }
    }

    // Stub for Biometric Authentication
    fun triggerBiometricAuth() {
        _state.update { it.copy(isBiometricAuthRequired = true) }
        // Real implementation would involve a BiometricPrompt setup in the Activity/Fragment
    }

    fun onBiometricAuthComplete(success: Boolean) {
        _state.update { it.copy(isBiometricAuthRequired = false) }
        if (success) {
            // Proceed with sensitive action, e.g., final submission
            _state.update { it.copy(statusMessage = "Biometric authentication successful. Finalizing submission...") }
        } else {
            _state.update { it.copy(error = "Biometric authentication failed or cancelled.") }
        }
    }

    // Stub for Payment Gateway Integration
    fun initiatePayment(gateway: String) {
        _state.update { it.copy(paymentGatewayStatus = "Initiating payment via $gateway...") }
        // Real implementation would launch the payment gateway SDK/Activity
        viewModelScope.launch {
            kotlinx.coroutines.delay(2000) // Simulate payment process
            _state.update { it.copy(paymentGatewayStatus = "Payment via $gateway simulated successfully.") }
        }
    }
}

// --- 4. UI Layer (Composable) ---

/**
 * Mock dependency injection setup for the screen.
 * In a real app, this would use Hilt/Koin.
 */
object Injection {
    private val retrofit = Retrofit.Builder()
        .baseUrl("https://api.remittance.com/") // Placeholder URL
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    private val apiService = retrofit.create(KycApiService::class.java)

    // Mock database for simplicity in this single file
    private val mockDao = object : KycDao {
        private val statusFlow = MutableStateFlow<KycStatusEntity?>(null)
        override fun getKycStatus(userId: String): Flow<KycStatusEntity?> = statusFlow
        override suspend fun insertKycStatus(status: KycStatusEntity) {
            statusFlow.value = status
        }
    }

    val repository = KycRepository(apiService, mockDao)

    fun provideViewModel(): KYCVerificationViewModel {
        return KYCVerificationViewModel(repository)
    }
}

@Composable
fun KYCVerificationScreen(
    viewModel: KYCVerificationViewModel = Injection.provideViewModel()
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current

    // Permission and Camera/Gallery Launchers
    val cameraPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted: Boolean ->
        if (isGranted) {
            // Permission granted, launch camera
            // Note: Launching camera requires a separate contract/launcher
        } else {
            // Permission denied
            viewModel.onDocumentSelected(null, null)
            viewModel.onBiometricAuthComplete(false) // Use a dedicated error state for permissions
        }
    }

    val cameraLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.TakePicturePreview()
    ) { bitmap: Bitmap? ->
        viewModel.onDocumentSelected(null, bitmap) // Using bitmap directly for simplicity
    }

    val galleryLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        // In a real app, you'd handle the Uri to get a File or Bitmap
        viewModel.onDocumentSelected(uri, null)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(text = stringResource(id = R.string.kyc_title)) },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer
                )
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .padding(paddingValues)
                .padding(16.dp)
                .verticalScroll(rememberScrollState())
                .fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // 1. Status Tracking
            StatusCard(state = state, onRefresh = viewModel::refreshStatus)
            Spacer(modifier = Modifier.height(24.dp))

            // 2. Document Upload Section
            DocumentUploadSection(
                state = state,
                onDocumentTypeSelected = viewModel::onDocumentTypeSelected,
                onUploadClicked = { viewModel.uploadDocument(context) },
                onCameraClicked = {
                    if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                        cameraLauncher.launch(null)
                    } else {
                        cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
                    }
                },
                onGalleryClicked = { galleryLauncher.launch("image/*") }
            )
            Spacer(modifier = Modifier.height(24.dp))

            // 3. Biometric Authentication (Example of a required step)
            BiometricAuthSection(
                state = state,
                onTriggerAuth = viewModel::triggerBiometricAuth
            )
            Spacer(modifier = Modifier.height(24.dp))

            // 4. Payment Gateway Stubs
            PaymentGatewaySection(
                state = state,
                onInitiatePayment = viewModel::initiatePayment
            )
        }
    }

    // Handle Biometric Prompt (requires Activity context, stubbed here)
    if (state.isBiometricAuthRequired) {
        AlertDialog(
            onDismissRequest = { viewModel.onBiometricAuthComplete(false) },
            title = { Text("Biometric Authentication") },
            text = { Text("Please use your fingerprint or face to authenticate the final submission.") },
            confirmButton = {
                Button(onClick = { viewModel.onBiometricAuthComplete(true) }) {
                    Text("Authenticate (Stub)")
                }
            },
            dismissButton = {
                TextButton(onClick = { viewModel.onBiometricAuthComplete(false) }) {
                    Text("Cancel")
                }
            }
        )
    }

    // Handle Error Display
    state.error?.let { errorMessage ->
        LaunchedEffect(errorMessage) {
            // In a real app, use a SnackbarHostState
            println("Error: $errorMessage")
        }
    }
}

// --- Composable Sub-components ---

@Composable
fun StatusCard(state: KycState, onRefresh: () -> Unit) {
    val statusColor = when (state.status) {
        VerificationStatus.VERIFIED -> MaterialTheme.colorScheme.primary
        VerificationStatus.IN_REVIEW -> MaterialTheme.colorScheme.tertiary
        VerificationStatus.REJECTED -> MaterialTheme.colorScheme.error
        VerificationStatus.PENDING -> MaterialTheme.colorScheme.secondary
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .semantics { contentDescription = "KYC Status: ${state.status.name}" },
        colors = CardDefaults.cardColors(containerColor = statusColor.copy(alpha = 0.1f))
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Verification Status",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                if (state.isLoading) {
                    CircularProgressIndicator(Modifier.size(24.dp))
                } else {
                    IconButton(onClick = onRefresh) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh Status")
                    }
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = state.status.name,
                style = MaterialTheme.typography.headlineSmall,
                color = statusColor
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = state.statusMessage,
                style = MaterialTheme.typography.bodyMedium
            )
        }
    }
}

@Composable
fun DocumentUploadSection(
    state: KycState,
    onDocumentTypeSelected: (DocumentType) -> Unit,
    onUploadClicked: () -> Unit,
    onCameraClicked: () -> Unit,
    onGalleryClicked: () -> Unit
) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = "Document Upload",
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(bottom = 8.dp)
        )

        // Document Type Selection
        OutlinedTextField(
            value = state.selectedDocumentType.displayName,
            onValueChange = { /* Read-only for simplicity */ },
            label = { Text("Document Type") },
            readOnly = true,
            trailingIcon = { Icon(Icons.Default.ArrowDropDown, contentDescription = null) },
            modifier = Modifier.fillMaxWidth()
        )
        // In a real app, this would be a DropdownMenu or ModalBottomSheet

        Spacer(modifier = Modifier.height(16.dp))

        // Document Preview and Selection Buttons
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f))
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                if (state.documentBitmap != null) {
                    Image(
                        bitmap = state.documentBitmap.asImageBitmap(),
                        contentDescription = "Selected document preview",
                        modifier = Modifier
                            .size(120.dp)
                            .padding(8.dp)
                    )
                } else if (state.documentUri != null) {
                    Icon(
                        Icons.Default.Description,
                        contentDescription = "Document selected",
                        modifier = Modifier.size(64.dp),
                        tint = MaterialTheme.colorScheme.primary
                    )
                    Text("File Selected: ${state.documentUri.lastPathSegment}", style = MaterialTheme.typography.bodySmall)
                } else {
                    Icon(
                        Icons.Default.CloudUpload,
                        contentDescription = "No document selected",
                        modifier = Modifier.size(64.dp),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text("No document selected", style = MaterialTheme.typography.bodyMedium)
                }

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    horizontalArrangement = Arrangement.SpaceEvenly,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    OutlinedButton(onClick = onCameraClicked) {
                        Icon(Icons.Default.CameraAlt, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Take Photo")
                    }
                    OutlinedButton(onClick = onGalleryClicked) {
                        Icon(Icons.Default.PhotoLibrary, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Choose File")
                    }
                }
            }
        }

        // Validation Feedback
        if (!state.isDocumentValid) {
            Text(
                text = state.validationError ?: "Invalid document selected.",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 8.dp)
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Upload Button
        Button(
            onClick = onUploadClicked,
            enabled = state.documentUri != null && state.isDocumentValid && !state.isLoading,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(if (state.isLoading) "Uploading..." else "Upload Document")
        }
    }
}

@Composable
fun BiometricAuthSection(state: KycState, onTriggerAuth: () -> Unit) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = "Security Check",
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(bottom = 8.dp)
        )
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f))
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column(Modifier.weight(1f)) {
                    Text("Biometric Authentication", style = MaterialTheme.typography.titleMedium)
                    Text("Use fingerprint/face ID for secure submission.", style = MaterialTheme.typography.bodySmall)
                }
                Button(onClick = onTriggerAuth) {
                    Icon(Icons.Default.Fingerprint, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("Verify")
                }
            }
        }
    }
}

@Composable
fun PaymentGatewaySection(state: KycState, onInitiatePayment: (String) -> Unit) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = "Payment Gateway Integration (Stub)",
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(bottom = 8.dp)
        )
        Text(
            text = "Current Status: ${state.paymentGatewayStatus}",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(bottom = 8.dp)
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            PaymentButton("Paystack", { onInitiatePayment("Paystack") })
            PaymentButton("Flutterwave", { onInitiatePayment("Flutterwave") })
            PaymentButton("Interswitch", { onInitiatePayment("Interswitch") })
        }
    }
}

@Composable
fun RowScope.PaymentButton(name: String, onClick: () -> Unit) {
    OutlinedButton(
        onClick = onClick,
        modifier = Modifier.weight(1f).padding(horizontal = 4.dp)
    ) {
        Text(name, maxLines = 1)
    }
}

// --- Preview (Requires Android Studio environment, stubbed for completeness) ---
/*
@Preview(showBackground = true)
@Composable
fun PreviewKYCVerificationScreen() {
    KYCVerificationScreen()
}
*/

// --- Documentation and Comments ---
// The code follows MVVM architecture.
// State is managed via Kotlin Flow/StateFlow in the ViewModel.
// Data access is abstracted via KycRepository, which uses KycApiService (Retrofit stub) and KycDao (Room stub).
// Offline mode is supported by observing the KycDao in the ViewModel.
// UI uses Jetpack Compose and Material Design 3 components.
// Accessibility is partially addressed with `contentDescription` in Composable functions.
// Complex features (Camera, Biometrics, Payments) are implemented as functional stubs, demonstrating the integration points.
// Form validation is simple (checking for document selection) and can be extended in a production environment.

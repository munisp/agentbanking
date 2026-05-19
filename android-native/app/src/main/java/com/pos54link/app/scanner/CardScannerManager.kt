package com.pos54link.app.scanner

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlin.coroutines.suspendCoroutine

/**
 * Card information extracted from scanning
 */
data class ScannedCardInfo(
    val cardNumber: String? = null,
    val expiryDate: String? = null,
    val cardholderName: String? = null,
    val cvv: String? = null,
    val confidence: Float = 0f,
    val cardType: CardType = CardType.UNKNOWN
)

/**
 * Card types
 */
enum class CardType(val displayName: String) {
    VISA("Visa"),
    MASTERCARD("Mastercard"),
    AMEX("American Express"),
    DISCOVER("Discover"),
    UNKNOWN("Unknown")
}

/**
 * Card scanner manager using ML Kit Text Recognition
 */
class CardScannerManager(private val context: Context) {

    private val textRecognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
    private var cameraExecutor: ExecutorService = Executors.newSingleThreadExecutor()
    private var imageAnalyzer: ImageAnalysis? = null
    private var camera: Camera? = null
    
    private var isScanning = false
    private var scanCallback: ((Result<ScannedCardInfo>) -> Unit)? = null
    
    // Regex patterns
    private val cardNumberPattern = Regex("""(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4})""")
    private val expiryPattern = Regex("""(0[1-9]|1[0-2])[\/\-](\d{2}|\d{4})""")
    private val cvvPattern = Regex("""\b\d{3,4}\b""")
    
    companion object {
        private const val REQUIRED_PERMISSION = Manifest.permission.CAMERA
        
        fun hasCameraPermission(context: Context): Boolean {
            return ContextCompat.checkSelfPermission(
                context,
                REQUIRED_PERMISSION
            ) == PackageManager.PERMISSION_GRANTED
        }
    }
    
    /**
     * Check if device supports card scanning
     */
    fun isCardScanningSupported(): Boolean {
        return context.packageManager.hasSystemFeature(PackageManager.FEATURE_CAMERA_ANY)
    }
    
    /**
     * Setup camera for card scanning
     */
    suspend fun setupCamera(
        lifecycleOwner: LifecycleOwner,
        previewView: PreviewView
    ): Result<Unit> = suspendCoroutine { continuation ->
        val cameraProviderFuture = ProcessCameraProvider.getInstance(context)
        
        cameraProviderFuture.addListener({
            try {
                val cameraProvider = cameraProviderFuture.get()
                
                // Preview
                val preview = Preview.Builder()
                    .build()
                    .also {
                        it.setSurfaceProvider(previewView.surfaceProvider)
                    }
                
                // Image analyzer
                imageAnalyzer = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()
                    .also {
                        it.setAnalyzer(cameraExecutor) { imageProxy ->
                            processImageProxy(imageProxy)
                        }
                    }
                
                // Select back camera
                val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA
                
                try {
                    // Unbind all use cases before rebinding
                    cameraProvider.unbindAll()
                    
                    // Bind use cases to camera
                    camera = cameraProvider.bindToLifecycle(
                        lifecycleOwner,
                        cameraSelector,
                        preview,
                        imageAnalyzer
                    )
                    
                    continuation.resume(Result.success(Unit))
                } catch (e: Exception) {
                    continuation.resume(Result.failure(CardScannerException.CameraBindingFailed(e)))
                }
                
            } catch (e: Exception) {
                continuation.resume(Result.failure(CardScannerException.CameraSetupFailed(e)))
            }
        }, ContextCompat.getMainExecutor(context))
    }
    
    /**
     * Start scanning for card
     */
    fun startScanning(callback: (Result<ScannedCardInfo>) -> Unit) {
        isScanning = true
        scanCallback = callback
    }
    
    /**
     * Stop scanning
     */
    fun stopScanning() {
        isScanning = false
        scanCallback = null
    }
    
    /**
     * Scan image directly (for gallery images)
     */
    suspend fun scanImage(bitmap: Bitmap): Result<ScannedCardInfo> = withContext(Dispatchers.IO) {
        suspendCoroutine { continuation ->
            val image = InputImage.fromBitmap(bitmap, 0)
            
            textRecognizer.process(image)
                .addOnSuccessListener { visionText ->
                    val cardInfo = extractCardInfo(visionText.text)
                    
                    if (cardInfo.cardNumber != null) {
                        continuation.resume(Result.success(cardInfo))
                    } else {
                        continuation.resume(
                            Result.failure(CardScannerException.NoCardDetected)
                        )
                    }
                }
                .addOnFailureListener { e ->
                    continuation.resume(Result.failure(e))
                }
        }
    }
    
    /**
     * Process camera image proxy
     */
    @androidx.camera.core.ExperimentalGetImage
    private fun processImageProxy(imageProxy: ImageProxy) {
        if (!isScanning) {
            imageProxy.close()
            return
        }
        
        val mediaImage = imageProxy.image
        if (mediaImage != null) {
            val image = InputImage.fromMediaImage(
                mediaImage,
                imageProxy.imageInfo.rotationDegrees
            )
            
            textRecognizer.process(image)
                .addOnSuccessListener { visionText ->
                    val cardInfo = extractCardInfo(visionText.text)
                    
                    // Only return if we have high confidence card number
                    if (cardInfo.cardNumber != null && cardInfo.confidence > 0.7f) {
                        isScanning = false
                        scanCallback?.invoke(Result.success(cardInfo))
                    }
                }
                .addOnFailureListener { e ->
                    // Continue scanning on failure
                }
                .addOnCompleteListener {
                    imageProxy.close()
                }
        } else {
            imageProxy.close()
        }
    }
    
    /**
     * Extract card information from recognized text
     */
    private fun extractCardInfo(text: String): ScannedCardInfo {
        val lines = text.split("\n")
        
        val cardNumber = extractCardNumber(lines)
        val expiryDate = extractExpiryDate(lines)
        val cardholderName = extractCardholderName(lines)
        val cardType = cardNumber?.let { getCardType(it) } ?: CardType.UNKNOWN
        
        // Calculate confidence based on what we found
        var confidence = 0f
        if (cardNumber != null) confidence += 0.5f
        if (expiryDate != null) confidence += 0.25f
        if (cardholderName != null) confidence += 0.25f
        
        return ScannedCardInfo(
            cardNumber = cardNumber,
            expiryDate = expiryDate,
            cardholderName = cardholderName,
            confidence = confidence,
            cardType = cardType
        )
    }
    
    /**
     * Extract card number from text lines
     */
    private fun extractCardNumber(lines: List<String>): String? {
        for (line in lines) {
            val match = cardNumberPattern.find(line)
            if (match != null) {
                val cleaned = match.value
                    .replace(" ", "")
                    .replace("-", "")
                
                if (isValidCardNumber(cleaned)) {
                    return formatCardNumber(cleaned)
                }
            }
        }
        return null
    }
    
    /**
     * Extract expiry date from text lines
     */
    private fun extractExpiryDate(lines: List<String>): String? {
        for (line in lines) {
            val match = expiryPattern.find(line)
            if (match != null) {
                return formatExpiryDate(match.value)
            }
        }
        return null
    }
    
    /**
     * Extract cardholder name from text lines
     */
    private fun extractCardholderName(lines: List<String>): String? {
        val namePattern = Regex("""^[A-Z][A-Z\s]{5,30}$""")
        val excludedWords = listOf("DEBIT", "CREDIT", "CARD", "BANK", "VALID", "THRU", "EXPIRES")
        
        for (line in lines) {
            val upperLine = line.uppercase()
            if (namePattern.matches(upperLine)) {
                val containsExcluded = excludedWords.any { upperLine.contains(it) }
                if (!containsExcluded) {
                    return upperLine
                }
            }
        }
        return null
    }
    
    /**
     * Validate card number using Luhn algorithm
     */
    private fun isValidCardNumber(number: String): Boolean {
        if (number.length < 13 || number.length > 19) return false
        if (!number.all { it.isDigit() }) return false
        
        var sum = 0
        var isSecond = false
        
        for (digit in number.reversed()) {
            var current = digit.toString().toInt()
            if (isSecond) {
                current *= 2
                if (current > 9) {
                    current -= 9
                }
            }
            sum += current
            isSecond = !isSecond
        }
        
        return sum % 10 == 0
    }
    
    /**
     * Format card number as XXXX XXXX XXXX XXXX
     */
    private fun formatCardNumber(number: String): String {
        return number.chunked(4).joinToString(" ")
    }
    
    /**
     * Format expiry date as MM/YY
     */
    private fun formatExpiryDate(date: String): String {
        val cleaned = date.replace("/", "").replace("-", "")
        
        return if (cleaned.length >= 4) {
            val month = cleaned.substring(0, 2)
            val year = cleaned.substring(cleaned.length - 2)
            "$month/$year"
        } else {
            date
        }
    }
    
    /**
     * Get card type from card number
     */
    fun getCardType(cardNumber: String): CardType {
        val cleaned = cardNumber.replace(" ", "")
        
        return when {
            cleaned.startsWith("4") -> CardType.VISA
            cleaned.startsWith("5") -> CardType.MASTERCARD
            cleaned.startsWith("3") -> CardType.AMEX
            cleaned.startsWith("6") -> CardType.DISCOVER
            else -> CardType.UNKNOWN
        }
    }
    
    /**
     * Release resources
     */
    fun release() {
        stopScanning()
        cameraExecutor.shutdown()
        textRecognizer.close()
    }
}

/**
 * Card scanner exceptions
 */
sealed class CardScannerException(message: String, cause: Throwable? = null) : Exception(message, cause) {
    object CameraNotAvailable : CardScannerException("Camera is not available on this device")
    object PermissionDenied : CardScannerException("Camera permission denied")
    object NoCardDetected : CardScannerException("No valid card detected")
    data class CameraSetupFailed(val cause: Throwable) : CardScannerException("Camera setup failed", cause)
    data class CameraBindingFailed(val cause: Throwable) : CardScannerException("Camera binding failed", cause)
}

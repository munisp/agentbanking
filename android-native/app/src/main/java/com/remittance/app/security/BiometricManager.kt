package com.pos54link.app.security

import android.content.Context
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricManager.Authenticators.*
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.suspendCancellableCoroutine
import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

enum class BiometricType {
    NONE,
    FINGERPRINT,
    FACE,
    IRIS,
    MULTIPLE
}

sealed class BiometricResult {
    object Success : BiometricResult()
    data class Error(val errorCode: Int, val errorMessage: String) : BiometricResult()
    object Cancelled : BiometricResult()
}

@Singleton
class BiometricAuthManager @Inject constructor(
    @ApplicationContext private val context: Context,
    private val tokenManager: TokenManager
) {
    
    private val biometricManager = BiometricManager.from(context)
    
    // MARK: - Availability Check
    
    fun isBiometricAvailable(): Boolean {
        return when (biometricManager.canAuthenticate(BIOMETRIC_STRONG)) {
            BiometricManager.BIOMETRIC_SUCCESS -> true
            else -> false
        }
    }
    
    fun canAuthenticateWithBiometric(): Int {
        return biometricManager.canAuthenticate(BIOMETRIC_STRONG)
    }
    
    fun getBiometricType(): BiometricType {
        return when {
            !isBiometricAvailable() -> BiometricType.NONE
            // Note: Android doesn't provide a direct way to determine the exact type
            // We can only check if biometric authentication is available
            else -> BiometricType.FINGERPRINT // Default assumption
        }
    }
    
    fun getAvailabilityMessage(): String {
        return when (biometricManager.canAuthenticate(BIOMETRIC_STRONG)) {
            BiometricManager.BIOMETRIC_SUCCESS ->
                "Biometric authentication is available"
            BiometricManager.BIOMETRIC_ERROR_NO_HARDWARE ->
                "No biometric hardware available"
            BiometricManager.BIOMETRIC_ERROR_HW_UNAVAILABLE ->
                "Biometric hardware is currently unavailable"
            BiometricManager.BIOMETRIC_ERROR_NONE_ENROLLED ->
                "No biometric credentials enrolled. Please set up fingerprint or face unlock in Settings"
            BiometricManager.BIOMETRIC_ERROR_SECURITY_UPDATE_REQUIRED ->
                "Security update required for biometric authentication"
            BiometricManager.BIOMETRIC_ERROR_UNSUPPORTED ->
                "Biometric authentication is not supported"
            BiometricManager.BIOMETRIC_STATUS_UNKNOWN ->
                "Biometric status unknown"
            else ->
                "Biometric authentication unavailable"
        }
    }
    
    // MARK: - Authentication
    
    suspend fun authenticate(
        activity: FragmentActivity,
        title: String = "Authenticate",
        subtitle: String = "Use your biometric to authenticate",
        description: String = "Confirm your identity to proceed",
        negativeButtonText: String = "Cancel"
    ): BiometricResult = suspendCancellableCoroutine { continuation ->
        
        val executor = ContextCompat.getMainExecutor(context)
        
        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle(title)
            .setSubtitle(subtitle)
            .setDescription(description)
            .setNegativeButtonText(negativeButtonText)
            .setAllowedAuthenticators(BIOMETRIC_STRONG)
            .setConfirmationRequired(true)
            .build()
        
        val biometricPrompt = BiometricPrompt(
            activity,
            executor,
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    super.onAuthenticationSucceeded(result)
                    Timber.d("Biometric authentication succeeded")
                    if (continuation.isActive) {
                        continuation.resume(BiometricResult.Success)
                    }
                }
                
                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    super.onAuthenticationError(errorCode, errString)
                    Timber.e("Biometric authentication error: $errorCode - $errString")
                    
                    if (continuation.isActive) {
                        when (errorCode) {
                            BiometricPrompt.ERROR_USER_CANCELED,
                            BiometricPrompt.ERROR_NEGATIVE_BUTTON,
                            BiometricPrompt.ERROR_CANCELED -> {
                                continuation.resume(BiometricResult.Cancelled)
                            }
                            else -> {
                                continuation.resume(
                                    BiometricResult.Error(errorCode, errString.toString())
                                )
                            }
                        }
                    }
                }
                
                override fun onAuthenticationFailed() {
                    super.onAuthenticationFailed()
                    Timber.w("Biometric authentication failed")
                    // Don't resume continuation here - let user retry
                }
            }
        )
        
        continuation.invokeOnCancellation {
            biometricPrompt.cancelAuthentication()
        }
        
        biometricPrompt.authenticate(promptInfo)
    }
    
    // MARK: - Biometric with Crypto
    
    suspend fun authenticateWithCrypto(
        activity: FragmentActivity,
        cryptoObject: BiometricPrompt.CryptoObject,
        title: String = "Authenticate",
        subtitle: String = "Use your biometric to authenticate",
        description: String = "Confirm your identity to proceed",
        negativeButtonText: String = "Cancel"
    ): BiometricResult = suspendCancellableCoroutine { continuation ->
        
        val executor = ContextCompat.getMainExecutor(context)
        
        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle(title)
            .setSubtitle(subtitle)
            .setDescription(description)
            .setNegativeButtonText(negativeButtonText)
            .setAllowedAuthenticators(BIOMETRIC_STRONG)
            .setConfirmationRequired(true)
            .build()
        
        val biometricPrompt = BiometricPrompt(
            activity,
            executor,
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    super.onAuthenticationSucceeded(result)
                    if (continuation.isActive) {
                        continuation.resume(BiometricResult.Success)
                    }
                }
                
                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    super.onAuthenticationError(errorCode, errString)
                    if (continuation.isActive) {
                        when (errorCode) {
                            BiometricPrompt.ERROR_USER_CANCELED,
                            BiometricPrompt.ERROR_NEGATIVE_BUTTON,
                            BiometricPrompt.ERROR_CANCELED -> {
                                continuation.resume(BiometricResult.Cancelled)
                            }
                            else -> {
                                continuation.resume(
                                    BiometricResult.Error(errorCode, errString.toString())
                                )
                            }
                        }
                    }
                }
                
                override fun onAuthenticationFailed() {
                    super.onAuthenticationFailed()
                    // Don't resume - let user retry
                }
            }
        )
        
        continuation.invokeOnCancellation {
            biometricPrompt.cancelAuthentication()
        }
        
        biometricPrompt.authenticate(promptInfo, cryptoObject)
    }
    
    // MARK: - Registration
    
    fun isBiometricRegistered(): Boolean {
        return tokenManager.isBiometricRegistered()
    }
    
    fun registerBiometric(publicKey: String) {
        tokenManager.saveBiometricPublicKey(publicKey)
    }
    
    fun unregisterBiometric() {
        tokenManager.clearBiometricPublicKey()
    }
    
    // MARK: - Device Credential Authentication
    
    suspend fun authenticateWithDeviceCredential(
        activity: FragmentActivity,
        title: String = "Authenticate",
        subtitle: String = "Use your device credential to authenticate",
        description: String = "Confirm your identity to proceed"
    ): BiometricResult = suspendCancellableCoroutine { continuation ->
        
        val executor = ContextCompat.getMainExecutor(context)
        
        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle(title)
            .setSubtitle(subtitle)
            .setDescription(description)
            .setAllowedAuthenticators(BIOMETRIC_STRONG or DEVICE_CREDENTIAL)
            .build()
        
        val biometricPrompt = BiometricPrompt(
            activity,
            executor,
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    super.onAuthenticationSucceeded(result)
                    if (continuation.isActive) {
                        continuation.resume(BiometricResult.Success)
                    }
                }
                
                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    super.onAuthenticationError(errorCode, errString)
                    if (continuation.isActive) {
                        when (errorCode) {
                            BiometricPrompt.ERROR_USER_CANCELED,
                            BiometricPrompt.ERROR_NEGATIVE_BUTTON,
                            BiometricPrompt.ERROR_CANCELED -> {
                                continuation.resume(BiometricResult.Cancelled)
                            }
                            else -> {
                                continuation.resume(
                                    BiometricResult.Error(errorCode, errString.toString())
                                )
                            }
                        }
                    }
                }
                
                override fun onAuthenticationFailed() {
                    super.onAuthenticationFailed()
                }
            }
        )
        
        continuation.invokeOnCancellation {
            biometricPrompt.cancelAuthentication()
        }
        
        biometricPrompt.authenticate(promptInfo)
    }
}

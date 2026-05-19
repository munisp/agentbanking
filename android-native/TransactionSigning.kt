package com.pos54link.app.security

import android.content.Context
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import java.security.MessageDigest
import java.util.*

/**
 * Transaction Signing with Biometrics
 * Prevents unauthorized transactions
 */
class TransactionSigning(private val context: Context) {
    
    data class Transaction(
        val amount: Double,
        val recipient: String,
        val type: TransactionType,
        val timestamp: Date = Date()
    ) {
        enum class TransactionType {
            PAYMENT, WIRE_TRANSFER, STOCK_TRADE, CRYPTO_TRADE, ACCOUNT_CHANGE, BENEFICIARY_ADD
        }
    }
    
    /**
     * Check if transaction requires biometric approval
     */
    fun requiresBiometricApproval(transaction: Transaction): Boolean {
        return when (transaction.type) {
            Transaction.TransactionType.PAYMENT -> transaction.amount > 100.0
            else -> true // Always require for sensitive operations
        }
    }
    
    /**
     * Sign transaction with biometric authentication
     */
    fun signTransaction(
        activity: FragmentActivity,
        transaction: Transaction,
        callback: (Result<String>) -> Unit
    ) {
        if (!requiresBiometricApproval(transaction)) {
            val signature = generateSignature(transaction)
            callback(Result.success(signature))
            return
        }
        
        val biometricManager = BiometricManager.from(context)
        when (biometricManager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG)) {
            BiometricManager.BIOMETRIC_SUCCESS -> {
                showBiometricPrompt(activity, transaction, callback)
            }
            else -> {
                callback(Result.failure(Exception("Biometric authentication not available")))
            }
        }
    }
    
    private fun showBiometricPrompt(
        activity: FragmentActivity,
        transaction: Transaction,
        callback: (Result<String>) -> Unit
    ) {
        val executor = ContextCompat.getMainExecutor(context)
        
        val biometricPrompt = BiometricPrompt(activity, executor,
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    super.onAuthenticationSucceeded(result)
                    val signature = generateSignature(transaction)
                    callback(Result.success(signature))
                }
                
                override fun onAuthenticationFailed() {
                    super.onAuthenticationFailed()
                    callback(Result.failure(Exception("Biometric authentication failed")))
                }
                
                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    super.onAuthenticationError(errorCode, errString)
                    callback(Result.failure(Exception(errString.toString())))
                }
            })
        
        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle("Approve Transaction")
            .setSubtitle("Approve ${transaction.type} of $${transaction.amount.toInt()}")
            .setNegativeButtonText("Cancel")
            .build()
        
        biometricPrompt.authenticate(promptInfo)
    }
    
    /**
     * Generate transaction signature
     */
    private fun generateSignature(transaction: Transaction): String {
        val data = "${transaction.amount}|${transaction.recipient}|${transaction.timestamp.time}"
        return sha256(data)
    }
    
    /**
     * Verify transaction signature
     */
    fun verifySignature(signature: String, transaction: Transaction): Boolean {
        val expectedSignature = generateSignature(transaction)
        return signature == expectedSignature
    }
    
    private fun sha256(input: String): String {
        val bytes = input.toByteArray()
        val md = MessageDigest.getInstance("SHA-256")
        val digest = md.digest(bytes)
        return digest.fold("") { str, it -> str + "%02x".format(it) }
    }
}

package com.pos54link.app.payment

import android.app.Activity
import android.content.Intent
import com.google.android.gms.common.api.ApiException
import com.google.android.gms.wallet.*
import kotlinx.coroutines.tasks.await
import org.json.JSONArray
import org.json.JSONObject
import java.math.BigDecimal

/**
 * Google Pay payment result
 */
data class PaymentResult(
    val transactionId: String,
    val status: String,
    val amount: BigDecimal,
    val currency: String
)

/**
 * Google Pay manager for wallet funding
 */
class GooglePayManager(private val activity: Activity) {

    private val paymentsClient: PaymentsClient by lazy {
        Wallet.getPaymentsClient(
            activity,
            Wallet.WalletOptions.Builder()
                .setEnvironment(WalletConstants.ENVIRONMENT_TEST) // Change to PRODUCTION for live
                .build()
        )
    }

    companion object {
        const val LOAD_PAYMENT_DATA_REQUEST_CODE = 991
        
        private const val MERCHANT_NAME = "Nigerian Remittance"
        private const val GATEWAY = "stripe" // Or your payment gateway
        private const val GATEWAY_MERCHANT_ID = "your_gateway_merchant_id"
    }

    /**
     * Check if Google Pay is available
     */
    suspend fun isGooglePayAvailable(): Boolean {
        val request = IsReadyToPayRequest.fromJson(isReadyToPayRequest().toString())
        
        return try {
            paymentsClient.isReadyToPay(request).await()
        } catch (e: ApiException) {
            false
        }
    }

    /**
     * Create IsReadyToPay request
     */
    private fun isReadyToPayRequest(): JSONObject {
        return JSONObject().apply {
            put("apiVersion", 2)
            put("apiVersionMinor", 0)
            put("allowedPaymentMethods", JSONArray().put(baseCardPaymentMethod()))
        }
    }

    /**
     * Base card payment method
     */
    private fun baseCardPaymentMethod(): JSONObject {
        return JSONObject().apply {
            put("type", "CARD")
            put("parameters", JSONObject().apply {
                put("allowedAuthMethods", JSONArray().apply {
                    put("PAN_ONLY")
                    put("CRYPTOGRAM_3DS")
                })
                put("allowedCardNetworks", JSONArray().apply {
                    put("AMEX")
                    put("DISCOVER")
                    put("MASTERCARD")
                    put("VISA")
                })
            })
        }
    }

    /**
     * Card payment method with tokenization
     */
    private fun cardPaymentMethod(): JSONObject {
        return baseCardPaymentMethod().apply {
            put("tokenizationSpecification", JSONObject().apply {
                put("type", "PAYMENT_GATEWAY")
                put("parameters", JSONObject().apply {
                    put("gateway", GATEWAY)
                    put("gatewayMerchantId", GATEWAY_MERCHANT_ID)
                })
            })
        }
    }

    /**
     * Create payment data request
     */
    private fun createPaymentDataRequest(
        amount: BigDecimal,
        currency: String
    ): JSONObject {
        return JSONObject().apply {
            put("apiVersion", 2)
            put("apiVersionMinor", 0)
            put("allowedPaymentMethods", JSONArray().put(cardPaymentMethod()))
            put("transactionInfo", JSONObject().apply {
                put("totalPrice", amount.toString())
                put("totalPriceStatus", "FINAL")
                put("currencyCode", currency)
                put("countryCode", "NG")
            })
            put("merchantInfo", JSONObject().apply {
                put("merchantName", MERCHANT_NAME)
            })
        }
    }

    /**
     * Present Google Pay sheet
     */
    fun presentGooglePay(amount: BigDecimal, currency: String) {
        val request = createPaymentDataRequest(amount, currency)
        val paymentDataRequest = PaymentDataRequest.fromJson(request.toString())
        
        AutoResolveHelper.resolveTask(
            paymentsClient.loadPaymentData(paymentDataRequest),
            activity,
            LOAD_PAYMENT_DATA_REQUEST_CODE
        )
    }

    /**
     * Handle activity result
     */
    fun handleActivityResult(
        requestCode: Int,
        resultCode: Int,
        data: Intent?,
        onSuccess: (PaymentData) -> Unit,
        onFailure: (Exception) -> Unit
    ) {
        when (requestCode) {
            LOAD_PAYMENT_DATA_REQUEST_CODE -> {
                when (resultCode) {
                    Activity.RESULT_OK -> {
                        data?.let { intent ->
                            PaymentData.getFromIntent(intent)?.let { paymentData ->
                                onSuccess(paymentData)
                            } ?: run {
                                onFailure(GooglePayException.PaymentDataNotFound)
                            }
                        }
                    }
                    Activity.RESULT_CANCELED -> {
                        onFailure(GooglePayException.Cancelled)
                    }
                    AutoResolveHelper.RESULT_ERROR -> {
                        val status = AutoResolveHelper.getStatusFromIntent(data)
                        onFailure(GooglePayException.ProcessingFailed(status?.statusMessage))
                    }
                }
            }
        }
    }

    /**
     * Extract payment token from PaymentData
     */
    fun extractPaymentToken(paymentData: PaymentData): String {
        val paymentInfo = JSONObject(paymentData.toJson())
        val paymentMethodData = paymentInfo.getJSONObject("paymentMethodData")
        val tokenizationData = paymentMethodData.getJSONObject("tokenizationData")
        return tokenizationData.getString("token")
    }

    /**
     * Process payment with backend
     */
    suspend fun processPayment(
        paymentData: PaymentData,
        amount: BigDecimal,
        currency: String
    ): Result<PaymentResult> {
        return try {
            val paymentToken = extractPaymentToken(paymentData)
            
            // Send to backend for processing
            val endpoint = "/api/v1/payments/google-pay"
            val parameters = mapOf(
                "payment_token" to paymentToken,
                "amount" to amount.toString(),
                "currency" to currency,
                "payment_method" to "google_pay"
            )
            
            // Make API call (using your existing ApiClient)
            // This is a placeholder - integrate with your actual API client
            val result = ApiClient.post(endpoint, parameters)
            
            val paymentResult = PaymentResult(
                transactionId = result["transaction_id"] as? String ?: "",
                status = result["status"] as? String ?: "",
                amount = amount,
                currency = currency
            )
            
            Result.success(paymentResult)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}

/**
 * Google Pay exceptions
 */
sealed class GooglePayException(message: String, cause: Throwable? = null) : Exception(message, cause) {
    object NotAvailable : GooglePayException("Google Pay is not available")
    object Cancelled : GooglePayException("Payment was cancelled")
    object PaymentDataNotFound : GooglePayException("Payment data not found")
    data class ProcessingFailed(val reason: String?) : GooglePayException("Payment processing failed: $reason")
}

/**
 * Mock ApiClient for demonstration
 * Replace with your actual API client implementation
 */
object ApiClient {
    suspend fun post(endpoint: String, parameters: Map<String, String>): Map<String, Any> {
        // Implement actual API call here
        return mapOf(
            "transaction_id" to "txn_${System.currentTimeMillis()}",
            "status" to "success"
        )
    }
}

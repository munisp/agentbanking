package com.pos54link.app.data.api

import com.pos54link.app.models.*
import retrofit2.Response
import retrofit2.http.*

interface TransferService {
    
    @POST("transfers/quote")
    suspend fun getQuote(@Body request: QuoteRequest): Response<QuoteResponse>
    
    @POST("transfers/initiate")
    suspend fun initiateTransfer(@Body request: TransferRequest): Response<TransferResponse>
    
    @GET("transfers/{id}/status")
    suspend fun getTransferStatus(@Path("id") transferId: String): Response<TransferStatusResponse>
    
    @GET("transfers/history")
    suspend fun getTransferHistory(
        @Query("page") page: Int = 1,
        @Query("limit") limit: Int = 20,
        @Query("status") status: String? = null
    ): Response<TransferHistoryResponse>
    
    @POST("transfers/{id}/cancel")
    suspend fun cancelTransfer(@Path("id") transferId: String): Response<CancelTransferResponse>
    
    @GET("transfers/exchange-rates")
    suspend fun getExchangeRates(
        @Query("from") fromCurrency: String,
        @Query("to") toCurrency: String
    ): Response<ExchangeRateResponse>
}

// Request Models
data class QuoteRequest(
    val sourceCurrency: String,
    val destinationCurrency: String,
    val amount: Double,
    val transferSpeed: String, // express, standard, economy
    val paymentSystem: String? = null // papss, cips, pix, upi, mojaloop, nibss
)

data class TransferRequest(
    val quoteId: String,
    val beneficiaryId: String,
    val sourceCurrency: String,
    val destinationCurrency: String,
    val amount: Double,
    val transferSpeed: String,
    val paymentSystem: String,
    val description: String? = null,
    val reference: String? = null
)

// Response Models
data class QuoteResponse(
    val success: Boolean,
    val data: QuoteData
)

data class QuoteData(
    val quoteId: String,
    val sourceCurrency: String,
    val destinationCurrency: String,
    val sourceAmount: Double,
    val destinationAmount: Double,
    val exchangeRate: Double,
    val fee: Double,
    val totalAmount: Double,
    val transferSpeed: String,
    val estimatedDelivery: String,
    val paymentSystems: List<PaymentSystemOption>,
    val expiresAt: String
)

data class PaymentSystemOption(
    val system: String,
    val name: String,
    val fee: Double,
    val estimatedDelivery: String,
    val available: Boolean
)

data class TransferResponse(
    val success: Boolean,
    val data: TransferData
)

data class TransferData(
    val transferId: String,
    val status: String,
    val reference: String,
    val estimatedCompletionTime: String,
    val requiresAction: Boolean,
    val actionUrl: String? = null
)

data class TransferStatusResponse(
    val success: Boolean,
    val data: TransferStatus
)

data class TransferStatus(
    val transferId: String,
    val status: String,
    val currentStep: String,
    val progress: Int, // 0-100
    val estimatedCompletionTime: String? = null,
    val timeline: List<TransferTimeline>
)

data class TransferTimeline(
    val step: String,
    val status: String,
    val timestamp: String,
    val message: String
)

data class TransferHistoryResponse(
    val success: Boolean,
    val data: TransferHistoryData
)

data class TransferHistoryData(
    val transfers: List<TransferHistoryItem>,
    val pagination: Pagination
)

data class TransferHistoryItem(
    val id: String,
    val beneficiary: String,
    val amount: Double,
    val currency: String,
    val status: String,
    val paymentSystem: String,
    val createdAt: String,
    val completedAt: String? = null
)

data class CancelTransferResponse(
    val success: Boolean,
    val message: String
)

data class ExchangeRateResponse(
    val success: Boolean,
    val data: ExchangeRateData
)

data class ExchangeRateData(
    val fromCurrency: String,
    val toCurrency: String,
    val rate: Double,
    val inverseRate: Double,
    val timestamp: String,
    val validUntil: String
)

package com.pos54link.app.data.api

import retrofit2.Response
import retrofit2.http.*

/**
 * 54Link POS Transaction Service
 *
 * Handles agent banking transactions: Cash In, Cash Out, Bill Payment,
 * Airtime purchase, and float balance queries. All mutation endpoints
 * require an X-Idempotency-Key header to prevent double-execution.
 */
interface TransactionService {

    @POST("api/trpc/cashIn.process")
    suspend fun cashIn(
        @Header("X-Idempotency-Key") idempotencyKey: String,
        @Body request: CashInRequest
    ): Response<TransactionResponse>

    @POST("api/trpc/cashOut.process")
    suspend fun cashOut(
        @Header("X-Idempotency-Key") idempotencyKey: String,
        @Body request: CashOutRequest
    ): Response<TransactionResponse>

    @POST("api/trpc/billPayments.pay")
    suspend fun billPayment(
        @Header("X-Idempotency-Key") idempotencyKey: String,
        @Body request: BillPaymentRequest
    ): Response<TransactionResponse>

    @POST("api/trpc/airtimeVending.purchase")
    suspend fun airtimePurchase(
        @Header("X-Idempotency-Key") idempotencyKey: String,
        @Body request: AirtimeRequest
    ): Response<TransactionResponse>

    @GET("api/trpc/agents.getFloat")
    suspend fun getAgentFloat(): Response<FloatResponse>

    @POST("api/trpc/cashOut.verifyPin")
    suspend fun verifyPinPad(@Body request: PinVerifyRequest): Response<PinVerifyResponse>

    @GET("api/trpc/transactions.list")
    suspend fun listTransactions(
        @Query("input") input: String
    ): Response<TransactionListResponse>

    @GET("api/trpc/transactions.getByRef")
    suspend fun getTransaction(
        @Query("input") ref: String
    ): TransactionDetail

    @POST("api/trpc/transactions.printReceipt")
    suspend fun printReceipt(@Query("ref") ref: String): Response<Unit>

    @POST("api/trpc/transactions.sendSmsReceipt")
    suspend fun sendSmsReceipt(@Query("ref") ref: String): Response<Unit>

    @POST("api/trpc/transactions.shareWhatsApp")
    suspend fun shareWhatsApp(@Query("ref") ref: String): Response<Unit>
}

data class TransactionDetail(
    val reference: String,
    val date: String,
    val time: String,
    val type: String,
    val customerPhone: String,
    val amount: String,
    val fee: String,
    val total: String,
    val status: String,
    val agentName: String,
    val agentCode: String,
    val terminalId: String,
    val simSlot: String
)

// --- Request models ---

data class CashInRequest(
    val json: CashInInput
)

data class CashInInput(
    val customerPhone: String,
    val amount: Double,
    val narration: String? = null,
    val inputMethod: String = "manual" // manual, nfc, qr
)

data class CashOutRequest(
    val json: CashOutInput
)

data class CashOutInput(
    val customerPhone: String,
    val amount: Double,
    val withdrawalCode: String
)

data class BillPaymentRequest(
    val json: BillPaymentInput
)

data class BillPaymentInput(
    val category: String,
    val provider: String,
    val customerRef: String,
    val amount: Double
)

data class AirtimeRequest(
    val json: AirtimeInput
)

data class AirtimeInput(
    val phone: String,
    val amount: Double,
    val network: String
)

data class PinVerifyRequest(
    val json: PinVerifyInput
)

data class PinVerifyInput(
    val phone: String,
    val amount: Double
)

// --- Response models ---

data class TransactionResponse(
    val result: TransactionResultWrapper
)

data class TransactionResultWrapper(
    val data: TransactionResultData
)

data class TransactionResultData(
    val json: TransactionResult
)

data class TransactionResult(
    val reference: String,
    val status: String,
    val amount: Double,
    val fee: Double,
    val commission: Double,
    val tax: Double,
    val netAmount: Double,
    val currency: String = "NGN"
)

data class FloatResponse(
    val result: FloatResultWrapper
)

data class FloatResultWrapper(
    val data: FloatResultData
)

data class FloatResultData(
    val json: FloatResult
)

data class FloatResult(
    val floatBalance: Double,
    val tier: String,
    val dailyUsed: Double,
    val dailyLimit: Double
)

data class PinVerifyResponse(
    val result: PinVerifyResultWrapper
)

data class PinVerifyResultWrapper(
    val data: PinVerifyResultData
)

data class PinVerifyResultData(
    val json: PinVerifyResult
)

data class PinVerifyResult(
    val verified: Boolean,
    val message: String? = null
)

data class TransactionListResponse(
    val result: TransactionListResultWrapper
)

data class TransactionListResultWrapper(
    val data: TransactionListResultData
)

data class TransactionListResultData(
    val json: TransactionListResult
)

data class TransactionListResult(
    val items: List<TransactionItem>,
    val total: Int,
    val page: Int
)

data class TransactionItem(
    val id: Int,
    val reference: String,
    val type: String,
    val amount: Double,
    val fee: Double,
    val status: String,
    val createdAt: String
)

package com.pos54link.app.data.api

import com.pos54link.app.models.*
import retrofit2.Response
import retrofit2.http.*

interface WalletService {
    
    @GET("wallet/balances")
    suspend fun getBalances(): Response<BalancesResponse>
    
    @GET("wallet/virtual-ibans")
    suspend fun getVirtualIBANs(): Response<VirtualIBANsResponse>
    
    @GET("wallet/transactions")
    suspend fun getTransactions(
        @Query("page") page: Int = 1,
        @Query("limit") limit: Int = 20,
        @Query("type") type: String? = null,
        @Query("status") status: String? = null,
        @Query("startDate") startDate: String? = null,
        @Query("endDate") endDate: String? = null
    ): Response<TransactionsResponse>
    
    @GET("wallet/transactions/{id}")
    suspend fun getTransaction(@Path("id") transactionId: String): Response<TransactionDetailResponse>
    
    @POST("wallet/add-funds")
    suspend fun addFunds(@Body request: AddFundsRequest): Response<AddFundsResponse>
    
    @POST("wallet/withdraw")
    suspend fun withdraw(@Body request: WithdrawRequest): Response<WithdrawResponse>
    
    @GET("wallet/statement")
    suspend fun getStatement(
        @Query("startDate") startDate: String,
        @Query("endDate") endDate: String,
        @Query("format") format: String = "pdf"
    ): Response<StatementResponse>
}

// Request Models
data class AddFundsRequest(
    val amount: Double,
    val currency: String,
    val paymentMethod: String,
    val paymentDetails: Map<String, Any>
)

data class WithdrawRequest(
    val amount: Double,
    val currency: String,
    val destinationAccount: String,
    val destinationBank: String
)

// Response Models
data class BalancesResponse(
    val success: Boolean,
    val data: List<CurrencyBalance>
)

data class CurrencyBalance(
    val currency: String,
    val currencyName: String,
    val currencySymbol: String,
    val amount: Double,
    val availableAmount: Double,
    val pendingAmount: Double,
    val usdEquivalent: Double
)

data class VirtualIBANsResponse(
    val success: Boolean,
    val data: List<VirtualIBAN>
)

data class VirtualIBAN(
    val id: String,
    val currency: String,
    val iban: String,
    val bic: String,
    val bankName: String,
    val accountHolderName: String,
    val status: String
)

data class TransactionsResponse(
    val success: Boolean,
    val data: TransactionsPaginatedData
)

data class TransactionsPaginatedData(
    val transactions: List<Transaction>,
    val pagination: Pagination
)

data class Transaction(
    val id: String,
    val type: String, // sent, received, exchange, fee
    val status: String, // pending, completed, failed, cancelled
    val amount: Double,
    val currency: String,
    val recipient: String? = null,
    val sender: String? = null,
    val description: String? = null,
    val fee: Double,
    val exchangeRate: Double? = null,
    val createdAt: String,
    val completedAt: String? = null
)

data class TransactionDetailResponse(
    val success: Boolean,
    val data: TransactionDetail
)

data class TransactionDetail(
    val id: String,
    val type: String,
    val status: String,
    val amount: Double,
    val currency: String,
    val recipient: RecipientDetail? = null,
    val sender: SenderDetail? = null,
    val description: String? = null,
    val fee: Double,
    val exchangeRate: Double? = null,
    val paymentSystem: String,
    val reference: String,
    val createdAt: String,
    val completedAt: String? = null,
    val timeline: List<TransactionTimeline>
)

data class RecipientDetail(
    val name: String,
    val accountNumber: String,
    val bankName: String,
    val country: String
)

data class SenderDetail(
    val name: String,
    val accountNumber: String,
    val bankName: String,
    val country: String
)

data class TransactionTimeline(
    val status: String,
    val timestamp: String,
    val message: String
)

data class AddFundsResponse(
    val success: Boolean,
    val data: AddFundsData
)

data class AddFundsData(
    val transactionId: String,
    val paymentUrl: String? = null,
    val instructions: String? = null
)

data class WithdrawResponse(
    val success: Boolean,
    val data: WithdrawData
)

data class WithdrawData(
    val transactionId: String,
    val estimatedCompletionTime: String
)

data class StatementResponse(
    val success: Boolean,
    val data: StatementData
)

data class StatementData(
    val downloadUrl: String,
    val expiresAt: String
)

data class Pagination(
    val currentPage: Int,
    val totalPages: Int,
    val totalItems: Int,
    val itemsPerPage: Int
)

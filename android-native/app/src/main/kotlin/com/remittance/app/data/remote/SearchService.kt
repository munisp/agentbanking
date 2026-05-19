package com.pos54link.app.data.remote

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/**
 * OpenSearch Integration Service for Android Native App
 * Connects to the unified search service endpoints
 */

// Search Index Types
enum class SearchIndex(val value: String) {
    TRANSACTIONS("transactions"),
    USERS("users"),
    BENEFICIARIES("beneficiaries"),
    DISPUTES("disputes"),
    AUDIT_LOGS("audit_logs"),
    KYC("kyc"),
    WALLETS("wallets"),
    CARDS("cards"),
    BILLS("bills"),
    AIRTIME("airtime")
}

// Search Request Models
@Serializable
data class SearchQuery(
    val query: String,
    val index: List<String>? = null,
    val filters: Map<String, String>? = null,
    val sort: SearchSort? = null,
    val pagination: SearchPagination? = null,
    val highlight: Boolean = true,
    val aggregations: List<String>? = null
)

@Serializable
data class SearchSort(
    val field: String,
    val order: String = "desc"
)

@Serializable
data class SearchPagination(
    val page: Int = 1,
    val size: Int = 20
)

// Search Response Models
@Serializable
data class SearchResponse<T>(
    val hits: List<SearchHit<T>>,
    val total: Int,
    val page: Int,
    val size: Int,
    val took: Long,
    val aggregations: Map<String, List<AggregationBucket>>? = null
)

@Serializable
data class SearchHit<T>(
    val id: String,
    val index: String,
    val score: Float,
    val source: T,
    val highlight: Map<String, List<String>>? = null
)

@Serializable
data class AggregationBucket(
    val key: String,
    val count: Int
)

// Domain-specific result types
@Serializable
data class TransactionSearchResult(
    val id: String,
    val reference: String,
    val type: String,
    val amount: Double,
    val currency: String,
    val status: String,
    val description: String,
    val createdAt: String,
    val senderId: String? = null,
    val recipientId: String? = null
)

@Serializable
data class BeneficiarySearchResult(
    val id: String,
    val name: String,
    val accountNumber: String,
    val bankCode: String,
    val bankName: String,
    val country: String,
    val currency: String,
    val createdAt: String
)

@Serializable
data class DisputeSearchResult(
    val id: String,
    val transactionId: String,
    val type: String,
    val status: String,
    val description: String,
    val createdAt: String,
    val resolvedAt: String? = null
)

@Serializable
data class AuditLogSearchResult(
    val id: String,
    val action: String,
    val category: String,
    val userId: String,
    val resourceType: String,
    val resourceId: String,
    val details: String,
    val ipAddress: String,
    val timestamp: String
)

@Serializable
data class SearchSuggestion(
    val text: String,
    val score: Float,
    val index: String
)

@Serializable
data class RecentSearch(
    val query: String,
    val index: String? = null,
    val timestamp: String
)

/**
 * OpenSearch Service Implementation
 */
class SearchService(
    private val baseUrl: String = "https://api.remittance.com/api/search",
    private val authToken: String? = null
) {
    private val json = Json { 
        ignoreUnknownKeys = true 
        isLenient = true
    }
    
    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()
    
    private val mediaType = "application/json; charset=utf-8".toMediaType()

    /**
     * Unified search across all indices
     */
    suspend fun search(query: SearchQuery): Result<SearchResponse<Map<String, Any>>> {
        return withContext(Dispatchers.IO) {
            try {
                val requestBody = json.encodeToString(SearchQuery.serializer(), query)
                    .toRequestBody(mediaType)
                
                val request = Request.Builder()
                    .url("$baseUrl/unified")
                    .post(requestBody)
                    .apply {
                        authToken?.let { addHeader("Authorization", "Bearer $it") }
                        addHeader("Content-Type", "application/json")
                    }
                    .build()
                
                val response = client.newCall(request).execute()
                
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "{}"
                    // Parse response - simplified for demonstration
                    Result.success(parseSearchResponse(body))
                } else {
                    Result.failure(Exception("Search failed: ${response.code}"))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    }

    /**
     * Search transactions
     */
    suspend fun searchTransactions(
        query: String,
        filters: Map<String, String>? = null,
        pagination: SearchPagination = SearchPagination()
    ): Result<SearchResponse<TransactionSearchResult>> {
        return withContext(Dispatchers.IO) {
            try {
                val searchQuery = SearchQuery(
                    query = query,
                    index = listOf(SearchIndex.TRANSACTIONS.value),
                    filters = filters,
                    pagination = pagination,
                    highlight = true
                )
                
                val requestBody = json.encodeToString(SearchQuery.serializer(), searchQuery)
                    .toRequestBody(mediaType)
                
                val request = Request.Builder()
                    .url("$baseUrl/transactions")
                    .post(requestBody)
                    .apply {
                        authToken?.let { addHeader("Authorization", "Bearer $it") }
                        addHeader("Content-Type", "application/json")
                    }
                    .build()
                
                val response = client.newCall(request).execute()
                
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "{}"
                    Result.success(parseTransactionResponse(body))
                } else {
                    Result.failure(Exception("Transaction search failed: ${response.code}"))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    }

    /**
     * Search beneficiaries
     */
    suspend fun searchBeneficiaries(
        query: String,
        filters: Map<String, String>? = null,
        pagination: SearchPagination = SearchPagination()
    ): Result<SearchResponse<BeneficiarySearchResult>> {
        return withContext(Dispatchers.IO) {
            try {
                val searchQuery = SearchQuery(
                    query = query,
                    index = listOf(SearchIndex.BENEFICIARIES.value),
                    filters = filters,
                    pagination = pagination,
                    highlight = true
                )
                
                val requestBody = json.encodeToString(SearchQuery.serializer(), searchQuery)
                    .toRequestBody(mediaType)
                
                val request = Request.Builder()
                    .url("$baseUrl/beneficiaries")
                    .post(requestBody)
                    .apply {
                        authToken?.let { addHeader("Authorization", "Bearer $it") }
                        addHeader("Content-Type", "application/json")
                    }
                    .build()
                
                val response = client.newCall(request).execute()
                
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "{}"
                    Result.success(parseBeneficiaryResponse(body))
                } else {
                    Result.failure(Exception("Beneficiary search failed: ${response.code}"))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    }

    /**
     * Search disputes
     */
    suspend fun searchDisputes(
        query: String,
        filters: Map<String, String>? = null,
        pagination: SearchPagination = SearchPagination()
    ): Result<SearchResponse<DisputeSearchResult>> {
        return withContext(Dispatchers.IO) {
            try {
                val searchQuery = SearchQuery(
                    query = query,
                    index = listOf(SearchIndex.DISPUTES.value),
                    filters = filters,
                    pagination = pagination,
                    highlight = true
                )
                
                val requestBody = json.encodeToString(SearchQuery.serializer(), searchQuery)
                    .toRequestBody(mediaType)
                
                val request = Request.Builder()
                    .url("$baseUrl/disputes")
                    .post(requestBody)
                    .apply {
                        authToken?.let { addHeader("Authorization", "Bearer $it") }
                        addHeader("Content-Type", "application/json")
                    }
                    .build()
                
                val response = client.newCall(request).execute()
                
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "{}"
                    Result.success(parseDisputeResponse(body))
                } else {
                    Result.failure(Exception("Dispute search failed: ${response.code}"))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    }

    /**
     * Search audit logs
     */
    suspend fun searchAuditLogs(
        query: String,
        filters: Map<String, String>? = null,
        pagination: SearchPagination = SearchPagination()
    ): Result<SearchResponse<AuditLogSearchResult>> {
        return withContext(Dispatchers.IO) {
            try {
                val searchQuery = SearchQuery(
                    query = query,
                    index = listOf(SearchIndex.AUDIT_LOGS.value),
                    filters = filters,
                    pagination = pagination,
                    highlight = true
                )
                
                val requestBody = json.encodeToString(SearchQuery.serializer(), searchQuery)
                    .toRequestBody(mediaType)
                
                val request = Request.Builder()
                    .url("$baseUrl/audit-logs")
                    .post(requestBody)
                    .apply {
                        authToken?.let { addHeader("Authorization", "Bearer $it") }
                        addHeader("Content-Type", "application/json")
                    }
                    .build()
                
                val response = client.newCall(request).execute()
                
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "{}"
                    Result.success(parseAuditLogResponse(body))
                } else {
                    Result.failure(Exception("Audit log search failed: ${response.code}"))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    }

    /**
     * Get search suggestions (autocomplete)
     */
    suspend fun getSuggestions(
        query: String,
        index: SearchIndex? = null
    ): Result<List<SearchSuggestion>> {
        return withContext(Dispatchers.IO) {
            try {
                val url = buildString {
                    append("$baseUrl/suggestions?q=$query")
                    index?.let { append("&index=${it.value}") }
                }
                
                val request = Request.Builder()
                    .url(url)
                    .get()
                    .apply {
                        authToken?.let { addHeader("Authorization", "Bearer $it") }
                    }
                    .build()
                
                val response = client.newCall(request).execute()
                
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "[]"
                    Result.success(parseSuggestions(body))
                } else {
                    Result.failure(Exception("Suggestions failed: ${response.code}"))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    }

    /**
     * Get recent searches
     */
    suspend fun getRecentSearches(): Result<List<RecentSearch>> {
        return withContext(Dispatchers.IO) {
            try {
                val request = Request.Builder()
                    .url("$baseUrl/recent")
                    .get()
                    .apply {
                        authToken?.let { addHeader("Authorization", "Bearer $it") }
                    }
                    .build()
                
                val response = client.newCall(request).execute()
                
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "[]"
                    Result.success(parseRecentSearches(body))
                } else {
                    Result.failure(Exception("Recent searches failed: ${response.code}"))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    }

    /**
     * Save a recent search
     */
    suspend fun saveRecentSearch(query: String, index: SearchIndex? = null): Result<Unit> {
        return withContext(Dispatchers.IO) {
            try {
                val body = buildString {
                    append("{\"query\":\"$query\"")
                    index?.let { append(",\"index\":\"${it.value}\"") }
                    append("}")
                }.toRequestBody(mediaType)
                
                val request = Request.Builder()
                    .url("$baseUrl/recent")
                    .post(body)
                    .apply {
                        authToken?.let { addHeader("Authorization", "Bearer $it") }
                        addHeader("Content-Type", "application/json")
                    }
                    .build()
                
                val response = client.newCall(request).execute()
                
                if (response.isSuccessful) {
                    Result.success(Unit)
                } else {
                    Result.failure(Exception("Save recent search failed: ${response.code}"))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    }

    /**
     * Clear recent searches
     */
    suspend fun clearRecentSearches(): Result<Unit> {
        return withContext(Dispatchers.IO) {
            try {
                val request = Request.Builder()
                    .url("$baseUrl/recent")
                    .delete()
                    .apply {
                        authToken?.let { addHeader("Authorization", "Bearer $it") }
                    }
                    .build()
                
                val response = client.newCall(request).execute()
                
                if (response.isSuccessful) {
                    Result.success(Unit)
                } else {
                    Result.failure(Exception("Clear recent searches failed: ${response.code}"))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    }

    // Response parsing helpers
    private fun parseSearchResponse(body: String): SearchResponse<Map<String, Any>> {
        // Simplified parsing - in production use proper JSON deserialization
        return SearchResponse(
            hits = emptyList(),
            total = 0,
            page = 1,
            size = 20,
            took = 0
        )
    }

    private fun parseTransactionResponse(body: String): SearchResponse<TransactionSearchResult> {
        return SearchResponse(
            hits = emptyList(),
            total = 0,
            page = 1,
            size = 20,
            took = 0
        )
    }

    private fun parseBeneficiaryResponse(body: String): SearchResponse<BeneficiarySearchResult> {
        return SearchResponse(
            hits = emptyList(),
            total = 0,
            page = 1,
            size = 20,
            took = 0
        )
    }

    private fun parseDisputeResponse(body: String): SearchResponse<DisputeSearchResult> {
        return SearchResponse(
            hits = emptyList(),
            total = 0,
            page = 1,
            size = 20,
            took = 0
        )
    }

    private fun parseAuditLogResponse(body: String): SearchResponse<AuditLogSearchResult> {
        return SearchResponse(
            hits = emptyList(),
            total = 0,
            page = 1,
            size = 20,
            took = 0
        )
    }

    private fun parseSuggestions(body: String): List<SearchSuggestion> {
        return emptyList()
    }

    private fun parseRecentSearches(body: String): List<RecentSearch> {
        return emptyList()
    }

    companion object {
        @Volatile
        private var instance: SearchService? = null

        fun getInstance(baseUrl: String? = null, authToken: String? = null): SearchService {
            return instance ?: synchronized(this) {
                instance ?: SearchService(
                    baseUrl = baseUrl ?: "https://api.remittance.com/api/search",
                    authToken = authToken
                ).also { instance = it }
            }
        }
    }
}

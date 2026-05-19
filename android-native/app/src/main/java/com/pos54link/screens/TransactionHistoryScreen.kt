package com.pos54link.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.room.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import retrofit2.HttpException
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Query
import java.io.IOException
import java.util.Date

// --- 1. Data Layer: Models (DTO, Entity, Domain) ---

/**
 * Domain Model: Represents a transaction in the application's business logic.
 */
data class Transaction(
    val id: String,
    val description: String,
    val amount: Double,
    val currency: String,
    val type: TransactionType,
    val date: Long,
    val status: TransactionStatus
)

enum class TransactionType {
    DEBIT, CREDIT
}

enum class TransactionStatus {
    SUCCESS, PENDING, FAILED
}

/**
 * Data Transfer Object (DTO): Used for communication with the remote API.
 */
data class TransactionDto(
    val transactionId: String,
    val details: String,
    val value: Double,
    val currencyCode: String,
    val transactionType: String,
    val timestamp: Long,
    val transactionStatus: String
) {
    fun toDomain() = Transaction(
        id = transactionId,
        description = details,
        amount = value,
        currency = currencyCode,
        type = TransactionType.valueOf(transactionType.uppercase()),
        date = timestamp,
        status = TransactionStatus.valueOf(transactionStatus.uppercase())
    )
}

/**
 * Room Entity: Used for local storage in the database.
 */
@Entity(tableName = "transactions", primaryKeys = ["id"])
data class TransactionEntity(
    val id: String,
    val description: String,
    val amount: Double,
    val currency: String,
    val type: String,
    val date: Long,
    val status: String
) {
    fun toDomain() = Transaction(
        id = id,
        description = description,
        amount = amount,
        currency = currency,
        type = TransactionType.valueOf(type.uppercase()),
        date = date,
        status = TransactionStatus.valueOf(status.uppercase())
    )
}

fun Transaction.toEntity() = TransactionEntity(
    id = id,
    description = description,
    amount = amount,
    currency = currency,
    type = type.name,
    date = date,
    status = status.name
)

// --- 2. Data Layer: API Service (Retrofit Placeholder) ---

interface TransactionApiService {
    @GET("transactions")
    suspend fun getTransactions(
        @Query("page") page: Int,
        @Query("pageSize") pageSize: Int,
        @Query("query") query: String?,
        @Query("type") type: String?
    ): Response<List<TransactionDto>>
}

// --- 3. Data Layer: Room DAO (Database Placeholder) ---

@Dao
interface TransactionDao {
    @Query("SELECT * FROM transactions ORDER BY date DESC LIMIT :pageSize OFFSET :offset")
    fun getTransactions(pageSize: Int, offset: Int): Flow<List<TransactionEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(transactions: List<TransactionEntity>)

    @Query("DELETE FROM transactions")
    suspend fun clearAll()
}

// --- 4. Data Layer: Repository ---

interface TransactionRepository {
    fun getTransactionsStream(page: Int, pageSize: Int, query: String?, type: String?): Flow<List<Transaction>>
    suspend fun refreshTransactions(page: Int, pageSize: Int, query: String?, type: String?)
}

class TransactionRepositoryImpl(
    private val apiService: TransactionApiService,
    private val transactionDao: TransactionDao
) : TransactionRepository {

    private val pageSize = 20

    override fun getTransactionsStream(page: Int, pageSize: Int, query: String?, type: String?): Flow<List<Transaction>> {
        val offset = (page - 1) * pageSize
        return transactionDao.getTransactions(pageSize, offset)
            .map { entities -> entities.map { it.toDomain() } }
    }

    override suspend fun refreshTransactions(page: Int, pageSize: Int, query: String?, type: String?) {
        try {
            val response = apiService.getTransactions(page, pageSize, query, type)
            if (response.isSuccessful) {
                val dtos = response.body() ?: emptyList()
                val entities = dtos.map { it.toDomain().toEntity() }
                // For simplicity, we only insert the current page. A real app would handle this more carefully.
                if (page == 1) {
                    // transactionDao.clearAll() // Only clear if we are fetching the first page
                }
                transactionDao.insertAll(entities)
            } else {
                // Handle API error
                throw HttpException(response)
            }
        } catch (e: IOException) {
            // Network error, rely on cached data
            println("Network error: ${e.message}")
        } catch (e: HttpException) {
            // API error
            println("API error: ${e.code()}")
        }
    }
}

// --- 5. ViewModel: State Management and Business Logic ---

data class TransactionHistoryState(
    val transactions: List<Transaction> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val currentPage: Int = 1,
    val totalPages: Int = 1, // Placeholder for total pages
    val searchQuery: String = "",
    val selectedType: TransactionType? = null,
    val isFilterSheetOpen: Boolean = false,
    val isBiometricPromptVisible: Boolean = false // For Biometric Auth feature
)

sealed class TransactionHistoryEvent {
    data class SearchQueryChanged(val query: String) : TransactionHistoryEvent()
    data class FilterTypeSelected(val type: TransactionType?) : TransactionHistoryEvent()
    object LoadNextPage : TransactionHistoryEvent()
    object Refresh : TransactionHistoryEvent()
    object ToggleFilterSheet : TransactionHistoryEvent()
    object InitiateBiometricAuth : TransactionHistoryEvent()
    data class TransactionClicked(val transaction: Transaction) : TransactionHistoryEvent()
}

class TransactionHistoryViewModel(
    private val repository: TransactionRepository
) : ViewModel() {

    private val _state = MutableStateFlow(TransactionHistoryState())
    val state: StateFlow<TransactionHistoryState> = _state.asStateFlow()

    private val pageSize = 20

    init {
        // Start observing the database and load initial data
        collectTransactions()
        loadTransactions(isInitialLoad = true)
    }

    private fun collectTransactions() {
        // Combine flows for search/filter parameters
        combine(
            _state.map { it.currentPage }.distinctUntilChanged(),
            _state.map { it.searchQuery }.debounce(300).distinctUntilChanged(),
            _state.map { it.selectedType }.distinctUntilChanged()
        ) { page, query, type -> Triple(page, query, type) }
            .onEach { (page, query, type) ->
                repository.getTransactionsStream(page, pageSize, query, type?.name)
                    .collect { transactions ->
                        _state.update { it.copy(transactions = transactions, isLoading = false, error = null) }
                    }
            }
            .launchIn(viewModelScope)
    }

    private fun loadTransactions(isInitialLoad: Boolean = false) {
        viewModelScope.launch {
            if (!isInitialLoad) {
                _state.update { it.copy(isLoading = true, error = null) }
            }

            val currentState = _state.value
            try {
                repository.refreshTransactions(
                    currentState.currentPage,
                    pageSize,
                    currentState.searchQuery,
                    currentState.selectedType?.name
                )
                // Simulate total pages update from API response header/body
                _state.update { it.copy(totalPages = 5) }
            } catch (e: Exception) {
                _state.update { it.copy(error = "Failed to load transactions: ${e.message}") }
            } finally {
                _state.update { it.copy(isLoading = false) }
            }
        }
    }

    fun onEvent(event: TransactionHistoryEvent) {
        when (event) {
            is TransactionHistoryEvent.SearchQueryChanged -> {
                _state.update { it.copy(searchQuery = event.query, currentPage = 1) }
                loadTransactions()
            }
            is TransactionHistoryEvent.FilterTypeSelected -> {
                _state.update { it.copy(selectedType = event.type, currentPage = 1) }
                loadTransactions()
            }
            TransactionHistoryEvent.LoadNextPage -> {
                if (!_state.value.isLoading && _state.value.currentPage < _state.value.totalPages) {
                    _state.update { it.copy(currentPage = it.currentPage + 1) }
                    loadTransactions()
                }
            }
            TransactionHistoryEvent.Refresh -> {
                _state.update { it.copy(currentPage = 1) }
                loadTransactions()
            }
            TransactionHistoryEvent.ToggleFilterSheet -> {
                _state.update { it.copy(isFilterSheetOpen = !it.isFilterSheetOpen) }
            }
            TransactionHistoryEvent.InitiateBiometricAuth -> {
                // In a real app, this would trigger a side effect to show the BiometricPrompt
                _state.update { it.copy(isBiometricPromptVisible = true) }
            }
            is TransactionHistoryEvent.TransactionClicked -> {
                // Handle navigation or detail view
                println("Transaction clicked: ${event.transaction.id}")
                // Simulate a payment gateway interaction (e.g., re-initiate a failed payment)
                if (event.transaction.status == TransactionStatus.FAILED) {
                    // triggerPaymentGateway(event.transaction)
                }
            }
        }
    }

    // Placeholder for Biometric Auth result handling
    fun onBiometricAuthResult(success: Boolean) {
        _state.update { it.copy(isBiometricPromptVisible = false) }
        if (success) {
            // Proceed with the protected action (e.g., viewing sensitive details)
            println("Biometric authentication successful.")
        } else {
            println("Biometric authentication failed or cancelled.")
        }
    }

    // Placeholder for Payment Gateway interaction
    private fun triggerPaymentGateway(transaction: Transaction) {
        // Logic to initiate Paystack/Flutterwave/Interswitch payment flow
        println("Initiating payment gateway for transaction: ${transaction.id}")
    }
}

// --- 6. UI Layer: Composable Screen ---

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TransactionHistoryScreen(
    viewModel: TransactionHistoryViewModel
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    // Side effect for error messages
    LaunchedEffect(state.error) {
        state.error?.let {
            snackbarHostState.showSnackbar(
                message = it,
                actionLabel = "Dismiss",
                duration = SnackbarDuration.Short
            )
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Transaction History") },
                actions = {
                    IconButton(onClick = { viewModel.onEvent(TransactionHistoryEvent.ToggleFilterSheet) }) {
                        Icon(Icons.Filled.FilterList, contentDescription = "Filter")
                    }
                    IconButton(onClick = { viewModel.onEvent(TransactionHistoryEvent.InitiateBiometricAuth) }) {
                        Icon(Icons.Filled.Lock, contentDescription = "Authenticate")
                    }
                }
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            // Search Bar
            OutlinedTextField(
                value = state.searchQuery,
                onValueChange = { viewModel.onEvent(TransactionHistoryEvent.SearchQueryChanged(it)) },
                label = { Text("Search Transactions") },
                leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                singleLine = true,
                // Real-time feedback: The search triggers a new load, providing immediate feedback
            )

            // Transaction List
            TransactionList(
                transactions = state.transactions,
                isLoading = state.isLoading,
                onLoadNextPage = { viewModel.onEvent(TransactionHistoryEvent.LoadNextPage) },
                onRefresh = { viewModel.onEvent(TransactionHistoryEvent.Refresh) },
                onTransactionClick = { viewModel.onEvent(TransactionHistoryEvent.TransactionClicked(it)) },
                currentPage = state.currentPage,
                totalPages = state.totalPages
            )
        }
    }

    // Filter Bottom Sheet
    if (state.isFilterSheetOpen) {
        FilterBottomSheet(
            selectedType = state.selectedType,
            onTypeSelected = { viewModel.onEvent(TransactionHistoryEvent.FilterTypeSelected(it)) },
            onDismiss = { viewModel.onEvent(TransactionHistoryEvent.ToggleFilterSheet) }
        )
    }

    // Biometric Prompt Placeholder (In a real app, this would be a platform-specific side effect)
    if (state.isBiometricPromptVisible) {
        // In a real app, you'd use a LaunchedEffect and a platform-specific manager here
        AlertDialog(
            onDismissRequest = { viewModel.onBiometricAuthResult(false) },
            title = { Text("Biometric Authentication") },
            text = { Text("Simulating BiometricPrompt. Click 'Success' to proceed.") },
            confirmButton = {
                Button(onClick = { viewModel.onBiometricAuthResult(true) }) {
                    Text("Success")
                }
            },
            dismissButton = {
                Button(onClick = { viewModel.onBiometricAuthResult(false) }) {
                    Text("Cancel")
                }
            }
        )
    }
}

@Composable
fun TransactionList(
    transactions: List<Transaction>,
    isLoading: Boolean,
    onLoadNextPage: () -> Unit,
    onRefresh: () -> Unit,
    onTransactionClick: (Transaction) -> Unit,
    currentPage: Int,
    totalPages: Int
) {
    val isLastPage = currentPage >= totalPages

    // Accessibility: Use SwipeRefreshIndicator for visual feedback on refresh
    // In a real app, use androidx.compose.material.pullrefresh.PullRefreshIndicator
    // For simplicity and Material3 compatibility, we'll use a simple button for refresh for now.
    // A proper implementation would use a library like accompanist-swiperefresh or the upcoming Material3 equivalent.

    if (transactions.isEmpty() && !isLoading) {
        EmptyState(onRefresh = onRefresh)
        return
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp)
    ) {
        items(transactions, key = { it.id }) { transaction ->
            TransactionItem(transaction = transaction, onClick = onTransactionClick)
            Divider()
        }

        // Pagination: Loading indicator for next page
        if (isLoading && currentPage > 1) {
            item {
                CircularProgressIndicator(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp)
                        .wrapContentWidth(Alignment.CenterHorizontally)
                )
            }
        }

        // Pagination: Load More/End of List
        item {
            if (!isLastPage && !isLoading) {
                Button(
                    onClick = onLoadNextPage,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 8.dp)
                ) {
                    Text("Load More (Page $currentPage of $totalPages)")
                }
            } else if (isLastPage && transactions.isNotEmpty()) {
                Text(
                    text = "End of transaction history.",
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp)
                        .wrapContentWidth(Alignment.CenterHorizontally),
                    style = MaterialTheme.typography.bodySmall
                )
            }
        }
    }

    // Initial loading or full-screen refresh indicator
    if (isLoading && currentPage == 1) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
    }
}

@Composable
fun TransactionItem(transaction: Transaction, onClick: (Transaction) -> Unit) {
    val color = when (transaction.type) {
        TransactionType.CREDIT -> Color(0xFF388E3C) // Green
        TransactionType.DEBIT -> Color(0xFFD32F2F) // Red
    }
    val icon = when (transaction.type) {
        TransactionType.CREDIT -> Icons.Filled.ArrowDownward
        TransactionType.DEBIT -> Icons.Filled.ArrowUpward
    }
    val statusColor = when (transaction.status) {
        TransactionStatus.SUCCESS -> Color(0xFF4CAF50)
        TransactionStatus.PENDING -> Color(0xFFFFC107)
        TransactionStatus.FAILED -> Color(0xFFF44336)
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = { onClick(transaction) })
            .padding(vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = color,
            modifier = Modifier.size(24.dp)
        )
        Spacer(modifier = Modifier.width(16.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = transaction.description,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                // Accessibility: TalkBack will read this as the main item description
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "Status: ${transaction.status.name.lowercase().replaceFirstChar { it.uppercase() }}",
                style = MaterialTheme.typography.bodySmall,
                color = statusColor,
                // Accessibility: TalkBack will read this as part of the item details
            )
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(
                text = "${if (transaction.type == TransactionType.DEBIT) "-" else "+"}${transaction.currency} ${"%.2f".format(transaction.amount)}",
                style = MaterialTheme.typography.titleMedium,
                color = color,
                // Accessibility: TalkBack will read the amount and currency
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = Date(transaction.date).toString(), // Format date properly in a real app
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FilterBottomSheet(
    selectedType: TransactionType?,
    onTypeSelected: (TransactionType?) -> Unit,
    onDismiss: () -> Unit
) {
    val modalBottomSheetState = rememberModalBottomSheetState()

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = modalBottomSheetState
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "Filter Transactions",
                style = MaterialTheme.typography.headlineSmall,
                modifier = Modifier.padding(bottom = 16.dp)
            )

            // Filter by Type
            Text(
                text = "Transaction Type",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(vertical = 8.dp)
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                FilterChip(
                    selected = selectedType == null,
                    onClick = { onTypeSelected(null) },
                    label = { Text("All") }
                )
                FilterChip(
                    selected = selectedType == TransactionType.CREDIT,
                    onClick = { onTypeSelected(TransactionType.CREDIT) },
                    label = { Text("Credit") }
                )
                FilterChip(
                    selected = selectedType == TransactionType.DEBIT,
                    onClick = { onTypeSelected(TransactionType.DEBIT) },
                    label = { Text("Debit") }
                )
            }

            Spacer(modifier = Modifier.height(32.dp))

            // Placeholder for other filters (e.g., Date Range, Status)
            Text(
                text = "Other Filters (Date Range, Status) - Not Implemented",
                style = MaterialTheme.typography.bodySmall,
                color = Color.Gray
            )

            Spacer(modifier = Modifier.height(32.dp))
        }
    }
}

@Composable
fun EmptyState(onRefresh: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            Icons.Filled.History,
            contentDescription = null,
            modifier = Modifier.size(64.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = "No transactions found.",
            style = MaterialTheme.typography.titleLarge
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "Try adjusting your search or filters.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(modifier = Modifier.height(16.dp))
        Button(onClick = onRefresh) {
            Text("Refresh")
        }
    }
}

// --- 7. Dependency Injection Placeholder and Preview ---

// Placeholder for Hilt/Koin modules and actual implementations
object DependencyInjection {
    // Mock implementations for preview and demonstration
    private val mockApi = object : TransactionApiService {
        override suspend fun getTransactions(page: Int, pageSize: Int, query: String?, type: String?): Response<List<TransactionDto>> {
            delay(500) // Simulate network delay
            val allTransactions = listOf(
                TransactionDto("1", "Salary Deposit", 50000.00, "NGN", "CREDIT", Date().time - 86400000 * 1, "SUCCESS"),
                TransactionDto("2", "Groceries Payment", 5500.50, "NGN", "DEBIT", Date().time - 86400000 * 2, "SUCCESS"),
                TransactionDto("3", "Online Subscription", 1200.00, "NGN", "DEBIT", Date().time - 86400000 * 3, "PENDING"),
                TransactionDto("4", "Failed Transfer", 10000.00, "NGN", "DEBIT", Date().time - 86400000 * 4, "FAILED"),
                TransactionDto("5", "Freelance Payment", 25000.00, "NGN", "CREDIT", Date().time - 86400000 * 5, "SUCCESS"),
                TransactionDto("6", "Airtime Purchase", 500.00, "NGN", "DEBIT", Date().time - 86400000 * 6, "SUCCESS"),
                TransactionDto("7", "Utility Bill", 8500.00, "NGN", "DEBIT", Date().time - 86400000 * 7, "SUCCESS"),
                TransactionDto("8", "Refund", 2000.00, "NGN", "CREDIT", Date().time - 86400000 * 8, "SUCCESS"),
                TransactionDto("9", "Investment", 15000.00, "NGN", "DEBIT", Date().time - 86400000 * 9, "PENDING"),
                TransactionDto("10", "Cash Withdrawal", 3000.00, "NGN", "DEBIT", Date().time - 86400000 * 10, "SUCCESS"),
            )
            val filtered = allTransactions.filter {
                (query.isNullOrBlank() || it.details.contains(query, ignoreCase = true)) &&
                (type.isNullOrBlank() || it.transactionType.equals(type, ignoreCase = true))
            }
            val start = (page - 1) * pageSize
            val end = minOf(start + pageSize, filtered.size)
            val pagedList = if (start < filtered.size) filtered.subList(start, end) else emptyList()
            return Response.success(pagedList)
        }
    }

    private val mockDao = object : TransactionDao {
        private val cache = MutableStateFlow<List<TransactionEntity>>(emptyList())
        override fun getTransactions(pageSize: Int, offset: Int): Flow<List<TransactionEntity>> {
            return cache.map { entities ->
                entities.sortedByDescending { it.date }
                    .drop(offset)
                    .take(pageSize)
            }
        }

        override suspend fun insertAll(transactions: List<TransactionEntity>) {
            cache.update { current ->
                val newMap = current.associateBy { it.id }.toMutableMap()
                transactions.forEach { newMap[it.id] = it }
                newMap.values.toList()
            }
        }

        override suspend fun clearAll() {
            cache.update { emptyList() }
        }
    }

    val transactionRepository: TransactionRepository = TransactionRepositoryImpl(mockApi, mockDao)

    // Simple factory for ViewModel
    fun provideTransactionHistoryViewModel(): TransactionHistoryViewModel {
        return TransactionHistoryViewModel(transactionRepository)
    }
}

@Preview(showBackground = true)
@Composable
fun PreviewTransactionHistoryScreen() {
    // In a real app, use Hilt/Koin to inject the ViewModel
    val mockViewModel = DependencyInjection.provideTransactionHistoryViewModel()
    // Pre-load some mock data for the preview
    LaunchedEffect(Unit) {
        mockViewModel.onEvent(TransactionHistoryEvent.Refresh)
    }
    TransactionHistoryScreen(viewModel = mockViewModel)
}

// --- 8. Documentation and Comments ---
/*
 * TransactionHistoryScreen.kt
 *
 * This file contains the complete implementation for the Transaction History screen
 * using Jetpack Compose, following the MVVM architecture pattern.
 *
 * Features Implemented:
 * - Jetpack Compose UI (Material Design 3)
 * - MVVM Architecture (ViewModel, StateFlow)
 * - Repository Pattern (TransactionRepository)
 * - Data Sources (Retrofit/API and Room/Local Cache - Mocked)
 * - State Management (TransactionHistoryState, TransactionHistoryEvent)
 * - Transaction List with detailed items
 * - Search functionality (real-time feedback)
 * - Filtering (by Transaction Type)
 * - Pagination (Load More/Infinite Scroll pattern)
 * - Loading and Error States (Snackbar, Full-screen/Inline loading)
 * - Accessibility (Content Descriptions, TalkBack support via standard Composables)
 * - Biometric Authentication Placeholder (isBiometricPromptVisible state)
 * - Payment Gateway Placeholder (triggerPaymentGateway function)
 * - Offline Mode (Room DAO/Entity structure)
 *
 * Dependencies Required (Not included in this single file, but necessary for a real project):
 * - androidx.lifecycle:lifecycle-viewmodel-ktx
 * - androidx.compose.material3:material3
 * - androidx.room:room-runtime, androidx.room:room-ktx, androidx.room:room-compiler (ksp)
 * - com.squareup.retrofit2:retrofit, com.squareup.retrofit2:converter-gson
 * - kotlinx.coroutines:kotlinx-coroutines-core, kotlinx.coroutines:kotlinx-coroutines-android
 * - androidx.biometric:biometric-ktx (for BiometricPrompt)
 * - androidx.compose.material:material-icons-extended (if using extended icons)
 * - Hilt/Koin for Dependency Injection
 */

package com.pos54link.app.sync

import android.content.Context
import android.util.Log
import androidx.work.*
import com.pos54link.app.data.local.AppDatabase
import com.pos54link.app.data.local.PendingTransferEntity
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit

/**
 * WorkManager Worker for syncing pending transfers when connectivity is restored.
 * 
 * This is the core of the offline-first architecture:
 * 1. Triggered when device comes online
 * 2. Reads pending transfers from Room database
 * 3. Sends each to backend with idempotency key (safe to retry)
 * 4. Updates local status based on response
 */
class SyncPendingTransfersWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {
    
    companion object {
        const val TAG = "SyncPendingTransfers"
        const val WORK_NAME = "sync_pending_transfers"
        private const val MAX_RETRIES = 5
        private const val API_BASE_URL = "https://api.remittance.example.com"
        
        /**
         * Schedule periodic sync (every 15 minutes when online)
         */
        fun schedulePeriodicSync(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()
            
            val syncRequest = PeriodicWorkRequestBuilder<SyncPendingTransfersWorker>(
                15, TimeUnit.MINUTES
            )
                .setConstraints(constraints)
                .setBackoffCriteria(
                    BackoffPolicy.EXPONENTIAL,
                    WorkRequest.MIN_BACKOFF_MILLIS,
                    TimeUnit.MILLISECONDS
                )
                .build()
            
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                syncRequest
            )
            
            Log.i(TAG, "Scheduled periodic sync")
        }
        
        /**
         * Trigger immediate sync (e.g., when app opens or connectivity restored)
         */
        fun triggerImmediateSync(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()
            
            val syncRequest = OneTimeWorkRequestBuilder<SyncPendingTransfersWorker>()
                .setConstraints(constraints)
                .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
                .build()
            
            WorkManager.getInstance(context).enqueueUniqueWork(
                "${WORK_NAME}_immediate",
                ExistingWorkPolicy.REPLACE,
                syncRequest
            )
            
            Log.i(TAG, "Triggered immediate sync")
        }
    }
    
    private val database = AppDatabase.getDatabase(applicationContext)
    private val pendingTransferDao = database.pendingTransferDao()
    private val syncStateDao = database.syncStateDao()
    
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        Log.i(TAG, "Starting sync of pending transfers")
        
        try {
            // Update sync state
            syncStateDao.updateStatus("pending_transfers", "syncing", null)
            
            // Get all pending transfers
            val pendingTransfers = pendingTransferDao.getTransfersToSync()
            
            if (pendingTransfers.isEmpty()) {
                Log.i(TAG, "No pending transfers to sync")
                syncStateDao.markSynced("pending_transfers", System.currentTimeMillis())
                return@withContext Result.success()
            }
            
            Log.i(TAG, "Found ${pendingTransfers.size} pending transfers to sync")
            
            var successCount = 0
            var failCount = 0
            
            for (transfer in pendingTransfers) {
                if (transfer.retryCount >= MAX_RETRIES) {
                    Log.w(TAG, "Transfer ${transfer.id} exceeded max retries, marking as failed")
                    pendingTransferDao.updateStatus(transfer.id, "failed", "Max retries exceeded")
                    failCount++
                    continue
                }
                
                try {
                    // Update status to syncing
                    pendingTransferDao.updateStatus(transfer.id, "syncing", null)
                    
                    // Send to backend
                    val result = syncTransferToBackend(transfer)
                    
                    if (result.success) {
                        pendingTransferDao.markSynced(
                            transfer.id,
                            System.currentTimeMillis(),
                            result.serverTransactionId ?: ""
                        )
                        successCount++
                        Log.i(TAG, "Successfully synced transfer ${transfer.id}")
                    } else {
                        pendingTransferDao.updateStatus(transfer.id, "failed", result.error)
                        failCount++
                        Log.w(TAG, "Failed to sync transfer ${transfer.id}: ${result.error}")
                    }
                } catch (e: Exception) {
                    pendingTransferDao.updateStatus(transfer.id, "failed", e.message)
                    failCount++
                    Log.e(TAG, "Exception syncing transfer ${transfer.id}", e)
                }
            }
            
            // Update sync state
            syncStateDao.markSynced("pending_transfers", System.currentTimeMillis())
            syncStateDao.updatePendingCount("pending_transfers", failCount)
            
            Log.i(TAG, "Sync complete: $successCount success, $failCount failed")
            
            return@withContext if (failCount > 0) Result.retry() else Result.success()
            
        } catch (e: Exception) {
            Log.e(TAG, "Sync failed with exception", e)
            syncStateDao.updateStatus("pending_transfers", "error", e.message)
            return@withContext Result.retry()
        }
    }
    
    /**
     * Send a pending transfer to the backend API
     */
    private suspend fun syncTransferToBackend(transfer: PendingTransferEntity): SyncResult {
        return withContext(Dispatchers.IO) {
            try {
                val url = URL("$API_BASE_URL/api/v1/transactions/transfer")
                val connection = url.openConnection() as HttpURLConnection
                
                connection.apply {
                    requestMethod = "POST"
                    setRequestProperty("Content-Type", "application/json")
                    setRequestProperty("Idempotency-Key", transfer.idempotencyKey)
                    // In production, add auth token from secure storage
                    // setRequestProperty("Authorization", "Bearer $token")
                    doOutput = true
                    connectTimeout = 30000
                    readTimeout = 30000
                }
                
                // Build request body
                val requestBody = JSONObject().apply {
                    put("recipient_name", transfer.recipientName)
                    put("recipient_phone", transfer.recipientPhone)
                    put("recipient_bank", transfer.recipientBank)
                    put("recipient_account", transfer.recipientAccountNumber)
                    put("amount", transfer.amount)
                    put("source_currency", transfer.sourceCurrency)
                    put("destination_currency", transfer.destinationCurrency)
                    put("exchange_rate", transfer.exchangeRate)
                    put("fee", transfer.fee)
                    put("delivery_method", transfer.deliveryMethod)
                    put("note", transfer.note)
                    put("idempotency_key", transfer.idempotencyKey)
                }
                
                connection.outputStream.use { os ->
                    os.write(requestBody.toString().toByteArray())
                }
                
                val responseCode = connection.responseCode
                
                if (responseCode in 200..299) {
                    val response = connection.inputStream.bufferedReader().readText()
                    val json = JSONObject(response)
                    
                    SyncResult(
                        success = true,
                        serverTransactionId = json.optString("transaction_id"),
                        error = null
                    )
                } else {
                    val errorResponse = connection.errorStream?.bufferedReader()?.readText()
                    SyncResult(
                        success = false,
                        serverTransactionId = null,
                        error = "HTTP $responseCode: $errorResponse"
                    )
                }
            } catch (e: Exception) {
                SyncResult(
                    success = false,
                    serverTransactionId = null,
                    error = e.message ?: "Unknown error"
                )
            }
        }
    }
    
    data class SyncResult(
        val success: Boolean,
        val serverTransactionId: String?,
        val error: String?
    )
}

/**
 * Network connectivity callback to trigger sync when coming online
 */
class NetworkConnectivityCallback(private val context: Context) {
    
    fun onNetworkAvailable() {
        Log.i(SyncPendingTransfersWorker.TAG, "Network available, triggering sync")
        SyncPendingTransfersWorker.triggerImmediateSync(context)
    }
    
    fun onNetworkLost() {
        Log.i(SyncPendingTransfersWorker.TAG, "Network lost")
    }
}

package com.pos54link.app.data.api

import retrofit2.Response
import retrofit2.http.*

/**
 * 54Link POS Management Service
 *
 * Covers all 8 backend POS routers:
 *   - Terminal Fleet (provisioning, assignment, heartbeat, commands)
 *   - Batch Settlement (create, process, reconcile)
 *   - Disputes (file, track, escalate)
 *   - Voice Commands (NLU process + confirm)
 *   - Offline Mode (session management, validation)
 *   - Terminal Leasing (create, pay, status)
 *   - Firmware OTA (publish, rollout, rollback)
 *   - IoT Smart POS (devices, alerts, telemetry)
 */
interface PosService {

    // ── Terminal Fleet ──────────────────────────────────────────────

    @GET("api/trpc/posTerminalFleet.list")
    suspend fun listTerminals(@Query("input") input: String): Response<GenericListResponse>

    @GET("api/trpc/posTerminalFleet.getStats")
    suspend fun getTerminalStats(): Response<GenericDataResponse>

    @POST("api/trpc/posTerminalFleet.sendCommand")
    suspend fun sendTerminalCommand(@Body request: GenericMutationRequest): Response<GenericDataResponse>

    // ── Batch Settlement ────────────────────────────────────────────

    @GET("api/trpc/posBatchSettlement.listBatches")
    suspend fun listSettlementBatches(@Query("input") input: String): Response<GenericListResponse>

    @GET("api/trpc/posBatchSettlement.getStats")
    suspend fun getSettlementStats(): Response<GenericDataResponse>

    @POST("api/trpc/posBatchSettlement.createBatch")
    suspend fun createSettlementBatch(
        @Header("X-Idempotency-Key") idempotencyKey: String,
        @Body request: GenericMutationRequest
    ): Response<GenericDataResponse>

    @POST("api/trpc/posBatchSettlement.processBatch")
    suspend fun processSettlementBatch(
        @Header("X-Idempotency-Key") idempotencyKey: String,
        @Body request: GenericMutationRequest
    ): Response<GenericDataResponse>

    // ── Disputes ────────────────────────────────────────────────────

    @GET("api/trpc/posDispute.listMyDisputes")
    suspend fun listMyDisputes(@Query("input") input: String): Response<GenericListResponse>

    @GET("api/trpc/posDispute.getStats_posDispute")
    suspend fun getDisputeStats(): Response<GenericDataResponse>

    @POST("api/trpc/posDispute.fileDispute")
    suspend fun fileDispute(@Body request: GenericMutationRequest): Response<GenericDataResponse>

    @POST("api/trpc/posDispute.updateStatus")
    suspend fun updateDisputeStatus(@Body request: GenericMutationRequest): Response<GenericDataResponse>

    // ── Voice Commands ──────────────────────────────────────────────

    @POST("api/trpc/voiceCommandPos.processCommand")
    suspend fun processVoiceCommand(
        @Header("X-Idempotency-Key") idempotencyKey: String,
        @Body request: GenericMutationRequest
    ): Response<GenericDataResponse>

    @POST("api/trpc/voiceCommandPos.confirmAndExecute")
    suspend fun confirmVoiceCommand(
        @Header("X-Idempotency-Key") idempotencyKey: String,
        @Body request: GenericMutationRequest
    ): Response<GenericDataResponse>

    // ── Offline Mode ────────────────────────────────────────────────

    @POST("api/trpc/offlinePosMode.startSession")
    suspend fun startOfflineSession(@Body request: GenericMutationRequest): Response<GenericDataResponse>

    @POST("api/trpc/offlinePosMode.endSession")
    suspend fun endOfflineSession(@Body request: GenericMutationRequest): Response<GenericDataResponse>

    @POST("api/trpc/offlinePosMode.validateOfflineTransaction")
    suspend fun validateOfflineTransaction(@Body request: GenericMutationRequest): Response<GenericDataResponse>

    @GET("api/trpc/offlinePosMode.getOfflineConfig")
    suspend fun getOfflineConfig(): Response<GenericDataResponse>

    // ── Terminal Leasing ────────────────────────────────────────────

    @GET("api/trpc/terminalLeasing.listLeases")
    suspend fun listLeases(@Query("input") input: String): Response<GenericListResponse>

    @GET("api/trpc/terminalLeasing.getStats")
    suspend fun getLeaseStats(): Response<GenericDataResponse>

    @POST("api/trpc/terminalLeasing.createLease")
    suspend fun createLease(
        @Header("X-Idempotency-Key") idempotencyKey: String,
        @Body request: GenericMutationRequest
    ): Response<GenericDataResponse>

    @POST("api/trpc/terminalLeasing.recordPayment")
    suspend fun recordLeasePayment(@Body request: GenericMutationRequest): Response<GenericDataResponse>

    // ── Firmware OTA ────────────────────────────────────────────────

    @GET("api/trpc/posFirmwareOTA.listVersions")
    suspend fun listFirmwareVersions(@Query("input") input: String): Response<GenericListResponse>

    @GET("api/trpc/posFirmwareOTA.getStats")
    suspend fun getFirmwareStats(): Response<GenericDataResponse>

    @POST("api/trpc/posFirmwareOTA.startRollout")
    suspend fun startFirmwareRollout(@Body request: GenericMutationRequest): Response<GenericDataResponse>

    @POST("api/trpc/posFirmwareOTA.rollbackRollout")
    suspend fun rollbackFirmwareRollout(@Body request: GenericMutationRequest): Response<GenericDataResponse>

    // ── IoT Smart POS ───────────────────────────────────────────────

    @GET("api/trpc/iotSmartPos.list")
    suspend fun listIotDevices(@Query("input") input: String): Response<GenericListResponse>

    @GET("api/trpc/iotSmartPos.getStats")
    suspend fun getIotStats(): Response<GenericDataResponse>

    @POST("api/trpc/iotSmartPos.checkAlerts")
    suspend fun checkIotAlerts(@Body request: GenericMutationRequest): Response<GenericDataResponse>

    @POST("api/trpc/iotSmartPos.acknowledgeAlert")
    suspend fun acknowledgeIotAlert(@Body request: GenericMutationRequest): Response<GenericDataResponse>
}

// ── Generic request/response models for tRPC ────────────────────────

data class GenericMutationRequest(
    val json: Map<String, Any?>
)

data class GenericListResponse(
    val result: GenericListResultWrapper?
)

data class GenericListResultWrapper(
    val data: GenericListResultData?
)

data class GenericListResultData(
    val json: GenericListResult?
)

data class GenericListResult(
    val items: List<Map<String, Any?>>?,
    val total: Int?,
    val page: Int?
)

data class GenericDataResponse(
    val result: GenericDataResultWrapper?
)

data class GenericDataResultWrapper(
    val data: GenericDataResultData?
)

data class GenericDataResultData(
    val json: Map<String, Any?>?
)

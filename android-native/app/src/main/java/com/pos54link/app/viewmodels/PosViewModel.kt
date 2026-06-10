package com.pos54link.app.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pos54link.app.data.api.*
import com.pos54link.app.security.IdempotencyKeyGenerator
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class PosUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val successMessage: String? = null,
    // Terminal Fleet
    val terminals: List<Map<String, Any?>> = emptyList(),
    val terminalStats: Map<String, Any?> = emptyMap(),
    // Settlement
    val settlementBatches: List<Map<String, Any?>> = emptyList(),
    val settlementStats: Map<String, Any?> = emptyMap(),
    // Disputes
    val disputes: List<Map<String, Any?>> = emptyList(),
    val disputeStats: Map<String, Any?> = emptyMap(),
    // Voice Command
    val voiceIntent: Map<String, Any?>? = null,
    val voiceConfirmationId: String? = null,
    // Leases
    val leases: List<Map<String, Any?>> = emptyList(),
    val leaseStats: Map<String, Any?> = emptyMap(),
    // Firmware
    val firmwareVersions: List<Map<String, Any?>> = emptyList(),
    val firmwareStats: Map<String, Any?> = emptyMap(),
    // IoT Devices
    val iotDevices: List<Map<String, Any?>> = emptyList(),
    val iotAlerts: List<Map<String, Any?>> = emptyList()
)

@HiltViewModel
class PosViewModel @Inject constructor(
    private val posService: PosService
) : ViewModel() {

    private val _uiState = MutableStateFlow(PosUiState())
    val uiState: StateFlow<PosUiState> = _uiState.asStateFlow()

    // ── Terminal Fleet ────────────────────────────────────────────────

    fun loadTerminals() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val response = posService.listTerminals("{}")
                val statsResponse = posService.getTerminalStats()
                if (response.isSuccessful) {
                    val items = response.body()?.result?.data?.json?.items ?: emptyList()
                    val stats = statsResponse.body()?.result?.data?.json ?: emptyMap()
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        terminals = items,
                        terminalStats = stats
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Failed to load terminals (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = e.message ?: "Failed to load terminals"
                )
            }
        }
    }

    fun sendTerminalCommand(terminalId: String, command: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val response = posService.sendTerminalCommand(
                    GenericMutationRequest(json = mapOf("terminalId" to terminalId, "command" to command))
                )
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        successMessage = "Command '$command' sent to terminal"
                    )
                    loadTerminals()
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Command failed (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
            }
        }
    }

    // ── Batch Settlement ──────────────────────────────────────────────

    fun loadSettlementBatches() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val response = posService.listSettlementBatches("{}")
                val statsResponse = posService.getSettlementStats()
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        settlementBatches = response.body()?.result?.data?.json?.items ?: emptyList(),
                        settlementStats = statsResponse.body()?.result?.data?.json ?: emptyMap()
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Failed to load settlements (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
            }
        }
    }

    fun createSettlementBatch(periodStart: String, periodEnd: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val idempotencyKey = IdempotencyKeyGenerator.generate()
            try {
                val response = posService.createSettlementBatch(
                    idempotencyKey = idempotencyKey,
                    request = GenericMutationRequest(
                        json = mapOf("periodStart" to periodStart, "periodEnd" to periodEnd)
                    )
                )
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        successMessage = "Settlement batch created"
                    )
                    loadSettlementBatches()
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Failed to create batch (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
            }
        }
    }

    // ── Disputes ──────────────────────────────────────────────────────

    fun loadDisputes() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val response = posService.listMyDisputes("{}")
                val statsResponse = posService.getDisputeStats()
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        disputes = response.body()?.result?.data?.json?.items ?: emptyList(),
                        disputeStats = statsResponse.body()?.result?.data?.json ?: emptyMap()
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Failed to load disputes (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
            }
        }
    }

    fun fileDispute(transactionRef: String, reason: String, description: String, expectedAmount: Double?) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val response = posService.fileDispute(
                    GenericMutationRequest(
                        json = mapOf(
                            "transactionRef" to transactionRef,
                            "reason" to reason,
                            "description" to description,
                            "expectedAmount" to expectedAmount,
                            "filedFromPOS" to true
                        )
                    )
                )
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        successMessage = "Dispute filed successfully"
                    )
                    loadDisputes()
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Failed to file dispute (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
            }
        }
    }

    // ── Voice Commands ────────────────────────────────────────────────

    fun processVoiceCommand(transcript: String, language: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null, voiceIntent = null)
            val idempotencyKey = IdempotencyKeyGenerator.generate()
            try {
                val response = posService.processVoiceCommand(
                    idempotencyKey = idempotencyKey,
                    request = GenericMutationRequest(
                        json = mapOf("transcript" to transcript, "language" to language)
                    )
                )
                if (response.isSuccessful) {
                    val data = response.body()?.result?.data?.json
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        voiceIntent = data,
                        voiceConfirmationId = data?.get("confirmationId") as? String
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Voice processing failed (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
            }
        }
    }

    fun confirmVoiceCommand(confirmationId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val idempotencyKey = IdempotencyKeyGenerator.generate()
            try {
                val response = posService.confirmVoiceCommand(
                    idempotencyKey = idempotencyKey,
                    request = GenericMutationRequest(
                        json = mapOf("confirmationId" to confirmationId)
                    )
                )
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        successMessage = "Voice command executed",
                        voiceIntent = null,
                        voiceConfirmationId = null
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Execution failed (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
            }
        }
    }

    // ── Terminal Leasing ──────────────────────────────────────────────

    fun loadLeases() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val response = posService.listLeases("{}")
                val statsResponse = posService.getLeaseStats()
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        leases = response.body()?.result?.data?.json?.items ?: emptyList(),
                        leaseStats = statsResponse.body()?.result?.data?.json ?: emptyMap()
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Failed to load leases (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
            }
        }
    }

    fun recordLeasePayment(leaseId: String, amount: Double) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val response = posService.recordLeasePayment(
                    GenericMutationRequest(json = mapOf("leaseId" to leaseId, "amount" to amount))
                )
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        successMessage = "Payment recorded"
                    )
                    loadLeases()
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Payment failed (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
            }
        }
    }

    // ── Firmware OTA ──────────────────────────────────────────────────

    fun loadFirmwareVersions() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val response = posService.listFirmwareVersions("{}")
                val statsResponse = posService.getFirmwareStats()
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        firmwareVersions = response.body()?.result?.data?.json?.items ?: emptyList(),
                        firmwareStats = statsResponse.body()?.result?.data?.json ?: emptyMap()
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Failed to load firmware (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
            }
        }
    }

    fun startFirmwareRollout(versionId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val response = posService.startFirmwareRollout(
                    GenericMutationRequest(json = mapOf("versionId" to versionId))
                )
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        successMessage = "Firmware rollout started"
                    )
                    loadFirmwareVersions()
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Rollout failed (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
            }
        }
    }

    fun rollbackFirmware(versionId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val response = posService.rollbackFirmwareRollout(
                    GenericMutationRequest(json = mapOf("versionId" to versionId))
                )
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        successMessage = "Firmware rollback initiated"
                    )
                    loadFirmwareVersions()
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Rollback failed (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
            }
        }
    }

    // ── IoT Smart POS ────────────────────────────────────────────────

    fun loadIotDevices() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val response = posService.listIotDevices("{}")
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        iotDevices = response.body()?.result?.data?.json?.items ?: emptyList()
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Failed to load IoT devices (${response.code()})"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
            }
        }
    }

    fun checkIotAlerts() {
        viewModelScope.launch {
            try {
                val response = posService.checkIotAlerts(
                    GenericMutationRequest(json = emptyMap())
                )
                if (response.isSuccessful) {
                    val alerts = response.body()?.result?.data?.json
                    val alertList = (alerts?.get("alerts") as? List<*>)
                        ?.filterIsInstance<Map<String, Any?>>() ?: emptyList()
                    _uiState.value = _uiState.value.copy(iotAlerts = alertList)
                }
            } catch (e: Exception) {
                // Non-critical
            }
        }
    }

    fun acknowledgeAlert(alertId: String) {
        viewModelScope.launch {
            try {
                posService.acknowledgeIotAlert(
                    GenericMutationRequest(json = mapOf("alertId" to alertId))
                )
                checkIotAlerts()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(error = e.message)
            }
        }
    }

    // ── Utilities ─────────────────────────────────────────────────────

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun clearSuccess() {
        _uiState.value = _uiState.value.copy(successMessage = null)
    }
}

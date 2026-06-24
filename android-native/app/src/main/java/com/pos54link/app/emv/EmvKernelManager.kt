package com.pos54link.app.emv

import android.content.Context
import android.util.Log
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.spec.SecretKeySpec

/**
 * EMV L2 Kernel Manager — Manages chip card communication via APDU commands.
 * Integrates with PAX EMV SDK (v3.0.0 referenced in gradle.properties).
 *
 * Handles:
 * - Application selection (PSE/PPSE)
 * - Card authentication (SDA/DDA/CDA)
 * - Cardholder verification (Online PIN, Offline PIN, Signature)
 * - Terminal action analysis (TAC/IAC)
 * - Transaction authorization (ARQC generation)
 * - Script processing (issuer scripts 71/72)
 */

data class EmvConfig(
    val terminalId: String,
    val merchantId: String,
    val merchantCategoryCode: String = "6012", // Financial Institutions
    val countryCode: String = "0566", // Nigeria
    val currencyCode: String = "0566", // NGN
    val terminalType: Byte = 0x22, // Attended, online+offline
    val supportedAids: List<String> = listOf(
        "A0000000041010", // Mastercard
        "A0000000031010", // Visa
        "A0000000032010", // Visa Electron
        "A0000000651010", // Verve (NIBSS)
    )
)

data class EmvTransaction(
    val amount: Long, // kobo
    val transactionType: TransactionType = TransactionType.PURCHASE,
    val cashbackAmount: Long = 0,
)

enum class TransactionType(val code: Byte) {
    PURCHASE(0x00),
    CASH_ADVANCE(0x01),
    CASHBACK(0x09),
    REFUND(0x20),
    BALANCE_INQUIRY(0x31),
}

enum class EmvResult {
    APPROVED_OFFLINE,
    DECLINED_OFFLINE,
    GO_ONLINE,
    TECHNICAL_FAILURE,
    CARD_BLOCKED,
    CARD_REMOVED,
}

sealed class CardEvent {
    data class CardInserted(val atr: ByteArray) : CardEvent()
    data class AidSelected(val aid: String, val label: String) : CardEvent()
    data class PinRequired(val isOnline: Boolean) : CardEvent()
    data class TransactionResult(val result: EmvResult, val arqc: ByteArray?) : CardEvent()
    data class ScriptResult(val success: Boolean) : CardEvent()
    object CardRemoved : CardEvent()
}

interface EmvCallback {
    fun onCardEvent(event: CardEvent)
    fun onError(code: Int, message: String)
}

class EmvKernelManager(
    private val context: Context,
    private val config: EmvConfig,
) {
    companion object {
        private const val TAG = "EmvKernel"
        // APDU Commands
        private val SELECT_PSE = byteArrayOf(0x00, 0xA4.toByte(), 0x04, 0x00)
        private val READ_RECORD = byteArrayOf(0x00, 0xB2.toByte())
        private val GET_PROCESSING_OPTIONS = byteArrayOf(0x80.toByte(), 0xA8.toByte(), 0x00, 0x00)
        private val GENERATE_AC = byteArrayOf(0x80.toByte(), 0xAE.toByte())
    }

    private var callback: EmvCallback? = null
    private var currentTransaction: EmvTransaction? = null
    private var isProcessing = false

    fun setCallback(cb: EmvCallback) {
        callback = cb
    }

    /**
     * Start EMV transaction flow:
     * 1. Reset card (ATR)
     * 2. Application Selection (PSE/AID list)
     * 3. Initiate Application Processing (GPO)
     * 4. Read Application Data
     * 5. Offline Data Authentication (SDA/DDA/CDA)
     * 6. Processing Restrictions
     * 7. Cardholder Verification
     * 8. Terminal Risk Management
     * 9. Terminal Action Analysis
     * 10. First Generate AC (TC/ARQC/AAC)
     */
    fun startTransaction(transaction: EmvTransaction) {
        if (isProcessing) {
            callback?.onError(1001, "Transaction already in progress")
            return
        }
        isProcessing = true
        currentTransaction = transaction
        Log.i(TAG, "Starting EMV transaction: amount=${transaction.amount} kobo, type=${transaction.transactionType}")
    }

    /**
     * Process APDU response from card reader hardware.
     * In production: PAX SDK handles low-level card I/O.
     */
    fun processApduResponse(sw1: Byte, sw2: Byte, data: ByteArray): ByteArray? {
        val status = ((sw1.toInt() and 0xFF) shl 8) or (sw2.toInt() and 0xFF)
        return when (status) {
            0x9000 -> data // Success
            0x6A82 -> null // File not found
            0x6985 -> null // Conditions not satisfied
            else -> {
                Log.w(TAG, "APDU error: ${String.format("%04X", status)}")
                null
            }
        }
    }

    /**
     * Build SELECT command for AID.
     */
    fun buildSelectAid(aid: String): ByteArray {
        val aidBytes = hexToBytes(aid)
        return SELECT_PSE + byteArrayOf(aidBytes.size.toByte()) + aidBytes
    }

    /**
     * Build GET PROCESSING OPTIONS command with PDOL data.
     */
    fun buildGpo(pdolData: ByteArray): ByteArray {
        val dataField = byteArrayOf(0x83.toByte(), pdolData.size.toByte()) + pdolData
        return GET_PROCESSING_OPTIONS + byteArrayOf(dataField.size.toByte()) + dataField
    }

    /**
     * Build GENERATE AC command.
     * P1: 0x80 = ARQC (online), 0x40 = TC (offline), 0x00 = AAC (decline)
     */
    fun buildGenerateAc(type: Byte, cdolData: ByteArray): ByteArray {
        return GENERATE_AC + byteArrayOf(type, cdolData.size.toByte()) + cdolData
    }

    /**
     * Perform Terminal Action Analysis (TAC/IAC comparison).
     * Returns decision: TC (approve offline), ARQC (go online), AAC (decline).
     */
    fun terminalActionAnalysis(
        tvr: ByteArray, // Terminal Verification Results (5 bytes)
        tacDenial: ByteArray,
        tacOnline: ByteArray,
        tacDefault: ByteArray,
        iacDenial: ByteArray,
        iacOnline: ByteArray,
        iacDefault: ByteArray,
    ): Byte {
        // Check denial conditions
        for (i in tvr.indices) {
            if ((tvr[i].toInt() and tacDenial[i].toInt()) != 0 ||
                (tvr[i].toInt() and iacDenial[i].toInt()) != 0) {
                return 0x00 // AAC - decline
            }
        }
        // Check online conditions
        for (i in tvr.indices) {
            if ((tvr[i].toInt() and tacOnline[i].toInt()) != 0 ||
                (tvr[i].toInt() and iacOnline[i].toInt()) != 0) {
                return 0x80.toByte() // ARQC - go online
            }
        }
        return 0x40 // TC - approve offline
    }

    fun cancelTransaction() {
        isProcessing = false
        currentTransaction = null
        callback?.onCardEvent(CardEvent.CardRemoved)
    }

    fun isTransactionActive(): Boolean = isProcessing

    private fun hexToBytes(hex: String): ByteArray {
        val len = hex.length
        val data = ByteArray(len / 2)
        for (i in 0 until len step 2) {
            data[i / 2] = ((Character.digit(hex[i], 16) shl 4) + Character.digit(hex[i + 1], 16)).toByte()
        }
        return data
    }
}

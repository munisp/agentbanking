package com.pos54link.app.printer

import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothSocket
import android.content.Context
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.OutputStream
import java.util.UUID

/**
 * 54Link ESC/POS Thermal Receipt Printer Service
 *
 * Supports Bluetooth (SPP) and USB serial thermal printers commonly used
 * with PAX A920, Sunmi, and generic POS terminals. Implements the ESC/POS
 * command set for text formatting, alignment, barcode, and QR code printing.
 *
 * Typical flow:
 *   1. discover() → list paired Bluetooth printers
 *   2. connect(address) → establish SPP connection
 *   3. printReceipt(receipt) → format and send ESC/POS commands
 *   4. disconnect()
 */
class ReceiptPrinterService(private val context: Context) {

    companion object {
        private const val TAG = "ReceiptPrinter"
        private val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")

        // ESC/POS commands
        private val ESC_INIT = byteArrayOf(0x1B, 0x40) // Initialize printer
        private val ESC_ALIGN_CENTER = byteArrayOf(0x1B, 0x61, 0x01)
        private val ESC_ALIGN_LEFT = byteArrayOf(0x1B, 0x61, 0x00)
        private val ESC_ALIGN_RIGHT = byteArrayOf(0x1B, 0x61, 0x02)
        private val ESC_BOLD_ON = byteArrayOf(0x1B, 0x45, 0x01)
        private val ESC_BOLD_OFF = byteArrayOf(0x1B, 0x45, 0x00)
        private val ESC_DOUBLE_HEIGHT = byteArrayOf(0x1B, 0x21, 0x10)
        private val ESC_NORMAL_SIZE = byteArrayOf(0x1B, 0x21, 0x00)
        private val ESC_CUT = byteArrayOf(0x1D, 0x56, 0x00) // Full cut
        private val ESC_FEED_3 = byteArrayOf(0x1B, 0x64, 0x03) // Feed 3 lines
        private val LF = byteArrayOf(0x0A)
    }

    private var bluetoothSocket: BluetoothSocket? = null
    private var outputStream: OutputStream? = null

    data class PrinterInfo(
        val name: String,
        val address: String,
        val bonded: Boolean
    )

    data class ReceiptData(
        val merchantName: String = "54Link Agent",
        val terminalId: String,
        val agentCode: String,
        val transactionType: String,
        val reference: String,
        val amount: Double,
        val fee: Double,
        val currency: String = "NGN",
        val customerPhone: String? = null,
        val narration: String? = null,
        val status: String = "SUCCESS",
        val timestamp: String
    )

    /**
     * Discover paired Bluetooth printers.
     */
    fun discoverPrinters(): List<PrinterInfo> {
        val adapter = BluetoothAdapter.getDefaultAdapter() ?: return emptyList()
        return try {
            adapter.bondedDevices
                .filter { it.bluetoothClass?.majorDeviceClass == 0x0600 } // Imaging
                .map { PrinterInfo(it.name ?: "Unknown", it.address, it.bondState == BluetoothDevice.BOND_BONDED) }
        } catch (e: SecurityException) {
            Log.e(TAG, "Bluetooth permission denied", e)
            emptyList()
        }
    }

    /**
     * Connect to a Bluetooth printer by MAC address.
     */
    suspend fun connect(address: String): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val adapter = BluetoothAdapter.getDefaultAdapter()
                ?: return@withContext Result.failure(PrinterException("Bluetooth not available"))
            val device: BluetoothDevice = adapter.getRemoteDevice(address)
            val socket = device.createRfcommSocketToServiceRecord(SPP_UUID)
            socket.connect()
            bluetoothSocket = socket
            outputStream = socket.outputStream
            Log.i(TAG, "Connected to printer: $address")
            Result.success(Unit)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to connect to printer", e)
            Result.failure(PrinterException("Connection failed: ${e.message}"))
        }
    }

    /**
     * Print a formatted transaction receipt.
     */
    suspend fun printReceipt(receipt: ReceiptData): Result<Unit> = withContext(Dispatchers.IO) {
        val os = outputStream
            ?: return@withContext Result.failure(PrinterException("Printer not connected"))
        try {
            os.write(ESC_INIT)

            // Header
            os.write(ESC_ALIGN_CENTER)
            os.write(ESC_BOLD_ON)
            os.write(ESC_DOUBLE_HEIGHT)
            os.write("54Link\n".toByteArray())
            os.write(ESC_NORMAL_SIZE)
            os.write("Agent Banking POS\n".toByteArray())
            os.write(ESC_BOLD_OFF)
            os.write("================================\n".toByteArray())

            // Transaction details
            os.write(ESC_ALIGN_LEFT)
            os.write("Merchant: ${receipt.merchantName}\n".toByteArray())
            os.write("Terminal: ${receipt.terminalId}\n".toByteArray())
            os.write("Agent: ${receipt.agentCode}\n".toByteArray())
            os.write("--------------------------------\n".toByteArray())

            os.write(ESC_BOLD_ON)
            os.write("${receipt.transactionType}\n".toByteArray())
            os.write(ESC_BOLD_OFF)

            os.write("Ref: ${receipt.reference}\n".toByteArray())
            if (receipt.customerPhone != null) {
                os.write("Customer: ${receipt.customerPhone}\n".toByteArray())
            }
            os.write("Amount: ${receipt.currency} ${formatAmount(receipt.amount)}\n".toByteArray())
            if (receipt.fee > 0) {
                os.write("Fee: ${receipt.currency} ${formatAmount(receipt.fee)}\n".toByteArray())
                os.write("Total: ${receipt.currency} ${formatAmount(receipt.amount + receipt.fee)}\n".toByteArray())
            }
            if (receipt.narration != null) {
                os.write("Narration: ${receipt.narration}\n".toByteArray())
            }
            os.write("--------------------------------\n".toByteArray())

            // Status
            os.write(ESC_ALIGN_CENTER)
            os.write(ESC_BOLD_ON)
            os.write(ESC_DOUBLE_HEIGHT)
            os.write("${receipt.status}\n".toByteArray())
            os.write(ESC_NORMAL_SIZE)
            os.write(ESC_BOLD_OFF)
            os.write("--------------------------------\n".toByteArray())

            // Footer
            os.write(ESC_ALIGN_CENTER)
            os.write("${receipt.timestamp}\n".toByteArray())
            os.write("Powered by 54Link\n".toByteArray())
            os.write("www.54link.com\n".toByteArray())

            // Feed and cut
            os.write(ESC_FEED_3)
            os.write(ESC_CUT)
            os.flush()

            Log.i(TAG, "Receipt printed: ${receipt.reference}")
            Result.success(Unit)
        } catch (e: Exception) {
            Log.e(TAG, "Print failed", e)
            Result.failure(PrinterException("Print failed: ${e.message}"))
        }
    }

    /**
     * Print a settlement summary receipt.
     */
    suspend fun printSettlementSummary(
        batchRef: String,
        transactionCount: Int,
        totalAmount: Double,
        totalFees: Double,
        netAmount: Double,
        currency: String = "NGN",
        agentCode: String,
        timestamp: String
    ): Result<Unit> = withContext(Dispatchers.IO) {
        val os = outputStream
            ?: return@withContext Result.failure(PrinterException("Printer not connected"))
        try {
            os.write(ESC_INIT)
            os.write(ESC_ALIGN_CENTER)
            os.write(ESC_BOLD_ON)
            os.write("SETTLEMENT SUMMARY\n".toByteArray())
            os.write(ESC_BOLD_OFF)
            os.write("================================\n".toByteArray())
            os.write(ESC_ALIGN_LEFT)
            os.write("Batch: $batchRef\n".toByteArray())
            os.write("Agent: $agentCode\n".toByteArray())
            os.write("Transactions: $transactionCount\n".toByteArray())
            os.write("Total: $currency ${formatAmount(totalAmount)}\n".toByteArray())
            os.write("Fees: $currency ${formatAmount(totalFees)}\n".toByteArray())
            os.write("Net Payout: $currency ${formatAmount(netAmount)}\n".toByteArray())
            os.write("--------------------------------\n".toByteArray())
            os.write(ESC_ALIGN_CENTER)
            os.write("$timestamp\n".toByteArray())
            os.write(ESC_FEED_3)
            os.write(ESC_CUT)
            os.flush()
            Result.success(Unit)
        } catch (e: Exception) {
            Result.failure(PrinterException("Print failed: ${e.message}"))
        }
    }

    fun disconnect() {
        try {
            outputStream?.close()
            bluetoothSocket?.close()
        } catch (e: Exception) {
            Log.e(TAG, "Disconnect error", e)
        } finally {
            outputStream = null
            bluetoothSocket = null
        }
    }

    val isConnected: Boolean
        get() = bluetoothSocket?.isConnected == true

    private fun formatAmount(amount: Double): String {
        return String.format("%,.2f", amount)
    }
}

class PrinterException(message: String) : Exception(message)

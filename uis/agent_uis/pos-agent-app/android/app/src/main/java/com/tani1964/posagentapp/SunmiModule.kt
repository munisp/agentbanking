package com.tani1964.posagentapp

import android.graphics.*
import android.os.*
import android.util.Log
import com.facebook.react.bridge.*
import com.facebook.react.modules.core.DeviceEventManagerModule
import com.sunmi.pay.hardware.aidl.AidlConstants
import com.sunmi.pay.hardware.aidl.bean.CardInfo
import com.sunmi.pay.hardware.aidl.bean.TransData
import com.sunmi.pay.hardware.aidl.print.PrinterOpt
import com.sunmi.pay.hardware.aidl.readcard.ReadCardCallback
import sunmi.paylib.SunmiPayKernel

class SunmiModule(private val reactContext: ReactApplicationContext) :
    ReactContextBaseJavaModule(reactContext) {

    companion object {
        private const val TAG = "SunmiModule"
        private const val CONNECT_TIMEOUT_MS = 6000L
        private const val PRINT_WIDTH_PX = 384
    }

    private val kernel = SunmiPayKernel.getInstance()
    private val handler = Handler(Looper.getMainLooper())

    @Volatile private var isConnected = false
    @Volatile private var isConnecting = false

    private val pending = mutableListOf<Pair<() -> Unit, (String) -> Unit>>()
    private var timeoutRunnable: Runnable? = null

    @Volatile private var activeCardPromise: Promise? = null

    override fun getName() = "SunmiModule"

    override fun invalidate() {
        try {
            kernel.destroyPaySDK()
        } catch (_: Exception) {}
        super.invalidate()
    }

    // ---------------------------
    // CONNECTION
    // ---------------------------

    private fun ensureConnected(onReady: () -> Unit, onError: (String) -> Unit) {
        synchronized(this) {
            if (isConnected) {
                onReady()
                return
            }

            pending.add(onReady to onError)

            if (isConnecting) return
            isConnecting = true
        }

        timeoutRunnable = Runnable {
            failPending("Sunmi connection timeout")
        }
        handler.postDelayed(timeoutRunnable!!, CONNECT_TIMEOUT_MS)

        val started = kernel.initPaySDK(reactContext, object : SunmiPayKernel.ConnectCallback {
            override fun onConnectPaySDK() {
                complete()
            }

            override fun onDisconnectPaySDK() {
                isConnected = false
            }
        })

        if (!started) {
            failPending("Failed to start Sunmi SDK")
        }
    }

    private fun complete() {
        val list: List<Pair<() -> Unit, (String) -> Unit>>

        synchronized(this) {
            isConnected = true
            isConnecting = false

            timeoutRunnable?.let { handler.removeCallbacks(it) }
            timeoutRunnable = null

            list = pending.toList()
            pending.clear()
        }

        list.forEach { (ok, _) ->
            try { ok() } catch (_: Exception) {}
        }
    }

    private fun failPending(msg: String) {
        val list: List<Pair<() -> Unit, (String) -> Unit>>

        synchronized(this) {
            isConnected = false
            isConnecting = false

            timeoutRunnable?.let { handler.removeCallbacks(it) }
            timeoutRunnable = null

            list = pending.toList()
            pending.clear()
        }

        list.forEach { (_, err) -> err(msg) }
    }

    // ---------------------------
    // BEEP
    // ---------------------------

    @ReactMethod
    fun beep(ms: Int, promise: Promise) {
        ensureConnected({
            try {
                val basic = kernel.mBasicOpt
                if (basic == null) {
                    promise.reject("NO_BASIC", "Basic module not available")
                    return@ensureConnected
                }

                val duration = ms.coerceIn(50, 3000)
                val count = if (duration > 1000) 2 else 1

                promise.resolve(basic.buzzerOnDevice(count) == 0)
            } catch (e: Exception) {
                promise.reject("BEEP_ERROR", e)
            }
        }, {
            promise.reject("NOT_CONNECTED", it)
        })
    }

    // ---------------------------
    // PRINTER INIT / STATUS
    // ---------------------------

    @ReactMethod
    fun initPrinter(promise: Promise) {
        ensureConnected({
            try {
                val printer = kernel.mPrinterOpt
                if (printer == null) {
                    promise.reject("NO_PRINTER", "Printer not available")
                    return@ensureConnected
                }

                // Warm up / validate printer channel.
                val openCode = printer.printOpen()
                if (openCode < 0) {
                    promise.reject("PRINTER_INIT_ERROR", "printOpen failed: $openCode")
                    return@ensureConnected
                }
                printer.printClose()
                promise.resolve(true)
            } catch (e: Exception) {
                promise.reject("PRINTER_INIT_ERROR", e)
            }
        }, {
            promise.reject("NOT_CONNECTED", it)
        })
    }

    @ReactMethod
    fun getPrinterStatus(promise: Promise) {
        ensureConnected({
            try {
                val printer = kernel.mPrinterOpt
                if (printer == null) {
                    promise.reject("NO_PRINTER", "Printer not available")
                    return@ensureConnected
                }

                val sdkStatus = printer.getPrinterStatus()

                // Map Sunmi statuses to legacy JS status contract:
                // 0 = OK, 1 = OUT_OF_PAPER, 2 = OVERHEAT, 3 = OTHER_ERROR.
                val mapped = when (sdkStatus) {
                    AidlConstants.PrinterStatus.IDLE,
                    AidlConstants.PrinterStatus.PRINTING -> 0
                    AidlConstants.PrinterStatus.PAPERLESS -> 1
                    AidlConstants.PrinterStatus.OVERTEMPERATURE -> 2
                    else -> if (sdkStatus < 0) sdkStatus else 3
                }

                promise.resolve(mapped)
            } catch (e: Exception) {
                promise.reject("PRINTER_STATUS_ERROR", e)
            }
        }, {
            promise.reject("NOT_CONNECTED", it)
        })
    }

    // ---------------------------
    // PRINTER (V1 ONLY)
    // ---------------------------

    @ReactMethod
    fun printReceipt(lines: ReadableArray, feed: Int, promise: Promise) {
        ensureConnected({
            try {
                val printer = kernel.mPrinterOpt
                if (printer == null) {
                    promise.reject("NO_PRINTER", "Printer not available")
                    return@ensureConnected
                }

                printer.printOpen()

                for (i in 0 until lines.size()) {
                    val line = lines.getMap(i) ?: continue
                    val text = line.getString("text") ?: continue

                    val bitmap = renderLine(line, text)
                    val rows = bitmapToBytes(bitmap)

                    rows.forEach {
                        printer.printPointLine(it)
                    }

                    bitmap.recycle()
                }

                printer.printFeedPaper(feed.coerceIn(0, 300))
                printer.printClose()

                promise.resolve(true)

            } catch (e: Exception) {
                promise.reject("PRINT_ERROR", e)
            }
        }, {
            promise.reject("NOT_CONNECTED", it)
        })
    }

    // ---------------------------
    // CARD (MAG + IC + NFC)
    // ---------------------------

    @ReactMethod
    fun searchCard(timeoutSeconds: Int, promise: Promise) {
        Log.e("SunmiModule", "🔥 searchCard ENTERED from JS")
        ensureConnected({
            synchronized(this) {
                if (activeCardPromise != null) {
                    promise.reject("BUSY", "Card scan already running")
                    return@ensureConnected
                }
                activeCardPromise = promise
            }

            val reader = kernel.mReadCardOpt
            if (reader == null) {
                clearCard()
                promise.reject("NO_READER", "Card reader not available")
                return@ensureConnected
            }

            val mask =
                AidlConstants.CardType.MAGNETIC.value or
                AidlConstants.CardType.IC.value or
                AidlConstants.CardType.NFC.value

            // checkBankCard requires transaction data to be initialized.
            val transData = TransData().apply {
                amount = "0"
                transType = "00"
                isForceOnline = AidlConstants.EMV.NO_ONLINE
            }

            val initCode = reader.initTransData(transData)
            if (initCode != 0) {
                clearCard()
                promise.reject(
                    "TRANS_DATA_INIT_ERROR",
                    "Failed to init transData for bank card check: $initCode",
                )
                return@ensureConnected
            }

            Log.e("SunmiModule", "🔥 reader = ${kernel.mReadCardOpt}")
            // Use bank-card flow to populate PAN/track fields when available.
            reader.checkBankCard(mask, object : ReadCardCallback.Stub() {

                override fun onStartCheckCard() {
                    Log.e("SunmiModule", "🟡 onStartCheckCard fired")
                }

                override fun onCardDetected(cardInfo: CardInfo?) {
                    Log.e("SunmiModule", "🟢 onCardDetected fired")
                    val p = clearCard() ?: return
                    if (cardInfo == null) {
                        p.reject("EMPTY", "No card data")
                        return
                    }
                    Log.e("SunmiModule", """
                    🟢 CARD INFO:
                    cardType = ${cardInfo.cardType}
                    cardNo = ${cardInfo.cardNo}
                    track1 = ${cardInfo.track1}
                    track2 = ${cardInfo.track2}
                    track3 = ${cardInfo.track3}
                    expireDate = ${cardInfo.expireDate}
                    serviceCode = ${cardInfo.serviceCode}
                    atr = ${cardInfo.atr}
                    cardSerialNo = ${cardInfo.cardSerialNo}
                    """.trimIndent())

                    val pan = cardInfo.cardNo?.trim().orEmpty()
                    val track2 = cardInfo.track2?.trim().orEmpty()
                    if (pan.isEmpty() && track2.isEmpty()) {
                        p.reject(
                            "CARD_DATA_MISSING",
                            "Card detected but PAN data is unavailable. Try inserting/swiping the card or use manual entry.",
                        )
                        return
                    }

                    p.resolve(cardToMap(cardInfo))
                }

                override fun onError(code: Int, message: String?) {
                    kernel.mReadCardOpt?.cancelCheckCard()
                    kernel.mEMVOpt?.abortTransactProcess()

                    val p = clearCard() ?: return
                    p.reject("CARD_ERROR_$code", message ?: "Error")
                }

            }, timeoutSeconds.coerceIn(1, 120))

        }, {
            promise.reject("NOT_CONNECTED", it)
        })
    }

    @ReactMethod
    fun stopCardSearch(promise: Promise) {
        ensureConnected({
            clearCard()?.reject("CANCELLED", "Stopped")
            kernel.mReadCardOpt?.cancelCheckCard()
            kernel.mEMVOpt?.abortTransactProcess()
            promise.resolve(true)
        }, {
            promise.reject("NOT_CONNECTED", it)
        })
    }

    private fun clearCard(): Promise? {
        val p = activeCardPromise
        activeCardPromise = null
        return p
    }

    // ---------------------------
    // CARD MAP
    // ---------------------------

    private fun cardToMap(card: CardInfo): WritableMap {
        return Arguments.createMap().apply {

            val pan = card.cardNo ?: ""

            putString("cardNo", pan)
            putString("maskCardNo", mask(pan))
    
            // ONLY real SDK fields
            putString("track1", card.track1 ?: "")
            putString("track2", card.track2 ?: "")
            putString("track3", card.track3 ?: "")
            putString("expireDate", card.expireDate ?: "")
            // Backward compatibility for existing JS types that expect 'expiredDate'.
            putString("expiredDate", card.expireDate ?: "")
            putString("serviceCode", card.serviceCode ?: "")
            putString("atr", card.atr ?: "")
            putString("cardSerialNo", card.cardSerialNo ?: "")

            val slot = when (card.cardType) {
                AidlConstants.CardType.MAGNETIC.value -> "SWIPE"
                AidlConstants.CardType.IC.value -> "ICC1"
                AidlConstants.CardType.NFC.value -> "RF"
                else -> "UNKNOWN"
            }
            putString("cardSlot", slot)
            putString("rfCardType", if (card.cardType == AidlConstants.CardType.NFC.value) "NFC" else "")
        }
    }

    private fun mask(pan: String): String {
        if (pan.length < 8) return "****"
        return pan.take(6) + "****" + pan.takeLast(4)
    }

    // ---------------------------
    // PRINT HELPERS
    // ---------------------------

    private fun renderLine(line: ReadableMap, text: String): Bitmap {
        val size = if (line.hasKey("fontSize") && !line.isNull("fontSize")) {
            line.getDouble("fontSize").toFloat().coerceIn(12f, 48f)
        } else {
            24f
        }

        val align = if (line.hasKey("align") && !line.isNull("align")) {
            line.getString("align")?.uppercase() ?: "LEFT"
        } else {
            "LEFT"
        }

        val isBold = line.hasKey("isBold") && !line.isNull("isBold") && line.getBoolean("isBold")

        val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.BLACK
            textSize = size
            typeface = if (isBold) Typeface.DEFAULT_BOLD else Typeface.DEFAULT
        }

        val textWidth = paint.measureText(text)
        val h = (size + 26f).toInt().coerceAtLeast(50)
        val bmp = Bitmap.createBitmap(PRINT_WIDTH_PX, h, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bmp)
        canvas.drawColor(Color.WHITE)

        val x = when (align) {
            "CENTER" -> ((PRINT_WIDTH_PX - textWidth) / 2f).coerceAtLeast(0f)
            "RIGHT" -> (PRINT_WIDTH_PX - textWidth - 10f).coerceAtLeast(0f)
            else -> 10f
        }

        val y = (h - 14f).coerceAtLeast(size)
        canvas.drawText(text, x, y, paint)
        return bmp
    }

    private fun bitmapToBytes(bitmap: Bitmap): List<ByteArray> {
        val w = bitmap.width
        val h = bitmap.height
        val bytesPerRow = (w + 7) / 8

        val list = mutableListOf<ByteArray>()

        for (y in 0 until h) {
            val row = ByteArray(bytesPerRow)

            for (x in 0 until w) {
                val pixel = bitmap.getPixel(x, y)
                val gray = (Color.red(pixel) + Color.green(pixel) + Color.blue(pixel)) / 3

                if (gray < 128) {
                    val b = x / 8
                    val bit = 7 - (x % 8)
                    row[b] = (row[b].toInt() or (1 shl bit)).toByte()
                }
            }

            list.add(row)
        }

        return list
    }

    // unused RN events
    @ReactMethod fun addListener(eventName: String) {}
    @ReactMethod fun removeListeners(count: Int) {}
}

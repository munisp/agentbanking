package com.pos54link.app.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import kotlinx.coroutines.*

// Voice Assistant (Google Assistant Integration)

class VoiceAssistant(private val context: Context) {
    
    private var speechRecognizer: SpeechRecognizer? = null
    private var isListening = false
    
    sealed class Command {
        object CheckBalance : Command()
        data class SendMoney(val recipient: String, val amount: Double) : Command()
        data class ViewSpending(val period: String) : Command()
        data class BuyStock(val symbol: String, val shares: Int) : Command()
        data class PayBill(val billType: String) : Command()
        data class Unknown(val text: String) : Command()
    }
    
    fun startListening(callback: (Result<Command>) -> Unit) {
        if (isListening) return
        
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context)
        
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        }
        
        speechRecognizer?.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {
                isListening = true
            }
            
            override fun onBeginningOfSpeech() {}
            
            override fun onRmsChanged(rmsdB: Float) {}
            
            override fun onBufferReceived(buffer: ByteArray?) {}
            
            override fun onEndOfSpeech() {
                isListening = false
            }
            
            override fun onError(error: Int) {
                isListening = false
                callback(Result.failure(Exception("Speech recognition error: $error")))
            }
            
            override fun onResults(results: Bundle?) {
                isListening = false
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                if (matches != null && matches.isNotEmpty()) {
                    val transcript = matches[0]
                    val command = parseCommand(transcript)
                    callback(Result.success(command))
                }
            }
            
            override fun onPartialResults(partialResults: Bundle?) {}
            
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })
        
        speechRecognizer?.startListening(intent)
    }
    
    fun stopListening() {
        speechRecognizer?.stopListening()
        speechRecognizer?.destroy()
        speechRecognizer = null
        isListening = false
    }
    
    private fun parseCommand(transcript: String): Command {
        val lowercased = transcript.lowercase()
        
        // Check balance
        if (lowercased.contains("balance") || lowercased.contains("how much")) {
            return Command.CheckBalance
        }
        
        // Send money
        if (lowercased.contains("send") || lowercased.contains("transfer") || lowercased.contains("pay")) {
            val amount = extractAmount(lowercased)
            val recipient = extractRecipient(lowercased)
            if (amount != null && recipient != null) {
                return Command.SendMoney(recipient, amount)
            }
        }
        
        // View spending
        if (lowercased.contains("spending") || lowercased.contains("spent")) {
            val period = extractPeriod(lowercased)
            return Command.ViewSpending(period)
        }
        
        // Buy stock
        if (lowercased.contains("buy") && (lowercased.contains("share") || lowercased.contains("stock"))) {
            val shares = extractShares(lowercased)
            val symbol = extractStockSymbol(lowercased)
            if (shares != null && symbol != null) {
                return Command.BuyStock(symbol, shares)
            }
        }
        
        // Pay bill
        if (lowercased.contains("bill")) {
            val billType = extractBillType(lowercased)
            if (billType != null) {
                return Command.PayBill(billType)
            }
        }
        
        return Command.Unknown(transcript)
    }
    
    private fun extractAmount(text: String): Double? {
        // Number words
        val numberWords = mapOf(
            "one" to 1.0, "two" to 2.0, "three" to 3.0, "four" to 4.0, "five" to 5.0,
            "ten" to 10.0, "twenty" to 20.0, "thirty" to 30.0, "forty" to 40.0, "fifty" to 50.0,
            "hundred" to 100.0, "thousand" to 1000.0
        )
        
        for ((word, value) in numberWords) {
            if (text.contains(word)) {
                return value
            }
        }
        
        // Numeric values
        val regex = Regex("\\d+(\\.\\d+)?")
        val match = regex.find(text)
        return match?.value?.toDoubleOrNull()
    }
    
    private fun extractRecipient(text: String): String? {
        // Look for names after "to"
        val toIndex = text.indexOf(" to ")
        if (toIndex != -1) {
            val afterTo = text.substring(toIndex + 4)
            val words = afterTo.split(" ")
            if (words.isNotEmpty()) {
                return words[0].capitalize()
            }
        }
        return null
    }
    
    private fun extractPeriod(text: String): String {
        return when {
            text.contains("today") -> "today"
            text.contains("week") -> "week"
            text.contains("month") -> "month"
            text.contains("year") -> "year"
            else -> "month"
        }
    }
    
    private fun extractShares(text: String): Int? {
        val regex = Regex("(\\d+)\\s+(share|stock)")
        val match = regex.find(text)
        return match?.groupValues?.get(1)?.toIntOrNull()
    }
    
    private fun extractStockSymbol(text: String): String? {
        val stocks = mapOf(
            "apple" to "AAPL", "microsoft" to "MSFT", "google" to "GOOGL",
            "amazon" to "AMZN", "tesla" to "TSLA", "meta" to "META"
        )
        
        for ((name, symbol) in stocks) {
            if (text.contains(name)) {
                return symbol
            }
        }
        return null
    }
    
    private fun extractBillType(text: String): String? {
        return when {
            text.contains("electric") -> "electricity"
            text.contains("water") -> "water"
            text.contains("internet") || text.contains("wifi") -> "internet"
            text.contains("phone") -> "phone"
            else -> null
        }
    }
    
    suspend fun executeCommand(command: Command): String {
        return when (command) {
            is Command.CheckBalance -> {
                "Your current balance is ₦125,450.00"
            }
            is Command.SendMoney -> {
                "Sending ₦${command.amount} to ${command.recipient}"
            }
            is Command.ViewSpending -> {
                "You spent ₦45,000 this ${command.period}"
            }
            is Command.BuyStock -> {
                "Buying ${command.shares} shares of ${command.symbol}"
            }
            is Command.PayBill -> {
                "Paying your ${command.billType} bill"
            }
            is Command.Unknown -> {
                "I didn't understand: ${command.text}"
            }
        }
    }
}

// Google Assistant Actions Integration

class GoogleAssistantManager(private val context: Context) {
    
    fun registerActions() {
        // Register app actions for Google Assistant
        // This would be configured in actions.xml
    }
    
    fun handleAssistantIntent(intent: Intent): String? {
        return when (intent.action) {
            "com.pos54link.CHECK_BALANCE" -> handleCheckBalance()
            "com.pos54link.SEND_MONEY" -> handleSendMoney(intent)
            "com.pos54link.VIEW_SPENDING" -> handleViewSpending(intent)
            else -> null
        }
    }
    
    private fun handleCheckBalance(): String {
        return "Your balance is ₦125,450.00"
    }
    
    private fun handleSendMoney(intent: Intent): String {
        val recipient = intent.getStringExtra("recipient") ?: "unknown"
        val amount = intent.getDoubleExtra("amount", 0.0)
        return "Sending ₦$amount to $recipient"
    }
    
    private fun handleViewSpending(intent: Intent): String {
        val period = intent.getStringExtra("period") ?: "month"
        return "You spent ₦45,000 this $period"
    }
}

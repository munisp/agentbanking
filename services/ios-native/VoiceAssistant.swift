import Foundation
import Speech
import Intents
import NaturalLanguage

// MARK: - Voice Assistant (Erica/Eno-like)

class VoiceAssistant: NSObject {
    static let shared = VoiceAssistant()
    
    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private let audioEngine = AVAudioEngine()
    
    enum Command {
        case checkBalance
        case sendMoney(recipient: String, amount: Double)
        case viewSpending(period: String)
        case buyStock(symbol: String, shares: Int)
        case payBill(billType: String)
        case unknown(String)
    }
    
    // MARK: - Start Listening
    
    func startListening(completion: @escaping (Result<Command, Error>) -> Void) throws {
        // Cancel previous task
        recognitionTask?.cancel()
        recognitionTask = nil
        
        // Configure audio session
        let audioSession = AVAudioSession.sharedInstance()
        try audioSession.setCategory(.record, mode: .measurement, options: .duckOthers)
        try audioSession.setActive(true, options: .notifyOthersOnDeactivation)
        
        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        
        guard let recognitionRequest = recognitionRequest else {
            throw NSError(domain: "VoiceAssistant", code: -1, userInfo: [NSLocalizedDescriptionKey: "Unable to create recognition request"])
        }
        
        recognitionRequest.shouldReportPartialResults = true
        
        // Configure microphone input
        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { buffer, _ in
            recognitionRequest.append(buffer)
        }
        
        audioEngine.prepare()
        try audioEngine.start()
        
        // Start recognition
        recognitionTask = speechRecognizer?.recognitionTask(with: recognitionRequest) { [weak self] result, error in
            if let result = result {
                let transcript = result.bestTranscription.formattedString
                
                if result.isFinal {
                    self?.stopListening()
                    let command = self?.parseCommand(from: transcript) ?? .unknown(transcript)
                    completion(.success(command))
                }
            }
            
            if let error = error {
                self?.stopListening()
                completion(.failure(error))
            }
        }
    }
    
    func stopListening() {
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionRequest = nil
        recognitionTask = nil
    }
    
    // MARK: - Command Parsing
    
    private func parseCommand(from transcript: String) -> Command {
        let lowercased = transcript.lowercased()
        
        // Check balance
        if lowercased.contains("balance") || lowercased.contains("how much") {
            return .checkBalance
        }
        
        // Send money
        if lowercased.contains("send") || lowercased.contains("transfer") || lowercased.contains("pay") {
            if let amount = extractAmount(from: lowercased),
               let recipient = extractRecipient(from: lowercased) {
                return .sendMoney(recipient: recipient, amount: amount)
            }
        }
        
        // View spending
        if lowercased.contains("spending") || lowercased.contains("spent") {
            let period = extractPeriod(from: lowercased)
            return .viewSpending(period: period)
        }
        
        // Buy stock
        if lowercased.contains("buy") && (lowercased.contains("share") || lowercased.contains("stock")) {
            if let shares = extractShares(from: lowercased),
               let symbol = extractStockSymbol(from: lowercased) {
                return .buyStock(symbol: symbol, shares: shares)
            }
        }
        
        // Pay bill
        if lowercased.contains("bill") {
            if let billType = extractBillType(from: lowercased) {
                return .payBill(billType: billType)
            }
        }
        
        return .unknown(transcript)
    }
    
    // MARK: - Natural Language Processing
    
    private func extractAmount(from text: String) -> Double? {
        let tagger = NLTagger(tagSchemes: [.lexicalClass])
        tagger.string = text
        
        var amount: Double?
        
        // Look for number words
        let numberWords = ["one": 1.0, "two": 2.0, "three": 3.0, "four": 4.0, "five": 5.0,
                          "ten": 10.0, "twenty": 20.0, "thirty": 30.0, "forty": 40.0, "fifty": 50.0,
                          "hundred": 100.0, "thousand": 1000.0]
        
        for (word, value) in numberWords {
            if text.contains(word) {
                amount = value
                break
            }
        }
        
        // Look for numeric values
        let pattern = "\\d+(\\.\\d+)?"
        if let regex = try? NSRegularExpression(pattern: pattern) {
            let matches = regex.matches(in: text, range: NSRange(text.startIndex..., in: text))
            if let match = matches.first {
                let range = Range(match.range, in: text)!
                amount = Double(text[range])
            }
        }
        
        return amount
    }
    
    private func extractRecipient(from text: String) -> String? {
        let tagger = NLTagger(tagSchemes: [.nameType])
        tagger.string = text
        
        var recipient: String?
        
        tagger.enumerateTags(in: text.startIndex..<text.endIndex, unit: .word, scheme: .nameType) { tag, range in
            if tag == .personalName {
                recipient = String(text[range])
                return false
            }
            return true
        }
        
        return recipient
    }
    
    private func extractPeriod(from text: String) -> String {
        if text.contains("today") {
            return "today"
        } else if text.contains("week") {
            return "week"
        } else if text.contains("month") {
            return "month"
        } else if text.contains("year") {
            return "year"
        }
        return "month"
    }
    
    private func extractShares(from text: String) -> Int? {
        let pattern = "(\\d+)\\s+(share|stock)"
        if let regex = try? NSRegularExpression(pattern: pattern) {
            let matches = regex.matches(in: text, range: NSRange(text.startIndex..., in: text))
            if let match = matches.first, match.numberOfRanges > 1 {
                let range = Range(match.range(at: 1), in: text)!
                return Int(text[range])
            }
        }
        return nil
    }
    
    private func extractStockSymbol(from text: String) -> String? {
        // Common stock names
        let stocks = ["apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL", 
                     "amazon": "AMZN", "tesla": "TSLA", "meta": "META"]
        
        for (name, symbol) in stocks {
            if text.contains(name) {
                return symbol
            }
        }
        
        return nil
    }
    
    private func extractBillType(from text: String) -> String? {
        if text.contains("electric") {
            return "electricity"
        } else if text.contains("water") {
            return "water"
        } else if text.contains("internet") || text.contains("wifi") {
            return "internet"
        } else if text.contains("phone") {
            return "phone"
        }
        return nil
    }
    
    // MARK: - Execute Command
    
    func executeCommand(_ command: Command, completion: @escaping (Result<String, Error>) -> Void) {
        switch command {
        case .checkBalance:
            // Fetch balance
            let balance = "₦125,450.00"
            completion(.success("Your current balance is \(balance)"))
            
        case .sendMoney(let recipient, let amount):
            // Execute transfer
            completion(.success("Sending ₦\(amount) to \(recipient)"))
            
        case .viewSpending(let period):
            // Fetch spending
            let spending = "₦45,000"
            completion(.success("You spent \(spending) this \(period)"))
            
        case .buyStock(let symbol, let shares):
            // Execute stock purchase
            completion(.success("Buying \(shares) shares of \(symbol)"))
            
        case .payBill(let billType):
            // Pay bill
            completion(.success("Paying your \(billType) bill"))
            
        case .unknown(let text):
            completion(.success("I didn't understand: \(text)"))
        }
    }
}

// MARK: - Siri Shortcuts Integration

class SiriShortcutsManager {
    static let shared = SiriShortcutsManager()
    
    func donateCheckBalanceIntent() {
        let intent = CheckBalanceIntent()
        intent.suggestedInvocationPhrase = "Check my balance"
        
        let interaction = INInteraction(intent: intent, response: nil)
        interaction.donate { error in
            if let error = error {
                print("Failed to donate intent: \(error)")
            }
        }
    }
    
    func donateSendMoneyIntent(recipient: String, amount: Double) {
        let intent = SendMoneyIntent()
        intent.recipient = recipient
        intent.amount = NSNumber(value: amount)
        intent.suggestedInvocationPhrase = "Send money to \(recipient)"
        
        let interaction = INInteraction(intent: intent, response: nil)
        interaction.donate { error in
            if let error = error {
                print("Failed to donate intent: \(error)")
            }
        }
    }
}

// MARK: - Intent Definitions

class CheckBalanceIntent: INIntent {}
class SendMoneyIntent: INIntent {
    @NSManaged var recipient: String?
    @NSManaged var amount: NSNumber?
}

import Foundation
import WatchConnectivity
import WidgetKit
import CoreNFC
import PassKit

// MARK: - 2. Apple Watch App

class WatchConnectivityManager: NSObject, WCSessionDelegate {
    static let shared = WatchConnectivityManager()
    
    private var session: WCSession?
    
    func activateSession() {
        if WCSession.isSupported() {
            session = WCSession.default
            session?.delegate = self
            session?.activate()
        }
    }
    
    func sendBalanceToWatch(balance: Double) {
        guard let session = session, session.isReachable else { return }
        
        let message = ["balance": balance]
        session.sendMessage(message, replyHandler: nil)
    }
    
    func sendTransactionsToWatch(transactions: [Transaction]) {
        guard let session = session else { return }
        
        let data = try? JSONEncoder().encode(transactions)
        session.transferUserInfo(["transactions": data as Any])
    }
    
    // WCSessionDelegate methods
    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {}
    func sessionDidBecomeInactive(_ session: WCSession) {}
    func sessionDidDeactivate(_ session: WCSession) {}
}

// MARK: - 3. Home Screen Widgets

struct BalanceWidgetEntry: TimelineEntry {
    let date: Date
    let balance: Double
    let currency: String
}

class WidgetDataProvider {
    static func getBalance() -> Double {
        // Fetch from UserDefaults or API
        return 125450.00
    }
    
    static func getRecentTransactions() -> [Transaction] {
        // Fetch recent transactions
        return []
    }
}

// MARK: - 4. QR Code Payments

class QRCodePaymentManager {
    
    func generateQRCode(amount: Double?, recipient: String) -> UIImage? {
        let data = """
        {
            "type": "payment",
            "recipient": "\(recipient)",
            "amount": \(amount ?? 0),
            "currency": "NGN"
        }
        """.data(using: .utf8)
        
        guard let qrFilter = CIFilter(name: "CIQRCodeGenerator") else { return nil }
        qrFilter.setValue(data, forKey: "inputMessage")
        qrFilter.setValue("H", forKey: "inputCorrectionLevel")
        
        guard let qrImage = qrFilter.outputImage else { return nil }
        
        let transform = CGAffineTransform(scaleX: 10, y: 10)
        let scaledQRImage = qrImage.transformed(by: transform)
        
        let context = CIContext()
        guard let cgImage = context.createCGImage(scaledQRImage, from: scaledQRImage.extent) else { return nil }
        
        return UIImage(cgImage: cgImage)
    }
    
    func scanQRCode(from image: UIImage, completion: @escaping (QRPaymentData?) -> Void) {
        guard let ciImage = CIImage(image: image) else {
            completion(nil)
            return
        }
        
        let detector = CIDetector(ofType: CIDetectorTypeQRCode, context: nil, options: [CIDetectorAccuracy: CIDetectorAccuracyHigh])
        let features = detector?.features(in: ciImage) as? [CIQRCodeFeature]
        
        guard let qrCode = features?.first, let messageString = qrCode.messageString else {
            completion(nil)
            return
        }
        
        if let data = messageString.data(using: .utf8),
           let paymentData = try? JSONDecoder().decode(QRPaymentData.self, from: data) {
            completion(paymentData)
        } else {
            completion(nil)
        }
    }
}

struct QRPaymentData: Codable {
    let type: String
    let recipient: String
    let amount: Double
    let currency: String
}

// MARK: - 5. NFC Tap-to-Pay

class NFCPaymentManager: NSObject, NFCNDEFReaderSessionDelegate {
    
    private var nfcSession: NFCNDEFReaderSession?
    
    func startNFCPayment(amount: Double, completion: @escaping (Result<String, Error>) -> Void) {
        nfcSession = NFCNDEFReaderSession(delegate: self, queue: nil, invalidateAfterFirstRead: true)
        nfcSession?.alertMessage = "Hold near payment terminal"
        nfcSession?.begin()
    }
    
    // NFCNDEFReaderSessionDelegate
    func readerSession(_ session: NFCNDEFReaderSession, didDetectNDEFs messages: [NFCNDEFMessage]) {
        // Process NFC payment
    }
    
    func readerSession(_ session: NFCNDEFReaderSession, didInvalidateWithError error: Error) {
        // Handle error
    }
}

// MARK: - 6. P2P Payments

class P2PPaymentManager {
    
    func sendMoney(to recipient: String, amount: Double, completion: @escaping (Result<String, Error>) -> Void) {
        // Validate recipient
        // Check balance
        // Execute transfer
        // Send push notification
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            completion(.success("₦\(amount) sent to \(recipient)"))
        }
    }
    
    func requestMoney(from sender: String, amount: Double, completion: @escaping (Result<String, Error>) -> Void) {
        // Create payment request
        // Send notification to sender
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            completion(.success("Request sent to \(sender) for ₦\(amount)"))
        }
    }
}

// MARK: - 7. Recurring Bill Pay

class RecurringBillPayManager {
    
    struct RecurringBill: Codable {
        let id: String
        let name: String
        let amount: Double
        let frequency: Frequency
        let nextPaymentDate: Date
        let autoPayEnabled: Bool
        
        enum Frequency: String, Codable {
            case weekly, monthly, quarterly, yearly
        }
    }
    
    func scheduleBill(_ bill: RecurringBill) {
        // Save to database
        // Schedule local notification
        // Set up auto-pay if enabled
    }
    
    func processAutoPay(for bill: RecurringBill, completion: @escaping (Result<String, Error>) -> Void) {
        // Check balance
        // Execute payment
        // Update next payment date
        // Send confirmation
        
        completion(.success("Bill paid: \(bill.name) - ₦\(bill.amount)"))
    }
}

// MARK: - 8. Savings Goals

class SavingsGoalManager {
    
    struct SavingsGoal: Codable {
        let id: String
        let name: String
        let targetAmount: Double
        var currentAmount: Double
        let deadline: Date
        let autoSaveRules: [AutoSaveRule]
    }
    
    struct AutoSaveRule: Codable {
        let type: RuleType
        let amount: Double
        
        enum RuleType: String, Codable {
            case roundUp
            case dailyTransfer
            case percentageOfIncome
        }
    }
    
    func createGoal(_ goal: SavingsGoal) {
        // Save goal
        // Set up automation rules
    }
    
    func applyRoundUp(transaction: Transaction, goal: SavingsGoal) {
        let roundedAmount = ceil(transaction.amount)
        let roundUpAmount = roundedAmount - transaction.amount
        
        // Transfer roundUpAmount to savings goal
    }
    
    func processDailyTransfer(goal: SavingsGoal) {
        guard let rule = goal.autoSaveRules.first(where: { $0.type == .dailyTransfer }) else { return }
        
        // Transfer rule.amount to goal
    }
}

// MARK: - 9. AI Investment Recommendations

class AIInvestmentAdvisor {
    
    struct InvestmentRecommendation {
        let symbol: String
        let action: Action
        let confidence: Double
        let reasoning: String
        let targetPrice: Double
        
        enum Action {
            case buy, sell, hold
        }
    }
    
    func getRecommendations(portfolio: [Stock], riskTolerance: RiskLevel) -> [InvestmentRecommendation] {
        // Analyze portfolio
        // Consider market conditions
        // Apply ML model
        // Generate recommendations
        
        return [
            InvestmentRecommendation(
                symbol: "AAPL",
                action: .buy,
                confidence: 0.85,
                reasoning: "Strong earnings growth and positive market sentiment",
                targetPrice: 185.0
            )
        ]
    }
    
    enum RiskLevel {
        case conservative, moderate, aggressive
    }
}

struct Stock: Codable {
    let symbol: String
    let shares: Int
    let averagePrice: Double
}

// MARK: - 10. Portfolio Rebalancing

class PortfolioRebalancer {
    
    func rebalance(currentPortfolio: [Stock], targetAllocation: [String: Double]) -> [RebalanceAction] {
        var actions: [RebalanceAction] = []
        
        // Calculate current allocation
        let totalValue = currentPortfolio.reduce(0.0) { $0 + (Double($1.shares) * $1.averagePrice) }
        
        for stock in currentPortfolio {
            let currentValue = Double(stock.shares) * stock.averagePrice
            let currentPercentage = currentValue / totalValue
            let targetPercentage = targetAllocation[stock.symbol] ?? 0
            
            let difference = targetPercentage - currentPercentage
            
            if abs(difference) > 0.05 { // 5% threshold
                let action: RebalanceAction.ActionType = difference > 0 ? .buy : .sell
                let amount = abs(difference) * totalValue
                
                actions.append(RebalanceAction(
                    symbol: stock.symbol,
                    action: action,
                    amount: amount
                ))
            }
        }
        
        return actions
    }
    
    struct RebalanceAction {
        let symbol: String
        let action: ActionType
        let amount: Double
        
        enum ActionType {
            case buy, sell
        }
    }
}

// MARK: - 11-15. Additional Features

class CryptoStakingManager {
    func stakeTokens(amount: Double, duration: Int) -> Double {
        let apr = 0.08 // 8% APR
        return amount * apr * (Double(duration) / 365.0)
    }
}

class VirtualCardManager {
    func generateVirtualCard() -> VirtualCard {
        return VirtualCard(
            number: generateCardNumber(),
            cvv: String(format: "%03d", Int.random(in: 100...999)),
            expiryDate: Date().addingTimeInterval(86400 * 365)
        )
    }
    
    private func generateCardNumber() -> String {
        let prefix = "4532" // Visa
        var number = prefix
        for _ in 0..<12 {
            number += String(Int.random(in: 0...9))
        }
        return number
    }
}

struct VirtualCard {
    let number: String
    let cvv: String
    let expiryDate: Date
}

class TravelModeManager {
    func enableTravelMode(countries: [String], startDate: Date, endDate: Date) {
        // Disable suspicious activity alerts
        // Enable international transactions
        // Send notifications for transactions
    }
}

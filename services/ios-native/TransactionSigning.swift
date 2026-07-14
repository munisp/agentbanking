import LocalAuthentication

/// Transaction Signing with Biometrics
class TransactionSigning {
    static let shared = TransactionSigning()
    
    struct Transaction {
        let amount: Double
        let recipient: String
        let type: TransactionType
        let timestamp: Date
        
        enum TransactionType {
            case payment, wireTransfer, stockTrade, cryptoTrade, accountChange, beneficiaryAdd
        }
    }
    
    func requiresBiometricApproval(_ transaction: Transaction) -> Bool {
        switch transaction.type {
        case .payment:
            return transaction.amount > 100 // $100 threshold
        case .wireTransfer, .stockTrade, .cryptoTrade, .accountChange, .beneficiaryAdd:
            return true // Always require for sensitive operations
        }
    }
    
    func signTransaction(_ transaction: Transaction, completion: @escaping (Result<String, Error>) -> Void) {
        guard requiresBiometricApproval(transaction) else {
            // Generate signature without biometric
            let signature = generateSignature(transaction)
            completion(.success(signature))
            return
        }
        
        let context = LAContext()
        var error: NSError?
        
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            completion(.failure(error ?? NSError(domain: "Biometric not available", code: -1)))
            return
        }
        
        let reason = "Approve \(transaction.type) of $\(Int(transaction.amount))"
        
        context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason) { success, error in
            DispatchQueue.main.async {
                if success {
                    let signature = self.generateSignature(transaction)
                    completion(.success(signature))
                } else {
                    completion(.failure(error ?? NSError(domain: "Biometric failed", code: -2)))
                }
            }
        }
    }
    
    private func generateSignature(_ transaction: Transaction) -> String {
        let data = "\(transaction.amount)|\(transaction.recipient)|\(transaction.timestamp.timeIntervalSince1970)"
        return data.sha256()
    }
    
    func verifySignature(_ signature: String, for transaction: Transaction) -> Bool {
        let expectedSignature = generateSignature(transaction)
        return signature == expectedSignature
    }
}

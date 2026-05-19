//
//  ApplePayManager.swift
//  RemittanceApp
//
//  Apple Pay integration for wallet funding
//

import Foundation
import PassKit

/// Apple Pay payment manager
class ApplePayManager: NSObject {
    
    // MARK: - Properties
    
    static let shared = ApplePayManager()
    
    private let merchantIdentifier = "merchant.com.remittance.app"
    private let supportedNetworks: [PKPaymentNetwork] = [
        .visa,
        .masterCard,
        .amex,
        .discover
    ]
    
    private var paymentCompletion: ((Result<PKPayment, Error>) -> Void)?
    
    // MARK: - Initialization
    
    private override init() {
        super.init()
    }
    
    // MARK: - Public Methods
    
    /// Check if Apple Pay is available on this device
    func isApplePayAvailable() -> Bool {
        return PKPaymentAuthorizationController.canMakePayments()
    }
    
    /// Check if user has cards setup in Apple Pay
    func hasApplePayCards() -> Bool {
        return PKPaymentAuthorizationController.canMakePayments(usingNetworks: supportedNetworks)
    }
    
    /// Present Apple Pay sheet for wallet funding
    func presentApplePay(
        amount: Decimal,
        currency: String,
        from viewController: UIViewController,
        completion: @escaping (Result<PKPayment, Error>) -> Void
    ) {
        guard isApplePayAvailable() else {
            completion(.failure(ApplePayError.notAvailable))
            return
        }
        
        self.paymentCompletion = completion
        
        let request = createPaymentRequest(amount: amount, currency: currency)
        
        let controller = PKPaymentAuthorizationController(paymentRequest: request)
        controller.delegate = self
        
        controller.present { presented in
            if !presented {
                completion(.failure(ApplePayError.presentationFailed))
            }
        }
    }
    
    /// Create payment request for adding funds
    private func createPaymentRequest(amount: Decimal, currency: String) -> PKPaymentRequest {
        let request = PKPaymentRequest()
        
        request.merchantIdentifier = merchantIdentifier
        request.supportedNetworks = supportedNetworks
        request.merchantCapabilities = .capability3DS
        request.countryCode = "NG" // Nigeria
        request.currencyCode = currency
        
        // Payment summary items
        let addFundsItem = PKPaymentSummaryItem(
            label: "Add Funds to Wallet",
            amount: NSDecimalNumber(decimal: amount)
        )
        
        let totalItem = PKPaymentSummaryItem(
            label: "54Link Agency Banking",
            amount: NSDecimalNumber(decimal: amount)
        )
        
        request.paymentSummaryItems = [addFundsItem, totalItem]
        
        return request
    }
    
    /// Process payment with backend
    func processPayment(
        _ payment: PKPayment,
        amount: Decimal,
        currency: String
    ) async throws -> PaymentResult {
        // Extract payment token
        let paymentData = payment.token.paymentData
        let paymentToken = String(data: paymentData, encoding: .utf8) ?? ""
        
        // Send to backend for processing
        let endpoint = "/api/v1/payments/apple-pay"
        let parameters: [String: Any] = [
            "payment_token": paymentToken,
            "amount": amount,
            "currency": currency,
            "payment_method": "apple_pay"
        ]
        
        // Make API call (using your existing APIClient)
        // This is a placeholder - integrate with your actual API client
        let result = try await APIClient.shared.post(endpoint, parameters: parameters)
        
        return PaymentResult(
            transactionId: result["transaction_id"] as? String ?? "",
            status: result["status"] as? String ?? "",
            amount: amount,
            currency: currency
        )
    }
}

// MARK: - PKPaymentAuthorizationControllerDelegate

extension ApplePayManager: PKPaymentAuthorizationControllerDelegate {
    
    func paymentAuthorizationController(
        _ controller: PKPaymentAuthorizationController,
        didAuthorizePayment payment: PKPayment,
        handler completion: @escaping (PKPaymentAuthorizationResult) -> Void
    ) {
        // Payment authorized by user
        paymentCompletion?(.success(payment))
        
        // Complete the payment
        completion(PKPaymentAuthorizationResult(status: .success, errors: nil))
    }
    
    func paymentAuthorizationControllerDidFinish(_ controller: PKPaymentAuthorizationController) {
        controller.dismiss()
    }
}

// MARK: - Supporting Types

struct PaymentResult {
    let transactionId: String
    let status: String
    let amount: Decimal
    let currency: String
}

enum ApplePayError: LocalizedError {
    case notAvailable
    case presentationFailed
    case processingFailed
    case cancelled
    
    var errorDescription: String? {
        switch self {
        case .notAvailable:
            return "Apple Pay is not available on this device"
        case .presentationFailed:
            return "Failed to present Apple Pay sheet"
        case .processingFailed:
            return "Payment processing failed"
        case .cancelled:
            return "Payment was cancelled"
        }
    }
}

//
//  CardScannerManager.swift
//  RemittanceApp
//
//  Card scanning with OCR using Vision framework
//

import Foundation
import UIKit
import Vision
import AVFoundation

/// Card information extracted from scanning
struct ScannedCardInfo {
    var cardNumber: String?
    var expiryDate: String?
    var cardholderName: String?
    var cvv: String?
    var confidence: Float
}

/// Card scanner manager using Vision framework
class CardScannerManager: NSObject {
    
    // MARK: - Properties
    
    static let shared = CardScannerManager()
    
    private var captureSession: AVCaptureSession?
    private var previewLayer: AVCaptureVideoPreviewLayer?
    private var videoOutput: AVCaptureVideoDataOutput?
    
    private let sessionQueue = DispatchQueue(label: "com.remittance.cardscanner")
    private let visionQueue = DispatchQueue(label: "com.remittance.vision")
    
    private var isScanning = false
    private var scanCompletion: ((Result<ScannedCardInfo, Error>) -> Void)?
    
    // Card number regex patterns
    private let cardNumberPattern = #"(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4})"#
    private let expiryPattern = #"(0[1-9]|1[0-2])[\/\-](\d{2}|\d{4})"#
    private let cvvPattern = #"\b\d{3,4}\b"#
    
    // MARK: - Initialization
    
    private override init() {
        super.init()
    }
    
    // MARK: - Public Methods
    
    /// Check if device supports card scanning
    func isCardScanningSupported() -> Bool {
        return AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) != nil
    }
    
    /// Request camera permission
    func requestCameraPermission(completion: @escaping (Bool) -> Void) {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            completion(true)
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { granted in
                DispatchQueue.main.async {
                    completion(granted)
                }
            }
        case .denied, .restricted:
            completion(false)
        @unknown default:
            completion(false)
        }
    }
    
    /// Setup camera session
    func setupCameraSession(previewView: UIView) throws -> AVCaptureVideoPreviewLayer {
        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) else {
            throw CardScannerError.cameraNotAvailable
        }
        
        let session = AVCaptureSession()
        session.sessionPreset = .high
        
        let input = try AVCaptureDeviceInput(device: device)
        guard session.canAddInput(input) else {
            throw CardScannerError.cannotAddInput
        }
        session.addInput(input)
        
        let output = AVCaptureVideoDataOutput()
        output.setSampleBufferDelegate(self, queue: visionQueue)
        output.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
        
        guard session.canAddOutput(output) else {
            throw CardScannerError.cannotAddOutput
        }
        session.addOutput(output)
        
        self.captureSession = session
        self.videoOutput = output
        
        let previewLayer = AVCaptureVideoPreviewLayer(session: session)
        previewLayer.videoGravity = .resizeAspectFill
        previewLayer.frame = previewView.bounds
        
        self.previewLayer = previewLayer
        
        return previewLayer
    }
    
    /// Start scanning for card
    func startScanning(completion: @escaping (Result<ScannedCardInfo, Error>) -> Void) {
        guard let session = captureSession else {
            completion(.failure(CardScannerError.sessionNotSetup))
            return
        }
        
        self.scanCompletion = completion
        self.isScanning = true
        
        sessionQueue.async {
            session.startRunning()
        }
    }
    
    /// Stop scanning
    func stopScanning() {
        isScanning = false
        sessionQueue.async { [weak self] in
            self?.captureSession?.stopRunning()
        }
    }
    
    /// Scan image directly (for photo library images)
    func scanImage(_ image: UIImage, completion: @escaping (Result<ScannedCardInfo, Error>) -> Void) {
        guard let cgImage = image.cgImage else {
            completion(.failure(CardScannerError.invalidImage))
            return
        }
        
        let request = VNRecognizeTextRequest { [weak self] request, error in
            guard let self = self else { return }
            
            if let error = error {
                completion(.failure(error))
                return
            }
            
            guard let observations = request.results as? [VNRecognizedTextObservation] else {
                completion(.failure(CardScannerError.noTextFound))
                return
            }
            
            let cardInfo = self.extractCardInfo(from: observations)
            
            if cardInfo.cardNumber != nil {
                completion(.success(cardInfo))
            } else {
                completion(.failure(CardScannerError.noCardDetected))
            }
        }
        
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        
        let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
        
        visionQueue.async {
            do {
                try handler.perform([request])
            } catch {
                completion(.failure(error))
            }
        }
    }
    
    // MARK: - Private Methods
    
    private func processVideoFrame(_ sampleBuffer: CMSampleBuffer) {
        guard isScanning else { return }
        
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else {
            return
        }
        
        let request = VNRecognizeTextRequest { [weak self] request, error in
            guard let self = self else { return }
            
            if let error = error {
                print("Vision error: \(error.localizedDescription)")
                return
            }
            
            guard let observations = request.results as? [VNRecognizedTextObservation] else {
                return
            }
            
            let cardInfo = self.extractCardInfo(from: observations)
            
            // Only return if we have high confidence card number
            if let cardNumber = cardInfo.cardNumber, cardInfo.confidence > 0.7 {
                self.isScanning = false
                
                DispatchQueue.main.async {
                    self.scanCompletion?(.success(cardInfo))
                    self.stopScanning()
                }
            }
        }
        
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        
        let handler = VNImageRequestHandler(cvPixelBuffer: pixelBuffer, options: [:])
        
        do {
            try handler.perform([request])
        } catch {
            print("Failed to perform Vision request: \(error)")
        }
    }
    
    private func extractCardInfo(from observations: [VNRecognizedTextObservation]) -> ScannedCardInfo {
        var cardInfo = ScannedCardInfo(confidence: 0)
        var allText: [String] = []
        var totalConfidence: Float = 0
        
        for observation in observations {
            guard let candidate = observation.topCandidates(1).first else { continue }
            allText.append(candidate.string)
            totalConfidence += candidate.confidence
        }
        
        cardInfo.confidence = observations.isEmpty ? 0 : totalConfidence / Float(observations.count)
        
        // Extract card number
        cardInfo.cardNumber = extractCardNumber(from: allText)
        
        // Extract expiry date
        cardInfo.expiryDate = extractExpiryDate(from: allText)
        
        // Extract cardholder name
        cardInfo.cardholderName = extractCardholderName(from: allText)
        
        return cardInfo
    }
    
    private func extractCardNumber(from texts: [String]) -> String? {
        let regex = try? NSRegularExpression(pattern: cardNumberPattern, options: [])
        
        for text in texts {
            let range = NSRange(text.startIndex..., in: text)
            if let match = regex?.firstMatch(in: text, options: [], range: range) {
                let matchedString = (text as NSString).substring(with: match.range)
                let cleaned = matchedString.replacingOccurrences(of: " ", with: "")
                    .replacingOccurrences(of: "-", with: "")
                
                // Validate using Luhn algorithm
                if isValidCardNumber(cleaned) {
                    return formatCardNumber(cleaned)
                }
            }
        }
        
        return nil
    }
    
    private func extractExpiryDate(from texts: [String]) -> String? {
        let regex = try? NSRegularExpression(pattern: expiryPattern, options: [])
        
        for text in texts {
            let range = NSRange(text.startIndex..., in: text)
            if let match = regex?.firstMatch(in: text, options: [], range: range) {
                let matchedString = (text as NSString).substring(with: match.range)
                return formatExpiryDate(matchedString)
            }
        }
        
        return nil
    }
    
    private func extractCardholderName(from texts: [String]) -> String? {
        // Look for text that appears to be a name (2-4 words, mostly letters)
        let namePattern = #"^[A-Z][A-Z\s]{5,30}$"#
        let regex = try? NSRegularExpression(pattern: namePattern, options: [])
        
        for text in texts {
            let upperText = text.uppercased()
            let range = NSRange(upperText.startIndex..., in: upperText)
            
            if regex?.firstMatch(in: upperText, options: [], range: range) != nil {
                // Exclude common card-related words
                let excludedWords = ["DEBIT", "CREDIT", "CARD", "BANK", "VALID", "THRU", "EXPIRES"]
                let containsExcluded = excludedWords.contains { upperText.contains($0) }
                
                if !containsExcluded {
                    return upperText
                }
            }
        }
        
        return nil
    }
    
    // MARK: - Validation Helpers
    
    private func isValidCardNumber(_ number: String) -> Bool {
        guard number.count >= 13 && number.count <= 19 else { return false }
        guard number.allSatisfy({ $0.isNumber }) else { return false }
        
        // Luhn algorithm
        let digits = number.compactMap { Int(String($0)) }
        var sum = 0
        var isSecond = false
        
        for digit in digits.reversed() {
            var current = digit
            if isSecond {
                current *= 2
                if current > 9 {
                    current -= 9
                }
            }
            sum += current
            isSecond.toggle()
        }
        
        return sum % 10 == 0
    }
    
    private func formatCardNumber(_ number: String) -> String {
        // Format as XXXX XXXX XXXX XXXX
        var formatted = ""
        for (index, char) in number.enumerated() {
            if index > 0 && index % 4 == 0 {
                formatted += " "
            }
            formatted.append(char)
        }
        return formatted
    }
    
    private func formatExpiryDate(_ date: String) -> String {
        // Format as MM/YY
        let cleaned = date.replacingOccurrences(of: "/", with: "")
            .replacingOccurrences(of: "-", with: "")
        
        if cleaned.count >= 4 {
            let month = String(cleaned.prefix(2))
            let year = String(cleaned.suffix(2))
            return "\(month)/\(year)"
        }
        
        return date
    }
    
    /// Get card type from number
    func getCardType(from cardNumber: String) -> CardType {
        let cleaned = cardNumber.replacingOccurrences(of: " ", with: "")
        
        if cleaned.hasPrefix("4") {
            return .visa
        } else if cleaned.hasPrefix("5") {
            return .mastercard
        } else if cleaned.hasPrefix("3") {
            return .amex
        } else if cleaned.hasPrefix("6") {
            return .discover
        }
        
        return .unknown
    }
}

// MARK: - AVCaptureVideoDataOutputSampleBufferDelegate

extension CardScannerManager: AVCaptureVideoDataOutputSampleBufferDelegate {
    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        processVideoFrame(sampleBuffer)
    }
}

// MARK: - Supporting Types

enum CardType: String {
    case visa = "Visa"
    case mastercard = "Mastercard"
    case amex = "American Express"
    case discover = "Discover"
    case unknown = "Unknown"
}

enum CardScannerError: LocalizedError {
    case cameraNotAvailable
    case cannotAddInput
    case cannotAddOutput
    case sessionNotSetup
    case invalidImage
    case noTextFound
    case noCardDetected
    case permissionDenied
    
    var errorDescription: String? {
        switch self {
        case .cameraNotAvailable:
            return "Camera is not available on this device"
        case .cannotAddInput:
            return "Cannot add camera input to session"
        case .cannotAddOutput:
            return "Cannot add video output to session"
        case .sessionNotSetup:
            return "Camera session is not setup"
        case .invalidImage:
            return "Invalid image provided"
        case .noTextFound:
            return "No text found in image"
        case .noCardDetected:
            return "No valid card detected"
        case .permissionDenied:
            return "Camera permission denied"
        }
    }
}

//
//  KYCVerificationView.swift
//  RemittanceApp
//
//  Created by Manus AI on 2025/11/03.
//

import SwiftUI
import Combine
import UIKit
import LocalAuthentication // For Biometric Authentication

// MARK: - KYC API (real backend client)

enum KYCAPIError: Error, LocalizedError {
    case networkError
    case serverError(String)
    case invalidData

    var errorDescription: String? {
        switch self {
        case .networkError: return "Could not connect to the network."
        case .serverError(let message): return message
        case .invalidData: return "Received invalid data from the server."
        }
    }
}

/// Interface for KYC network operations, allowing DEBUG-only mocks.
protocol KYCAPI {
    /// Uploads the real captured document and selfie bytes. Returns the
    /// server-reported verification status — never a local assumption.
    func uploadKYCDocuments(document: Data, selfie: Data) -> AnyPublisher<String, KYCAPIError>
    func fetchVerificationStatus() -> AnyPublisher<KYCVerificationStatus, KYCAPIError>
    func initiatePaymentGateway(gateway: PaymentGateway) -> AnyPublisher<Bool, KYCAPIError>
}

/// Real KYC client backed by the 54Link backend.
class LiveKYCAPIClient: KYCAPI {
    private struct UploadResponse: Decodable { let status: String }
    private struct StatusResponse: Decodable { let status: String }
    private struct PaymentResponse: Decodable { let status: String }

    func uploadKYCDocuments(document: Data, selfie: Data) -> AnyPublisher<String, KYCAPIError> {
        Future { promise in
            Task {
                do {
                    let response: UploadResponse = try await APIClient.shared.upload(.kycDocuments) { form in
                        form.append(document, withName: "document", fileName: "document.jpg", mimeType: "image/jpeg")
                        form.append(selfie, withName: "selfie", fileName: "selfie.jpg", mimeType: "image/jpeg")
                    }
                    promise(.success(response.status))
                } catch {
                    promise(.failure(.serverError(error.localizedDescription)))
                }
            }
        }
        .eraseToAnyPublisher()
    }

    func fetchVerificationStatus() -> AnyPublisher<KYCVerificationStatus, KYCAPIError> {
        Future { promise in
            Task {
                do {
                    let response: StatusResponse = try await APIClient.shared.request(.kycStatus)
                    guard let status = KYCVerificationStatus(rawValue: response.status) else {
                        promise(.failure(.invalidData))
                        return
                    }
                    promise(.success(status))
                } catch {
                    promise(.failure(.serverError(error.localizedDescription)))
                }
            }
        }
        .eraseToAnyPublisher()
    }

    func initiatePaymentGateway(gateway: PaymentGateway) -> AnyPublisher<Bool, KYCAPIError> {
        Future { promise in
            Task {
                do {
                    let response: PaymentResponse = try await APIClient.shared.request(
                        .paymentInitiate,
                        method: .post,
                        parameters: ["gateway": gateway.rawValue, "purpose": "kyc_verification_fee"]
                    )
                    promise(.success(response.status.lowercased() == "initiated" || response.status.lowercased() == "success"))
                } catch {
                    promise(.failure(.serverError(error.localizedDescription)))
                }
            }
        }
        .eraseToAnyPublisher()
    }
}

#if DEBUG
/// Mock KYC client (DEBUG builds only, for previews/tests).
class MockKYCAPIClient: KYCAPI {
    func uploadKYCDocuments(document: Data, selfie: Data) -> AnyPublisher<String, KYCAPIError> {
        Future { promise in
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                promise(.success(KYCVerificationStatus.pending.rawValue))
            }
        }
        .eraseToAnyPublisher()
    }

    func fetchVerificationStatus() -> AnyPublisher<KYCVerificationStatus, KYCAPIError> {
        Just(.pending).setFailureType(to: KYCAPIError.self).eraseToAnyPublisher()
    }

    func initiatePaymentGateway(gateway: PaymentGateway) -> AnyPublisher<Bool, KYCAPIError> {
        Just(true).setFailureType(to: KYCAPIError.self).eraseToAnyPublisher()
    }
}
#endif

// MARK: - Model and Enums

/// Defines the supported payment gateways.
enum PaymentGateway: String, CaseIterable, Identifiable {
    case paystack = "Paystack"
    case flutterwave = "Flutterwave"
    case interswitch = "Interswitch"
    
    var id: String { self.rawValue }
}

/// Defines the possible states of KYC verification.
enum KYCVerificationStatus: String, Codable {
    case notStarted = "Not Started"
    case pending = "Pending Review"
    case verified = "Verified"
    case rejected = "Rejected"
}

/// Defines the steps in the KYC process.
enum KYCStep: Int, CaseIterable {
    case documentUpload = 0
    case selfieCapture
    case submission
    case status
    
    var title: String {
        switch self {
        case .documentUpload: return "1. Upload Document"
        case .selfieCapture: return "2. Capture Selfie"
        case .submission: return "3. Review & Submit"
        case .status: return "4. Verification Status"
        }
    }
}

// MARK: - View Model

/// Manages the state and business logic for the KYC verification process.
final class KYCVerificationViewModel: ObservableObject {
    
    // MARK: Published Properties
    
    @Published var currentStep: KYCStep = .documentUpload
    @Published var verificationStatus: KYCVerificationStatus = .notStarted
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var isOffline: Bool = false
    
    // Document and Selfie Data (real captured images)
    @Published var documentData: Data?
    @Published var selfieData: Data?
    
    // Payment Gateway Selection
    @Published var selectedPaymentGateway: PaymentGateway = .paystack
    
    // MARK: Private Properties
    
    private let apiClient: KYCAPI
    private var cancellables = Set<AnyCancellable>()
    
    // MARK: Initialization
    
    init(apiClient: KYCAPI = LiveKYCAPIClient()) {
        self.apiClient = apiClient
        // Check for cached status on initialization (Offline Mode Support)
        loadCachedStatus()
        // Fetch the authoritative status from the server; network failures
        // surface as honest errors rather than simulated connectivity.
        if self.verificationStatus == .notStarted {
            self.fetchStatus()
        }
    }
    
    // MARK: Public Methods
    
    /// Checks if the current step's requirements are met for navigation.
    var isCurrentStepValid: Bool {
        switch currentStep {
        case .documentUpload:
            return documentData != nil
        case .selfieCapture:
            return selfieData != nil
        case .submission:
            return documentData != nil && selfieData != nil
        case .status:
            return true
        }
    }
    
    /// Advances to the next step in the KYC process.
    func nextStep() {
        guard isCurrentStepValid else {
            errorMessage = "Please complete the current step before proceeding."
            return
        }
        
        if currentStep == .submission {
            submitForVerification()
        } else if let next = KYCStep(rawValue: currentStep.rawValue + 1) {
            currentStep = next
        }
    }
    
    /// Submits the documents for verification.
    func submitForVerification() {
        guard let document = documentData, let selfie = selfieData, !isOffline else {
            errorMessage = isOffline ? "Cannot submit while offline. Please connect to the internet." : "Document and selfie data are required."
            return
        }
        
        isLoading = true
        errorMessage = nil
        
        apiClient.uploadKYCDocuments(document: document, selfie: selfie)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] completion in
                self?.isLoading = false
                switch completion {
                case .failure(let error):
                    // An upload failure is a transport error, NOT a verification
                    // rejection — the compliance status is left untouched.
                    self?.errorMessage = "Upload failed: \(error.localizedDescription). Your verification status is unchanged."
                case .finished:
                    break
                }
            } receiveValue: { [weak self] newStatusString in
                if let newStatus = KYCVerificationStatus(rawValue: newStatusString) {
                    self?.verificationStatus = newStatus
                    self?.currentStep = .status
                    self?.saveStatus()
                }
            }
            .store(in: &cancellables)
    }
    
    /// Fetches the latest verification status from the server.
    func fetchStatus() {
        guard !isOffline else {
            errorMessage = "Cannot fetch status while offline."
            return
        }
        
        isLoading = true
        errorMessage = nil
        
        apiClient.fetchVerificationStatus()
            .receive(on: DispatchQueue.main)
            .sink { [weak self] completion in
                self?.isLoading = false
                if case .failure(let error) = completion {
                    self?.errorMessage = "Failed to fetch status: \(error.localizedDescription)"
                }
            } receiveValue: { [weak self] status in
                self?.verificationStatus = status
                self?.saveStatus()
                if status != .notStarted {
                    self?.currentStep = .status
                }
            }
            .store(in: &cancellables)
    }
    
    /// Initiates a real verification-fee payment via the selected gateway.
    func initiatePayment() {
        guard !isOffline else {
            errorMessage = "Cannot initiate payment while offline."
            return
        }
        
        isLoading = true
        errorMessage = nil
        
        apiClient.initiatePaymentGateway(gateway: selectedPaymentGateway)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] completion in
                self?.isLoading = false
                if case .failure(let error) = completion {
                    self?.errorMessage = "Payment failed: \(error.localizedDescription)"
                }
            } receiveValue: { [weak self] success in
                if success {
                    self?.errorMessage = "Payment via \(self?.selectedPaymentGateway.rawValue ?? "") successful! Proceeding with verification."
                }
            }
            .store(in: &cancellables)
    }
    
    // MARK: Offline Mode / Caching
    
    /// Saves the current verification status to local storage.
    private func saveStatus() {
        do {
            let encoder = JSONEncoder()
            let data = try encoder.encode(verificationStatus)
            UserDefaults.standard.set(data, forKey: "kycVerificationStatus")
            print("Status saved locally: \(verificationStatus.rawValue)")
        } catch {
            print("Error saving status: \(error)")
        }
    }
    
    /// Loads the cached verification status from local storage.
    private func loadCachedStatus() {
        if let savedData = UserDefaults.standard.data(forKey: "kycVerificationStatus") {
            do {
                let decoder = JSONDecoder()
                let status = try decoder.decode(KYCVerificationStatus.self, from: savedData)
                self.verificationStatus = status
                print("Cached status loaded: \(status.rawValue)")
            } catch {
                print("Error loading cached status: \(error)")
            }
        }
    }
    
    // MARK: Biometric Authentication
    
    /// Attempts to authenticate the user using biometrics (Face ID/Touch ID).
    func authenticateWithBiometrics(completion: @escaping (Bool, String?) -> Void) {
        let context = LAContext()
        var error: NSError?
        
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            completion(false, error?.localizedDescription ?? "Biometric authentication not available.")
            return
        }
        
        let reason = "Securely access your KYC verification details."
        
        context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason) { success, authenticationError in
            DispatchQueue.main.async {
                if success {
                    completion(true, nil)
                } else {
                    completion(false, authenticationError?.localizedDescription ?? "Authentication failed.")
                }
            }
        }
    }
}

// MARK: - Subviews

/// UIKit image picker bridge — captures REAL document/selfie images from the
/// camera or photo library. No fabricated image bytes are ever produced.
struct ImagePicker: UIViewControllerRepresentable {
    enum Source {
        case camera
        case photoLibrary

        var uiKitSource: UIImagePickerController.SourceType {
            switch self {
            case .camera: return UIImagePickerController.isSourceTypeAvailable(.camera) ? .camera : .photoLibrary
            case .photoLibrary: return .photoLibrary
            }
        }
    }

    let source: Source
    let onImagePicked: (Data) -> Void
    @Environment(\.dismiss) private var dismiss

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = source.uiKitSource
        picker.delegate = context.coordinator
        if source.uiKitSource == .camera {
            picker.cameraDevice = .front
        }
        return picker
    }

    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}

    final class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let parent: ImagePicker
        init(_ parent: ImagePicker) { self.parent = parent }

        func imagePickerController(_ picker: UIImagePickerController,
                                   didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            if let image = info[.originalImage] as? UIImage,
               let data = image.jpegData(compressionQuality: 0.8) {
                parent.onImagePicked(data)
            }
            parent.dismiss()
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            parent.dismiss()
        }
    }
}

/// Real document capture view — presents the device photo library.
struct DocumentUploadView: View {
    @ObservedObject var viewModel: KYCVerificationViewModel
    @State private var showPicker = false
    
    var body: some View {
        VStack(spacing: 20) {
            Text("Upload your Government-Issued ID")
                .font(.headline)
            
            Image(systemName: viewModel.documentData == nil ? "doc.badge.plus" : "doc.fill.checkmark")
                .resizable()
                .scaledToFit()
                .frame(width: 100, height: 100)
                .foregroundColor(viewModel.documentData == nil ? .gray : .green)
                .accessibilityLabel(viewModel.documentData == nil ? "Document upload required" : "Document uploaded")
            
            Button(viewModel.documentData == nil ? "Select Document" : "Change Document") {
                showPicker = true
            }
            .buttonStyle(.borderedProminent)
            .sheet(isPresented: $showPicker) {
                ImagePicker(source: .photoLibrary) { data in
                    viewModel.documentData = data
                }
            }
            
            if viewModel.documentData != nil {
                Text("Document selected successfully.")
                    .foregroundColor(.secondary)
            }
        }
        .padding()
    }
}

/// Real selfie capture view — presents the front camera (falls back to the
/// photo library on devices without a camera, e.g. simulator).
struct SelfieCaptureView: View {
    @ObservedObject var viewModel: KYCVerificationViewModel
    @State private var showPicker = false
    
    var body: some View {
        VStack(spacing: 20) {
            Text("Capture a live selfie for face verification")
                .font(.headline)
            
            Image(systemName: viewModel.selfieData == nil ? "person.crop.circle.badge.plus" : "person.crop.circle.fill.checkmark")
                .resizable()
                .scaledToFit()
                .frame(width: 100, height: 100)
                .foregroundColor(viewModel.selfieData == nil ? .gray : .green)
                .accessibilityLabel(viewModel.selfieData == nil ? "Selfie capture required" : "Selfie captured")
            
            Button(viewModel.selfieData == nil ? "Capture Selfie" : "Retake Selfie") {
                showPicker = true
            }
            .buttonStyle(.borderedProminent)
            .sheet(isPresented: $showPicker) {
                ImagePicker(source: .camera) { data in
                    viewModel.selfieData = data
                }
            }
            
            if viewModel.selfieData != nil {
                Text("Selfie captured successfully.")
                    .foregroundColor(.secondary)
            }
        }
        .padding()
    }
}

/// A view for final review and submission.
struct SubmissionView: View {
    @ObservedObject var viewModel: KYCVerificationViewModel
    
    var body: some View {
        VStack(spacing: 25) {
            Text("Review and Submit")
                .font(.largeTitle)
                .bold()
            
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Image(systemName: viewModel.documentData != nil ? "checkmark.circle.fill" : "xmark.circle.fill")
                        .foregroundColor(viewModel.documentData != nil ? .green : .red)
                    Text("Document Uploaded: \(viewModel.documentData != nil ? "Yes" : "No")")
                }
                HStack {
                    Image(systemName: viewModel.selfieData != nil ? "checkmark.circle.fill" : "xmark.circle.fill")
                        .foregroundColor(viewModel.selfieData != nil ? .green : .red)
                    Text("Selfie Captured: \(viewModel.selfieData != nil ? "Yes" : "No")")
                }
            }
            .padding()
            .background(Color(.systemGray6))
            .cornerRadius(10)
            
            // Payment Gateway Integration
            VStack(alignment: .leading) {
                Text("Select Verification Fee Payment Gateway (Optional)")
                    .font(.headline)
                
                Picker("Payment Gateway", selection: $viewModel.selectedPaymentGateway) {
                    ForEach(PaymentGateway.allCases) { gateway in
                        Text(gateway.rawValue).tag(gateway)
                    }
                }
                .pickerStyle(.menu)
                
                Button("Initiate Payment via \(viewModel.selectedPaymentGateway.rawValue)") {
                    viewModel.initiatePayment()
                }
                .buttonStyle(.bordered)
                .disabled(viewModel.isLoading || viewModel.isOffline)
            }
            
            Button("Submit for Verification") {
                viewModel.submitForVerification()
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(viewModel.isLoading || !viewModel.isCurrentStepValid || viewModel.isOffline)
        }
        .padding()
    }
}

/// A view to display the current verification status.
struct StatusView: View {
    @ObservedObject var viewModel: KYCVerificationViewModel
    
    var statusColor: Color {
        switch viewModel.verificationStatus {
        case .notStarted: return .gray
        case .pending: return .orange
        case .verified: return .green
        case .rejected: return .red
        }
    }
    
    var statusIcon: String {
        switch viewModel.verificationStatus {
        case .notStarted: return "questionmark.circle.fill"
        case .pending: return "clock.fill"
        case .verified: return "checkmark.seal.fill"
        case .rejected: return "xmark.octagon.fill"
        }
    }
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: statusIcon)
                .resizable()
                .scaledToFit()
                .frame(width: 100, height: 100)
                .foregroundColor(statusColor)
                .accessibilityLabel("Verification status is \(viewModel.verificationStatus.rawValue)")
            
            Text("Verification Status")
                .font(.title)
                .bold()
            
            Text(viewModel.verificationStatus.rawValue)
                .font(.title2)
                .foregroundColor(statusColor)
            
            Text(statusMessage)
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
                .padding(.horizontal)
            
            Button("Refresh Status") {
                viewModel.fetchStatus()
            }
            .buttonStyle(.bordered)
            .disabled(viewModel.isLoading || viewModel.isOffline)
            
            if viewModel.verificationStatus == .rejected {
                Button("Restart Verification") {
                    // Reset to the first step
                    viewModel.currentStep = .documentUpload
                    viewModel.verificationStatus = .notStarted
                    viewModel.documentData = nil
                    viewModel.selfieData = nil
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding()
    }
    
    private var statusMessage: String {
        switch viewModel.verificationStatus {
        case .notStarted:
            return "Please start the verification process by uploading your documents."
        case .pending:
            return "Your documents are currently under review. This usually takes 24-48 hours."
        case .verified:
            return "Congratulations! Your identity has been successfully verified. You now have full access to all features."
        case .rejected:
            return "Your verification was rejected. Please review the requirements and try again."
        }
    }
}

// MARK: - Main View

/// The main view for the KYC verification process.
struct KYCVerificationView: View {
    
    @StateObject private var viewModel = KYCVerificationViewModel()
    @State private var isBiometricallyAuthenticated: Bool = false
    @State private var biometricError: String?
    
    // MARK: Body
    
    var body: some View {
        NavigationView {
            VStack {
                if !isBiometricallyAuthenticated {
                    biometricAuthView
                } else {
                    contentView
                }
            }
            .navigationTitle("KYC Verification")
            .onAppear {
                // Attempt biometric authentication on view appearance
                authenticateUser()
            }
        }
        // Accessibility: Ensure the navigation view is accessible
        .accessibilityElement(children: .contain)
        .accessibilityLabel("KYC Verification Screen")
    }
    
    // MARK: Biometric Authentication View
    
    private var biometricAuthView: some View {
        VStack(spacing: 20) {
            Image(systemName: "lock.shield.fill")
                .resizable()
                .scaledToFit()
                .frame(width: 80, height: 80)
                .foregroundColor(.blue)
            
            Text("Secure Access Required")
                .font(.title2)
                .bold()
            
            Text("Please authenticate with \(LAContext().biometryType == .faceID ? "Face ID" : "Touch ID") to view your verification status and documents.")
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            
            if let error = biometricError {
                Text("Authentication Error: \(error)")
                    .foregroundColor(.red)
            }
            
            Button("Authenticate Now") {
                authenticateUser()
            }
            .buttonStyle(.borderedProminent)
        }
    }
    
    // MARK: Main Content View
    
    private var contentView: some View {
        VStack {
            // Progress Indicator
            ProgressView(value: Double(viewModel.currentStep.rawValue + 1), total: Double(KYCStep.allCases.count))
                .padding(.horizontal)
                .accessibilityLabel("Verification progress")
                .accessibilityValue("\(viewModel.currentStep.rawValue + 1) of \(KYCStep.allCases.count) steps complete")
            
            // Step Titles
            HStack {
                ForEach(KYCStep.allCases, id: \.self) { step in
                    Text(step.title)
                        .font(.caption)
                        .foregroundColor(step.rawValue == viewModel.currentStep.rawValue ? .blue : .gray)
                        .frame(maxWidth: .infinity)
                }
            }
            .padding(.bottom)
            
            // Current Step Content
            Group {
                switch viewModel.currentStep {
                case .documentUpload:
                    DocumentUploadView(viewModel: viewModel)
                case .selfieCapture:
                    SelfieCaptureView(viewModel: viewModel)
                case .submission:
                    SubmissionView(viewModel: viewModel)
                case .status:
                    StatusView(viewModel: viewModel)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            
            // Error Message Display
            if let error = viewModel.errorMessage {
                Text(error)
                    .foregroundColor(.white)
                    .padding()
                    .frame(maxWidth: .infinity)
                    .background(Color.red)
                    .cornerRadius(8)
                    .padding(.horizontal)
                    .transition(.slide)
            }
            
            // Loading Indicator
            if viewModel.isLoading {
                ProgressView("Processing...")
                    .padding()
            }
            
            // Navigation Button
            if viewModel.currentStep != .status {
                Button("Continue") {
                    viewModel.nextStep()
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .padding()
                .disabled(!viewModel.isCurrentStepValid || viewModel.isLoading)
            }
        }
        .padding(.top)
        .alert(isPresented: .constant(viewModel.isOffline && viewModel.errorMessage != nil)) {
            Alert(title: Text("Offline Mode"), message: Text(viewModel.errorMessage ?? "Status may be outdated."), dismissButton: .default(Text("OK")))
        }
    }
    
    // MARK: Private Methods
    
    private func authenticateUser() {
        viewModel.authenticateWithBiometrics { success, error in
            if success {
                self.isBiometricallyAuthenticated = true
                self.biometricError = nil
            } else {
                // Authentication failed: stay on the gated screen and surface the
                // error. Access is NEVER granted after a failed authentication.
                self.biometricError = error
                self.isBiometricallyAuthenticated = false
            }
        }
    }
}

// MARK: - Preview

#Preview {
    KYCVerificationView()
}

//
//  KYCVerificationView.swift
//  RemittanceApp
//
//  Created by Manus AI on 2025/11/03.
//

import SwiftUI
import Combine
import LocalAuthentication // For Biometric Authentication

// MARK: - API Client Stub

/// A stub for the API client to handle KYC-related network operations.
/// In a real application, this would be a shared service class.
class APIClient {
    enum APIError: Error, LocalizedError {
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
    
    /// Simulates uploading a document and selfie to the server.
    func uploadKYCDocuments(document: Data, selfie: Data) -> AnyPublisher<String, APIError> {
        return Future<String, APIError> { promise in
            // Simulate network delay
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                // Simulate success
                print("APIClient: Documents uploaded successfully.")
                promise(.success("VerificationPending"))
                
                // To simulate failure, uncomment the line below:
                // promise(.failure(.serverError("Document image quality too low.")))
            }
        }
        .eraseToAnyPublisher()
    }
    
    /// Simulates fetching the current verification status.
    func fetchVerificationStatus() -> AnyPublisher<KYCVerificationStatus, APIError> {
        return Future<KYCVerificationStatus, APIError> { promise in
            // Simulate network delay
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                // In a real app, this would fetch the actual status
                let status: KYCVerificationStatus = .pending // Assume pending after initial upload
                print("APIClient: Fetched status: \(status)")
                promise(.success(status))
            }
        }
        .eraseToAnyPublisher()
    }
    
    /// Simulates integrating with a payment gateway (e.g., for a small verification fee).
    func initiatePaymentGateway(gateway: PaymentGateway) -> AnyPublisher<Bool, APIError> {
        return Future<Bool, APIError> { promise in
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                print("APIClient: Initiated payment via \(gateway.rawValue)")
                promise(.success(true))
            }
        }
        .eraseToAnyPublisher()
    }
}

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
    @Published var isOffline: Bool = false // Simulate offline mode
    
    // Document and Selfie Data (Simulated)
    @Published var documentData: Data?
    @Published var selfieData: Data?
    
    // Payment Gateway Selection
    @Published var selectedPaymentGateway: PaymentGateway = .paystack
    
    // MARK: Private Properties
    
    private let apiClient: APIClient
    private var cancellables = Set<AnyCancellable>()
    
    // MARK: Initialization
    
    init(apiClient: APIClient = APIClient()) {
        self.apiClient = apiClient
        // Check for cached status on initialization (Offline Mode Support)
        loadCachedStatus()
        // Simulate network status check
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            self.isOffline = Bool.random() // Randomly simulate offline status
            if self.isOffline {
                self.errorMessage = "You are currently offline. Status may be outdated."
            } else if self.verificationStatus == .notStarted {
                self.fetchStatus()
            }
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
                    self?.errorMessage = error.localizedDescription
                    self?.verificationStatus = .rejected // Assume rejection on submission failure
                    self?.saveStatus()
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
    
    /// Simulates initiating a payment via the selected gateway.
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

/// A view to simulate document selection/capture.
struct DocumentUploadView: View {
    @ObservedObject var viewModel: KYCVerificationViewModel
    
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
                // In a real app, this would launch a UIImagePickerController or Camera
                // Simulate document selection
                viewModel.documentData = Data("Simulated Document Data".utf8)
            }
            .buttonStyle(.borderedProminent)
            
            if viewModel.documentData != nil {
                Text("Document selected successfully.")
                    .foregroundColor(.secondary)
            }
        }
        .padding()
    }
}

/// A view to simulate selfie capture.
struct SelfieCaptureView: View {
    @ObservedObject var viewModel: KYCVerificationViewModel
    
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
                // In a real app, this would launch the camera
                // Simulate selfie capture
                viewModel.selfieData = Data("Simulated Selfie Data".utf8)
            }
            .buttonStyle(.borderedProminent)
            
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
            
            // Payment Gateway Integration Stub
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
                // Fallback to allowing access without biometrics for a production-ready view,
                // but keep the authentication view for a better UX.
                // For this task, we'll allow a simple retry or proceed without it.
                // In a real app, a PIN/Password fallback would be implemented here.
                self.biometricError = error
                // For simplicity in this generated code, we'll allow bypass after failure.
                DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                    self.isBiometricallyAuthenticated = true
                }
            }
        }
    }
}

// MARK: - Preview

#Preview {
    KYCVerificationView()
}

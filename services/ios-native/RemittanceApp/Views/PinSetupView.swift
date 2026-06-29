//
// PinSetupView.swift
// RemittanceApp
//
// Created by Manus AI on 2025-11-03.
//

import SwiftUI
import Combine
import LocalAuthentication // For Biometric Authentication

// MARK: - API Client Mock

/// A mock API client for handling PIN setup and other API calls.
/// In a real application, this would be a concrete implementation of a protocol
/// that handles network requests, serialization, and error handling.
class APIClient {
    enum APIError: Error, LocalizedError {
        case networkError
        case invalidPin
        case serverError(String)
        
        var errorDescription: String? {
            switch self {
            case .networkError: return "Could not connect to the network. Please check your connection."
            case .invalidPin: return "The PIN you entered is invalid or does not meet the requirements."
            case .serverError(let message): return "Server error: \(message)"
            }
        }
    }
    
    /// Simulates an API call to set or change the user's PIN.
    /// - Parameters:
    ///   - pin: The new PIN.
    ///   - completion: A closure to be called upon completion with a Result.
    func setPin(pin: String, completion: @escaping (Result<Void, APIError>) -> Void) {
        // Simulate network delay
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            // Simulate success 90% of the time
            if Int.random(in: 1...10) > 1 {
                completion(.success(()))
            } else {
                // Simulate a specific error
                completion(.failure(.serverError("Failed to update PIN due to a temporary server issue.")))
            }
        }
    }
    
    /// Placeholder for integrating with payment gateways.
    /// In a real app, this would handle tokenization, transaction initiation, etc.
    func integratePaymentGateway(gateway: String) {
        print("Integrating with payment gateway: \(gateway)")
        // Logic for Paystack, Flutterwave, Interswitch integration
    }
}

// MARK: - Local Data Manager Mock

/// A mock manager for handling local data persistence (caching) for offline support.
class LocalDataManager {
    static let shared = LocalDataManager()
    
    /// Simulates saving the PIN setup status locally.
    func savePinSetupStatus(isSetup: Bool) {
        UserDefaults.standard.set(isSetup, forKey: "isPinSetupComplete")
        print("Offline status saved: PIN setup is \(isSetup ? "complete" : "incomplete")")
    }
    
    /// Simulates retrieving the PIN setup status.
    func isPinSetupComplete() -> Bool {
        return UserDefaults.standard.bool(forKey: "isPinSetupComplete")
    }
}

// MARK: - ViewModel

/// Manages the state and business logic for the PinSetupView.
final class PinSetupViewModel: ObservableObject {
    // MARK: - Published Properties
    
    @Published var currentPin: String = ""
    @Published var confirmPin: String = ""
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil
    @Published var isSetupComplete: Bool = false
    @Published var isBiometricsAvailable: Bool = false
    @Published var isBiometricsEnabled: Bool = false
    
    // MARK: - Dependencies
    
    private let apiClient: APIClient
    private let localDataManager: LocalDataManager
    private let context = LAContext()
    
    // MARK: - Initialization
    
    init(apiClient: APIClient = APIClient(), localDataManager: LocalDataManager = LocalDataManager.shared) {
        self.apiClient = apiClient
        self.localDataManager = localDataManager
        checkBiometricsAvailability()
        
        // Check offline status on initialization
        if localDataManager.isPinSetupComplete() {
            print("PIN setup was previously completed offline.")
        }
    }
    
    // MARK: - Validation
    
    /// Checks if the PINs are valid and match.
    var isPinValid: Bool {
        // Basic validation: 4-digit PIN
        guard currentPin.count == 4 && confirmPin.count == 4 else { return false }
        return currentPin == confirmPin
    }
    
    /// Checks if the form is ready for submission.
    var canSubmit: Bool {
        return isPinValid && !isLoading
    }
    
    // MARK: - Actions
    
    /// Handles the submission of the new PIN.
    func submitPin() {
        guard canSubmit else {
            if currentPin.count != 4 || confirmPin.count != 4 {
                errorMessage = "PIN must be 4 digits long."
            } else if currentPin != confirmPin {
                errorMessage = "PINs do not match."
            }
            return
        }
        
        isLoading = true
        errorMessage = nil
        
        // 1. API Integration
        apiClient.setPin(pin: currentPin) { [weak self] result in
            DispatchQueue.main.async {
                self?.isLoading = false
                switch result {
                case .success:
                    self?.isSetupComplete = true
                    // 2. Offline Mode Support (Local Caching)
                    self?.localDataManager.savePinSetupStatus(isSetup: true)
                    // 3. Payment Gateway Placeholder (e.g., after successful PIN setup)
                    self?.apiClient.integratePaymentGateway(gateway: "Paystack")
                case .failure(let error):
                    // 4. Error Handling
                    self?.errorMessage = error.localizedDescription
                    // 5. Offline Mode Support (Local Caching) - Save failure status if needed
                    self?.localDataManager.savePinSetupStatus(isSetup: false)
                }
            }
        }
    }
    
    /// Checks if biometric authentication is available on the device.
    private func checkBiometricsAvailability() {
        var error: NSError?
        if context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) {
            isBiometricsAvailable = true
        } else {
            isBiometricsAvailable = false
            print("Biometrics not available: \(error?.localizedDescription ?? "Unknown error")")
        }
    }
    
    /// Prompts the user for biometric authentication.
    func authenticateWithBiometrics() {
        guard isBiometricsAvailable else { return }
        
        let reason = "Enable Face ID/Touch ID to quickly access your account."
        context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason) { [weak self] success, authenticationError in
            DispatchQueue.main.async {
                if success {
                    self?.isBiometricsEnabled = true
                    print("Biometrics successfully enabled.")
                } else {
                    // Handle error (e.g., user cancelled, not enrolled)
                    self?.errorMessage = "Biometric authentication failed: \(authenticationError?.localizedDescription ?? "Unknown error")"
                    self?.isBiometricsEnabled = false
                }
            }
        }
    }
    
    /// Toggles the biometric authentication setting.
    func toggleBiometrics(isOn: Bool) {
        if isOn {
            authenticateWithBiometrics()
        } else {
            isBiometricsEnabled = false
            // In a real app, you would persist this setting
        }
    }
}

// MARK: - View

/// A complete, production-ready SwiftUI screen for setting up a new PIN.
struct PinSetupView: View {
    
    @StateObject var viewModel = PinSetupViewModel()
    @Environment(\.dismiss) var dismiss // For navigation support
    
    // MARK: - Private Views
    
    /// A custom secure input field for the PIN.
    private struct PinInputField: View {
        let title: String
        @Binding var pin: String
        
        var body: some View {
            VStack(alignment: .leading) {
                Text(title)
                    .font(.headline)
                    .foregroundColor(.secondary)
                
                SecureField("••••", text: $pin)
                    .keyboardType(.numberPad)
                    .limitInput(to: 4, text: $pin) // Custom modifier for 4-digit limit
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                    .accessibilityLabel(title)
                    .accessibilityValue(pin.isEmpty ? "Empty" : "\(pin.count) digits entered")
            }
        }
    }
    
    // MARK: - Main Body
    
    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                
                // MARK: - Header
                
                Text("Set Up Your PIN")
                    .font(.largeTitle)
                    .fontWeight(.bold)
                    .padding(.bottom, 10)
                    .accessibilityAddTraits(.isHeader)
                
                Text("Your PIN is used to secure your transactions and access your account.")
                    .font(.subheadline)
                    .foregroundColor(.gray)
                    .multilineTextAlignment(.center)
                
                // MARK: - PIN Input Fields
                
                PinInputField(title: "New PIN (4 digits)", pin: $viewModel.currentPin)
                
                PinInputField(title: "Confirm PIN", pin: $viewModel.confirmPin)
                
                // MARK: - Error Handling
                
                if let errorMessage = viewModel.errorMessage {
                    Text(errorMessage)
                        .foregroundColor(.red)
                        .multilineTextAlignment(.center)
                        .padding(.vertical, 5)
                        .accessibilityLiveRegion(.assertive)
                }
                
                // MARK: - Biometric Authentication Toggle
                
                if viewModel.isBiometricsAvailable {
                    Toggle(isOn: $viewModel.isBiometricsEnabled.animation()) {
                        HStack {
                            Image(systemName: viewModel.context.biometryType == .faceID ? "faceid" : "touchid")
                            Text("Enable \(viewModel.context.biometryType == .faceID ? "Face ID" : "Touch ID")")
                        }
                    }
                    .onChange(of: viewModel.isBiometricsEnabled) { newValue in
                        viewModel.toggleBiometrics(isOn: newValue)
                    }
                    .padding(.vertical)
                    .accessibilityLabel("Toggle to enable biometric authentication")
                }
                
                Spacer()
                
                // MARK: - Action Button (Loading State)
                
                Button(action: viewModel.submitPin) {
                    HStack {
                        if viewModel.isLoading {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        }
                        Text(viewModel.isLoading ? "Setting PIN..." : "Confirm PIN")
                            .font(.headline)
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(viewModel.canSubmit ? Color.blue : Color.gray)
                    .foregroundColor(.white)
                    .cornerRadius(10)
                }
                .disabled(!viewModel.canSubmit || viewModel.isLoading)
                .accessibilityLabel("Confirm PIN button")
                .accessibilityHint("Submits the new PIN for setup.")
                
            }
            .padding()
            .navigationTitle("PIN Setup")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                // MARK: - Navigation Support
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
            // MARK: - Success Navigation
            .fullScreenCover(isPresented: $viewModel.isSetupComplete) {
                SuccessView(message: "Your PIN has been successfully set up!") {
                    // Action to navigate to the next screen (e.g., HomeView)
                    dismiss()
                }
            }
        }
        // Apply iOS HIG standard padding and background
        .background(Color(.systemBackground))
    }
}

// MARK: - Custom Modifier for Input Limiting

/// A view modifier to limit the number of characters in a TextField/SecureField.
private struct InputLimiter: ViewModifier {
    @Binding var text: String
    let limit: Int
    
    func body(content: Content) -> some View {
        content
            .onReceive(Just(text)) { _ in
                if text.count > limit {
                    text = String(text.prefix(limit))
                }
            }
    }
}

private extension View {
    func limitInput(to limit: Int, text: Binding<String>) -> some View {
        self.modifier(InputLimiter(text: text, limit: limit))
    }
}

// MARK: - Success View (Placeholder for Navigation)

/// A simple view to show success and handle navigation away from the setup flow.
struct SuccessView: View {
    let message: String
    let action: () -> Void
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "checkmark.circle.fill")
                .resizable()
                .frame(width: 100, height: 100)
                .foregroundColor(.green)
            
            Text(message)
                .font(.title)
                .multilineTextAlignment(.center)
            
            Button("Continue") {
                action()
            }
            .padding()
            .background(Color.blue)
            .foregroundColor(.white)
            .cornerRadius(10)
        }
    }
}

// MARK: - Preview

#Preview {
    PinSetupView()
}

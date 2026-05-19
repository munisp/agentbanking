//
// BiometricAuthView.swift
// RemittanceApp
//
// Created by Manus AI on 2025-11-03.
//

import SwiftUI
import LocalAuthentication

// MARK: - 1. API Client Mock

/// A mock API client to simulate network operations.
/// In a real application, this would handle secure communication with the backend.
class APIClient {
    static let shared = APIClient()
    
    enum APIError: Error {
        case networkError
        case serverError(String)
    }
    
    /// Simulates registering the user's biometric preference on the server.
    func registerBiometricPreference(isEnabled: Bool) async throws -> Bool {
        // Simulate network delay
        try await Task.sleep(nanoseconds: 1_000_000_000)
        
        // Simulate a successful response
        if isEnabled {
            print("API: Biometric preference set to enabled.")
        } else {
            print("API: Biometric preference set to disabled.")
        }
        
        // Simulate payment gateway integration update
        await updatePaymentGatewaySettings(isEnabled: isEnabled)
        
        return true
    }
    
    /// Simulates updating payment gateway settings (Paystack, Flutterwave, Interswitch)
    /// to use biometrics for transaction confirmation.
    private func updatePaymentGatewaySettings(isEnabled: Bool) async {
        // This is a placeholder for actual SDK/API calls to payment providers.
        // In a real app, this would involve secure token exchange and configuration.
        print("API: Updating Paystack/Flutterwave/Interswitch settings for biometric use: \(isEnabled)")
    }
    
    /// Simulates fetching a cached setting for offline mode.
    func getCachedBiometricSetting() -> Bool {
        // Placeholder for local caching logic (e.g., using UserDefaults or CoreData)
        return UserDefaults.standard.bool(forKey: "isBiometricEnabledCache")
    }
    
    /// Simulates saving a setting for offline mode.
    func saveBiometricSettingToCache(isEnabled: Bool) {
        UserDefaults.standard.set(isEnabled, forKey: "isBiometricEnabledCache")
        print("Local Cache: Biometric setting saved: \(isEnabled)")
    }
}

// MARK: - 2. View Model

/// Manages the state and business logic for the BiometricAuthView.
@MainActor
final class BiometricAuthViewModel: ObservableObject {
    
    // MARK: Published Properties
    
    @Published var isBiometricEnabled: Bool = false
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var isAuthenticationSuccessful: Bool = false
    @Published var biometricType: LABiometryType = .none
    
    // MARK: Private Properties
    
    private let context = LAContext()
    private let api: APIClient
    
    // MARK: Initialization
    
    init(api: APIClient = .shared) {
        self.api = api
        self.isBiometricEnabled = api.getCachedBiometricSetting()
        self.checkBiometricCapability()
    }
    
    // MARK: Biometric Logic
    
    /// Checks the device's biometric capability and updates `biometricType`.
    func checkBiometricCapability() {
        var error: NSError?
        if context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) {
            self.biometricType = context.biometryType
        } else {
            self.biometricType = .none
            if let error = error {
                print("Biometric check failed: \(error.localizedDescription)")
            }
        }
    }
    
    /// Returns the user-friendly name for the detected biometric type.
    var biometricName: String {
        switch biometricType {
        case .faceID: return "Face ID"
        case .touchID: return "Touch ID"
        default: return "Biometrics"
        }
    }
    
    /// Authenticates the user using biometrics.
    func authenticateUser() {
        guard biometricType != .none else {
            self.errorMessage = "Biometric authentication is not available on this device."
            return
        }
        
        let reason = "To enable \(biometricName) for quick and secure access."
        
        context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason) { success, authenticationError in
            Task { @MainActor in
                if success {
                    self.isAuthenticationSuccessful = true
                    // Only proceed to enable if authentication is successful
                    await self.setBiometricPreference(isEnabled: true)
                } else {
                    // Handle authentication failure (e.g., user cancelled, too many attempts)
                    self.errorMessage = "Authentication failed. Please try again or use your passcode."
                    if let error = authenticationError as? LAError {
                        print("Authentication Error: \(error.localizedDescription)")
                    }
                }
            }
        }
    }
    
    // MARK: API and State Management
    
    /// Toggles the biometric preference and syncs with the API and local cache.
    func setBiometricPreference(isEnabled: Bool) async {
        guard !isLoading else { return }
        
        isLoading = true
        errorMessage = nil
        
        do {
            let success = try await api.registerBiometricPreference(isEnabled: isEnabled)
            if success {
                self.isBiometricEnabled = isEnabled
                api.saveBiometricSettingToCache(isEnabled: isEnabled) // Update local cache
            } else {
                // Revert state if API call fails but no error is thrown
                self.errorMessage = "Failed to update preference on the server."
            }
        } catch let error as APIClient.APIError {
            self.errorMessage = switch error {
            case .networkError: "Network error. Please check your connection."
            case .serverError(let msg): "Server error: \(msg)"
            }
            // Revert the toggle state on failure
            self.isBiometricEnabled = !isEnabled
        } catch {
            self.errorMessage = "An unexpected error occurred: \(error.localizedDescription)"
            self.isBiometricEnabled = !isEnabled
        }
        
        isLoading = false
    }
    
    /// Action to perform when the user taps the main setup button.
    func setupButtonTapped() {
        if isBiometricEnabled {
            // If already enabled, the button might act as a "Done" or "Continue"
            print("Biometrics already enabled. Continuing...")
        } else {
            // Start the authentication process to enable biometrics
            authenticateUser()
        }
    }
    
    /// Action to perform when the user taps the skip button.
    func skipButtonTapped() async {
        // Explicitly disable biometrics if the user skips, and sync with API
        if isBiometricEnabled {
            await setBiometricPreference(isEnabled: false)
        }
        print("User skipped biometric setup. Navigating away...")
        // In a real app, this would trigger navigation to the next screen.
    }
}

// MARK: - 3. View

struct BiometricAuthView: View {
    
    @StateObject private var viewModel = BiometricAuthViewModel()
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationView {
            VStack(spacing: 30) {
                
                Spacer()
                
                // MARK: - Icon
                Image(systemName: viewModel.biometricType == .faceID ? "faceid" : "touchid")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 100, height: 100)
                    .foregroundColor(.blue)
                    .accessibilityLabel(Text("\(viewModel.biometricName) icon"))
                
                // MARK: - Title and Description
                VStack(spacing: 10) {
                    Text("Enable \(viewModel.biometricName)")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                        .accessibilityAddTraits(.isHeader)
                    
                    Text("Use your \(viewModel.biometricName) to quickly and securely log in and authorize transactions, including payments via Paystack, Flutterwave, and Interswitch.")
                        .font(.body)
                        .foregroundColor(.gray)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                }
                
                // MARK: - Status/Error Message
                if let errorMessage = viewModel.errorMessage {
                    Text(errorMessage)
                        .foregroundColor(.red)
                        .padding()
                        .background(Color.red.opacity(0.1))
                        .cornerRadius(8)
                        .accessibilityLiveRegion(.assertive)
                } else if viewModel.isBiometricEnabled {
                    Text("\(viewModel.biometricName) is now enabled!")
                        .foregroundColor(.green)
                        .padding()
                        .background(Color.green.opacity(0.1))
                        .cornerRadius(8)
                        .accessibilityLiveRegion(.assertive)
                }
                
                Spacer()
                
                // MARK: - Action Button
                Button {
                    viewModel.setupButtonTapped()
                } label: {
                    if viewModel.isLoading {
                        ProgressView()
                            .progressViewStyle(.circular)
                            .tint(.white)
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.blue)
                            .cornerRadius(10)
                    } else {
                        Text(viewModel.isBiometricEnabled ? "Continue to App" : "Set Up \(viewModel.biometricName)")
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.blue)
                            .foregroundColor(.white)
                            .cornerRadius(10)
                    }
                }
                .disabled(viewModel.isLoading || viewModel.biometricType == .none)
                .accessibilityLabel(Text(viewModel.isBiometricEnabled ? "Continue to the main application" : "Set up \(viewModel.biometricName)"))
                
                // MARK: - Skip Button
                Button {
                    Task { await viewModel.skipButtonTapped() }
                    dismiss() // Mock navigation away
                } label: {
                    Text("Skip for Now")
                        .font(.subheadline)
                        .foregroundColor(.gray)
                }
                .padding(.bottom, 20)
                .accessibilityLabel(Text("Skip biometric setup"))
            }
            .padding(.horizontal, 20)
            .navigationTitle("Security Setup")
            .navigationBarTitleDisplayMode(.inline)
            .onAppear {
                // Ensure capability is checked on view appearance
                viewModel.checkBiometricCapability()
            }
            .alert("Biometrics Unavailable", isPresented: .constant(viewModel.biometricType == .none && viewModel.errorMessage == nil)) {
                Button("OK") {
                    // Handle case where biometrics is not available
                    Task { await viewModel.skipButtonTapped() }
                    dismiss()
                }
            } message: {
                Text("Your device does not support Face ID or Touch ID, or it has not been configured. You can continue to use your passcode.")
            }
        }
        // Support for offline mode: The initial state is loaded from cache in the ViewModel init.
        // The view will display the cached state until a successful API call updates it.
    }
}

// MARK: - 4. Documentation

/*
 BiometricAuthView:
 
 This screen guides the user through setting up biometric authentication (Face ID or Touch ID) for the RemittanceApp.
 
 Features Implemented:
 - SwiftUI View and Layout: Clean, modern UI following HIG.
 - State Management: BiometricAuthViewModel (ObservableObject) manages all view state, loading, and errors.
 - Biometric Integration: Uses LocalAuthentication (LAContext) to check capability and perform authentication.
 - API Integration (Mock): APIClient simulates server communication for registering preferences.
 - Error/Loading States: Displays ProgressView during loading and clear error messages.
 - Navigation: Includes a "Continue" or "Skip" button for flow control (mocked with dismiss()).
 - Accessibility: Proper labels and traits are included for screen readers.
 - Offline Support: ViewModel initializes state from a local cache (UserDefaults mock).
 - Payment Gateway Integration (Mock): APIClient includes a placeholder for updating payment gateway settings (Paystack, Flutterwave, Interswitch) upon successful biometric setup.
 
 Dependencies:
 - SwiftUI
 - LocalAuthentication
 */

// MARK: - 5. Preview

#Preview {
    BiometricAuthView()
}

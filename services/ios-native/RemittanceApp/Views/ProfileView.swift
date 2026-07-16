//
// ProfileView.swift
// RemittanceApp
//
// Created by Manus AI on 2025-11-03.
//

import SwiftUI
import Combine
import LocalAuthentication // For Biometric Authentication

// MARK: - 1. Data Models

/// Represents the user's profile data.
struct UserProfile: Identifiable, Codable {
    let id: String
    var firstName: String
    var lastName: String
    var email: String
    var phoneNumber: String
    var verificationStatus: VerificationStatus
    var avatarURL: URL?
    var isBiometricsEnabled: Bool
    var preferredPaymentGateway: PaymentGateway
    
    static var mock: UserProfile {
        UserProfile(
            id: "user-12345",
            firstName: "Aisha",
            lastName: "Bello",
            email: "aisha.bello@example.com",
            phoneNumber: "+234 801 234 5678",
            verificationStatus: .verified,
            avatarURL: URL(string: "https://i.pravatar.cc/150?img=47"),
            isBiometricsEnabled: true,
            preferredPaymentGateway: .paystack
        )
    }
}

/// Represents the verification status of the user.
enum VerificationStatus: String, Codable {
    case unverified = "Unverified"
    case pending = "Pending Review"
    case verified = "Verified"
    
    var color: Color {
        switch self {
        case .unverified: return .red
        case .pending: return .orange
        case .verified: return .green
        }
    }
}

/// Represents the supported payment gateways.
enum PaymentGateway: String, Codable, CaseIterable {
    case paystack = "Paystack"
    case flutterwave = "Flutterwave"
    case interswitch = "Interswitch"
}

// MARK: - 2. API Client (Mocked)

/// A mock API client for fetching and updating user data.
class APIClient {
    enum APIError: Error, LocalizedError {
        case networkError
        case invalidResponse
        case serverError(String)
        
        var errorDescription: String? {
            switch self {
            case .networkError: return "A network connection error occurred."
            case .invalidResponse: return "The server returned an invalid response."
            case .serverError(let message): return message
            }
        }
    }
    
    /// Simulates fetching the user profile from a remote server.
    func fetchUserProfile() -> AnyPublisher<UserProfile, APIError> {
        Future { promise in
            // Simulate network delay
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                // Simulate success
                promise(.success(UserProfile.mock))
                
                // To simulate an error, uncomment the line below:
                // promise(.failure(.serverError("Failed to load profile data.")))
            }
        }
        .eraseToAnyPublisher()
    }
    
    /// Simulates updating the user profile.
    func updateProfile(_ profile: UserProfile) -> AnyPublisher<UserProfile, APIError> {
        Future { promise in
            // Simulate network delay
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                // Simulate success
                promise(.success(profile))
            }
        }
        .eraseToAnyPublisher()
    }
}

// MARK: - 3. View Model

/// Manages the state and business logic for the ProfileView.
final class ProfileViewModel: ObservableObject {
    
    // MARK: State Properties
    
    @Published var profile: UserProfile?
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var isEditing: Bool = false
    @Published var isBiometricAuthSuccessful: Bool = false
    
    private var apiClient = APIClient()
    private var cancellables = Set<AnyCancellable>()
    
    // MARK: Initialization
    
    init() {
        // Load cached data on initialization (Offline Mode Support)
        loadCachedProfile()
        // Fetch fresh data
        fetchProfile()
    }
    
    // MARK: API Interaction
    
    /// Fetches the user profile from the API.
    func fetchProfile() {
        isLoading = true
        errorMessage = nil
        
        apiClient.fetchUserProfile()
            .receive(on: DispatchQueue.main)
            .sink { [weak self] completion in
                self?.isLoading = false
                switch completion {
                case .failure(let error):
                    // Only show error if we don't have a cached profile
                    if self?.profile == nil {
                        self?.errorMessage = error.localizedDescription
                    }
                    print("Error fetching profile: \(error.localizedDescription)")
                case .finished:
                    break
                }
            } receiveValue: { [weak self] fetchedProfile in
                self?.profile = fetchedProfile
                self?.cacheProfile(fetchedProfile) // Cache the fresh data
            }
            .store(in: &cancellables)
    }
    
    /// Saves the edited profile to the API.
    func saveProfile(updatedProfile: UserProfile) {
        isLoading = true
        errorMessage = nil
        
        apiClient.updateProfile(updatedProfile)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] completion in
                self?.isLoading = false
                switch completion {
                case .failure(let error):
                    self?.errorMessage = "Save failed: \(error.localizedDescription)"
                case .finished:
                    self?.isEditing = false
                }
            } receiveValue: { [weak self] savedProfile in
                self?.profile = savedProfile
                self?.cacheProfile(savedProfile)
            }
            .store(in: &cancellables)
    }
    
    // MARK: Offline Mode / Caching
    
    private func cacheProfile(_ profile: UserProfile) {
        if let encoded = try? JSONEncoder().encode(profile) {
            UserDefaults.standard.set(encoded, forKey: "cachedUserProfile")
        }
    }
    
    private func loadCachedProfile() {
        if let savedData = UserDefaults.standard.data(forKey: "cachedUserProfile"),
           let decodedProfile = try? JSONDecoder().decode(UserProfile.self, from: savedData) {
            self.profile = decodedProfile
            print("Loaded profile from cache.")
        }
    }
    
    // MARK: Biometric Authentication
    
    /// Attempts to authenticate the user using biometrics (Face ID/Touch ID).
    func authenticateWithBiometrics() {
        let context = LAContext()
        var error: NSError?
        
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            // Biometrics not available or not configured
            self.errorMessage = "Biometric authentication is not available or configured."
            self.isBiometricAuthSuccessful = false
            return
        }
        
        let reason = "To access sensitive profile settings."
        
        context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason) { success, authenticationError in
            DispatchQueue.main.async {
                if success {
                    self.isBiometricAuthSuccessful = true
                } else {
                    self.errorMessage = "Biometric authentication failed: \(authenticationError?.localizedDescription ?? "Unknown error")"
                    self.isBiometricAuthSuccessful = false
                }
            }
        }
    }
    
    // MARK: Validation Placeholder
    
    /// Placeholder for form validation logic.
    func isProfileValid(profile: UserProfile) -> Bool {
        // Simple validation: check if first name and email are not empty
        return !profile.firstName.isEmpty && profile.email.contains("@")
    }
}

// MARK: - 4. Main View

struct ProfileView: View {
    
    @StateObject var viewModel = ProfileViewModel()
    
    var body: some View {
        NavigationView {
            Group {
                if viewModel.isLoading && viewModel.profile == nil {
                    loadingView
                } else if let errorMessage = viewModel.errorMessage, viewModel.profile == nil {
                    errorView(message: errorMessage)
                } else if let profile = viewModel.profile {
                    profileContent(profile: profile)
                } else {
                    // Should not happen, but as a fallback
                    Text("No profile data available.")
                }
            }
            .navigationTitle("My Profile")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    if viewModel.profile != nil {
                        Button(viewModel.isEditing ? "Done" : "Edit") {
                            if viewModel.isEditing {
                                // Save logic will be handled in the EditProfileView
                                viewModel.isEditing = false
                            } else {
                                viewModel.isEditing = true
                            }
                        }
                        .accessibilityLabel(viewModel.isEditing ? "Save changes" : "Edit profile")
                    }
                }
            }
            .sheet(isPresented: $viewModel.isEditing) {
                if let profile = viewModel.profile {
                    EditProfileView(
                        viewModel: viewModel,
                        draftProfile: profile
                    )
                }
            }
        }
        .onAppear {
            // If we don't have a profile (even cached), try to fetch again
            if viewModel.profile == nil {
                viewModel.fetchProfile()
            }
        }
    }
    
    // MARK: Subviews
    
    private var loadingView: some View {
        VStack {
            ProgressView()
                .progressViewStyle(.circular)
                .accessibilityLabel("Loading profile data")
            Text("Loading Profile...")
                .foregroundColor(.secondary)
        }
    }
    
    private func errorView(message: String) -> some View {
        VStack(spacing: 10) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundColor(.red)
                .font(.largeTitle)
                .accessibilityHidden(true)
            Text("Error")
                .font(.headline)
            Text(message)
                .font(.subheadline)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
                .accessibilityLabel("Error loading profile: \(message)")
            
            Button("Retry") {
                viewModel.fetchProfile()
            }
            .buttonStyle(.borderedProminent)
            .padding(.top)
        }
    }
    
    @ViewBuilder
    private func profileContent(profile: UserProfile) -> some View {
        List {
            // MARK: Avatar and Basic Info
            Section {
                HStack {
                    // Avatar
                    AsyncImage(url: profile.avatarURL) { phase in
                        if let image = phase.image {
                            image
                                .resizable()
                                .aspectRatio(contentMode: .fill)
                        } else if phase.error != nil {
                            Image(systemName: "person.circle.fill")
                                .resizable()
                                .foregroundColor(.gray)
                        } else {
                            ProgressView()
                        }
                    }
                    .frame(width: 80, height: 80)
                    .clipShape(Circle())
                    .accessibilityLabel("User profile avatar")
                    
                    VStack(alignment: .leading) {
                        Text("\(profile.firstName) \(profile.lastName)")
                            .font(.title2)
                            .fontWeight(.bold)
                            .accessibilityLabel("User name: \(profile.firstName) \(profile.lastName)")
                        
                        HStack {
                            Text(profile.verificationStatus.rawValue)
                                .font(.caption)
                                .foregroundColor(.white)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(profile.verificationStatus.color)
                                .clipShape(Capsule())
                                .accessibilityLabel("Verification status: \(profile.verificationStatus.rawValue)")
                            
                            if profile.verificationStatus == .unverified {
                                Button("Verify Now") {
                                    // Action to navigate to verification flow
                                }
                                .font(.caption)
                            }
                        }
                    }
                    .padding(.leading)
                }
            }
            .listRowBackground(Color.clear)
            
            // MARK: Personal Information
            Section("Personal Information") {
                ProfileDetailRow(label: "Email", value: profile.email, icon: "envelope.fill")
                ProfileDetailRow(label: "Phone", value: profile.phoneNumber, icon: "phone.fill")
            }
            
            // MARK: Security and Settings
            Section("Security & Preferences") {
                // Biometric Authentication Toggle
                Toggle(isOn: $viewModel.profile.unwrap(default: profile).isBiometricsEnabled) {
                    Label("Biometric Login", systemImage: "faceid")
                }
                .onChange(of: viewModel.profile?.isBiometricsEnabled) { newValue in
                    // Only prompt for auth if the user is trying to enable it
                    if newValue == true && !viewModel.isBiometricAuthSuccessful {
                        viewModel.authenticateWithBiometrics()
                    }
                }
                .disabled(viewModel.isLoading)
                .accessibilityValue(profile.isBiometricsEnabled ? "Enabled" : "Disabled")
                
                // Payment Gateway Integration
                NavigationLink(destination: PaymentGatewaySettingsView(
                    preferredGateway: $viewModel.profile.unwrap(default: profile).preferredPaymentGateway
                )) {
                    HStack {
                        Label("Preferred Gateway", systemImage: "creditcard.fill")
                        Spacer()
                        Text(profile.preferredPaymentGateway.rawValue)
                            .foregroundColor(.secondary)
                    }
                }
                .accessibilityLabel("Preferred payment gateway setting, currently \(profile.preferredPaymentGateway.rawValue)")
                
                // Sensitive Action (requires Biometric Auth)
                Button {
                    if viewModel.isBiometricAuthSuccessful {
                        // Perform sensitive action
                        print("Sensitive action performed.")
                    } else {
                        viewModel.authenticateWithBiometrics()
                    }
                } label: {
                    HStack {
                        Label("Access Sensitive Data", systemImage: "lock.fill")
                        Spacer()
                        Image(systemName: viewModel.isBiometricAuthSuccessful ? "checkmark.circle.fill" : "chevron.right")
                            .foregroundColor(viewModel.isBiometricAuthSuccessful ? .green : .secondary)
                    }
                }
                .disabled(viewModel.isLoading)
                .accessibilityHint("Requires Face ID or Touch ID to proceed.")
            }
            
            // MARK: Logout
            Section {
                Button(role: .destructive) {
                    // Logout action
                } label: {
                    HStack {
                        Text("Log Out")
                        Spacer()
                        Image(systemName: "arrow.right.square.fill")
                    }
                }
                .accessibilityLabel("Log out of the application")
            }
        }
        .refreshable {
            viewModel.fetchProfile()
        }
    }
}

// MARK: - 5. Supporting Views

/// A reusable row for displaying profile details.
struct ProfileDetailRow: View {
    let label: String
    let value: String
    let icon: String
    
    var body: some View {
        HStack {
            Label(label, systemImage: icon)
            Spacer()
            Text(value)
                .foregroundColor(.secondary)
                .accessibilityLabel("\(label): \(value)")
        }
    }
}

/// A view for editing the user profile.
struct EditProfileView: View {
    @ObservedObject var viewModel: ProfileViewModel
    @State var draftProfile: UserProfile
    
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationView {
            Form {
                Section("Basic Information") {
                    TextField("First Name", text: $draftProfile.firstName)
                        .textContentType(.givenName)
                        .autocorrectionDisabled()
                    TextField("Last Name", text: $draftProfile.lastName)
                        .textContentType(.familyName)
                        .autocorrectionDisabled()
                    TextField("Email", text: $draftProfile.email)
                        .textContentType(.emailAddress)
                        .keyboardType(.emailAddress)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                }
                
                Section("Contact") {
                    TextField("Phone Number", text: $draftProfile.phoneNumber)
                        .textContentType(.telephoneNumber)
                        .keyboardType(.phonePad)
                }
                
                // Placeholder for Form Validation
                if !viewModel.isProfileValid(profile: draftProfile) {
                    Text("Please ensure your first name is not empty and your email is valid.")
                        .foregroundColor(.red)
                        .font(.caption)
                }
            }
            .navigationTitle("Edit Profile")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Save") {
                        viewModel.saveProfile(updatedProfile: draftProfile)
                        dismiss()
                    }
                    .disabled(!viewModel.isProfileValid(profile: draftProfile) || viewModel.isLoading)
                }
            }
            .overlay {
                if viewModel.isLoading {
                    Color.black.opacity(0.4)
                        .ignoresSafeArea()
                    ProgressView("Saving...")
                        .padding()
                        .background(Color.white)
                        .cornerRadius(10)
                }
            }
        }
    }
}

/// A view for managing payment gateway settings.
struct PaymentGatewaySettingsView: View {
    @Binding var preferredGateway: PaymentGateway
    
    var body: some View {
        List {
            Section("Select Preferred Payment Gateway") {
                Picker("Gateway", selection: $preferredGateway) {
                    ForEach(PaymentGateway.allCases, id: \.self) { gateway in
                        Text(gateway.rawValue).tag(gateway)
                    }
                }
                .pickerStyle(.inline)
            }
            
            Section("Gateway Details") {
                Text("Configuration for \(preferredGateway.rawValue) would go here.")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                // Placeholder for integration details (e.g., API keys, account status)
                Button("Manage \(preferredGateway.rawValue) Account") {
                    // Action to link to external gateway management
                }
            }
        }
        .navigationTitle("Payment Gateway")
    }
}

// MARK: - 6. Utility Extensions

extension Optional where Wrapped == UserProfile {
    /// Utility to safely unwrap the profile for use in bindings, falling back to a default.
    func unwrap(default defaultValue: UserProfile) -> UserProfile {
        self ?? defaultValue
    }
}

// MARK: - Preview

#Preview {
    ProfileView()
}

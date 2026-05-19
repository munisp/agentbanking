//
// CDPRegistrationService.swift
// 54Link Agency Banking
//
// This file contains the API service and data models for the Customer Data Platform (CDP)
// email OTP registration flow.
//

import Foundation
import Combine

// MARK: - 1. Data Models

/// Represents the request body to start the registration process (request OTP).
struct StartRegistrationRequest: Codable {
    let email: String
}

/// Represents the response body after successfully starting registration.
struct StartRegistrationResponse: Codable {
    /// A unique identifier for the registration session, used in the verification step.
    let registrationId: String
    /// A message confirming the OTP has been sent.
    let message: String
}

/// Represents the request body to verify the OTP and complete registration.
struct VerifyOTPRequest: Codable {
    let registrationId: String
    let otp: String
    let password: String
    let firstName: String
    let lastName: String
}

/// Represents the response body after successful OTP verification and registration.
struct VerifyOTPResponse: Codable {
    /// The authentication token for the newly registered user.
    let authToken: String
    /// The ID of the newly created user.
    let userId: String
}

/// Represents a generic error response from the API.
struct APIErrorResponse: Codable, LocalizedError {
    let code: String
    let message: String
    
    var errorDescription: String? {
        return message
    }
}

// MARK: - 2. API Service

/// A service class to handle all network operations related to CDP registration.
final class CDPRegistrationService {
    
    // MARK: - Configuration
    
    /// The base URL for the CDP API.
    private let baseURL = URL(string: "https://api.nigerianremittance.com/v1/cdp")!
    
    /// A shared URLSession for network requests.
    private let session: URLSession
    
    init(session: URLSession = .shared) {
        self.session = session
    }
    
    // MARK: - API Endpoints
    
    /// Hypothetical endpoint for starting registration and requesting an OTP.
    private func startRegistrationURL() -> URL {
        return baseURL.appendingPathComponent("/register/start")
    }
    
    /// Hypothetical endpoint for verifying the OTP and completing registration.
    private func verifyOTPURL() -> URL {
        return baseURL.appendingPathComponent("/register/verify")
    }
    
    // MARK: - Public Methods
    
    /**
     Initiates the registration process by sending the user's email and requesting an OTP.
     
     - Parameter email: The user's email address.
     - Returns: A publisher that emits a `StartRegistrationResponse` on success or an `Error` on failure.
     */
    func startRegistration(email: String) -> AnyPublisher<StartRegistrationResponse, Error> {
        let requestBody = StartRegistrationRequest(email: email)
        
        var request = URLRequest(url: startRegistrationURL())
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        do {
            request.httpBody = try JSONEncoder().encode(requestBody)
        } catch {
            return Fail(error: error).eraseToAnyPublisher()
        }
        
        return execute(request: request)
    }
    
    /**
     Verifies the OTP and completes the user registration.
     
     - Parameter request: The `VerifyOTPRequest` containing registration details.
     - Returns: A publisher that emits a `VerifyOTPResponse` on success or an `Error` on failure.
     */
    func verifyOTP(requestBody: VerifyOTPRequest) -> AnyPublisher<VerifyOTPResponse, Error> {
        var request = URLRequest(url: verifyOTPURL())
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        do {
            request.httpBody = try JSONEncoder().encode(requestBody)
        } catch {
            return Fail(error: error).eraseToAnyPublisher()
        }
        
        return execute(request: request)
    }
    
    // MARK: - Private Helper
    
    /// Generic function to execute a URLRequest and decode the response.
    private func execute<T: Decodable>(request: URLRequest) -> AnyPublisher<T, Error> {
        return session.dataTaskPublisher(for: request)
            .tryMap { data, response in
                guard let httpResponse = response as? HTTPURLResponse else {
                    throw URLError(.badServerResponse)
                }
                
                // Check for success status codes (200-299)
                if (200...299).contains(httpResponse.statusCode) {
                    return data
                }
                
                // Handle API error responses (e.g., 400, 401, 500)
                if let apiError = try? JSONDecoder().decode(APIErrorResponse.self, from: data) {
                    throw apiError
                }
                
                // Fallback for unhandled status codes
                throw URLError(.init(rawValue: httpResponse.statusCode))
            }
            .decode(type: T.self, decoder: JSONDecoder())
            .eraseToAnyPublisher()
    }
}

// MARK: - RegisterView.swift (SwiftUI View and ViewModel)

//
// RegisterView.swift
// 54Link Agency Banking
//
// This file contains the SwiftUI view and view model for the CDP email OTP registration flow.
// It handles state management, input validation, API integration, and error handling.
//

import SwiftUI
import Combine

// MARK: - 1. View Model

/// Manages the state and business logic for the registration flow.
final class RegisterViewModel: ObservableObject {
    
    // MARK: - State Properties
    
    @Published var email: String = ""
    @Published var otp: String = ""
    @Published var password: String = ""
    @Published var confirmPassword: String = ""
    @Published var firstName: String = ""
    @Published var lastName: String = ""
    
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? {
        didSet {
            // Automatically clear error message after a short delay
            if errorMessage != nil {
                DispatchQueue.main.asyncAfter(deadline: .now() + 5) {
                    self.errorMessage = nil
                }
            }
        }
    }
    @Published var isRegistrationStarted: Bool = false
    @Published var isRegistrationComplete: Bool = false
    
    // MARK: - Internal Properties
    
    private let service: CDPRegistrationService
    private var cancellables = Set<AnyCancellable>()
    private var registrationId: String?
    
    // MARK: - Validation Properties
    
    var isEmailValid: Bool {
        // Simple email regex for basic validation
        let emailRegex = "[A-Z0-9a-z._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,64}"
        let emailPredicate = NSPredicate(format: "SELF MATCHES %@", emailRegex)
        return emailPredicate.evaluate(with: email)
    }
    
    var isPasswordValid: Bool {
        // Password must be at least 8 characters, contain an uppercase letter, a lowercase letter, and a number.
        let passwordRegex = "^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d)[a-zA-Z\\d]{8,}$"
        let passwordPredicate = NSPredicate(format: "SELF MATCHES %@", passwordRegex)
        return passwordPredicate.evaluate(with: password)
    }
    
    var passwordsMatch: Bool {
        return password == confirmPassword && !password.isEmpty
    }
    
    var isStartRegistrationFormValid: Bool {
        return isEmailValid
    }
    
    var isVerifyOTPFormValid: Bool {
        return !otp.isEmpty && isPasswordValid && passwordsMatch && !firstName.isEmpty && !lastName.isEmpty
    }
    
    // MARK: - Initialization
    
    init(service: CDPRegistrationService = CDPRegistrationService()) {
        self.service = service
    }
    
    // MARK: - Actions
    
    /// Step 1: Requests an OTP to be sent to the provided email.
    func startRegistrationFlow() {
        guard isStartRegistrationFormValid else {
            errorMessage = "Please enter a valid email address."
            return
        }
        
        isLoading = true
        errorMessage = nil
        
        service.startRegistration(email: email)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] completion in
                self?.isLoading = false
                switch completion {
                case .failure(let error):
                    self?.errorMessage = "Failed to request OTP: \(error.localizedDescription)"
                case .finished:
                    break
                }
            } receiveValue: { [weak self] response in
                self?.registrationId = response.registrationId
                self?.isRegistrationStarted = true
                self?.errorMessage = "OTP sent to \(self?.email ?? "your email"). Please check your inbox."
            }
            .store(in: &cancellables)
    }
    
    /// Step 2: Verifies the OTP and completes the user registration.
    func verifyOTPAndRegister() {
        guard isVerifyOTPFormValid, let id = registrationId else {
            errorMessage = "Please ensure all fields are valid and passwords match."
            return
        }
        
        isLoading = true
        errorMessage = nil
        
        let requestBody = VerifyOTPRequest(
            registrationId: id,
            otp: otp,
            password: password,
            firstName: firstName,
            lastName: lastName
        )
        
        service.verifyOTP(requestBody: requestBody)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] completion in
                self?.isLoading = false
                switch completion {
                case .failure(let error):
                    self?.errorMessage = "Registration failed: \(error.localizedDescription)"
                case .finished:
                    break
                }
            } receiveValue: { [weak self] response in
                // In a real app, you would save the authToken and navigate to the main app screen.
                print("Registration successful! Auth Token: \(response.authToken)")
                self?.isRegistrationComplete = true
                self?.errorMessage = nil // Clear any previous success message
            }
            .store(in: &cancellables)
    }
    
    /// Resets the flow to the initial state.
    func resetFlow() {
        email = ""
        otp = ""
        password = ""
        confirmPassword = ""
        firstName = ""
        lastName = ""
        isLoading = false
        errorMessage = nil
        isRegistrationStarted = false
        isRegistrationComplete = false
        registrationId = nil
        cancellables.removeAll()
    }
}

// MARK: - 2. SwiftUI View

struct RegisterView: View {
    
    @StateObject private var viewModel = RegisterViewModel()
    
    var body: some View {
        NavigationView {
            VStack {
                if viewModel.isRegistrationComplete {
                    successView
                } else if viewModel.isRegistrationStarted {
                    verifyOTPForm
                } else {
                    startRegistrationForm
                }
            }
            .padding()
            .navigationTitle("CDP Registration")
            .alert(item: $viewModel.errorMessage) { message in
                Alert(title: Text("Error"), message: Text(message), dismissButton: .default(Text("OK")))
            }
            .overlay(
                Group {
                    if viewModel.isLoading {
                        ProgressView("Processing...")
                            .padding()
                            .background(Color.black.opacity(0.7))
                            .foregroundColor(.white)
                            .cornerRadius(10)
                    }
                }
            )
        }
    }
    
    // MARK: - Subviews
    
    /// View for the initial step: collecting email and requesting OTP.
    private var startRegistrationForm: some View {
        VStack(spacing: 20) {
            Text("Step 1: Enter your email to start registration.")
                .font(.headline)
            
            TextField("Email Address", text: $viewModel.email)
                .keyboardType(.emailAddress)
                .autocapitalization(.none)
                .textFieldStyle(RoundedBorderTextFieldStyle())
                .border(viewModel.email.isEmpty || viewModel.isEmailValid ? Color.gray : Color.red)
            
            if !viewModel.email.isEmpty && !viewModel.isEmailValid {
                Text("Please enter a valid email address.")
                    .foregroundColor(.red)
                    .font(.caption)
            }
            
            Button(action: viewModel.startRegistrationFlow) {
                Text("Request OTP")
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(viewModel.isStartRegistrationFormValid ? Color.blue : Color.gray)
                    .foregroundColor(.white)
                    .cornerRadius(8)
            }
            .disabled(!viewModel.isStartRegistrationFormValid || viewModel.isLoading)
        }
    }
    
    /// View for the second step: collecting OTP, password, and user details.
    private var verifyOTPForm: some View {
        ScrollView {
            VStack(spacing: 20) {
                Text("Step 2: Verify OTP and complete your profile.")
                    .font(.headline)
                
                // OTP Field
                SecureField("OTP (One-Time Password)", text: $viewModel.otp)
                    .keyboardType(.numberPad)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .border(viewModel.otp.isEmpty ? Color.gray : Color.green)
                
                // First Name
                TextField("First Name", text: $viewModel.firstName)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .border(viewModel.firstName.isEmpty ? Color.red : Color.green)
                
                // Last Name
                TextField("Last Name", text: $viewModel.lastName)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .border(viewModel.lastName.isEmpty ? Color.red : Color.green)
                
                // Password Field
                SecureField("Password", text: $viewModel.password)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .border(viewModel.password.isEmpty || viewModel.isPasswordValid ? Color.gray : Color.red)
                
                if !viewModel.password.isEmpty && !viewModel.isPasswordValid {
                    Text("Password must be 8+ chars, with uppercase, lowercase, and a number.")
                        .foregroundColor(.red)
                        .font(.caption)
                }
                
                // Confirm Password Field
                SecureField("Confirm Password", text: $viewModel.confirmPassword)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .border(viewModel.confirmPassword.isEmpty || viewModel.passwordsMatch ? Color.gray : Color.red)
                
                if !viewModel.confirmPassword.isEmpty && !viewModel.passwordsMatch {
                    Text("Passwords do not match.")
                        .foregroundColor(.red)
                        .font(.caption)
                }
                
                Button(action: viewModel.verifyOTPAndRegister) {
                    Text("Complete Registration")
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(viewModel.isVerifyOTPFormValid ? Color.green : Color.gray)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }
                .disabled(!viewModel.isVerifyOTPFormValid || viewModel.isLoading)
                
                Button("Start Over") {
                    viewModel.resetFlow()
                }
                .foregroundColor(.blue)
                .padding(.top, 10)
            }
        }
    }
    
    /// View shown upon successful registration.
    private var successView: some View {
        VStack(spacing: 20) {
            Image(systemName: "checkmark.circle.fill")
                .resizable()
                .frame(width: 100, height: 100)
                .foregroundColor(.green)
            
            Text("Registration Successful!")
                .font(.largeTitle)
                .fontWeight(.bold)
            
            Text("Welcome to 54Link Agency Banking. You can now log in with your new credentials.")
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
            
            Button("Go to Login") {
                // In a real app, this would trigger navigation to the LoginView
                print("Navigating to Login...")
                viewModel.resetFlow() // Resetting for demonstration
            }
            .padding()
            .background(Color.blue)
            .foregroundColor(.white)
            .cornerRadius(8)
        }
        .padding()
    }
}

// MARK: - 3. Preview (For Xcode)

// To run this in a real Xcode project, you would need to define a mock service
// for the preview to work without a live network connection.
/*
struct RegisterView_Previews: PreviewProvider {
    static var previews: some View {
        RegisterView()
    }
}
*/
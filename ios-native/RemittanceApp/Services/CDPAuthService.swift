//
// CDPAuthService.swift
// 54Link Agency Banking
//
// Created by Manus AI on 2025-11-05.
// Copyright © 2025 54Link Agency Banking. All rights reserved.
//

import Foundation

// MARK: - API Endpoints and Configuration

/// A structure to hold configuration details for the CDP API.
struct CDPAPIConfig {
    static let baseURL = "https://api.nigerianremittance.com/cdp/v1"
    
    // Authentication Endpoints
    static let requestOTPEndpoint = baseURL + "/auth/otp/request"
    static let verifyOTPEndpoint = baseURL + "/auth/otp/verify"
    
    // Wallet and Session Endpoints
    static let createWalletEndpoint = baseURL + "/wallet/create"
    static let refreshSessionEndpoint = baseURL + "/session/refresh"
    static let logoutEndpoint = baseURL + "/session/logout"
}

// MARK: - Data Models

/// Represents the response from a successful OTP request.
struct OTPRequestResponse: Decodable {
    let success: Bool
    let message: String
    let otpReference: String // A reference ID to be used for OTP verification
}

/// Represents the response from a successful OTP verification and login.
struct LoginResponse: Decodable {
    let success: Bool
    let message: String
    let accessToken: String
    let refreshToken: String
    let userDidCreateWallet: Bool // Indicates if a wallet was created during this process
}

/// Represents the response from a successful wallet creation.
struct WalletCreationResponse: Decodable {
    let success: Bool
    let message: String
    let walletId: String
}

/// Represents a standardized error structure for API calls.
struct APIError: Error, Decodable {
    let code: Int
    let message: String
    
    var localizedDescription: String {
        return "Error \(code): \(message)"
    }
}

// MARK: - Service Protocol

/// Protocol defining the contract for the CDP Authentication Service.
protocol CDPAuthServiceProtocol {
    /// Requests an OTP to be sent to the provided email address.
    /// - Parameters:
    ///   - email: The user's email address.
    /// - Returns: The OTP reference string needed for verification.
    func requestOTP(email: String) async throws -> String
    
    /// Verifies the OTP and completes the login process.
    /// - Parameters:
    ///   - otpReference: The reference ID received from `requestOTP`.
    ///   - otp: The 6-digit OTP provided by the user.
    /// - Returns: The login response containing tokens and wallet status.
    func verifyOTP(otpReference: String, otp: String) async throws -> LoginResponse
    
    /// Creates a new wallet for the authenticated user.
    /// - Returns: The ID of the newly created wallet.
    func createWallet() async throws -> String
    
    /// Refreshes the user's session using the refresh token.
    /// - Returns: The new access token.
    func refreshSession() async throws -> String
    
    /// Logs out the user and invalidates the session.
    func logout() async throws
    
    /// Checks if the user is currently authenticated.
    var isAuthenticated: Bool { get }
}

// MARK: - Main Service Implementation

/// A production-ready service class for handling all CDP authentication and session management.
final class CDPAuthService: CDPAuthServiceProtocol {
    
    // MARK: - Properties
    
    /// A simple in-memory store for session tokens. In a real app, this would use Keychain.
    private var accessToken: String?
    private var refreshToken: String?
    
    /// The shared URLSession for making network requests.
    private let urlSession: URLSession
    
    /// Initializes the service with a custom URLSession (for testing) or the default shared session.
    init(urlSession: URLSession = .shared) {
        self.urlSession = urlSession
    }
    
    /// Checks if the user is currently authenticated by checking for an access token.
    var isAuthenticated: Bool {
        return accessToken != nil
    }
    
    // MARK: - Helper Methods
    
    /// Performs a generic network request and decodes the response.
    /// - Parameters:
    ///   - url: The URL for the request.
    ///   - method: The HTTP method (e.g., "POST").
    ///   - body: Optional data to be sent in the request body.
    ///   - token: Optional access token for authorization.
    /// - Returns: The decoded response object.
    private func performRequest<T: Decodable>(url: URL, method: String, body: [String: Any]? = nil, token: String? = nil) async throws -> T {
        
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Add Authorization header if a token is provided
        if let token = token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        // Add request body
        if let body = body {
            request.httpBody = try JSONSerialization.data(withJSONObject: body, options: [])
        }
        
        let (data, response) = try await urlSession.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        
        // Handle successful response (200-299)
        if (200...299).contains(httpResponse.statusCode) {
            do {
                let decoder = JSONDecoder()
                // Use keyDecodingStrategy to convert snake_case from API to camelCase in Swift
                decoder.keyDecodingStrategy = .convertFromSnakeCase
                return try decoder.decode(T.self, from: data)
            } catch {
                // Handle decoding errors
                print("Decoding Error: \(error)")
                throw error
            }
        } else {
            // Handle API errors (4xx, 5xx)
            do {
                let apiError = try JSONDecoder().decode(APIError.self, from: data)
                throw apiError
            } catch {
                // If API error decoding fails, throw a generic error
                throw URLError(.init(rawValue: httpResponse.statusCode), userInfo: [NSLocalizedDescriptionKey: "Server responded with status code \(httpResponse.statusCode)"])
            }
        }
    }
    
    // MARK: - Authentication Flow
    
    /// Requests an OTP for the given email.
    /// - Throws: `APIError` or `URLError` if the request fails.
    func requestOTP(email: String) async throws -> String {
        // 1. Input Validation
        guard isValidEmail(email) else {
            throw NSError(domain: "CDPAuthService", code: 1001, userInfo: [NSLocalizedDescriptionKey: "Invalid email format."])
        }
        
        guard let url = URL(string: CDPAPIConfig.requestOTPEndpoint) else {
            throw URLError(.badURL)
        }
        
        let body: [String: Any] = ["email": email]
        
        // 2. Perform API Request
        let response: OTPRequestResponse = try await performRequest(url: url, method: "POST", body: body)
        
        // 3. Return OTP Reference
        return response.otpReference
    }
    
    /// Verifies the OTP and logs the user in.
    /// - Throws: `APIError` or `URLError` if the request fails.
    func verifyOTP(otpReference: String, otp: String) async throws -> LoginResponse {
        // 1. Input Validation
        guard !otpReference.isEmpty, otp.count == 6, CharacterSet.decimalDigits.isSuperset(of: CharacterSet(charactersIn: otp)) else {
            throw NSError(domain: "CDPAuthService", code: 1002, userInfo: [NSLocalizedDescriptionKey: "Invalid OTP or reference provided."])
        }
        
        guard let url = URL(string: CDPAPIConfig.verifyOTPEndpoint) else {
            throw URLError(.badURL)
        }
        
        let body: [String: Any] = [
            "otp_reference": otpReference,
            "otp": otp
        ]
        
        // 2. Perform API Request
        let response: LoginResponse = try await performRequest(url: url, method: "POST", body: body)
        
        // 3. Session Management: Store tokens securely (in a real app, use Keychain)
        self.accessToken = response.accessToken
        self.refreshToken = response.refreshToken
        
        return response
    }
    
    // MARK: - Wallet Creation
    
    /// Creates a new wallet for the currently authenticated user.
    /// - Throws: `APIError`, `URLError`, or a custom error if not authenticated.
    func createWallet() async throws -> String {
        // 1. Authentication Check
        guard let token = accessToken else {
            throw NSError(domain: "CDPAuthService", code: 1003, userInfo: [NSLocalizedDescriptionKey: "User not authenticated. Please log in first."])
        }
        
        guard let url = URL(string: CDPAPIConfig.createWalletEndpoint) else {
            throw URLError(.badURL)
        }
        
        // 2. Perform API Request with Authorization
        let response: WalletCreationResponse = try await performRequest(url: url, method: "POST", token: token)
        
        // 3. Return Wallet ID
        return response.walletId
    }
    
    // MARK: - Session Management
    
    /// Refreshes the access token using the stored refresh token.
    /// - Throws: `APIError`, `URLError`, or a custom error if no refresh token is available.
    func refreshSession() async throws -> String {
        // 1. Token Check
        guard let currentRefreshToken = refreshToken else {
            throw NSError(domain: "CDPAuthService", code: 1004, userInfo: [NSLocalizedDescriptionKey: "No refresh token available. User needs to re-authenticate."])
        }
        
        guard let url = URL(string: CDPAPIConfig.refreshSessionEndpoint) else {
            throw URLError(.badURL)
        }
        
        let body: [String: Any] = ["refresh_token": currentRefreshToken]
        
        // 2. Perform API Request
        let response: LoginResponse = try await performRequest(url: url, method: "POST", body: body)
        
        // 3. Update Session Tokens
        self.accessToken = response.accessToken
        self.refreshToken = response.refreshToken // Refresh token might also be rotated
        
        return response.accessToken
    }
    
    /// Clears all session tokens and effectively logs the user out.
    func logout() async throws {
        // In a real application, you would send a request to the backend to invalidate the refresh token.
        // For this implementation, we will simulate the backend call and then clear local state.
        
        guard let token = accessToken else {
            // Already logged out or never logged in, no action needed.
            return
        }
        
        guard let url = URL(string: CDPAPIConfig.logoutEndpoint) else {
            // Even if URL is bad, we must clear local state.
            clearLocalSession()
            throw URLError(.badURL)
        }
        
        do {
            // 1. Perform API Request to invalidate session
            // The response type is irrelevant for logout, we just check for success status code.
            let _: OTPRequestResponse = try await performRequest(url: url, method: "POST", token: token)
        } catch {
            // Log the error but proceed to clear local state, as the user expects to be logged out locally.
            print("Warning: Backend logout failed: \(error.localizedDescription). Clearing local session anyway.")
        }
        
        // 2. Clear Local Session
        clearLocalSession()
    }
    
    /// Internal method to clear the locally stored tokens.
    private func clearLocalSession() {
        self.accessToken = nil
        self.refreshToken = nil
        // In a real app, this would also clear Keychain entries.
    }
    
    // MARK: - Validation Utility
    
    /// Simple email validation using a regular expression.
    /// - Parameter email: The email string to validate.
    /// - Returns: `true` if the email is valid, `false` otherwise.
    private func isValidEmail(_ email: String) -> Bool {
        let emailRegex = "[A-Z0-9a-z._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,64}"
        let emailPredicate = NSPredicate(format:"SELF MATCHES %@", emailRegex)
        return emailPredicate.evaluate(with: email)
    }
}

// MARK: - Example Usage (Optional)

/*
// Example of how to use the service in a ViewModel or Controller:

class AuthViewModel: ObservableObject {
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var isAuthenticated = false
    
    private let authService = CDPAuthService()
    
    func handleLogin(email: String, otp: String) async {
        guard !isLoading else { return }
        isLoading = true
        errorMessage = nil
        
        do {
            // 1. Request OTP
            let otpReference = try await authService.requestOTP(email: email)
            print("OTP requested successfully. Reference: \(otpReference)")
            
            // (User enters OTP)
            
            // 2. Verify OTP and Log In
            let loginResponse = try await authService.verifyOTP(otpReference: otpReference, otp: otp)
            print("Login successful. Access Token: \(loginResponse.accessToken)")
            
            isAuthenticated = authService.isAuthenticated
            
            // 3. Conditional Wallet Creation
            if !loginResponse.userDidCreateWallet {
                let walletId = try await authService.createWallet()
                print("Wallet created successfully. ID: \(walletId)")
            }
            
        } catch let apiError as APIError {
            errorMessage = "API Error: \(apiError.message)"
        } catch {
            errorMessage = "An unexpected error occurred: \(error.localizedDescription)"
        }
        
        isLoading = false
    }
    
    func handleLogout() async {
        do {
            try await authService.logout()
            isAuthenticated = authService.isAuthenticated
            print("User logged out.")
        } catch {
            errorMessage = "Logout failed: \(error.localizedDescription)"
        }
    }
    
    func refreshSessionIfNeeded() async {
        guard !isLoading else { return }
        isLoading = true
        
        do {
            let newAccessToken = try await authService.refreshSession()
            print("Session refreshed. New Access Token: \(newAccessToken)")
        } catch {
            // Handle refresh failure, e.g., force user to log in again
            print("Session refresh failed: \(error.localizedDescription)")
            isAuthenticated = false
        }
        
        isLoading = false
    }
}
*/
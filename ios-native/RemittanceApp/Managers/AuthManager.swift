import Foundation
import SwiftUI

class AuthManager: ObservableObject {
    @Published var isAuthenticated = false
    @Published var currentUser: User?
    @Published var isLoading = false
    @Published var error: String?
    
    private let baseURL = "https://api.54link.ng"
    
    struct User: Codable {
        let id: String
        let email: String
        let firstName: String
        let lastName: String
        let phone: String
        let kycStatus: String
    }
    
    struct LoginResponse: Codable {
        let user: User
        let token: String
    }
    
    func login(email: String, password: String) async {
        await MainActor.run {
            isLoading = true
            error = nil
        }
        
        do {
            guard let url = URL(string: "\(baseURL)/api/auth/login") else {
                throw URLError(.badURL)
            }
            
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            
            let body = ["email": email, "password": password]
            request.httpBody = try JSONEncoder().encode(body)
            
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else {
                throw URLError(.badServerResponse)
            }
            
            let loginResponse = try JSONDecoder().decode(LoginResponse.self, from: data)
            
            await MainActor.run {
                self.currentUser = loginResponse.user
                self.isAuthenticated = true
                self.isLoading = false
                
                // Store token securely
                UserDefaults.standard.set(loginResponse.token, forKey: "authToken")
            }
        } catch {
            await MainActor.run {
                self.error = error.localizedDescription
                self.isLoading = false
            }
        }
    }
    
    func register(firstName: String, lastName: String, email: String, phone: String, password: String) async {
        await MainActor.run {
            isLoading = true
            error = nil
        }
        
        do {
            guard let url = URL(string: "\(baseURL)/api/auth/register") else {
                throw URLError(.badURL)
            }
            
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            
            let body: [String: String] = [
                "firstName": firstName,
                "lastName": lastName,
                "email": email,
                "phone": phone,
                "password": password
            ]
            request.httpBody = try JSONEncoder().encode(body)
            
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else {
                throw URLError(.badServerResponse)
            }
            
            let loginResponse = try JSONDecoder().decode(LoginResponse.self, from: data)
            
            await MainActor.run {
                self.currentUser = loginResponse.user
                self.isAuthenticated = true
                self.isLoading = false
                
                UserDefaults.standard.set(loginResponse.token, forKey: "authToken")
            }
        } catch {
            await MainActor.run {
                self.error = error.localizedDescription
                self.isLoading = false
            }
        }
    }
    
    func logout() {
        currentUser = nil
        isAuthenticated = false
        UserDefaults.standard.removeObject(forKey: "authToken")
    }
    
    func checkAuthStatus() {
        if let _ = UserDefaults.standard.string(forKey: "authToken") {
            isAuthenticated = true
        }
    }
}

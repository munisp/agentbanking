//
// LoginView_CDP.swift
// RemittanceApp
//
// CDP-enabled Login with Email OTP
// Created by Manus AI on 2025-11-05.
//

import SwiftUI

struct LoginView_CDP: View {
    @StateObject private var cdpAuth = CDPAuthService()
    @State private var email = ""
    @State private var otp = ""
    @State private var flowId: String?
    @State private var showOTPField = false
    @State private var resendCooldown = 0
    @State private var showError = false
    @State private var navigateToDashboard = false
    
    let timer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()
    
    var body: some View {
        NavigationView {
            ZStack {
                // Background gradient
                LinearGradient(
                    gradient: Gradient(colors: [Color.blue.opacity(0.1), Color.indigo.opacity(0.2)]),
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                .ignoresSafeArea()
                
                ScrollView {
                    VStack(spacing: 24) {
                        Spacer().frame(height: 60)
                        
                        // Logo
                        ZStack {
                            Circle()
                                .fill(LinearGradient(
                                    gradient: Gradient(colors: [Color.blue, Color.indigo]),
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                ))
                                .frame(width: 80, height: 80)
                            
                            Image(systemName: "envelope.fill")
                                .font(.system(size: 36))
                                .foregroundColor(.white)
                        }
                        
                        // Title
                        VStack(spacing: 8) {
                            Text("Welcome Back")
                                .font(.system(size: 28, weight: .bold))
                                .foregroundColor(.primary)
                            
                            Text(showOTPField ? "Enter the code sent to your email" : "Sign in with your email")
                                .font(.system(size: 16))
                                .foregroundColor(.secondary)
                        }
                        
                        // Error Message
                        if showError, let errorMessage = cdpAuth.errorMessage {
                            HStack {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .foregroundColor(.red)
                                Text(errorMessage)
                                    .font(.system(size: 14))
                                    .foregroundColor(.red)
                            }
                            .padding()
                            .frame(maxWidth: .infinity)
                            .background(Color.red.opacity(0.1))
                            .cornerRadius(12)
                        }
                        
                        // Form Content
                        VStack(spacing: 20) {
                            if !showOTPField {
                                // Email Input Form
                                emailInputForm
                            } else {
                                // OTP Verification Form
                                otpVerificationForm
                            }
                        }
                        .padding(.horizontal, 24)
                        
                        Spacer()
                    }
                }
            }
            .navigationBarHidden(true)
            .navigationDestination(isPresented: $navigateToDashboard) {
                // Navigate to Dashboard
                Text("Dashboard") // Replace with actual DashboardView
            }
        }
        .onReceive(timer) { _ in
            if resendCooldown > 0 {
                resendCooldown -= 1
            }
        }
    }
    
    // MARK: - Email Input Form
    
    private var emailInputForm: some View {
        VStack(spacing: 20) {
            // Email Field
            VStack(alignment: .leading, spacing: 8) {
                Text("Email Address")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundColor(.secondary)
                
                HStack {
                    Image(systemName: "envelope")
                        .foregroundColor(.gray)
                    
                    TextField("you@example.com", text: $email)
                        .textContentType(.emailAddress)
                        .keyboardType(.emailAddress)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                }
                .padding()
                .background(Color(.systemBackground))
                .cornerRadius(12)
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.gray.opacity(0.3), lineWidth: 1)
                )
            }
            
            // Send Code Button
            Button(action: sendOTP) {
                HStack {
                    if cdpAuth.isLoading {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            .scaleEffect(0.8)
                        Text("Sending...")
                    } else {
                        Text("Send Code")
                        Image(systemName: "arrow.right")
                    }
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(
                    LinearGradient(
                        gradient: Gradient(colors: [Color.blue, Color.indigo]),
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .foregroundColor(.white)
                .cornerRadius(12)
            }
            .disabled(cdpAuth.isLoading || email.isEmpty)
            .opacity((cdpAuth.isLoading || email.isEmpty) ? 0.6 : 1.0)
            
            // Sign Up Link
            HStack {
                Text("Don't have an account?")
                    .font(.system(size: 14))
                    .foregroundColor(.secondary)
                
                Button("Sign up") {
                    // Navigate to RegisterView
                }
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(.blue)
            }
        }
    }
    
    // MARK: - OTP Verification Form
    
    private var otpVerificationForm: some View {
        VStack(spacing: 20) {
            // OTP Field
            VStack(alignment: .leading, spacing: 8) {
                Text("Verification Code")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundColor(.secondary)
                
                TextField("000000", text: $otp)
                    .font(.system(size: 24, weight: .medium, design: .monospaced))
                    .multilineTextAlignment(.center)
                    .keyboardType(.numberPad)
                    .padding()
                    .background(Color(.systemBackground))
                    .cornerRadius(12)
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color.gray.opacity(0.3), lineWidth: 1)
                    )
                    .onChange(of: otp) { newValue in
                        // Limit to 6 digits
                        let filtered = newValue.filter { $0.isNumber }
                        if filtered.count > 6 {
                            otp = String(filtered.prefix(6))
                        } else {
                            otp = filtered
                        }
                    }
                
                Text("Code sent to \(email)")
                    .font(.system(size: 12))
                    .foregroundColor(.secondary)
            }
            
            // Verify Button
            Button(action: verifyOTP) {
                HStack {
                    if cdpAuth.isLoading {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            .scaleEffect(0.8)
                        Text("Verifying...")
                    } else {
                        Text("Verify & Sign In")
                        Image(systemName: "arrow.right")
                    }
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(
                    LinearGradient(
                        gradient: Gradient(colors: [Color.blue, Color.indigo]),
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .foregroundColor(.white)
                .cornerRadius(12)
            }
            .disabled(cdpAuth.isLoading || otp.count != 6)
            .opacity((cdpAuth.isLoading || otp.count != 6) ? 0.6 : 1.0)
            
            // Actions Row
            HStack {
                Button(action: {
                    showOTPField = false
                    otp = ""
                    flowId = nil
                }) {
                    HStack {
                        Image(systemName: "arrow.left")
                        Text("Change email")
                    }
                    .font(.system(size: 14))
                    .foregroundColor(.gray)
                }
                
                Spacer()
                
                Button(action: resendOTP) {
                    Text(resendCooldown > 0 ? "Resend in \(resendCooldown)s" : "Resend code")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(resendCooldown > 0 ? .gray : .blue)
                }
                .disabled(resendCooldown > 0)
            }
        }
    }
    
    // MARK: - Actions
    
    private func sendOTP() {
        showError = false
        
        Task {
            do {
                let newFlowId = try await cdpAuth.sendOTP(email: email)
                await MainActor.run {
                    flowId = newFlowId
                    showOTPField = true
                    resendCooldown = 60
                }
            } catch {
                await MainActor.run {
                    showError = true
                }
            }
        }
    }
    
    private func verifyOTP() {
        guard let flowId = flowId else { return }
        showError = false
        
        Task {
            do {
                let walletAddress = try await cdpAuth.verifyOTP(
                    flowId: flowId,
                    otp: otp,
                    email: email
                )
                
                await MainActor.run {
                    print("✅ Login successful! Wallet: \(walletAddress)")
                    navigateToDashboard = true
                }
            } catch {
                await MainActor.run {
                    showError = true
                }
            }
        }
    }
    
    private func resendOTP() {
        if resendCooldown > 0 { return }
        
        showError = false
        otp = ""
        
        Task {
            do {
                let newFlowId = try await cdpAuth.sendOTP(email: email)
                await MainActor.run {
                    flowId = newFlowId
                    resendCooldown = 60
                }
            } catch {
                await MainActor.run {
                    showError = true
                }
            }
        }
    }
}

// MARK: - Info Banner

struct InfoBanner: View {
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "lock.shield.fill")
                .foregroundColor(.blue)
            
            Text("Secure email authentication powered by Coinbase. Your wallet is created automatically.")
                .font(.system(size: 12))
                .foregroundColor(.secondary)
                .multilineTextAlignment(.leading)
        }
        .padding()
        .background(Color.blue.opacity(0.1))
        .cornerRadius(12)
    }
}

// MARK: - Preview

struct LoginView_CDP_Previews: PreviewProvider {
    static var previews: some View {
        LoginView_CDP()
    }
}

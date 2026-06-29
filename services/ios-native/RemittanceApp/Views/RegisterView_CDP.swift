//
// RegisterView_CDP.swift
// RemittanceApp
//
// CDP-enabled Registration with Email OTP
// Created by Manus AI on 2025-11-05.
//

import SwiftUI

struct RegisterView_CDP: View {
    @StateObject private var cdpAuth = CDPAuthService()
    @State private var email = ""
    @State private var otp = ""
    @State private var flowId: String?
    @State private var showOTPField = false
    @State private var termsAccepted = false
    @State private var resendCooldown = 0
    @State private var showError = false
    @State private var navigateToDashboard = false
    
    let timer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()
    
    var body: some View {
        NavigationView {
            ZStack {
                // Background gradient
                LinearGradient(
                    gradient: Gradient(colors: [Color.green.opacity(0.1), Color.emerald.opacity(0.2)]),
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
                                    gradient: Gradient(colors: [Color.green, Color.emerald]),
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
                            Text("Create Account")
                                .font(.system(size: 28, weight: .bold))
                                .foregroundColor(.primary)
                            
                            Text(showOTPField ? "Enter the code sent to your email" : "Get started in 30 seconds")
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
                        
                        // Info Banner
                        InfoBanner()
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
            
            // Terms & Conditions
            HStack(alignment: .top, spacing: 12) {
                Button(action: {
                    termsAccepted.toggle()
                }) {
                    Image(systemName: termsAccepted ? "checkmark.square.fill" : "square")
                        .foregroundColor(termsAccepted ? .green : .gray)
                        .font(.system(size: 20))
                }
                
                VStack(alignment: .leading, spacing: 4) {
                    Text("I agree to the ")
                        .font(.system(size: 14))
                        .foregroundColor(.secondary)
                    + Text("Terms of Service")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(.green)
                    + Text(" and ")
                        .font(.system(size: 14))
                        .foregroundColor(.secondary)
                    + Text("Privacy Policy")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(.green)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            
            // Benefits Card
            VStack(alignment: .leading, spacing: 12) {
                Text("What you get:")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(.primary)
                
                BenefitRow(icon: "checkmark.circle.fill", text: "Instant wallet creation")
                BenefitRow(icon: "checkmark.circle.fill", text: "No passwords or seed phrases")
                BenefitRow(icon: "checkmark.circle.fill", text: "Ultra-low transaction fees")
                BenefitRow(icon: "checkmark.circle.fill", text: "Access from up to 5 devices")
            }
            .padding()
            .background(Color.green.opacity(0.1))
            .cornerRadius(12)
            
            // Create Account Button
            Button(action: sendOTP) {
                HStack {
                    if cdpAuth.isLoading {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            .scaleEffect(0.8)
                        Text("Sending...")
                    } else {
                        Text("Create Account")
                        Image(systemName: "arrow.right")
                    }
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(
                    LinearGradient(
                        gradient: Gradient(colors: [Color.green, Color.emerald]),
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .foregroundColor(.white)
                .cornerRadius(12)
            }
            .disabled(cdpAuth.isLoading || email.isEmpty || !termsAccepted)
            .opacity((cdpAuth.isLoading || email.isEmpty || !termsAccepted) ? 0.6 : 1.0)
            
            // Sign In Link
            HStack {
                Text("Already have an account?")
                    .font(.system(size: 14))
                    .foregroundColor(.secondary)
                
                Button("Sign in") {
                    // Navigate to LoginView
                }
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(.green)
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
            
            // What Happens Next Card
            VStack(alignment: .leading, spacing: 12) {
                Text("What happens next:")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(.primary)
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("1. Your wallet is created automatically")
                        .font(.system(size: 14))
                        .foregroundColor(.secondary)
                    Text("2. You're instantly signed in")
                        .font(.system(size: 14))
                        .foregroundColor(.secondary)
                    Text("3. Start sending money immediately")
                        .font(.system(size: 14))
                        .foregroundColor(.secondary)
                }
            }
            .padding()
            .background(Color.blue.opacity(0.1))
            .cornerRadius(12)
            
            // Verify Button
            Button(action: verifyOTP) {
                HStack {
                    if cdpAuth.isLoading {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            .scaleEffect(0.8)
                        Text("Creating Account...")
                    } else {
                        Text("Verify & Create Account")
                        Image(systemName: "arrow.right")
                    }
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(
                    LinearGradient(
                        gradient: Gradient(colors: [Color.green, Color.emerald]),
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
                        .foregroundColor(resendCooldown > 0 ? .gray : .green)
                }
                .disabled(resendCooldown > 0)
            }
        }
    }
    
    // MARK: - Actions
    
    private func sendOTP() {
        if !termsAccepted {
            cdpAuth.errorMessage = "Please accept the terms and conditions"
            showError = true
            return
        }
        
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
                    print("✅ Registration successful! Wallet: \(walletAddress)")
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

// MARK: - Benefit Row Component

struct BenefitRow: View {
    let icon: String
    let text: String
    
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .foregroundColor(.green)
                .font(.system(size: 14))
            
            Text(text)
                .font(.system(size: 14))
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Custom Colors Extension

extension Color {
    static let emerald = Color(red: 16/255, green: 185/255, blue: 129/255)
}

// MARK: - Preview

struct RegisterView_CDP_Previews: PreviewProvider {
    static var previews: some View {
        RegisterView_CDP()
    }
}

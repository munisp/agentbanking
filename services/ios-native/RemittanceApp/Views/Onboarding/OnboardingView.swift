import SwiftUI

struct OnboardingView: View {
    @State private var currentPage = 0
    @State private var showLogin = false
    @State private var showRegister = false
    
    let onboardingPages = [
        OnboardingPage(
            title: "Send Money Globally",
            description: "Transfer money to over 100 countries with the best exchange rates",
            imageName: "globe.americas.fill",
            color: Color("PrimaryColor")
        ),
        OnboardingPage(
            title: "Fast & Secure",
            description: "Your money arrives in minutes with bank-level security",
            imageName: "bolt.shield.fill",
            color: Color("SecondaryColor")
        ),
        OnboardingPage(
            title: "Low Fees",
            description: "Save money with our transparent, low-cost transfers",
            imageName: "dollarsign.circle.fill",
            color: Color("AccentColor")
        )
    ]
    
    var body: some View {
        ZStack {
            if showLogin {
                LoginView(showRegister: $showRegister)
            } else if showRegister {
                RegisterView(showLogin: $showLogin)
            } else {
                onboardingContent
            }
        }
        .animation(.easeInOut, value: showLogin)
        .animation(.easeInOut, value: showRegister)
    }
    
    var onboardingContent: some View {
        VStack(spacing: 0) {
            // Page content
            TabView(selection: $currentPage) {
                ForEach(0..<onboardingPages.count, id: \.self) { index in
                    OnboardingPageView(page: onboardingPages[index])
                        .tag(index)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
            
            // Page indicator
            HStack(spacing: 8) {
                ForEach(0..<onboardingPages.count, id: \.self) { index in
                    Circle()
                        .fill(currentPage == index ? Color("PrimaryColor") : Color.gray.opacity(0.3))
                        .frame(width: 8, height: 8)
                }
            }
            .padding(.bottom, 20)
            
            // Action buttons
            VStack(spacing: 16) {
                Button(action: {
                    showRegister = true
                }) {
                    Text("Get Started")
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 56)
                        .background(Color("PrimaryColor"))
                        .cornerRadius(12)
                }
                
                Button(action: {
                    showLogin = true
                }) {
                    Text("I already have an account")
                        .font(.subheadline)
                        .foregroundColor(Color("PrimaryColor"))
                }
            }
            .padding(.horizontal, 24)
            .padding(.bottom, 40)
        }
    }
}

struct OnboardingPage {
    let title: String
    let description: String
    let imageName: String
    let color: Color
}

struct OnboardingPageView: View {
    let page: OnboardingPage
    
    var body: some View {
        VStack(spacing: 32) {
            Spacer()
            
            Image(systemName: page.imageName)
                .resizable()
                .scaledToFit()
                .frame(width: 200, height: 200)
                .foregroundColor(page.color)
            
            VStack(spacing: 16) {
                Text(page.title)
                    .font(.system(size: 32, weight: .bold))
                    .multilineTextAlignment(.center)
                
                Text(page.description)
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }
            
            Spacer()
        }
        .padding()
    }
}

struct LoginView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @Binding var showRegister: Bool
    
    @State private var email = ""
    @State private var password = ""
    @State private var showPassword = false
    @State private var showForgotPassword = false
    
    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Header
                VStack(spacing: 8) {
                    Text("Welcome Back")
                        .font(.system(size: 32, weight: .bold))
                    
                    Text("Log in to your account")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.top, 60)
                
                // Biometric login button
                if authManager.isBiometricEnabled {
                    Button(action: {
                        Task {
                            await authManager.loginWithBiometric()
                        }
                    }) {
                        HStack {
                            Image(systemName: authManager.biometricType == .faceID ? "faceid" : "touchid")
                            Text("Login with \(authManager.biometricType.displayName)")
                        }
                        .font(.headline)
                        .foregroundColor(Color("PrimaryColor"))
                        .frame(maxWidth: .infinity)
                        .frame(height: 56)
                        .background(Color("PrimaryColor").opacity(0.1))
                        .cornerRadius(12)
                    }
                    .padding(.horizontal, 24)
                    
                    HStack {
                        Rectangle()
                            .fill(Color.gray.opacity(0.3))
                            .frame(height: 1)
                        Text("or")
                            .foregroundColor(.secondary)
                            .padding(.horizontal, 8)
                        Rectangle()
                            .fill(Color.gray.opacity(0.3))
                            .frame(height: 1)
                    }
                    .padding(.horizontal, 24)
                }
                
                // Email field
                VStack(alignment: .leading, spacing: 8) {
                    Text("Email")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    TextField("Enter your email", text: $email)
                        .textContentType(.emailAddress)
                        .keyboardType(.emailAddress)
                        .autocapitalization(.none)
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(12)
                }
                .padding(.horizontal, 24)
                
                // Password field
                VStack(alignment: .leading, spacing: 8) {
                    Text("Password")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    HStack {
                        if showPassword {
                            TextField("Enter your password", text: $password)
                        } else {
                            SecureField("Enter your password", text: $password)
                        }
                        
                        Button(action: { showPassword.toggle() }) {
                            Image(systemName: showPassword ? "eye.slash.fill" : "eye.fill")
                                .foregroundColor(.secondary)
                        }
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)
                }
                .padding(.horizontal, 24)
                
                // Forgot password
                HStack {
                    Spacer()
                    Button(action: { showForgotPassword = true }) {
                        Text("Forgot Password?")
                            .font(.subheadline)
                            .foregroundColor(Color("PrimaryColor"))
                    }
                }
                .padding(.horizontal, 24)
                
                // Error message
                if let error = authManager.errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                        .padding(.horizontal, 24)
                }
                
                // Login button
                Button(action: {
                    Task {
                        await authManager.login(email: email, password: password)
                    }
                }) {
                    if authManager.isLoading {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    } else {
                        Text("Login")
                            .font(.headline)
                    }
                }
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 56)
                .background(isFormValid ? Color("PrimaryColor") : Color.gray)
                .cornerRadius(12)
                .disabled(!isFormValid || authManager.isLoading)
                .padding(.horizontal, 24)
                
                // Register link
                HStack {
                    Text("Don't have an account?")
                        .foregroundColor(.secondary)
                    Button(action: { showRegister = true }) {
                        Text("Sign Up")
                            .foregroundColor(Color("PrimaryColor"))
                            .fontWeight(.semibold)
                    }
                }
                .font(.subheadline)
                .padding(.top, 8)
                
                Spacer()
            }
        }
        .sheet(isPresented: $showForgotPassword) {
            ForgotPasswordView()
        }
    }
    
    var isFormValid: Bool {
        !email.isEmpty && email.contains("@") && password.count >= 6
    }
}

struct RegisterView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @Binding var showLogin: Bool
    
    @State private var email = ""
    @State private var password = ""
    @State private var confirmPassword = ""
    @State private var firstName = ""
    @State private var lastName = ""
    @State private var phoneNumber = ""
    @State private var country = "Nigeria"
    @State private var showPassword = false
    @State private var acceptedTerms = false
    
    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Header
                VStack(spacing: 8) {
                    Text("Create Account")
                        .font(.system(size: 32, weight: .bold))
                    
                    Text("Sign up to get started")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.top, 60)
                
                // First name
                VStack(alignment: .leading, spacing: 8) {
                    Text("First Name")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    TextField("Enter your first name", text: $firstName)
                        .textContentType(.givenName)
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(12)
                }
                .padding(.horizontal, 24)
                
                // Last name
                VStack(alignment: .leading, spacing: 8) {
                    Text("Last Name")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    TextField("Enter your last name", text: $lastName)
                        .textContentType(.familyName)
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(12)
                }
                .padding(.horizontal, 24)
                
                // Email
                VStack(alignment: .leading, spacing: 8) {
                    Text("Email")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    TextField("Enter your email", text: $email)
                        .textContentType(.emailAddress)
                        .keyboardType(.emailAddress)
                        .autocapitalization(.none)
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(12)
                }
                .padding(.horizontal, 24)
                
                // Phone number
                VStack(alignment: .leading, spacing: 8) {
                    Text("Phone Number")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    TextField("Enter your phone number", text: $phoneNumber)
                        .textContentType(.telephoneNumber)
                        .keyboardType(.phonePad)
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(12)
                }
                .padding(.horizontal, 24)
                
                // Password
                VStack(alignment: .leading, spacing: 8) {
                    Text("Password")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    HStack {
                        if showPassword {
                            TextField("Create a password", text: $password)
                        } else {
                            SecureField("Create a password", text: $password)
                        }
                        
                        Button(action: { showPassword.toggle() }) {
                            Image(systemName: showPassword ? "eye.slash.fill" : "eye.fill")
                                .foregroundColor(.secondary)
                        }
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)
                    
                    Text("At least 8 characters")
                        .font(.caption)
                        .foregroundColor(password.count >= 8 ? .green : .secondary)
                }
                .padding(.horizontal, 24)
                
                // Confirm password
                VStack(alignment: .leading, spacing: 8) {
                    Text("Confirm Password")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    SecureField("Confirm your password", text: $confirmPassword)
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(12)
                    
                    if !confirmPassword.isEmpty && password != confirmPassword {
                        Text("Passwords do not match")
                            .font(.caption)
                            .foregroundColor(.red)
                    }
                }
                .padding(.horizontal, 24)
                
                // Terms and conditions
                HStack(alignment: .top, spacing: 12) {
                    Button(action: { acceptedTerms.toggle() }) {
                        Image(systemName: acceptedTerms ? "checkmark.square.fill" : "square")
                            .foregroundColor(acceptedTerms ? Color("PrimaryColor") : .secondary)
                    }
                    
                    Text("I agree to the Terms of Service and Privacy Policy")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding(.horizontal, 24)
                
                // Error message
                if let error = authManager.errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                        .padding(.horizontal, 24)
                }
                
                // Register button
                Button(action: {
                    Task {
                        await authManager.register(
                            email: email,
                            password: password,
                            firstName: firstName,
                            lastName: lastName,
                            phoneNumber: phoneNumber,
                            country: country
                        )
                    }
                }) {
                    if authManager.isLoading {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    } else {
                        Text("Create Account")
                            .font(.headline)
                    }
                }
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 56)
                .background(isFormValid ? Color("PrimaryColor") : Color.gray)
                .cornerRadius(12)
                .disabled(!isFormValid || authManager.isLoading)
                .padding(.horizontal, 24)
                
                // Login link
                HStack {
                    Text("Already have an account?")
                        .foregroundColor(.secondary)
                    Button(action: { showLogin = true }) {
                        Text("Log In")
                            .foregroundColor(Color("PrimaryColor"))
                            .fontWeight(.semibold)
                    }
                }
                .font(.subheadline)
                .padding(.top, 8)
                
                Spacer()
            }
        }
    }
    
    var isFormValid: Bool {
        !firstName.isEmpty &&
        !lastName.isEmpty &&
        !email.isEmpty && email.contains("@") &&
        !phoneNumber.isEmpty &&
        password.count >= 8 &&
        password == confirmPassword &&
        acceptedTerms
    }
}

struct ForgotPasswordView: View {
    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var authManager: AuthenticationManager
    
    @State private var email = ""
    @State private var emailSent = false
    
    var body: some View {
        NavigationView {
            VStack(spacing: 24) {
                if emailSent {
                    VStack(spacing: 16) {
                        Image(systemName: "envelope.circle.fill")
                            .resizable()
                            .scaledToFit()
                            .frame(width: 100, height: 100)
                            .foregroundColor(Color("PrimaryColor"))
                        
                        Text("Check Your Email")
                            .font(.title2)
                            .fontWeight(.bold)
                        
                        Text("We've sent password reset instructions to \(email)")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                        
                        Button(action: { dismiss() }) {
                            Text("Done")
                                .font(.headline)
                                .foregroundColor(.white)
                                .frame(maxWidth: .infinity)
                                .frame(height: 56)
                                .background(Color("PrimaryColor"))
                                .cornerRadius(12)
                        }
                        .padding(.horizontal, 24)
                        .padding(.top, 16)
                    }
                } else {
                    VStack(spacing: 16) {
                        Text("Reset Password")
                            .font(.title2)
                            .fontWeight(.bold)
                        
                        Text("Enter your email address and we'll send you instructions to reset your password")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                        
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Email")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                            
                            TextField("Enter your email", text: $email)
                                .textContentType(.emailAddress)
                                .keyboardType(.emailAddress)
                                .autocapitalization(.none)
                                .padding()
                                .background(Color(.systemGray6))
                                .cornerRadius(12)
                        }
                        .padding(.horizontal, 24)
                        
                        Button(action: {
                            Task {
                                let success = await authManager.forgotPassword(email: email)
                                if success {
                                    emailSent = true
                                }
                            }
                        }) {
                            if authManager.isLoading {
                                ProgressView()
                                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            } else {
                                Text("Send Reset Link")
                                    .font(.headline)
                            }
                        }
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 56)
                        .background(email.contains("@") ? Color("PrimaryColor") : Color.gray)
                        .cornerRadius(12)
                        .disabled(!email.contains("@") || authManager.isLoading)
                        .padding(.horizontal, 24)
                    }
                }
                
                Spacer()
            }
            .padding(.top, 40)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark")
                            .foregroundColor(.primary)
                    }
                }
            }
        }
    }
}

#Preview {
    OnboardingView()
        .environmentObject(AuthenticationManager())
}

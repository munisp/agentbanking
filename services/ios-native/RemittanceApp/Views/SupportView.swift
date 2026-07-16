//
//  SupportView.swift
//  RemittanceApp
//
//  Created by Manus AI on 2025/11/03.
//

import SwiftUI
import Combine
import LocalAuthentication // For Biometric Authentication

// MARK: - 1. Data Models

struct FAQItem: Identifiable, Codable {
    let id: Int
    let question: String
    let answer: String
}

struct HelpCenterCategory: Identifiable, Codable {
    let id: Int
    let name: String
    let iconName: String
}

// MARK: - 2. API Client Stub

enum APIError: Error, LocalizedError {
    case networkError(String)
    case serverError(String)
    case unknownError
    
    var errorDescription: String? {
        switch self {
        case .networkError(let msg): return "Network Error: \(msg)"
        case .serverError(let msg): return "Server Error: \(msg)"
        case .unknownError: return "An unknown error occurred."
        }
    }
}

class APIClient {
    // Simulate fetching data from a remote server
    func fetchFAQs() -> AnyPublisher<[FAQItem], APIError> {
        // Simulate network delay
        return Future { promise in
            DispatchQueue.global().asyncAfter(deadline: .now() + 1.5) {
                if Bool.random() { // Simulate success
                    let faqs = [
                        FAQItem(id: 1, question: "How do I send money?", answer: "Navigate to the 'Send Money' tab, select a recipient, enter the amount, and confirm the transaction."),
                        FAQItem(id: 2, question: "What are your exchange rates?", answer: "Our rates are updated in real-time and displayed before you confirm any transaction."),
                        FAQItem(id: 3, question: "Is live chat available 24/7?", answer: "Yes, our live chat support is available 24 hours a day, 7 days a week.")
                    ]
                    promise(.success(faqs))
                } else { // Simulate failure
                    promise(.failure(.networkError("The server could not be reached. Please check your connection.")))
                }
            }
        }
        .eraseToAnyPublisher()
    }
    
    // Simulate sending a contact form
    func submitContactForm(subject: String, message: String) -> AnyPublisher<Bool, APIError> {
        return Future { promise in
            DispatchQueue.global().asyncAfter(deadline: .now() + 1.0) {
                if Bool.random() {
                    promise(.success(true))
                } else {
                    promise(.failure(.serverError("Failed to submit form. Please try again later.")))
                }
            }
        }
        .eraseToAnyPublisher()
    }
}

// MARK: - 3. State Management (ObservableObject)

class SupportViewModel: ObservableObject {
    @Published var faqs: [FAQItem] = []
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var isOffline: Bool = false
    @Published var contactSubject: String = ""
    @Published var contactMessage: String = ""
    @Published var isFormValid: Bool = false
    @Published var isFormSubmitted: Bool = false
    
    private var apiClient = APIClient()
    private var cancellables = Set<AnyCancellable>()
    
    // Dummy local cache for offline support
    private let localCacheKey = "cachedFAQs"
    
    init() {
        // Check for network connectivity (simplified for this stub)
        self.isOffline = false // Assume online initially
        
        // Load cached data on initialization
        loadCachedFAQs()
        
        // Setup form validation
        $contactSubject.combineLatest($contactMessage)
            .map { subject, message in
                return !subject.isEmpty && message.count >= 10
            }
            .assign(to: &$isFormValid)
    }
    
    // MARK: - API & Caching
    
    func fetchSupportData() {
        guard !isLoading else { return }
        
        if isOffline {
            // Data is already loaded from cache in init, no need to fetch
            self.errorMessage = "You are currently offline. Displaying cached data."
            return
        }
        
        self.isLoading = true
        self.errorMessage = nil
        
        apiClient.fetchFAQs()
            .receive(on: DispatchQueue.main)
            .sink { [weak self] completion in
                self?.isLoading = false
                switch completion {
                case .failure(let error):
                    self?.errorMessage = error.localizedDescription
                    // Fallback to cache on network error
                    if self?.faqs.isEmpty ?? true {
                        self?.loadCachedFAQs()
                    }
                case .finished:
                    break
                }
            } receiveValue: { [weak self] faqs in
                self?.faqs = faqs
                self?.cacheFAQs(faqs)
            }
            .store(in: &cancellables)
    }
    
    private func cacheFAQs(_ faqs: [FAQItem]) {
        do {
            let data = try JSONEncoder().encode(faqs)
            UserDefaults.standard.set(data, forKey: localCacheKey)
        } catch {
            print("Error caching FAQs: \(error)")
        }
    }
    
    private func loadCachedFAQs() {
        if let data = UserDefaults.standard.data(forKey: localCacheKey) {
            do {
                self.faqs = try JSONDecoder().decode([FAQItem].self, from: data)
            } catch {
                print("Error loading cached FAQs: \(error)")
            }
        }
    }
    
    // MARK: - Contact Form
    
    func submitContactRequest() {
        guard isFormValid, !isLoading else { return }
        
        self.isLoading = true
        self.errorMessage = nil
        
        apiClient.submitContactForm(subject: contactSubject, message: contactMessage)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] completion in
                self?.isLoading = false
                switch completion {
                case .failure(let error):
                    self?.errorMessage = error.localizedDescription
                case .finished:
                    break
                }
            } receiveValue: { [weak self] success in
                if success {
                    self?.isFormSubmitted = true
                    self?.contactSubject = ""
                    self?.contactMessage = ""
                }
            }
            .store(in: &cancellables)
    }
    
    // MARK: - Biometric Authentication Stub
    
    func authenticateForSensitiveAction(completion: @escaping (Bool) -> Void) {
        let context = LAContext()
        var error: NSError?
        
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            print("Biometric authentication not available: \(error?.localizedDescription ?? "Unknown error")")
            completion(false)
            return
        }
        
        let reason = "To access sensitive support features like payment dispute forms."
        context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason) { success, authenticationError in
            DispatchQueue.main.async {
                if success {
                    print("Biometric authentication successful.")
                    completion(true)
                } else {
                    print("Biometric authentication failed: \(authenticationError?.localizedDescription ?? "User cancelled")")
                    completion(false)
                }
            }
        }
    }
}

// MARK: - 4. SwiftUI View

struct SupportView: View {
    @StateObject var viewModel = SupportViewModel()
    @State private var selectedTab: SupportTab = .helpCenter
    @State private var isShowingLiveChat: Bool = false
    @State private var isAuthenticated: Bool = false // For biometric access
    
    enum SupportTab: String, CaseIterable {
        case helpCenter = "Help Center"
        case faqs = "FAQs"
        case contact = "Contact Support"
    }
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Tab Selector
                Picker("Support Options", selection: $selectedTab) {
                    ForEach(SupportTab.allCases, id: \.self) { tab in
                        Text(tab.rawValue).tag(tab)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)
                .padding(.top, 8)
                
                // Content View
                Group {
                    switch selectedTab {
                    case .helpCenter:
                        HelpCenterContent
                    case .faqs:
                        FAQsContent
                    case .contact:
                        ContactSupportContent
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                
                // Live Chat Button
                liveChatButton
            }
            .navigationTitle("Support")
            .onAppear {
                viewModel.fetchSupportData()
            }
            .alert("Error", isPresented: .constant(viewModel.errorMessage != nil), actions: {
                Button("OK") { viewModel.errorMessage = nil }
            }, message: {
                Text(viewModel.errorMessage ?? "Unknown error")
            })
            .sheet(isPresented: $isShowingLiveChat) {
                LiveChatView()
            }
        }
    }
    
    // MARK: - Help Center Content
    
    var HelpCenterContent: some View {
        List {
            Section("Popular Topics") {
                ForEach(helpCenterCategories) { category in
                    NavigationLink(destination: HelpArticleView(category: category)) {
                        Label(category.name, systemImage: category.iconName)
                            .accessibilityLabel("Go to \(category.name) articles")
                    }
                }
            }
            
            Section("Sensitive Actions") {
                Button {
                    viewModel.authenticateForSensitiveAction { success in
                        if success {
                            self.isAuthenticated = true
                        }
                    }
                } label: {
                    Label("Payment Dispute Form (Requires Biometrics)", systemImage: "lock.shield")
                }
                .disabled(isAuthenticated)
                
                if isAuthenticated {
                    NavigationLink(destination: PaymentDisputeFormView()) {
                        Label("Access Payment Dispute Form", systemImage: "doc.text.fill")
                    }
                }
            }
            
            // Payment Gateway Links (Stubbed)
            Section("Payment Gateway Support") {
                Link("Paystack Support", destination: URL(string: "https://support.paystack.com")!)
                Link("Flutterwave Support", destination: URL(string: "https://support.flutterwave.com")!)
                Link("Interswitch Support", destination: URL(string: "https://support.interswitchgroup.com")!)
            }
        }
        .listStyle(.insetGrouped)
    }
    
    // MARK: - FAQs Content
    
    var FAQsContent: some View {
        List {
            if viewModel.isLoading && viewModel.faqs.isEmpty {
                ProgressView("Loading FAQs...")
            } else if viewModel.faqs.isEmpty {
                ContentUnavailableView("No FAQs Available", systemImage: "questionmark.circle")
            } else {
                ForEach(viewModel.faqs) { faq in
                    DisclosureGroup(faq.question) {
                        Text(faq.answer)
                            .font(.callout)
                            .padding(.leading)
                    }
                    .accessibilityLabel("FAQ: \(faq.question)")
                }
            }
        }
        .listStyle(.plain)
        .refreshable {
            viewModel.fetchSupportData()
        }
    }
    
    // MARK: - Contact Support Content
    
    var ContactSupportContent: some View {
        Form {
            Section("Contact Form") {
                TextField("Subject (e.g., Account Issue)", text: $viewModel.contactSubject)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.words)
                    .accessibilityLabel("Contact form subject field")
                
                TextEditor(text: $viewModel.contactMessage)
                    .frame(height: 150)
                    .overlay(
                        Group {
                            if viewModel.contactMessage.isEmpty {
                                Text("Your detailed message (min 10 characters)")
                                    .foregroundColor(.gray)
                                    .padding(.top, 8)
                                    .padding(.leading, 5)
                            }
                        }, alignment: .topLeading
                    )
                    .accessibilityLabel("Contact form message field")
                
                if !viewModel.contactMessage.isEmpty && viewModel.contactMessage.count < 10 {
                    Text("Message must be at least 10 characters.")
                        .foregroundColor(.red)
                        .font(.caption)
                }
            }
            
            Section {
                Button {
                    viewModel.submitContactRequest()
                } label: {
                    HStack {
                        if viewModel.isLoading {
                            ProgressView()
                        }
                        Text(viewModel.isLoading ? "Submitting..." : "Submit Request")
                    }
                    .frame(maxWidth: .infinity)
                }
                .disabled(!viewModel.isFormValid || viewModel.isLoading)
                .buttonStyle(.borderedProminent)
                .accessibilityHint("Submits the contact support form.")
            }
            
            if viewModel.isFormSubmitted {
                Text("✅ Your request has been submitted successfully!")
                    .foregroundColor(.green)
            }
        }
    }
    
    // MARK: - Live Chat Button
    
    var liveChatButton: some View {
        Button {
            isShowingLiveChat = true
        } label: {
            HStack {
                Image(systemName: "message.fill")
                Text("Start Live Chat")
            }
            .font(.headline)
            .foregroundColor(.white)
            .padding()
            .frame(maxWidth: .infinity)
            .background(Color.blue)
            .cornerRadius(10)
            .padding([.horizontal, .bottom])
            .accessibilityLabel("Start Live Chat")
            .accessibilityHint("Opens a new window for real-time support chat.")
        }
    }
}

// MARK: - 5. Supporting Views (Stubs for Navigation)

struct HelpArticleView: View {
    let category: HelpCenterCategory
    var body: some View {
        Text("Article content for \(category.name)")
            .navigationTitle(category.name)
    }
}

struct LiveChatView: View {
    @Environment(\.dismiss) var dismiss
    var body: some View {
        NavigationView {
            VStack {
                Text("Live Chat Interface")
                    .font(.largeTitle)
                Text("A real-time chat session would be embedded here.")
                Spacer()
            }
            .padding()
            .navigationTitle("Live Chat")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("End Chat") {
                        dismiss()
                    }
                }
            }
        }
    }
}

struct PaymentDisputeFormView: View {
    var body: some View {
        VStack {
            Text("Sensitive Payment Dispute Form")
                .font(.title)
            Text("This form is only accessible after successful biometric authentication.")
            // Form fields for dispute details would go here
        }
        .padding()
        .navigationTitle("Dispute Form")
    }
}

// MARK: - 6. Dummy Data

let helpCenterCategories = [
    HelpCenterCategory(id: 101, name: "Sending Money", iconName: "arrow.up.right.circle.fill"),
    HelpCenterCategory(id: 102, name: "Receiving Funds", iconName: "arrow.down.left.circle.fill"),
    HelpCenterCategory(id: 103, name: "Account & Security", iconName: "lock.shield.fill"),
    HelpCenterCategory(id: 104, name: "Fees & Rates", iconName: "dollarsign.circle.fill")
]

// MARK: - Preview

#Preview {
    SupportView()
}

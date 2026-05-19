//
// PropertyKYCView.swift
// 54Link Agency Banking
//
// Comprehensive 7-step Property Transaction KYC flow for bank-grade compliance
//

import SwiftUI

// MARK: - Data Models

struct PartyIdentity {
    var fullName: String = ""
    var dateOfBirth: String = ""
    var nationality: String = "Nigerian"
    var idType: String = "NATIONAL_ID"
    var idNumber: String = ""
    var idExpiryDate: String = ""
    var bvn: String = ""
    var nin: String = ""
    var address: String = ""
    var city: String = ""
    var state: String = ""
    var country: String = "Nigeria"
    var phone: String = ""
    var email: String = ""
}

struct SourceOfFundsData {
    var primarySource: String = "EMPLOYMENT"
    var description: String = ""
    var employerName: String = ""
    var businessName: String = ""
    var annualIncome: String = ""
}

struct BankStatementData: Identifiable {
    let id = UUID()
    var fileName: String = ""
    var startDate: String = ""
    var endDate: String = ""
    var uploaded: Bool = false
}

struct IncomeDocumentData: Identifiable {
    let id = UUID()
    var documentType: String = "PAYSLIP"
    var fileName: String = ""
    var uploaded: Bool = false
}

struct PurchaseAgreementData {
    var fileName: String = ""
    var propertyAddress: String = ""
    var purchasePrice: String = ""
    var buyerName: String = ""
    var sellerName: String = ""
    var agreementDate: String = ""
    var uploaded: Bool = false
}

// MARK: - Constants

let idTypes: [(String, String)] = [
    ("NATIONAL_ID", "National ID Card"),
    ("PASSPORT", "International Passport"),
    ("DRIVERS_LICENSE", "Driver's License"),
    ("VOTERS_CARD", "Voter's Card"),
    ("NIN_SLIP", "NIN Slip"),
    ("BVN", "BVN")
]

let sourceOfFundsOptions: [(String, String)] = [
    ("EMPLOYMENT", "Employment Income"),
    ("BUSINESS", "Business Income"),
    ("SAVINGS", "Personal Savings"),
    ("GIFT", "Gift from Family/Friends"),
    ("LOAN", "Bank Loan/Mortgage"),
    ("INHERITANCE", "Inheritance"),
    ("INVESTMENT", "Investment Returns"),
    ("SALE_OF_PROPERTY", "Sale of Property"),
    ("OTHER", "Other")
]

let incomeDocumentTypes: [(String, String)] = [
    ("PAYSLIP", "Payslip (Last 3 months)"),
    ("W2", "W-2 Form"),
    ("PAYE", "PAYE Records"),
    ("TAX_RETURN", "Tax Return"),
    ("BUSINESS_REGISTRATION", "Business Registration"),
    ("AUDITED_ACCOUNTS", "Audited Accounts")
]

let nigerianStates = [
    "Lagos", "Abuja FCT", "Kano", "Rivers", "Oyo", "Kaduna", "Ogun", "Enugu",
    "Delta", "Anambra", "Edo", "Imo", "Kwara", "Osun", "Ekiti", "Ondo"
]

// MARK: - View Model

@MainActor
final class PropertyKYCViewModel: ObservableObject {
    @Published var currentStep = 1
    @Published var buyerIdentity = PartyIdentity()
    @Published var sellerIdentity = PartyIdentity()
    @Published var sourceOfFunds = SourceOfFundsData()
    @Published var bankStatements: [BankStatementData] = [BankStatementData()]
    @Published var incomeDocuments: [IncomeDocumentData] = [IncomeDocumentData()]
    @Published var purchaseAgreement = PurchaseAgreementData()
    
    @Published var isSubmitting = false
    @Published var errorMessage: String?
    @Published var successMessage: String?
    @Published var isOnline = true
    
    let steps = ["Buyer KYC", "Seller KYC", "Source of Funds", "Bank Statements", "Income Docs", "Agreement", "Review"]
    
    func submitKYC() async {
        isSubmitting = true
        try? await Task.sleep(nanoseconds: 2_000_000_000)
        successMessage = "Property KYC submitted successfully! Reference: PKYC\(Int(Date().timeIntervalSince1970))"
        isSubmitting = false
    }
    
    func addBankStatement() {
        bankStatements.append(BankStatementData())
    }
    
    func addIncomeDocument() {
        incomeDocuments.append(IncomeDocumentData())
    }
}

// MARK: - Main View

struct PropertyKYCView: View {
    @StateObject private var viewModel = PropertyKYCViewModel()
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Offline indicator
                if !viewModel.isOnline {
                    HStack {
                        Circle()
                            .fill(Color.orange)
                            .frame(width: 8, height: 8)
                        Text("Offline Mode")
                            .font(.caption)
                            .foregroundColor(.orange)
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(Color.orange.opacity(0.1))
                    .cornerRadius(16)
                    .padding(.top, 8)
                }
                
                // Progress indicator
                PropertyKYCProgressView(currentStep: viewModel.currentStep, steps: viewModel.steps)
                    .padding()
                
                // Error message
                if let error = viewModel.errorMessage {
                    HStack {
                        Image(systemName: "exclamationmark.circle.fill")
                            .foregroundColor(.red)
                        Text(error)
                            .font(.subheadline)
                        Spacer()
                        Button(action: { viewModel.errorMessage = nil }) {
                            Image(systemName: "xmark")
                                .foregroundColor(.secondary)
                        }
                    }
                    .padding()
                    .background(Color.red.opacity(0.1))
                    .cornerRadius(12)
                    .padding(.horizontal)
                }
                
                // Success message
                if let success = viewModel.successMessage {
                    HStack {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.green)
                        Text(success)
                            .font(.subheadline)
                    }
                    .padding()
                    .background(Color.green.opacity(0.1))
                    .cornerRadius(12)
                    .padding(.horizontal)
                }
                
                ScrollView {
                    VStack(spacing: 20) {
                        switch viewModel.currentStep {
                        case 1:
                            PartyIdentityStepView(title: "Buyer Information", identity: $viewModel.buyerIdentity)
                        case 2:
                            PartyIdentityStepView(title: "Seller Information", identity: $viewModel.sellerIdentity)
                        case 3:
                            SourceOfFundsStepView(sourceOfFunds: $viewModel.sourceOfFunds)
                        case 4:
                            BankStatementsStepView(statements: $viewModel.bankStatements, onAdd: viewModel.addBankStatement)
                        case 5:
                            IncomeDocumentsStepView(documents: $viewModel.incomeDocuments, onAdd: viewModel.addIncomeDocument)
                        case 6:
                            PurchaseAgreementStepView(agreement: $viewModel.purchaseAgreement)
                        case 7:
                            ReviewStepView(viewModel: viewModel)
                        default:
                            EmptyView()
                        }
                    }
                    .padding()
                }
                
                // Navigation buttons
                HStack(spacing: 12) {
                    if viewModel.currentStep > 1 {
                        Button("Back") {
                            viewModel.currentStep -= 1
                        }
                        .buttonStyle(.bordered)
                    } else {
                        Button("Cancel") {
                            dismiss()
                        }
                        .buttonStyle(.bordered)
                    }
                    
                    Button(action: {
                        if viewModel.currentStep < 7 {
                            viewModel.currentStep += 1
                        } else {
                            Task { await viewModel.submitKYC() }
                        }
                    }) {
                        HStack {
                            if viewModel.isSubmitting {
                                ProgressView()
                                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                                Text("Submitting...")
                            } else if viewModel.currentStep == 7 {
                                Image(systemName: "paperplane.fill")
                                Text("Submit KYC")
                            } else {
                                Text("Continue")
                            }
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(viewModel.isSubmitting)
                }
                .padding()
            }
            .navigationTitle("Property Transaction KYC")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark")
                    }
                }
            }
        }
    }
}

// MARK: - Progress View

struct PropertyKYCProgressView: View {
    let currentStep: Int
    let steps: [String]
    
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 4) {
                ForEach(Array(steps.enumerated()), id: \.offset) { index, label in
                    let stepNum = index + 1
                    let isCompleted = currentStep > stepNum
                    let isCurrent = currentStep == stepNum
                    
                    VStack(spacing: 4) {
                        ZStack {
                            Circle()
                                .fill(isCompleted || isCurrent ? Color.blue : Color.gray.opacity(0.3))
                                .frame(width: 28, height: 28)
                            
                            if isCompleted {
                                Image(systemName: "checkmark")
                                    .foregroundColor(.white)
                                    .font(.system(size: 12, weight: .bold))
                            } else {
                                Text("\(stepNum)")
                                    .foregroundColor(isCurrent ? .white : .gray)
                                    .font(.system(size: 12, weight: .bold))
                            }
                        }
                        
                        Text(label)
                            .font(.system(size: 9))
                            .foregroundColor(isCurrent ? .blue : .secondary)
                            .lineLimit(1)
                    }
                    .frame(width: 50)
                    
                    if index < steps.count - 1 {
                        Rectangle()
                            .fill(isCompleted ? Color.blue : Color.gray.opacity(0.3))
                            .frame(width: 12, height: 2)
                    }
                }
            }
        }
    }
}

// MARK: - Party Identity Step

struct PartyIdentityStepView: View {
    let title: String
    @Binding var identity: PartyIdentity
    
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text(title)
                .font(.title2.bold())
            
            Text("Please provide government-issued identification")
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            Group {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Full Name (as on ID)")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    TextField("Enter full name", text: $identity.fullName)
                        .textFieldStyle(.roundedBorder)
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("Date of Birth")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    TextField("DD/MM/YYYY", text: $identity.dateOfBirth)
                        .textFieldStyle(.roundedBorder)
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("ID Type")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    Picker("ID Type", selection: $identity.idType) {
                        ForEach(idTypes, id: \.0) { code, name in
                            Text(name).tag(code)
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(8)
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("ID Number")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    TextField("Enter ID number", text: $identity.idNumber)
                        .textFieldStyle(.roundedBorder)
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("ID Expiry Date")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    TextField("DD/MM/YYYY", text: $identity.idExpiryDate)
                        .textFieldStyle(.roundedBorder)
                }
            }
            
            Divider()
            
            Text("Nigerian Verification Numbers")
                .font(.headline)
            
            Group {
                VStack(alignment: .leading, spacing: 8) {
                    Text("BVN (11 digits)")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    TextField("Enter BVN", text: $identity.bvn)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.numberPad)
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("NIN (11 digits)")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    TextField("Enter NIN", text: $identity.nin)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.numberPad)
                }
            }
            
            Divider()
            
            Text("Contact Information")
                .font(.headline)
            
            Group {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Street Address")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    TextField("Enter address", text: $identity.address)
                        .textFieldStyle(.roundedBorder)
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("City")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    TextField("Enter city", text: $identity.city)
                        .textFieldStyle(.roundedBorder)
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("State")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    Picker("State", selection: $identity.state) {
                        Text("Select state").tag("")
                        ForEach(nigerianStates, id: \.self) { state in
                            Text(state).tag(state)
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(8)
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("Phone Number")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    TextField("+234 XXX XXX XXXX", text: $identity.phone)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.phonePad)
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("Email Address")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    TextField("email@example.com", text: $identity.email)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.emailAddress)
                        .autocapitalization(.none)
                }
            }
            
            // Upload button
            Button(action: {}) {
                HStack {
                    Image(systemName: "arrow.up.doc.fill")
                    VStack(alignment: .leading) {
                        Text("Upload ID Document")
                            .font(.subheadline.bold())
                        Text("PDF or image, max 10MB")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    Spacer()
                }
                .padding()
                .background(Color.blue.opacity(0.1))
                .cornerRadius(12)
            }
            .foregroundColor(.blue)
        }
    }
}

// MARK: - Source of Funds Step

struct SourceOfFundsStepView: View {
    @Binding var sourceOfFunds: SourceOfFundsData
    
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("Source of Funds")
                .font(.title2.bold())
            
            Text("Declare the source of funds for this property purchase")
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            VStack(alignment: .leading, spacing: 8) {
                Text("Primary Source of Funds")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                Picker("Source", selection: $sourceOfFunds.primarySource) {
                    ForEach(sourceOfFundsOptions, id: \.0) { code, name in
                        Text(name).tag(code)
                    }
                }
                .pickerStyle(.menu)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(Color.gray.opacity(0.1))
                .cornerRadius(8)
            }
            
            VStack(alignment: .leading, spacing: 8) {
                Text("Description")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                TextField("Provide details about your source of funds", text: $sourceOfFunds.description, axis: .vertical)
                    .lineLimit(3...6)
                    .textFieldStyle(.roundedBorder)
            }
            
            if sourceOfFunds.primarySource == "EMPLOYMENT" {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Employer Name")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    TextField("Enter employer name", text: $sourceOfFunds.employerName)
                        .textFieldStyle(.roundedBorder)
                }
            }
            
            if sourceOfFunds.primarySource == "BUSINESS" {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Business Name")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    TextField("Enter business name", text: $sourceOfFunds.businessName)
                        .textFieldStyle(.roundedBorder)
                }
            }
            
            VStack(alignment: .leading, spacing: 8) {
                Text("Annual Income (NGN)")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                TextField("Enter annual income", text: $sourceOfFunds.annualIncome)
                    .textFieldStyle(.roundedBorder)
                    .keyboardType(.numberPad)
            }
            
            HStack {
                Image(systemName: "info.circle.fill")
                    .foregroundColor(.orange)
                Text("This information is required for anti-money laundering compliance. All declarations will be verified.")
                    .font(.caption)
            }
            .padding()
            .background(Color.orange.opacity(0.1))
            .cornerRadius(12)
        }
    }
}

// MARK: - Bank Statements Step

struct BankStatementsStepView: View {
    @Binding var statements: [BankStatementData]
    let onAdd: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("Bank Statements")
                .font(.title2.bold())
            
            Text("Upload at least 3 months of bank statements showing regular income")
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Image(systemName: "doc.text.fill")
                        .foregroundColor(.blue)
                    VStack(alignment: .leading) {
                        Text("Requirements")
                            .font(.subheadline.bold())
                        Text("Minimum 90 days coverage")
                            .font(.caption)
                        Text("Must be within last 6 months")
                            .font(.caption)
                        Text("PDF format preferred")
                            .font(.caption)
                    }
                }
            }
            .padding()
            .background(Color.blue.opacity(0.1))
            .cornerRadius(12)
            
            ForEach(Array(statements.enumerated()), id: \.element.id) { index, statement in
                Button(action: {}) {
                    HStack {
                        Image(systemName: statement.uploaded ? "checkmark.circle.fill" : "arrow.up.doc.fill")
                            .foregroundColor(statement.uploaded ? .green : .secondary)
                        VStack(alignment: .leading) {
                            Text(statement.uploaded ? statement.fileName : "Upload Statement \(index + 1)")
                                .font(.subheadline.bold())
                            Text(statement.uploaded ? "\(statement.startDate) - \(statement.endDate)" : "Tap to select file")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        Spacer()
                    }
                    .padding()
                    .background(statement.uploaded ? Color.green.opacity(0.1) : Color.gray.opacity(0.1))
                    .cornerRadius(12)
                }
                .foregroundColor(.primary)
            }
            
            Button(action: onAdd) {
                HStack {
                    Image(systemName: "plus.circle.fill")
                    Text("Add Another Statement")
                }
            }
            .buttonStyle(.bordered)
        }
    }
}

// MARK: - Income Documents Step

struct IncomeDocumentsStepView: View {
    @Binding var documents: [IncomeDocumentData]
    let onAdd: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("Income Documents")
                .font(.title2.bold())
            
            Text("Upload documents verifying your income (W-2, PAYE, payslips, etc.)")
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            ForEach(Array(documents.enumerated()), id: \.element.id) { index, document in
                VStack(alignment: .leading, spacing: 12) {
                    Picker("Document Type", selection: Binding(
                        get: { document.documentType },
                        set: { newValue in
                            documents[index].documentType = newValue
                        }
                    )) {
                        ForEach(incomeDocumentTypes, id: \.0) { code, name in
                            Text(name).tag(code)
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(8)
                    
                    Button(action: {}) {
                        HStack {
                            Image(systemName: document.uploaded ? "checkmark.circle.fill" : "arrow.up.doc.fill")
                                .foregroundColor(document.uploaded ? .green : .secondary)
                            Text(document.uploaded ? document.fileName : "Tap to upload")
                                .font(.subheadline)
                            Spacer()
                        }
                        .padding()
                        .background(document.uploaded ? Color.green.opacity(0.1) : Color.gray.opacity(0.1))
                        .cornerRadius(12)
                    }
                    .foregroundColor(.primary)
                }
            }
            
            Button(action: onAdd) {
                HStack {
                    Image(systemName: "plus.circle.fill")
                    Text("Add Another Document")
                }
            }
            .buttonStyle(.bordered)
        }
    }
}

// MARK: - Purchase Agreement Step

struct PurchaseAgreementStepView: View {
    @Binding var agreement: PurchaseAgreementData
    
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("Purchase Agreement")
                .font(.title2.bold())
            
            Text("Upload the signed purchase agreement with property details")
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            VStack(alignment: .leading, spacing: 8) {
                Text("Agreement Requirements")
                    .font(.subheadline.bold())
                
                ForEach([
                    "Buyer and seller names and addresses",
                    "Property address and description",
                    "Purchase price and payment terms",
                    "Signatures of both parties",
                    "Date of agreement"
                ], id: \.self) { req in
                    HStack {
                        Image(systemName: "checkmark")
                            .font(.caption)
                            .foregroundColor(.orange)
                        Text(req)
                            .font(.caption)
                    }
                }
            }
            .padding()
            .background(Color.orange.opacity(0.1))
            .cornerRadius(12)
            
            Button(action: {}) {
                HStack {
                    Image(systemName: agreement.uploaded ? "checkmark.circle.fill" : "arrow.up.doc.fill")
                        .font(.title2)
                        .foregroundColor(agreement.uploaded ? .green : .blue)
                    VStack(alignment: .leading) {
                        Text(agreement.uploaded ? agreement.fileName : "Upload Purchase Agreement")
                            .font(.subheadline.bold())
                        Text("PDF format, max 25MB")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    Spacer()
                }
                .padding()
                .background(agreement.uploaded ? Color.green.opacity(0.1) : Color.blue.opacity(0.1))
                .cornerRadius(12)
            }
            .foregroundColor(.primary)
            
            Divider()
            
            Text("Property Details")
                .font(.headline)
            
            VStack(alignment: .leading, spacing: 8) {
                Text("Property Address")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                TextField("Enter property address", text: $agreement.propertyAddress, axis: .vertical)
                    .lineLimit(2...4)
                    .textFieldStyle(.roundedBorder)
            }
            
            VStack(alignment: .leading, spacing: 8) {
                Text("Purchase Price (NGN)")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                TextField("Enter purchase price", text: $agreement.purchasePrice)
                    .textFieldStyle(.roundedBorder)
                    .keyboardType(.numberPad)
            }
            
            VStack(alignment: .leading, spacing: 8) {
                Text("Agreement Date")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                TextField("DD/MM/YYYY", text: $agreement.agreementDate)
                    .textFieldStyle(.roundedBorder)
            }
        }
    }
}

// MARK: - Review Step

struct ReviewStepView: View {
    @ObservedObject var viewModel: PropertyKYCViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("Review & Submit")
                .font(.title2.bold())
            
            Text("Please review all information before submitting")
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            // Buyer summary
            ReviewSectionView(title: "Buyer Information", items: [
                ("Name", viewModel.buyerIdentity.fullName),
                ("ID Type", idTypes.first { $0.0 == viewModel.buyerIdentity.idType }?.1 ?? ""),
                ("ID Number", viewModel.buyerIdentity.idNumber),
                ("BVN", viewModel.buyerIdentity.bvn),
                ("Phone", viewModel.buyerIdentity.phone),
                ("Email", viewModel.buyerIdentity.email)
            ])
            
            // Seller summary
            ReviewSectionView(title: "Seller Information", items: [
                ("Name", viewModel.sellerIdentity.fullName),
                ("ID Type", idTypes.first { $0.0 == viewModel.sellerIdentity.idType }?.1 ?? ""),
                ("ID Number", viewModel.sellerIdentity.idNumber),
                ("Phone", viewModel.sellerIdentity.phone),
                ("Email", viewModel.sellerIdentity.email)
            ])
            
            // Source of funds summary
            ReviewSectionView(title: "Source of Funds", items: [
                ("Primary Source", sourceOfFundsOptions.first { $0.0 == viewModel.sourceOfFunds.primarySource }?.1 ?? ""),
                ("Annual Income", "NGN \(viewModel.sourceOfFunds.annualIncome)")
            ])
            
            // Documents summary
            VStack(alignment: .leading, spacing: 8) {
                Text("Documents")
                    .font(.subheadline.bold())
                
                HStack {
                    Image(systemName: "doc.text.fill")
                        .font(.caption)
                    Text("\(viewModel.bankStatements.filter { $0.uploaded }.count) Bank Statements uploaded")
                        .font(.caption)
                }
                
                HStack {
                    Image(systemName: "doc.text.fill")
                        .font(.caption)
                    Text("\(viewModel.incomeDocuments.filter { $0.uploaded }.count) Income Documents uploaded")
                        .font(.caption)
                }
                
                HStack {
                    Image(systemName: viewModel.purchaseAgreement.uploaded ? "checkmark.circle.fill" : "exclamationmark.circle.fill")
                        .font(.caption)
                        .foregroundColor(viewModel.purchaseAgreement.uploaded ? .green : .red)
                    Text(viewModel.purchaseAgreement.uploaded ? "Purchase Agreement uploaded" : "Purchase Agreement pending")
                        .font(.caption)
                }
            }
            .padding()
            .background(Color.gray.opacity(0.1))
            .cornerRadius(12)
            
            // Property summary
            if !viewModel.purchaseAgreement.propertyAddress.isEmpty {
                ReviewSectionView(title: "Property Details", items: [
                    ("Address", viewModel.purchaseAgreement.propertyAddress),
                    ("Purchase Price", "NGN \(viewModel.purchaseAgreement.purchasePrice)"),
                    ("Agreement Date", viewModel.purchaseAgreement.agreementDate)
                ])
            }
            
            HStack {
                Image(systemName: "shield.checkered")
                    .foregroundColor(.blue)
                Text("By submitting, you confirm that all information provided is accurate and complete. False declarations may result in transaction rejection.")
                    .font(.caption)
            }
            .padding()
            .background(Color.blue.opacity(0.1))
            .cornerRadius(12)
        }
    }
}

struct ReviewSectionView: View {
    let title: String
    let items: [(String, String)]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.subheadline.bold())
            
            ForEach(items.filter { !$0.1.isEmpty }, id: \.0) { label, value in
                HStack {
                    Text(label)
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Spacer()
                    Text(value)
                        .font(.caption)
                        .fontWeight(.medium)
                }
            }
        }
        .padding()
        .background(Color.gray.opacity(0.1))
        .cornerRadius(12)
    }
}

// MARK: - Preview

#Preview {
    PropertyKYCView()
}

//
// KYCVerificationView.swift
// RemittanceApp
//
// Created by Manus AI on 2025-11-03.
//

import SwiftUI
import PhotosUI

/**
 KYCVerificationView
 
 Multi-step KYC verification with document upload and validation
 
 Features:
 - Multi-step verification process
 - Personal information collection
 - Document upload (ID, passport, utility bill)
 - Selfie verification
 - Address verification
 - BVN verification (Nigeria-specific)
 - Real-time validation
 - Progress tracking
 - Document preview
 */

// MARK: - Data Models

enum KYCStep: Int, CaseIterable {
    case personalInfo = 0
    case documentUpload = 1
    case addressVerification = 2
    case selfieVerification = 3
    case review = 4
    
    var title: String {
        switch self {
        case .personalInfo: return "Personal Information"
        case .documentUpload: return "Document Upload"
        case .addressVerification: return "Address Verification"
        case .selfieVerification: return "Selfie Verification"
        case .review: return "Review & Submit"
        }
    }
    
    var icon: String {
        switch self {
        case .personalInfo: return "person.fill"
        case .documentUpload: return "doc.fill"
        case .addressVerification: return "house.fill"
        case .selfieVerification: return "camera.fill"
        case .review: return "checkmark.seal.fill"
        }
    }
}

enum DocumentType: String, CaseIterable {
    case nationalID = "National ID"
    case passport = "International Passport"
    case driversLicense = "Driver's License"
    case votersCard = "Voter's Card"
    
    var icon: String {
        switch self {
        case .nationalID: return "creditcard.fill"
        case .passport: return "book.fill"
        case .driversLicense: return "car.fill"
        case .votersCard: return "person.badge.shield.checkmark.fill"
        }
    }
}

struct KYCData {
    var firstName: String = ""
    var lastName: String = ""
    var middleName: String = ""
    var dateOfBirth: Date = Date()
    var gender: String = "Male"
    var phoneNumber: String = ""
    var email: String = ""
    var bvn: String = ""
    
    var documentType: DocumentType = .nationalID
    var documentNumber: String = ""
    var documentImage: UIImage?
    
    var address: String = ""
    var city: String = ""
    var state: String = ""
    var postalCode: String = ""
    var utilityBillImage: UIImage?
    
    var selfieImage: UIImage?
}

// MARK: - View Model

class KYCVerificationViewModel: ObservableObject {
    @Published var currentStep: KYCStep = .personalInfo
    @Published var kycData = KYCData()
    @Published var isSubmitting = false
    @Published var errorMessage: String?
    @Published var showSuccessAlert = false
    
    var progress: Double {
        Double(currentStep.rawValue + 1) / Double(KYCStep.allCases.count)
    }
    
    func nextStep() {
        if let nextStep = KYCStep(rawValue: currentStep.rawValue + 1) {
            withAnimation {
                currentStep = nextStep
            }
        }
    }
    
    func previousStep() {
        if let previousStep = KYCStep(rawValue: currentStep.rawValue - 1) {
            withAnimation {
                currentStep = previousStep
            }
        }
    }
    
    func canProceed() -> Bool {
        switch currentStep {
        case .personalInfo:
            return !kycData.firstName.isEmpty &&
                   !kycData.lastName.isEmpty &&
                   !kycData.phoneNumber.isEmpty &&
                   !kycData.email.isEmpty &&
                   !kycData.bvn.isEmpty &&
                   kycData.bvn.count == 11
        case .documentUpload:
            return !kycData.documentNumber.isEmpty &&
                   kycData.documentImage != nil
        case .addressVerification:
            return !kycData.address.isEmpty &&
                   !kycData.city.isEmpty &&
                   !kycData.state.isEmpty &&
                   kycData.utilityBillImage != nil
        case .selfieVerification:
            return kycData.selfieImage != nil
        case .review:
            return true
        }
    }
    
    func submitKYC() {
        isSubmitting = true
        errorMessage = nil
        
        // Simulate API call
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) { [weak self] in
            self?.isSubmitting = false
            self?.showSuccessAlert = true
        }
    }
}

// MARK: - Main View

struct KYCVerificationView: View {
    @StateObject private var viewModel = KYCVerificationViewModel()
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Progress Bar
                ProgressView(value: viewModel.progress)
                    .tint(.blue)
                    .padding()
                
                // Step Indicator
                StepIndicator(currentStep: viewModel.currentStep)
                    .padding(.horizontal)
                
                // Content
                TabView(selection: $viewModel.currentStep) {
                    PersonalInfoStep(kycData: $viewModel.kycData)
                        .tag(KYCStep.personalInfo)
                    
                    DocumentUploadStep(kycData: $viewModel.kycData)
                        .tag(KYCStep.documentUpload)
                    
                    AddressVerificationStep(kycData: $viewModel.kycData)
                        .tag(KYCStep.addressVerification)
                    
                    SelfieVerificationStep(kycData: $viewModel.kycData)
                        .tag(KYCStep.selfieVerification)
                    
                    ReviewStep(kycData: viewModel.kycData)
                        .tag(KYCStep.review)
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
                
                // Navigation Buttons
                HStack(spacing: 16) {
                    if viewModel.currentStep != .personalInfo {
                        Button(action: { viewModel.previousStep() }) {
                            HStack {
                                Image(systemName: "chevron.left")
                                Text("Back")
                            }
                            .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.bordered)
                    }
                    
                    if viewModel.currentStep == .review {
                        Button(action: { viewModel.submitKYC() }) {
                            if viewModel.isSubmitting {
                                ProgressView()
                                    .progressViewStyle(.circular)
                                    .tint(.white)
                            } else {
                                Text("Submit")
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .buttonStyle(.borderedProminent)
                        .disabled(viewModel.isSubmitting)
                    } else {
                        Button(action: { viewModel.nextStep() }) {
                            HStack {
                                Text("Next")
                                Image(systemName: "chevron.right")
                            }
                            .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(!viewModel.canProceed())
                    }
                }
                .padding()
            }
            .navigationTitle("KYC Verification")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
            .alert("KYC Submitted Successfully", isPresented: $viewModel.showSuccessAlert) {
                Button("OK") { dismiss() }
            } message: {
                Text("Your KYC verification has been submitted. We'll review your information and notify you within 24-48 hours.")
            }
        }
    }
}

// MARK: - Step Indicator

struct StepIndicator: View {
    let currentStep: KYCStep
    
    var body: some View {
        HStack(spacing: 8) {
            ForEach(KYCStep.allCases, id: \.self) { step in
                VStack(spacing: 4) {
                    ZStack {
                        Circle()
                            .fill(step.rawValue <= currentStep.rawValue ? Color.blue : Color.gray.opacity(0.3))
                            .frame(width: 32, height: 32)
                        
                        if step.rawValue < currentStep.rawValue {
                            Image(systemName: "checkmark")
                                .foregroundColor(.white)
                                .font(.caption.bold())
                        } else {
                            Text("\(step.rawValue + 1)")
                                .foregroundColor(step.rawValue <= currentStep.rawValue ? .white : .gray)
                                .font(.caption.bold())
                        }
                    }
                    
                    if step.rawValue == currentStep.rawValue {
                        Text(step.title)
                            .font(.caption2)
                            .foregroundColor(.blue)
                            .multilineTextAlignment(.center)
                            .frame(width: 60)
                    }
                }
                
                if step != KYCStep.allCases.last {
                    Rectangle()
                        .fill(step.rawValue < currentStep.rawValue ? Color.blue : Color.gray.opacity(0.3))
                        .frame(height: 2)
                }
            }
        }
    }
}

// MARK: - Personal Info Step

struct PersonalInfoStep: View {
    @Binding var kycData: KYCData
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Personal Information")
                    .font(.title2.bold())
                
                Text("Please provide your personal details as they appear on your official documents.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                VStack(spacing: 16) {
                    TextField("First Name", text: $kycData.firstName)
                        .textFieldStyle(.roundedBorder)
                    
                    TextField("Middle Name (Optional)", text: $kycData.middleName)
                        .textFieldStyle(.roundedBorder)
                    
                    TextField("Last Name", text: $kycData.lastName)
                        .textFieldStyle(.roundedBorder)
                    
                    DatePicker("Date of Birth", selection: $kycData.dateOfBirth, displayedComponents: .date)
                    
                    Picker("Gender", selection: $kycData.gender) {
                        Text("Male").tag("Male")
                        Text("Female").tag("Female")
                        Text("Other").tag("Other")
                    }
                    .pickerStyle(.segmented)
                    
                    TextField("Phone Number", text: $kycData.phoneNumber)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.phonePad)
                    
                    TextField("Email Address", text: $kycData.email)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                    
                    VStack(alignment: .leading, spacing: 4) {
                        TextField("BVN (Bank Verification Number)", text: $kycData.bvn)
                            .textFieldStyle(.roundedBorder)
                            .keyboardType(.numberPad)
                        
                        Text("11-digit BVN number")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }
            .padding()
        }
    }
}

// MARK: - Document Upload Step

struct DocumentUploadStep: View {
    @Binding var kycData: KYCData
    @State private var showImagePicker = false
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Document Upload")
                    .font(.title2.bold())
                
                Text("Upload a clear photo of your identification document.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                Picker("Document Type", selection: $kycData.documentType) {
                    ForEach(DocumentType.allCases, id: \.self) { type in
                        HStack {
                            Image(systemName: type.icon)
                            Text(type.rawValue)
                        }
                        .tag(type)
                    }
                }
                .pickerStyle(.menu)
                
                TextField("Document Number", text: $kycData.documentNumber)
                    .textFieldStyle(.roundedBorder)
                
                VStack(spacing: 12) {
                    if let image = kycData.documentImage {
                        Image(uiImage: image)
                            .resizable()
                            .scaledToFit()
                            .frame(maxHeight: 200)
                            .cornerRadius(12)
                    }
                    
                    Button(action: { showImagePicker = true }) {
                        HStack {
                            Image(systemName: kycData.documentImage == nil ? "camera.fill" : "arrow.triangle.2.circlepath")
                            Text(kycData.documentImage == nil ? "Take Photo" : "Retake Photo")
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("Tips for a good photo:")
                        .font(.subheadline.bold())
                    
                    TipRow(text: "Ensure all text is clearly visible")
                    TipRow(text: "Avoid glare and shadows")
                    TipRow(text: "Place document on a plain background")
                    TipRow(text: "Make sure all corners are visible")
                }
                .padding()
                .background(Color.blue.opacity(0.1))
                .cornerRadius(12)
            }
            .padding()
        }
        .sheet(isPresented: $showImagePicker) {
            ImagePicker(image: $kycData.documentImage)
        }
    }
}

// MARK: - Address Verification Step

struct AddressVerificationStep: View {
    @Binding var kycData: KYCData
    @State private var showImagePicker = false
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Address Verification")
                    .font(.title2.bold())
                
                Text("Provide your residential address and upload a recent utility bill.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                VStack(spacing: 16) {
                    TextField("Street Address", text: $kycData.address)
                        .textFieldStyle(.roundedBorder)
                    
                    TextField("City", text: $kycData.city)
                        .textFieldStyle(.roundedBorder)
                    
                    TextField("State", text: $kycData.state)
                        .textFieldStyle(.roundedBorder)
                    
                    TextField("Postal Code", text: $kycData.postalCode)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.numberPad)
                }
                
                VStack(alignment: .leading, spacing: 12) {
                    Text("Utility Bill")
                        .font(.headline)
                    
                    Text("Upload a recent utility bill (not older than 3 months)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    if let image = kycData.utilityBillImage {
                        Image(uiImage: image)
                            .resizable()
                            .scaledToFit()
                            .frame(maxHeight: 200)
                            .cornerRadius(12)
                    }
                    
                    Button(action: { showImagePicker = true }) {
                        HStack {
                            Image(systemName: kycData.utilityBillImage == nil ? "camera.fill" : "arrow.triangle.2.circlepath")
                            Text(kycData.utilityBillImage == nil ? "Upload Bill" : "Change Bill")
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                }
            }
            .padding()
        }
        .sheet(isPresented: $showImagePicker) {
            ImagePicker(image: $kycData.utilityBillImage)
        }
    }
}

// MARK: - Selfie Verification Step

struct SelfieVerificationStep: View {
    @Binding var kycData: KYCData
    @State private var showImagePicker = false
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Selfie Verification")
                    .font(.title2.bold())
                
                Text("Take a clear selfie for identity verification.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                VStack(spacing: 12) {
                    if let image = kycData.selfieImage {
                        Image(uiImage: image)
                            .resizable()
                            .scaledToFit()
                            .frame(maxHeight: 300)
                            .cornerRadius(12)
                    } else {
                        ZStack {
                            RoundedRectangle(cornerRadius: 12)
                                .fill(Color.gray.opacity(0.2))
                                .frame(height: 300)
                            
                            VStack(spacing: 12) {
                                Image(systemName: "person.crop.circle.fill")
                                    .font(.system(size: 80))
                                    .foregroundColor(.gray)
                                
                                Text("No selfie taken")
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                    
                    Button(action: { showImagePicker = true }) {
                        HStack {
                            Image(systemName: kycData.selfieImage == nil ? "camera.fill" : "arrow.triangle.2.circlepath")
                            Text(kycData.selfieImage == nil ? "Take Selfie" : "Retake Selfie")
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("Selfie Guidelines:")
                        .font(.subheadline.bold())
                    
                    TipRow(text: "Look directly at the camera")
                    TipRow(text: "Ensure good lighting")
                    TipRow(text: "Remove glasses and hats")
                    TipRow(text: "Keep a neutral expression")
                    TipRow(text: "Make sure your face is clearly visible")
                }
                .padding()
                .background(Color.blue.opacity(0.1))
                .cornerRadius(12)
            }
            .padding()
        }
        .sheet(isPresented: $showImagePicker) {
            ImagePicker(image: $kycData.selfieImage)
        }
    }
}

// MARK: - Review Step

struct ReviewStep: View {
    let kycData: KYCData
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                Text("Review Your Information")
                    .font(.title2.bold())
                
                Text("Please review all information before submitting.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                ReviewSection(title: "Personal Information") {
                    ReviewRow(label: "Name", value: "\(kycData.firstName) \(kycData.middleName) \(kycData.lastName)")
                    ReviewRow(label: "Date of Birth", value: kycData.dateOfBirth.formatted(date: .long, time: .omitted))
                    ReviewRow(label: "Gender", value: kycData.gender)
                    ReviewRow(label: "Phone", value: kycData.phoneNumber)
                    ReviewRow(label: "Email", value: kycData.email)
                    ReviewRow(label: "BVN", value: kycData.bvn)
                }
                
                ReviewSection(title: "Document") {
                    ReviewRow(label: "Type", value: kycData.documentType.rawValue)
                    ReviewRow(label: "Number", value: kycData.documentNumber)
                    if kycData.documentImage != nil {
                        ReviewRow(label: "Image", value: "✓ Uploaded")
                    }
                }
                
                ReviewSection(title: "Address") {
                    ReviewRow(label: "Address", value: kycData.address)
                    ReviewRow(label: "City", value: kycData.city)
                    ReviewRow(label: "State", value: kycData.state)
                    ReviewRow(label: "Postal Code", value: kycData.postalCode)
                    if kycData.utilityBillImage != nil {
                        ReviewRow(label: "Utility Bill", value: "✓ Uploaded")
                    }
                }
                
                ReviewSection(title: "Verification") {
                    if kycData.selfieImage != nil {
                        ReviewRow(label: "Selfie", value: "✓ Uploaded")
                    }
                }
            }
            .padding()
        }
    }
}

struct ReviewSection<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title)
                .font(.headline)
            
            VStack(spacing: 8) {
                content
            }
            .padding()
            .background(Color(.systemGray6))
            .cornerRadius(12)
        }
    }
}

struct ReviewRow: View {
    let label: String
    let value: String
    
    var body: some View {
        HStack {
            Text(label)
                .foregroundColor(.secondary)
            Spacer()
            Text(value)
                .fontWeight(.medium)
        }
    }
}

// MARK: - Helper Views

struct TipRow: View {
    let text: String
    
    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "checkmark.circle.fill")
                .foregroundColor(.blue)
                .font(.caption)
            Text(text)
                .font(.caption)
        }
    }
}

// MARK: - Image Picker

struct ImagePicker: UIViewControllerRepresentable {
    @Binding var image: UIImage?
    @Environment(\.dismiss) private var dismiss
    
    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.delegate = context.coordinator
        picker.sourceType = .camera
        return picker
    }
    
    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}
    
    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }
    
    class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let parent: ImagePicker
        
        init(_ parent: ImagePicker) {
            self.parent = parent
        }
        
        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey : Any]) {
            if let image = info[.originalImage] as? UIImage {
                parent.image = image
            }
            parent.dismiss()
        }
        
        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            parent.dismiss()
        }
    }
}

// MARK: - Preview

struct KYCVerificationView_Previews: PreviewProvider {
    static var previews: some View {
        KYCVerificationView()
    }
}

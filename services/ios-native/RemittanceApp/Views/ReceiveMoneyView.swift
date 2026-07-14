//
// ReceiveMoneyView.swift
// RemittanceApp
//
// Created by Manus AI on 2025-11-03.
//

import SwiftUI
import CoreImage.CIFilterBuiltins

/**
 ReceiveMoneyView
 
 Display QR code, account details, and share options for receiving money
 
 Features:
 - QR code generation with user account details
 - Account information display (account number, bank details)
 - Share functionality (QR code, account details)
 - Copy to clipboard
 - Multiple payment method options
 - Transaction history for received payments
 */

// MARK: - Data Models

struct AccountDetails {
    let accountNumber: String
    let accountName: String
    let bankName: String
    let bankCode: String
    let walletAddress: String
    let phoneNumber: String
}

struct PaymentMethod: Identifiable {
    let id = UUID()
    let name: String
    let icon: String
    let details: String
}

// MARK: - View Model

class ReceiveMoneyViewModel: ObservableObject {
    @Published var accountDetails: AccountDetails?
    @Published var qrCodeImage: UIImage?
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var showShareSheet = false
    @Published var copiedField: String?
    
    init() {
        loadAccountDetails()
    }
    
    func loadAccountDetails() {
        isLoading = true
        errorMessage = nil
        
        // Simulate API call
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [weak self] in
            self?.accountDetails = AccountDetails(
                accountNumber: "0123456789",
                accountName: "Adebayo Okonkwo",
                bankName: "First Bank of Nigeria",
                bankCode: "011",
                walletAddress: "wallet_abc123xyz",
                phoneNumber: "+234 803 456 7890"
            )
            
            self?.generateQRCode()
            self?.isLoading = false
        }
    }
    
    func generateQRCode() {
        guard let details = accountDetails else { return }
        
        // Create QR code data string
        let qrString = """
        {
            "type": "receive_payment",
            "account_number": "\(details.accountNumber)",
            "account_name": "\(details.accountName)",
            "bank_name": "\(details.bankName)",
            "bank_code": "\(details.bankCode)",
            "wallet_address": "\(details.walletAddress)",
            "phone_number": "\(details.phoneNumber)"
        }
        """
        
        let context = CIContext()
        let filter = CIFilter.qrCodeGenerator()
        
        guard let data = qrString.data(using: .utf8) else { return }
        filter.setValue(data, forKey: "inputMessage")
        filter.setValue("H", forKey: "inputCorrectionLevel")
        
        guard let outputImage = filter.outputImage else { return }
        
        // Scale up the QR code
        let transform = CGAffineTransform(scaleX: 10, y: 10)
        let scaledImage = outputImage.transformed(by: transform)
        
        if let cgImage = context.createCGImage(scaledImage, from: scaledImage.extent) {
            qrCodeImage = UIImage(cgImage: cgImage)
        }
    }
    
    func copyToClipboard(_ text: String, field: String) {
        UIPasteboard.general.string = text
        copiedField = field
        
        // Reset after 2 seconds
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) { [weak self] in
            self?.copiedField = nil
        }
    }
    
    func shareAccountDetails() {
        showShareSheet = true
    }
}

// MARK: - Main View

struct ReceiveMoneyView: View {
    @StateObject private var viewModel = ReceiveMoneyViewModel()
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 24) {
                    if viewModel.isLoading {
                        ProgressView("Loading account details...")
                            .padding()
                    } else if let error = viewModel.errorMessage {
                        ErrorView(message: error) {
                            viewModel.loadAccountDetails()
                        }
                    } else {
                        // QR Code Section
                        QRCodeSection(
                            qrImage: viewModel.qrCodeImage,
                            onShare: { viewModel.shareAccountDetails() }
                        )
                        
                        // Account Details Section
                        if let details = viewModel.accountDetails {
                            AccountDetailsSection(
                                details: details,
                                copiedField: viewModel.copiedField,
                                onCopy: { text, field in
                                    viewModel.copyToClipboard(text, field: field)
                                }
                            )
                        }
                        
                        // Payment Methods Section
                        PaymentMethodsSection()
                        
                        // Instructions Section
                        InstructionsSection()
                    }
                }
                .padding()
            }
            .navigationTitle("Receive Money")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { viewModel.shareAccountDetails() }) {
                        Image(systemName: "square.and.arrow.up")
                    }
                }
            }
            .sheet(isPresented: $viewModel.showShareSheet) {
                if let details = viewModel.accountDetails {
                    ShareSheet(items: [createShareText(details: details)])
                }
            }
        }
    }
    
    private func createShareText(details: AccountDetails) -> String {
        """
        Send money to:
        
        Account Name: \(details.accountName)
        Account Number: \(details.accountNumber)
        Bank: \(details.bankName)
        
        Or use:
        Phone: \(details.phoneNumber)
        Wallet: \(details.walletAddress)
        """
    }
}

// MARK: - QR Code Section

struct QRCodeSection: View {
    let qrImage: UIImage?
    let onShare: () -> Void
    
    var body: some View {
        VStack(spacing: 16) {
            Text("Scan to Pay")
                .font(.headline)
            
            if let image = qrImage {
                Image(uiImage: image)
                    .interpolation(.none)
                    .resizable()
                    .scaledToFit()
                    .frame(width: 250, height: 250)
                    .background(Color.white)
                    .cornerRadius(12)
                    .shadow(radius: 4)
            } else {
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color.gray.opacity(0.2))
                    .frame(width: 250, height: 250)
                    .overlay(
                        ProgressView()
                    )
            }
            
            Button(action: onShare) {
                HStack {
                    Image(systemName: "square.and.arrow.up")
                    Text("Share QR Code")
                }
                .font(.subheadline.weight(.medium))
            }
            .buttonStyle(.bordered)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(radius: 2)
    }
}

// MARK: - Account Details Section

struct AccountDetailsSection: View {
    let details: AccountDetails
    let copiedField: String?
    let onCopy: (String, String) -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Account Details")
                .font(.headline)
            
            AccountDetailRow(
                title: "Account Name",
                value: details.accountName,
                icon: "person.fill",
                isCopied: copiedField == "name",
                onCopy: { onCopy(details.accountName, "name") }
            )
            
            AccountDetailRow(
                title: "Account Number",
                value: details.accountNumber,
                icon: "number",
                isCopied: copiedField == "account",
                onCopy: { onCopy(details.accountNumber, "account") }
            )
            
            AccountDetailRow(
                title: "Bank",
                value: details.bankName,
                icon: "building.2.fill",
                isCopied: copiedField == "bank",
                onCopy: { onCopy(details.bankName, "bank") }
            )
            
            AccountDetailRow(
                title: "Phone Number",
                value: details.phoneNumber,
                icon: "phone.fill",
                isCopied: copiedField == "phone",
                onCopy: { onCopy(details.phoneNumber, "phone") }
            )
            
            AccountDetailRow(
                title: "Wallet Address",
                value: details.walletAddress,
                icon: "wallet.pass.fill",
                isCopied: copiedField == "wallet",
                onCopy: { onCopy(details.walletAddress, "wallet") }
            )
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(radius: 2)
    }
}

struct AccountDetailRow: View {
    let title: String
    let value: String
    let icon: String
    let isCopied: Bool
    let onCopy: () -> Void
    
    var body: some View {
        HStack {
            Image(systemName: icon)
                .foregroundColor(.blue)
                .frame(width: 24)
            
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text(value)
                    .font(.body)
            }
            
            Spacer()
            
            Button(action: onCopy) {
                Image(systemName: isCopied ? "checkmark.circle.fill" : "doc.on.doc")
                    .foregroundColor(isCopied ? .green : .blue)
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Payment Methods Section

struct PaymentMethodsSection: View {
    let methods = [
        PaymentMethod(name: "Bank Transfer", icon: "building.columns.fill", details: "Use account number"),
        PaymentMethod(name: "Mobile Money", icon: "phone.fill", details: "Use phone number"),
        PaymentMethod(name: "Wallet Transfer", icon: "wallet.pass.fill", details: "Use wallet address"),
        PaymentMethod(name: "QR Code", icon: "qrcode", details: "Scan to pay")
    ]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Payment Methods")
                .font(.headline)
            
            ForEach(methods) { method in
                HStack {
                    Image(systemName: method.icon)
                        .foregroundColor(.blue)
                        .frame(width: 32)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text(method.name)
                            .font(.subheadline.weight(.medium))
                        Text(method.details)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    
                    Spacer()
                    
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                }
                .padding(.vertical, 8)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(radius: 2)
    }
}

// MARK: - Instructions Section

struct InstructionsSection: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("How to Receive Money")
                .font(.headline)
            
            InstructionStep(number: 1, text: "Share your QR code or account details with the sender")
            InstructionStep(number: 2, text: "Sender initiates payment using any of the available methods")
            InstructionStep(number: 3, text: "You'll receive a notification when payment is received")
            InstructionStep(number: 4, text: "Money will be instantly credited to your wallet")
        }
        .padding()
        .background(Color.blue.opacity(0.1))
        .cornerRadius(16)
    }
}

struct InstructionStep: View {
    let number: Int
    let text: String
    
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Text("\(number)")
                .font(.caption.weight(.bold))
                .foregroundColor(.white)
                .frame(width: 24, height: 24)
                .background(Color.blue)
                .clipShape(Circle())
            
            Text(text)
                .font(.subheadline)
                .foregroundColor(.primary)
        }
    }
}

// MARK: - Error View

struct ErrorView: View {
    let message: String
    let retry: () -> Void
    
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 48))
                .foregroundColor(.orange)
            
            Text(message)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            
            Button("Retry", action: retry)
                .buttonStyle(.borderedProminent)
        }
        .padding()
    }
}

// MARK: - Share Sheet

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]
    
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }
    
    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}

// MARK: - Preview

struct ReceiveMoneyView_Previews: PreviewProvider {
    static var previews: some View {
        ReceiveMoneyView()
    }
}

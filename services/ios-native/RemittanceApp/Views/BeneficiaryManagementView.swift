//
// BeneficiaryManagementView.swift
// RemittanceApp
//
// Created by Manus AI on 2025-11-03.
//

import SwiftUI

/**
 BeneficiaryManagementView
 
 Add, edit, delete beneficiaries with recent recipients list
 
 Features:
 - List of saved beneficiaries
 - Add new beneficiary with form validation
 - Edit existing beneficiary
 - Delete beneficiary with confirmation
 - Search and filter beneficiaries
 - Recent recipients
 - Favorite beneficiaries
 - Quick send to beneficiary
 */

// MARK: - Data Models

struct Beneficiary: Identifiable, Codable {
    let id: UUID
    var name: String
    var accountNumber: String
    var bankName: String
    var bankCode: String
    var phoneNumber: String?
    var email: String?
    var isFavorite: Bool
    var lastUsed: Date?
    var totalTransactions: Int
    
    init(id: UUID = UUID(), name: String, accountNumber: String, bankName: String, bankCode: String, phoneNumber: String? = nil, email: String? = nil, isFavorite: Bool = false, lastUsed: Date? = nil, totalTransactions: Int = 0) {
        self.id = id
        self.name = name
        self.accountNumber = accountNumber
        self.bankName = bankName
        self.bankCode = bankCode
        self.phoneNumber = phoneNumber
        self.email = email
        self.isFavorite = isFavorite
        self.lastUsed = lastUsed
        self.totalTransactions = totalTransactions
    }
}

// MARK: - View Model

class BeneficiaryManagementViewModel: ObservableObject {
    @Published var beneficiaries: [Beneficiary] = []
    @Published var searchText = ""
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var showAddSheet = false
    @Published var selectedBeneficiary: Beneficiary?
    @Published var showDeleteAlert = false
    @Published var beneficiaryToDelete: Beneficiary?
    
    var filteredBeneficiaries: [Beneficiary] {
        if searchText.isEmpty {
            return beneficiaries
        }
        return beneficiaries.filter { beneficiary in
            beneficiary.name.localizedCaseInsensitiveContains(searchText) ||
            beneficiary.accountNumber.contains(searchText) ||
            beneficiary.bankName.localizedCaseInsensitiveContains(searchText)
        }
    }
    
    var favoriteBeneficiaries: [Beneficiary] {
        beneficiaries.filter { $0.isFavorite }
    }
    
    var recentBeneficiaries: [Beneficiary] {
        beneficiaries
            .filter { $0.lastUsed != nil }
            .sorted { ($0.lastUsed ?? Date.distantPast) > ($1.lastUsed ?? Date.distantPast) }
            .prefix(5)
            .map { $0 }
    }
    
    init() {
        loadBeneficiaries()
    }
    
    func loadBeneficiaries() {
        isLoading = true
        errorMessage = nil
        
        // Simulate API call
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
            self?.beneficiaries = [
                Beneficiary(
                    name: "Chioma Adeyemi",
                    accountNumber: "0123456789",
                    bankName: "GTBank",
                    bankCode: "058",
                    phoneNumber: "+234 801 234 5678",
                    isFavorite: true,
                    lastUsed: Date().addingTimeInterval(-86400),
                    totalTransactions: 15
                ),
                Beneficiary(
                    name: "Emeka Okafor",
                    accountNumber: "9876543210",
                    bankName: "Access Bank",
                    bankCode: "044",
                    phoneNumber: "+234 802 345 6789",
                    isFavorite: false,
                    lastUsed: Date().addingTimeInterval(-172800),
                    totalTransactions: 8
                ),
                Beneficiary(
                    name: "Fatima Ibrahim",
                    accountNumber: "5555666677",
                    bankName: "Zenith Bank",
                    bankCode: "057",
                    isFavorite: true,
                    lastUsed: Date().addingTimeInterval(-259200),
                    totalTransactions: 22
                ),
                Beneficiary(
                    name: "Oluwaseun Balogun",
                    accountNumber: "1111222233",
                    bankName: "First Bank",
                    bankCode: "011",
                    phoneNumber: "+234 803 456 7890",
                    isFavorite: false,
                    totalTransactions: 3
                )
            ]
            self?.isLoading = false
        }
    }
    
    func addBeneficiary(_ beneficiary: Beneficiary) {
        beneficiaries.append(beneficiary)
        // In real app, save to API and local storage
    }
    
    func updateBeneficiary(_ beneficiary: Beneficiary) {
        if let index = beneficiaries.firstIndex(where: { $0.id == beneficiary.id }) {
            beneficiaries[index] = beneficiary
        }
    }
    
    func toggleFavorite(_ beneficiary: Beneficiary) {
        if let index = beneficiaries.firstIndex(where: { $0.id == beneficiary.id }) {
            beneficiaries[index].isFavorite.toggle()
        }
    }
    
    func deleteBeneficiary(_ beneficiary: Beneficiary) {
        beneficiaries.removeAll { $0.id == beneficiary.id }
        // In real app, delete from API and local storage
    }
    
    func confirmDelete(_ beneficiary: Beneficiary) {
        beneficiaryToDelete = beneficiary
        showDeleteAlert = true
    }
}

// MARK: - Main View

struct BeneficiaryManagementView: View {
    @StateObject private var viewModel = BeneficiaryManagementViewModel()
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationView {
            ZStack {
                if viewModel.isLoading {
                    ProgressView("Loading beneficiaries...")
                } else if let error = viewModel.errorMessage {
                    ErrorView(message: error) {
                        viewModel.loadBeneficiaries()
                    }
                } else {
                    ScrollView {
                        VStack(spacing: 20) {
                            // Search Bar
                            SearchBar(text: $viewModel.searchText)
                            
                            // Favorites Section
                            if !viewModel.favoriteBeneficiaries.isEmpty && viewModel.searchText.isEmpty {
                                FavoritesSection(
                                    beneficiaries: viewModel.favoriteBeneficiaries,
                                    onSelect: { beneficiary in
                                        viewModel.selectedBeneficiary = beneficiary
                                    },
                                    onToggleFavorite: { beneficiary in
                                        viewModel.toggleFavorite(beneficiary)
                                    }
                                )
                            }
                            
                            // Recent Section
                            if !viewModel.recentBeneficiaries.isEmpty && viewModel.searchText.isEmpty {
                                RecentSection(
                                    beneficiaries: viewModel.recentBeneficiaries,
                                    onSelect: { beneficiary in
                                        viewModel.selectedBeneficiary = beneficiary
                                    }
                                )
                            }
                            
                            // All Beneficiaries Section
                            AllBeneficiariesSection(
                                beneficiaries: viewModel.filteredBeneficiaries,
                                onSelect: { beneficiary in
                                    viewModel.selectedBeneficiary = beneficiary
                                },
                                onToggleFavorite: { beneficiary in
                                    viewModel.toggleFavorite(beneficiary)
                                },
                                onDelete: { beneficiary in
                                    viewModel.confirmDelete(beneficiary)
                                }
                            )
                        }
                        .padding()
                    }
                }
            }
            .navigationTitle("Beneficiaries")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { viewModel.showAddSheet = true }) {
                        Image(systemName: "plus.circle.fill")
                            .font(.title3)
                    }
                }
            }
            .sheet(isPresented: $viewModel.showAddSheet) {
                AddBeneficiaryView { beneficiary in
                    viewModel.addBeneficiary(beneficiary)
                }
            }
            .sheet(item: $viewModel.selectedBeneficiary) { beneficiary in
                BeneficiaryDetailView(
                    beneficiary: beneficiary,
                    onUpdate: { updated in
                        viewModel.updateBeneficiary(updated)
                    },
                    onDelete: {
                        viewModel.confirmDelete(beneficiary)
                    }
                )
            }
            .alert("Delete Beneficiary", isPresented: $viewModel.showDeleteAlert) {
                Button("Cancel", role: .cancel) {}
                Button("Delete", role: .destructive) {
                    if let beneficiary = viewModel.beneficiaryToDelete {
                        viewModel.deleteBeneficiary(beneficiary)
                    }
                }
            } message: {
                Text("Are you sure you want to delete this beneficiary? This action cannot be undone.")
            }
        }
    }
}

// MARK: - Search Bar

struct SearchBar: View {
    @Binding var text: String
    
    var body: some View {
        HStack {
            Image(systemName: "magnifyingglass")
                .foregroundColor(.gray)
            
            TextField("Search beneficiaries...", text: $text)
                .textFieldStyle(.plain)
            
            if !text.isEmpty {
                Button(action: { text = "" }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.gray)
                }
            }
        }
        .padding(12)
        .background(Color(.systemGray6))
        .cornerRadius(10)
    }
}

// MARK: - Favorites Section

struct FavoritesSection: View {
    let beneficiaries: [Beneficiary]
    let onSelect: (Beneficiary) -> Void
    let onToggleFavorite: (Beneficiary) -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Favorites")
                .font(.headline)
            
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(beneficiaries) { beneficiary in
                        FavoriteCard(
                            beneficiary: beneficiary,
                            onSelect: { onSelect(beneficiary) }
                        )
                    }
                }
            }
        }
    }
}

struct FavoriteCard: View {
    let beneficiary: Beneficiary
    let onSelect: () -> Void
    
    var body: some View {
        Button(action: onSelect) {
            VStack(spacing: 8) {
                ZStack {
                    Circle()
                        .fill(Color.blue.opacity(0.2))
                        .frame(width: 60, height: 60)
                    
                    Text(beneficiary.name.prefix(1))
                        .font(.title2.bold())
                        .foregroundColor(.blue)
                }
                
                Text(beneficiary.name)
                    .font(.caption)
                    .foregroundColor(.primary)
                    .lineLimit(2)
                    .multilineTextAlignment(.center)
                    .frame(width: 80)
            }
            .padding()
            .background(Color(.systemBackground))
            .cornerRadius(12)
            .shadow(radius: 2)
        }
    }
}

// MARK: - Recent Section

struct RecentSection: View {
    let beneficiaries: [Beneficiary]
    let onSelect: (Beneficiary) -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Recent")
                .font(.headline)
            
            ForEach(beneficiaries) { beneficiary in
                Button(action: { onSelect(beneficiary) }) {
                    BeneficiaryRow(beneficiary: beneficiary, showChevron: true)
                }
            }
        }
    }
}

// MARK: - All Beneficiaries Section

struct AllBeneficiariesSection: View {
    let beneficiaries: [Beneficiary]
    let onSelect: (Beneficiary) -> Void
    let onToggleFavorite: (Beneficiary) -> Void
    let onDelete: (Beneficiary) -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("All Beneficiaries (\(beneficiaries.count))")
                .font(.headline)
            
            ForEach(beneficiaries) { beneficiary in
                BeneficiaryRow(
                    beneficiary: beneficiary,
                    showChevron: true,
                    onTap: { onSelect(beneficiary) },
                    onToggleFavorite: { onToggleFavorite(beneficiary) },
                    onDelete: { onDelete(beneficiary) }
                )
            }
        }
    }
}

// MARK: - Beneficiary Row

struct BeneficiaryRow: View {
    let beneficiary: Beneficiary
    var showChevron: Bool = false
    var onTap: (() -> Void)? = nil
    var onToggleFavorite: (() -> Void)? = nil
    var onDelete: (() -> Void)? = nil
    
    var body: some View {
        HStack(spacing: 12) {
            // Avatar
            ZStack {
                Circle()
                    .fill(Color.blue.opacity(0.2))
                    .frame(width: 50, height: 50)
                
                Text(beneficiary.name.prefix(1))
                    .font(.title3.bold())
                    .foregroundColor(.blue)
            }
            
            // Details
            VStack(alignment: .leading, spacing: 4) {
                Text(beneficiary.name)
                    .font(.subheadline.weight(.medium))
                    .foregroundColor(.primary)
                
                Text("\(beneficiary.bankName) • \(beneficiary.accountNumber)")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                if beneficiary.totalTransactions > 0 {
                    Text("\(beneficiary.totalTransactions) transactions")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
            
            Spacer()
            
            // Favorite Button
            if let toggleFavorite = onToggleFavorite {
                Button(action: toggleFavorite) {
                    Image(systemName: beneficiary.isFavorite ? "star.fill" : "star")
                        .foregroundColor(beneficiary.isFavorite ? .yellow : .gray)
                }
                .buttonStyle(.plain)
            }
            
            if showChevron {
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundColor(.gray)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 1)
        .contentShape(Rectangle())
        .onTapGesture {
            onTap?()
        }
        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
            if let delete = onDelete {
                Button(role: .destructive, action: delete) {
                    Label("Delete", systemImage: "trash")
                }
            }
        }
    }
}

// MARK: - Add Beneficiary View

struct AddBeneficiaryView: View {
    @Environment(\.dismiss) private var dismiss
    let onAdd: (Beneficiary) -> Void
    
    @State private var name = ""
    @State private var accountNumber = ""
    @State private var bankName = ""
    @State private var bankCode = ""
    @State private var phoneNumber = ""
    @State private var email = ""
    
    var isValid: Bool {
        !name.isEmpty && !accountNumber.isEmpty && !bankName.isEmpty
    }
    
    var body: some View {
        NavigationView {
            Form {
                Section("Beneficiary Details") {
                    TextField("Full Name", text: $name)
                    TextField("Account Number", text: $accountNumber)
                        .keyboardType(.numberPad)
                    TextField("Bank Name", text: $bankName)
                    TextField("Bank Code", text: $bankCode)
                        .keyboardType(.numberPad)
                }
                
                Section("Optional Details") {
                    TextField("Phone Number", text: $phoneNumber)
                        .keyboardType(.phonePad)
                    TextField("Email", text: $email)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                }
            }
            .navigationTitle("Add Beneficiary")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        let beneficiary = Beneficiary(
                            name: name,
                            accountNumber: accountNumber,
                            bankName: bankName,
                            bankCode: bankCode,
                            phoneNumber: phoneNumber.isEmpty ? nil : phoneNumber,
                            email: email.isEmpty ? nil : email
                        )
                        onAdd(beneficiary)
                        dismiss()
                    }
                    .disabled(!isValid)
                }
            }
        }
    }
}

// MARK: - Beneficiary Detail View

struct BeneficiaryDetailView: View {
    @Environment(\.dismiss) private var dismiss
    let beneficiary: Beneficiary
    let onUpdate: (Beneficiary) -> Void
    let onDelete: () -> Void
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 24) {
                    // Avatar
                    ZStack {
                        Circle()
                            .fill(Color.blue.opacity(0.2))
                            .frame(width: 100, height: 100)
                        
                        Text(beneficiary.name.prefix(1))
                            .font(.system(size: 48, weight: .bold))
                            .foregroundColor(.blue)
                    }
                    
                    Text(beneficiary.name)
                        .font(.title2.bold())
                    
                    // Details
                    VStack(spacing: 16) {
                        DetailRow(label: "Account Number", value: beneficiary.accountNumber)
                        DetailRow(label: "Bank", value: beneficiary.bankName)
                        DetailRow(label: "Bank Code", value: beneficiary.bankCode)
                        
                        if let phone = beneficiary.phoneNumber {
                            DetailRow(label: "Phone", value: phone)
                        }
                        
                        if let email = beneficiary.email {
                            DetailRow(label: "Email", value: email)
                        }
                        
                        DetailRow(label: "Total Transactions", value: "\(beneficiary.totalTransactions)")
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)
                    
                    // Actions
                    VStack(spacing: 12) {
                        Button(action: { /* Send money */ }) {
                            Text("Send Money")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        
                        Button(action: onDelete) {
                            Text("Delete Beneficiary")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.bordered)
                        .tint(.red)
                    }
                }
                .padding()
            }
            .navigationTitle("Beneficiary Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

struct DetailRow: View {
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

// MARK: - Preview

struct BeneficiaryManagementView_Previews: PreviewProvider {
    static var previews: some View {
        BeneficiaryManagementView()
    }
}

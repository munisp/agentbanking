import SwiftUI

struct AccountHealthDashboardView: View {
    @StateObject private var viewModel = AccountHealthDashboardViewModel()
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                Text("AccountHealthDashboard Feature")
                    .font(.largeTitle)
                    .fontWeight(.bold)
                
                // Feature content will be implemented here
                featureContent
            }
            .padding()
        }
        .navigationTitle("AccountHealthDashboard")
        .onAppear {
            viewModel.loadData()
        }
    }
    
    private var featureContent: some View {
        VStack(spacing: 16) {
            ForEach(viewModel.items) { item in
                ItemRow(item: item)
            }
        }
    }
}

struct ItemRow: View {
    let item: AccountHealthDashboardItem
    
    var body: some View {
        HStack {
            VStack(alignment: .leading) {
                Text(item.title)
                    .font(.headline)
                Text(item.subtitle)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Spacer()
            Image(systemName: "chevron.right")
                .foregroundColor(.secondary)
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

class AccountHealthDashboardViewModel: ObservableObject {
    @Published var items: [AccountHealthDashboardItem] = []
    @Published var isLoading = false
    
    private let apiService = APIService.shared
    
    func loadData() {
        isLoading = true
        // API integration
        Task {
            do {
                // let data = try await apiService.get("/api/AccountHealthDashboard")
                await MainActor.run {
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                }
            }
        }
    }
}

struct AccountHealthDashboardItem: Identifiable {
    let id = UUID()
    let title: String
    let subtitle: String
}

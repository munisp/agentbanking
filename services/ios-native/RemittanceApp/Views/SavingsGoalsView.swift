import SwiftUI

struct SavingsGoal: Identifiable {
    let id = UUID()
    let goalId: String
    let name: String
    let category: String
    let icon: String
    let targetAmount: Double
    let currentAmount: Double
    let stablecoin: String
    let progressPercent: Int
    let autoConvertEnabled: Bool
    let autoConvertPercent: Int?
    let targetDate: Date?
    let status: String
}

struct SavingsGoalsView: View {
    @State private var goals: [SavingsGoal] = []
    @State private var loading = true
    @State private var showCreateSheet = false
    @Environment(\.dismiss) var dismiss
    
    var totalSaved: Double {
        goals.reduce(0) { $0 + $1.currentAmount }
    }
    
    var activeGoals: Int {
        goals.filter { $0.status == "ACTIVE" }.count
    }
    
    var body: some View {
        NavigationView {
            ScrollView {
                if loading {
                    ProgressView()
                        .padding(.top, 100)
                } else {
                    VStack(spacing: 20) {
                        // Stats Cards
                        HStack(spacing: 12) {
                            StatCard(title: "Total Saved", value: String(format: "$%.2f", totalSaved), icon: "dollarsign.circle.fill", color: .green)
                            StatCard(title: "Active Goals", value: "\(activeGoals)", icon: "target", color: .blue)
                        }
                        
                        // Goals List
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                Text("Your Goals")
                                    .font(.headline)
                                Spacer()
                                Button(action: { showCreateSheet = true }) {
                                    HStack {
                                        Image(systemName: "plus")
                                        Text("New Goal")
                                    }
                                    .font(.subheadline)
                                }
                            }
                            
                            if goals.isEmpty {
                                VStack(spacing: 16) {
                                    Image(systemName: "target")
                                        .font(.system(size: 48))
                                        .foregroundColor(.gray)
                                    Text("No savings goals yet")
                                        .foregroundColor(.gray)
                                    Button("Create Your First Goal") {
                                        showCreateSheet = true
                                    }
                                    .buttonStyle(.borderedProminent)
                                }
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 40)
                            } else {
                                ForEach(goals) { goal in
                                    GoalCard(goal: goal)
                                }
                            }
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle("Savings Goals")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Back") { dismiss() }
                }
            }
            .sheet(isPresented: $showCreateSheet) {
                CreateGoalView()
            }
        }
        .onAppear { loadGoals() }
    }
    
    private func loadGoals() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            goals = [
                SavingsGoal(goalId: "goal-001", name: "University Fees", category: "EDUCATION", icon: "graduationcap.fill", targetAmount: 5000, currentAmount: 3250, stablecoin: "USDT", progressPercent: 65, autoConvertEnabled: true, autoConvertPercent: 10, targetDate: Calendar.current.date(byAdding: .month, value: 6, to: Date()), status: "ACTIVE"),
                SavingsGoal(goalId: "goal-002", name: "Emergency Fund", category: "EMERGENCY", icon: "cross.case.fill", targetAmount: 2000, currentAmount: 900, stablecoin: "USDC", progressPercent: 45, autoConvertEnabled: false, autoConvertPercent: nil, targetDate: nil, status: "ACTIVE"),
                SavingsGoal(goalId: "goal-003", name: "Holiday Trip", category: "TRAVEL", icon: "airplane", targetAmount: 1500, currentAmount: 1500, stablecoin: "USDT", progressPercent: 100, autoConvertEnabled: false, autoConvertPercent: nil, targetDate: Calendar.current.date(byAdding: .month, value: -1, to: Date()), status: "COMPLETED")
            ]
            loading = false
        }
    }
}

struct StatCard: View {
    let title: String
    let value: String
    let icon: String
    let color: Color
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(color)
                Spacer()
            }
            Text(value)
                .font(.title2)
                .fontWeight(.bold)
            Text(title)
                .font(.caption)
                .foregroundColor(.gray)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 5)
    }
}

struct GoalCard: View {
    let goal: SavingsGoal
    
    var categoryColor: Color {
        switch goal.category {
        case "EDUCATION": return .blue
        case "EMERGENCY": return .red
        case "TRAVEL": return .purple
        case "HOUSING": return .green
        case "BUSINESS": return .orange
        default: return .gray
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: goal.icon)
                    .font(.title2)
                    .foregroundColor(categoryColor)
                    .frame(width: 44, height: 44)
                    .background(categoryColor.opacity(0.1))
                    .cornerRadius(12)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(goal.name)
                        .fontWeight(.semibold)
                    HStack {
                        Text(goal.category)
                            .font(.caption)
                            .foregroundColor(categoryColor)
                        Text("•")
                            .foregroundColor(.gray)
                        Text(goal.stablecoin)
                            .font(.caption)
                            .foregroundColor(.gray)
                    }
                }
                
                Spacer()
                
                if goal.status == "COMPLETED" {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                        .font(.title2)
                }
            }
            
            HStack {
                Text(String(format: "$%.2f", goal.currentAmount))
                    .fontWeight(.medium)
                Text("of")
                    .foregroundColor(.gray)
                Text(String(format: "$%.2f", goal.targetAmount))
                    .foregroundColor(.gray)
                Spacer()
                Text("\(goal.progressPercent)%")
                    .fontWeight(.medium)
                    .foregroundColor(goal.progressPercent >= 100 ? .green : .blue)
            }
            .font(.subheadline)
            
            ProgressView(value: Double(goal.progressPercent) / 100)
                .tint(goal.progressPercent >= 100 ? .green : categoryColor)
            
            if goal.autoConvertEnabled, let percent = goal.autoConvertPercent {
                HStack {
                    Image(systemName: "arrow.triangle.2.circlepath")
                        .font(.caption)
                        .foregroundColor(.purple)
                    Text("Auto-convert \(percent)% of transfers")
                        .font(.caption)
                        .foregroundColor(.purple)
                }
            }
            
            if let targetDate = goal.targetDate, goal.status == "ACTIVE" {
                HStack {
                    Image(systemName: "calendar")
                        .font(.caption)
                        .foregroundColor(.gray)
                    Text("Target: \(targetDate.formatted(date: .abbreviated, time: .omitted))")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 5)
    }
}

struct CreateGoalView: View {
    @Environment(\.dismiss) var dismiss
    @State private var goalName = ""
    @State private var targetAmount = ""
    @State private var selectedCategory = "EDUCATION"
    @State private var selectedStablecoin = "USDT"
    @State private var autoConvertEnabled = false
    @State private var autoConvertPercent = 10.0
    
    let categories = ["EDUCATION", "EMERGENCY", "TRAVEL", "HOUSING", "BUSINESS", "RETIREMENT", "WEDDING", "HEALTHCARE", "VEHICLE", "OTHER"]
    let stablecoins = ["USDT", "USDC", "DAI", "BUSD"]
    
    var body: some View {
        NavigationView {
            Form {
                Section("Goal Details") {
                    TextField("Goal Name", text: $goalName)
                    TextField("Target Amount (USD)", text: $targetAmount)
                        .keyboardType(.decimalPad)
                }
                
                Section("Category") {
                    Picker("Category", selection: $selectedCategory) {
                        ForEach(categories, id: \.self) { category in
                            Text(category).tag(category)
                        }
                    }
                }
                
                Section("Stablecoin") {
                    Picker("Save in", selection: $selectedStablecoin) {
                        ForEach(stablecoins, id: \.self) { coin in
                            Text(coin).tag(coin)
                        }
                    }
                    .pickerStyle(.segmented)
                }
                
                Section("Auto-Convert") {
                    Toggle("Enable Auto-Convert", isOn: $autoConvertEnabled)
                    
                    if autoConvertEnabled {
                        VStack(alignment: .leading) {
                            Text("Convert \(Int(autoConvertPercent))% of each transfer")
                                .font(.subheadline)
                            Slider(value: $autoConvertPercent, in: 1...50, step: 1)
                        }
                    }
                }
            }
            .navigationTitle("New Savings Goal")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Create") { dismiss() }
                        .disabled(goalName.isEmpty || targetAmount.isEmpty)
                }
            }
        }
    }
}

#Preview {
    SavingsGoalsView()
}

import SwiftUI

struct HelpView: View {
    @State private var searchText = ""
    
    let faqs = [
        FAQ(question: "How do I send money?", answer: "Go to Send Money screen, enter recipient details and amount."),
        FAQ(question: "What are the fees?", answer: "Fees vary by payment method and destination country."),
        FAQ(question: "How long does a transfer take?", answer: "Most transfers complete within 1-3 business days."),
        FAQ(question: "Is my money safe?", answer: "Yes, we use bank-level encryption and security measures."),
    ]
    
    var body: View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    // Search Bar
                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundColor(.gray)
                        TextField("Search for help...", text: $searchText)
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(10)
                    .padding(.horizontal)
                    
                    // Quick Actions
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 15) {
                        QuickActionCard(icon: "message.fill", title: "Live Chat", color: .blue)
                        QuickActionCard(icon: "play.circle.fill", title: "Tutorials", color: .green)
                        QuickActionCard(icon: "phone.fill", title: "Call Support", color: .orange)
                        QuickActionCard(icon: "envelope.fill", title: "Email Us", color: .purple)
                    }
                    .padding(.horizontal)
                    
                    // FAQs
                    VStack(alignment: .leading, spacing: 15) {
                        Text("Frequently Asked Questions")
                            .font(.headline)
                            .padding(.horizontal)
                        
                        ForEach(faqs) { faq in
                            FAQCard(faq: faq)
                        }
                    }
                    .padding(.top)
                }
                .padding(.vertical)
            }
            .navigationTitle("Help Center")
        }
    }
}

struct FAQ: Identifiable {
    let id = UUID()
    let question: String
    let answer: String
}

struct QuickActionCard: View {
    let icon: String
    let title: String
    let color: Color
    
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 32))
                .foregroundColor(color)
            Text(title)
                .font(.subheadline)
                .fontWeight(.medium)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 25)
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.05), radius: 5, x: 0, y: 2)
    }
}

struct FAQCard: View {
    let faq: FAQ
    @State private var isExpanded = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Button(action: { withAnimation { isExpanded.toggle() } }) {
                HStack {
                    Text(faq.question)
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.primary)
                    Spacer()
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .foregroundColor(.gray)
                }
            }
            
            if isExpanded {
                Text(faq.answer)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .transition(.opacity)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.05), radius: 5, x: 0, y: 2)
        .padding(.horizontal)
    }
}

struct HelpView_Previews: PreviewProvider {
    static var previews: some View {
        HelpView()
    }
}

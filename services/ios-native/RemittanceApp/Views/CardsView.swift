import SwiftUI

struct CardsView: View {
    @State private var cards = [
        PaymentCard(last4: "4242", brand: "Visa", expiry: "12/25", isDefault: true),
        PaymentCard(last4: "5555", brand: "Mastercard", expiry: "06/26", isDefault: false),
    ]
    @State private var showingAddCard = false
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    ForEach(cards) { card in
                        CardView(card: card)
                    }
                    
                    // Add Card Button
                    Button(action: { showingAddCard = true }) {
                        HStack {
                            Image(systemName: "plus.circle.fill")
                            Text("Add New Card")
                        }
                        .font(.headline)
                        .foregroundColor(.blue)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(12)
                    }
                }
                .padding()
            }
            .navigationTitle("My Cards")
            .sheet(isPresented: $showingAddCard) {
                AddCardView()
            }
        }
    }
}

struct PaymentCard: Identifiable {
    let id = UUID()
    let last4: String
    let brand: String
    let expiry: String
    var isDefault: Bool
}

struct CardView: View {
    let card: PaymentCard
    
    var body: some View {
        ZStack {
            LinearGradient(
                gradient: Gradient(colors: [Color.blue, Color.blue.opacity(0.7)]),
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            
            VStack(alignment: .leading, spacing: 20) {
                HStack {
                    Image(systemName: "creditcard.fill")
                        .font(.system(size: 32))
                    Spacer()
                    if card.isDefault {
                        Text("Default")
                            .font(.caption)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(Color.white.opacity(0.3))
                            .cornerRadius(12)
                    }
                }
                
                Spacer()
                
                Text("•••• •••• •••• \(card.last4)")
                    .font(.title2)
                    .fontWeight(.semibold)
                    .tracking(2)
                
                HStack {
                    Text(card.brand)
                        .font(.subheadline)
                    Spacer()
                    Text("Exp: \(card.expiry)")
                        .font(.subheadline)
                }
                
                Button(action: {}) {
                    HStack {
                        Image(systemName: "trash")
                        Text("Remove Card")
                    }
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.8))
                }
            }
            .padding(20)
        }
        .foregroundColor(.white)
        .frame(height: 200)
        .cornerRadius(16)
        .shadow(color: Color.black.opacity(0.2), radius: 10, x: 0, y: 5)
    }
}

struct AddCardView: View {
    @Environment(\.presentationMode) var presentationMode
    @State private var cardNumber = ""
    @State private var expiry = ""
    @State private var cvv = ""
    
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Card Information")) {
                    TextField("Card Number", text: $cardNumber)
                        .keyboardType(.numberPad)
                    TextField("MM/YY", text: $expiry)
                        .keyboardType(.numberPad)
                    TextField("CVV", text: $cvv)
                        .keyboardType(.numberPad)
                }
                
                Button(action: {
                    presentationMode.wrappedValue.dismiss()
                }) {
                    Text("Add Card")
                        .frame(maxWidth: .infinity)
                        .foregroundColor(.white)
                        .padding()
                        .background(Color.blue)
                        .cornerRadius(10)
                }
            }
            .navigationTitle("Add New Card")
            .navigationBarItems(trailing: Button("Cancel") {
                presentationMode.wrappedValue.dismiss()
            })
        }
    }
}

struct CardsView_Previews: PreviewProvider {
    static var previews: some View {
        CardsView()
    }
}

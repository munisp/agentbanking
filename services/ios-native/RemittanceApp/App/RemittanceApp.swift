import SwiftUI
import FirebaseCore

@main
struct RemittanceApp: App {
    @StateObject private var authManager = AuthenticationManager()
    @StateObject private var walletManager = WalletManager()
    @StateObject private var notificationManager = NotificationManager()
    @StateObject private var networkMonitor = NetworkMonitor()
    
    init() {
        // Configure Firebase
        FirebaseApp.configure()
        
        // Configure app appearance
        configureAppearance()
        
        // Configure networking
        APIClient.shared.configure()
    }
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(authManager)
                .environmentObject(walletManager)
                .environmentObject(notificationManager)
                .environmentObject(networkMonitor)
                .onAppear {
                    setupApp()
                }
        }
    }
    
    private func setupApp() {
        // Request notification permissions
        notificationManager.requestAuthorization()
        
        // Check biometric availability
        authManager.checkBiometricAvailability()
        
        // Start network monitoring
        networkMonitor.startMonitoring()
        
        // Load user session if exists
        Task {
            await authManager.loadSession()
        }
    }
    
    private func configureAppearance() {
        // Configure navigation bar appearance
        let appearance = UINavigationBarAppearance()
        appearance.configureWithOpaqueBackground()
        appearance.backgroundColor = UIColor(named: "PrimaryColor")
        appearance.titleTextAttributes = [.foregroundColor: UIColor.white]
        appearance.largeTitleTextAttributes = [.foregroundColor: UIColor.white]
        
        UINavigationBar.appearance().standardAppearance = appearance
        UINavigationBar.appearance().scrollEdgeAppearance = appearance
        UINavigationBar.appearance().compactAppearance = appearance
        
        // Configure tab bar appearance
        let tabBarAppearance = UITabBarAppearance()
        tabBarAppearance.configureWithOpaqueBackground()
        tabBarAppearance.backgroundColor = UIColor.systemBackground
        
        UITabBar.appearance().standardAppearance = tabBarAppearance
        UITabBar.appearance().scrollEdgeAppearance = tabBarAppearance
        
        // Set tint color
        UIView.appearance(whenContainedInInstancesOf: [UIAlertController.self]).tintColor = UIColor(named: "PrimaryColor")
    }
}

// MARK: - Content View
struct ContentView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @EnvironmentObject var networkMonitor: NetworkMonitor
    
    var body: some View {
        ZStack {
            if authManager.isLoading {
                SplashView()
            } else if authManager.isAuthenticated {
                MainTabView()
            } else {
                OnboardingView()
            }
            
            // Network status banner
            if !networkMonitor.isConnected {
                VStack {
                    NetworkStatusBanner()
                    Spacer()
                }
                .transition(.move(edge: .top))
            }
        }
        .animation(.easeInOut, value: authManager.isAuthenticated)
        .animation(.easeInOut, value: networkMonitor.isConnected)
    }
}

// MARK: - Main Tab View
struct MainTabView: View {
    @State private var selectedTab = 0
    @EnvironmentObject var walletManager: WalletManager
    
    var body: some View {
        TabView(selection: $selectedTab) {
            DashboardView()
                .tabItem {
                    Label("Home", systemImage: "house.fill")
                }
                .tag(0)
            
            SendMoneyView()
                .tabItem {
                    Label("Send", systemImage: "arrow.up.circle.fill")
                }
                .tag(1)
            
            TransactionsView()
                .tabItem {
                    Label("Activity", systemImage: "list.bullet")
                }
                .tag(2)
            
            WalletView()
                .tabItem {
                    Label("Wallet", systemImage: "creditcard.fill")
                }
                .tag(3)
            
            ProfileView()
                .tabItem {
                    Label("Profile", systemImage: "person.fill")
                }
                .tag(4)
        }
        .accentColor(Color("PrimaryColor"))
        .onAppear {
            // Load wallet data when tab view appears
            Task {
                await walletManager.loadBalances()
            }
        }
    }
}

// MARK: - Splash View
struct SplashView: View {
    var body: some View {
        ZStack {
            Color("PrimaryColor")
                .ignoresSafeArea()
            
            VStack(spacing: 20) {
                Image("AppLogo")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 120, height: 120)
                
                Text("Remittance")
                    .font(.system(size: 32, weight: .bold))
                    .foregroundColor(.white)
                
                ProgressView()
                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    .scaleEffect(1.5)
            }
        }
    }
}

// MARK: - Network Status Banner
struct NetworkStatusBanner: View {
    var body: some View {
        HStack {
            Image(systemName: "wifi.slash")
                .foregroundColor(.white)
            
            Text("No Internet Connection")
                .font(.subheadline)
                .foregroundColor(.white)
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(Color.red)
    }
}

#Preview {
    ContentView()
        .environmentObject(AuthenticationManager())
        .environmentObject(WalletManager())
        .environmentObject(NotificationManager())
        .environmentObject(NetworkMonitor())
}

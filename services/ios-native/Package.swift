// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "RemittanceApp",
    platforms: [
        .iOS(.v16)
    ],
    products: [
        .library(
            name: "RemittanceApp",
            targets: ["RemittanceApp"]
        )
    ],
    dependencies: [
        // Networking
        .package(url: "https://github.com/Alamofire/Alamofire.git", from: "5.8.0"),
        
        // Secure Storage
        .package(url: "https://github.com/kishikawakatsumi/KeychainAccess.git", from: "4.2.2"),
        
        // Image Loading
        .package(url: "https://github.com/onevcat/Kingfisher.git", from: "7.10.0"),
        
        // QR Code
        .package(url: "https://github.com/twostraws/CodeScanner.git", from: "2.3.0"),
        
        // Biometrics
        .package(url: "https://github.com/rushisangani/BiometricAuthentication.git", from: "3.1.3"),
        
        // Analytics
        .package(url: "https://github.com/firebase/firebase-ios-sdk.git", from: "10.18.0"),
        
        // Utilities
        .package(url: "https://github.com/SwiftyJSON/SwiftyJSON.git", from: "5.0.1")
    ],
    targets: [
        .target(
            name: "RemittanceApp",
            dependencies: [
                "Alamofire",
                "KeychainAccess",
                "Kingfisher",
                "CodeScanner",
                "BiometricAuthentication",
                .product(name: "FirebaseAnalytics", package: "firebase-ios-sdk"),
                .product(name: "FirebaseCrashlytics", package: "firebase-ios-sdk"),
                .product(name: "FirebaseMessaging", package: "firebase-ios-sdk"),
                "SwiftyJSON"
            ]
        ),
        .testTarget(
            name: "RemittanceAppTests",
            dependencies: ["RemittanceApp"]
        )
    ]
)

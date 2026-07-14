// swift-tools-version:5.9
// The swift-tools-version declares the minimum version of Swift required to build this package.

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
        ),
    ],
    dependencies: [
        // Coinbase Wallet SDK for CDP integration
        .package(
            url: "https://github.com/coinbase/coinbase-wallet-sdk-ios.git",
            from: "1.0.0"
        ),
        // Other dependencies
        .package(
            url: "https://github.com/Alamofire/Alamofire.git",
            from: "5.8.0"
        ),
    ],
    targets: [
        .target(
            name: "RemittanceApp",
            dependencies: [
                .product(name: "CoinbaseWalletSDK", package: "coinbase-wallet-sdk-ios"),
                "Alamofire",
            ]
        ),
        .testTarget(
            name: "RemittanceAppTests",
            dependencies: ["RemittanceApp"]
        ),
    ]
)

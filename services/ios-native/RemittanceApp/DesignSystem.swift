import SwiftUI

// MARK: - Brand Colors - Unified Design System

struct BrandColors {
    // Primary Blue Palette
    static let primary50 = Color(hex: "EFF6FF")
    static let primary100 = Color(hex: "DBEAFE")
    static let primary200 = Color(hex: "BFDBFE")
    static let primary300 = Color(hex: "93C5FD")
    static let primary400 = Color(hex: "60A5FA")
    static let primary500 = Color(hex: "3B82F6")
    static let primary600 = Color(hex: "1A56DB")
    static let primary700 = Color(hex: "1D4ED8")
    static let primary800 = Color(hex: "1E40AF")
    static let primary900 = Color(hex: "1E3A8A")
    
    // Success Green Palette
    static let success50 = Color(hex: "ECFDF5")
    static let success100 = Color(hex: "D1FAE5")
    static let success500 = Color(hex: "10B981")
    static let success600 = Color(hex: "059669")
    static let success700 = Color(hex: "047857")
    
    // Warning Orange Palette
    static let warning50 = Color(hex: "FFFBEB")
    static let warning100 = Color(hex: "FEF3C7")
    static let warning500 = Color(hex: "F59E0B")
    static let warning600 = Color(hex: "D97706")
    static let warning700 = Color(hex: "B45309")
    
    // Error Red Palette
    static let error50 = Color(hex: "FEF2F2")
    static let error100 = Color(hex: "FEE2E2")
    static let error500 = Color(hex: "EF4444")
    static let error600 = Color(hex: "DC2626")
    static let error700 = Color(hex: "B91C1C")
    
    // Neutral Palette
    static let neutral50 = Color(hex: "F9FAFB")
    static let neutral100 = Color(hex: "F3F4F6")
    static let neutral200 = Color(hex: "E5E7EB")
    static let neutral300 = Color(hex: "D1D5DB")
    static let neutral400 = Color(hex: "9CA3AF")
    static let neutral500 = Color(hex: "6B7280")
    static let neutral600 = Color(hex: "4B5563")
    static let neutral700 = Color(hex: "374151")
    static let neutral800 = Color(hex: "1F2937")
    static let neutral900 = Color(hex: "111827")
}

// MARK: - Color Extension for Hex Support

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (1, 1, 1, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue:  Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

// MARK: - Spacing Scale

struct AppSpacing {
    static let xs: CGFloat = 4
    static let sm: CGFloat = 8
    static let md: CGFloat = 16
    static let lg: CGFloat = 24
    static let xl: CGFloat = 32
    static let xxl: CGFloat = 48
    static let xxxl: CGFloat = 64
}

// MARK: - Corner Radius Scale

struct AppCornerRadius {
    static let xs: CGFloat = 4
    static let sm: CGFloat = 8
    static let md: CGFloat = 12
    static let lg: CGFloat = 16
    static let xl: CGFloat = 24
    static let full: CGFloat = 9999
}

// MARK: - Typography

struct AppTypography {
    static let display = Font.system(size: 48, weight: .bold, design: .default)
    static let h1 = Font.system(size: 32, weight: .bold, design: .default)
    static let h2 = Font.system(size: 24, weight: .semibold, design: .default)
    static let h3 = Font.system(size: 20, weight: .semibold, design: .default)
    static let h4 = Font.system(size: 18, weight: .medium, design: .default)
    static let bodyLarge = Font.system(size: 16, weight: .regular, design: .default)
    static let body = Font.system(size: 14, weight: .regular, design: .default)
    static let caption = Font.system(size: 12, weight: .regular, design: .default)
    static let overline = Font.system(size: 10, weight: .medium, design: .default)
}

// MARK: - Shadow Styles

struct AppShadow {
    static let sm = Shadow(color: Color.black.opacity(0.05), radius: 2, x: 0, y: 1)
    static let md = Shadow(color: Color.black.opacity(0.1), radius: 6, x: 0, y: 4)
    static let lg = Shadow(color: Color.black.opacity(0.1), radius: 15, x: 0, y: 10)
    static let xl = Shadow(color: Color.black.opacity(0.15), radius: 25, x: 0, y: 20)
    static let glow = Shadow(color: BrandColors.primary600.opacity(0.3), radius: 20, x: 0, y: 0)
}

struct Shadow {
    let color: Color
    let radius: CGFloat
    let x: CGFloat
    let y: CGFloat
}

// MARK: - Animation Durations

struct AppAnimation {
    static let fast: Double = 0.15
    static let normal: Double = 0.25
    static let slow: Double = 0.35
    
    static let springResponse: Double = 0.4
    static let springDamping: Double = 0.7
}

// MARK: - Custom Button Styles

struct PrimaryButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled
    
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 14, weight: .semibold))
            .foregroundColor(.white)
            .padding(.horizontal, AppSpacing.lg)
            .padding(.vertical, AppSpacing.md)
            .background(
                RoundedRectangle(cornerRadius: AppCornerRadius.md)
                    .fill(isEnabled ? BrandColors.primary600 : BrandColors.neutral400)
            )
            .scaleEffect(configuration.isPressed ? 0.98 : 1.0)
            .animation(.spring(response: 0.2, dampingFraction: 0.7), value: configuration.isPressed)
            .shadow(color: isEnabled ? BrandColors.primary600.opacity(0.3) : .clear, radius: configuration.isPressed ? 4 : 8, y: configuration.isPressed ? 2 : 4)
    }
}

struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 14, weight: .semibold))
            .foregroundColor(BrandColors.neutral700)
            .padding(.horizontal, AppSpacing.lg)
            .padding(.vertical, AppSpacing.md)
            .background(
                RoundedRectangle(cornerRadius: AppCornerRadius.md)
                    .fill(Color.white)
                    .overlay(
                        RoundedRectangle(cornerRadius: AppCornerRadius.md)
                            .stroke(BrandColors.neutral200, lineWidth: 1)
                    )
            )
            .scaleEffect(configuration.isPressed ? 0.98 : 1.0)
            .animation(.spring(response: 0.2, dampingFraction: 0.7), value: configuration.isPressed)
    }
}

struct GhostButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 14, weight: .semibold))
            .foregroundColor(BrandColors.primary600)
            .padding(.horizontal, AppSpacing.lg)
            .padding(.vertical, AppSpacing.md)
            .background(
                RoundedRectangle(cornerRadius: AppCornerRadius.md)
                    .fill(configuration.isPressed ? BrandColors.primary50 : Color.clear)
            )
            .scaleEffect(configuration.isPressed ? 0.98 : 1.0)
            .animation(.spring(response: 0.2, dampingFraction: 0.7), value: configuration.isPressed)
    }
}

// MARK: - Custom Card View

struct CardView<Content: View>: View {
    let content: Content
    var isInteractive: Bool = false
    
    init(isInteractive: Bool = false, @ViewBuilder content: () -> Content) {
        self.isInteractive = isInteractive
        self.content = content()
    }
    
    var body: some View {
        content
            .padding(AppSpacing.lg)
            .background(
                RoundedRectangle(cornerRadius: AppCornerRadius.lg)
                    .fill(Color.white)
                    .shadow(color: Color.black.opacity(0.08), radius: 8, x: 0, y: 4)
            )
            .overlay(
                RoundedRectangle(cornerRadius: AppCornerRadius.lg)
                    .stroke(BrandColors.neutral100, lineWidth: 1)
            )
    }
}

// MARK: - Custom Input Field

struct AppTextField: View {
    let label: String
    @Binding var text: String
    var placeholder: String = ""
    var errorMessage: String? = nil
    var isSecure: Bool = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: AppSpacing.sm) {
            Text(label)
                .font(AppTypography.caption)
                .foregroundColor(BrandColors.neutral700)
            
            Group {
                if isSecure {
                    SecureField(placeholder, text: $text)
                } else {
                    TextField(placeholder, text: $text)
                }
            }
            .font(AppTypography.body)
            .padding(.horizontal, AppSpacing.md)
            .padding(.vertical, AppSpacing.md)
            .background(
                RoundedRectangle(cornerRadius: AppCornerRadius.md)
                    .fill(Color.white)
                    .overlay(
                        RoundedRectangle(cornerRadius: AppCornerRadius.md)
                            .stroke(errorMessage != nil ? BrandColors.error500 : BrandColors.neutral200, lineWidth: 1)
                    )
            )
            
            if let error = errorMessage {
                HStack(spacing: AppSpacing.xs) {
                    Image(systemName: "exclamationmark.circle.fill")
                        .font(.system(size: 12))
                    Text(error)
                        .font(AppTypography.caption)
                }
                .foregroundColor(BrandColors.error600)
            }
        }
    }
}

// MARK: - Badge View

struct BadgeView: View {
    let text: String
    var style: BadgeStyle = .primary
    
    enum BadgeStyle {
        case primary, success, warning, error, neutral
        
        var backgroundColor: Color {
            switch self {
            case .primary: return BrandColors.primary100
            case .success: return BrandColors.success50
            case .warning: return BrandColors.warning50
            case .error: return BrandColors.error50
            case .neutral: return BrandColors.neutral100
            }
        }
        
        var textColor: Color {
            switch self {
            case .primary: return BrandColors.primary700
            case .success: return BrandColors.success700
            case .warning: return BrandColors.warning700
            case .error: return BrandColors.error700
            case .neutral: return BrandColors.neutral700
            }
        }
    }
    
    var body: some View {
        Text(text)
            .font(.system(size: 12, weight: .medium))
            .foregroundColor(style.textColor)
            .padding(.horizontal, AppSpacing.sm + 2)
            .padding(.vertical, AppSpacing.xs)
            .background(
                Capsule()
                    .fill(style.backgroundColor)
            )
    }
}

// MARK: - Avatar View

struct AvatarView: View {
    let initials: String
    var size: AvatarSize = .md
    var imageURL: URL? = nil
    
    enum AvatarSize {
        case sm, md, lg, xl
        
        var dimension: CGFloat {
            switch self {
            case .sm: return 32
            case .md: return 40
            case .lg: return 48
            case .xl: return 64
            }
        }
        
        var fontSize: CGFloat {
            switch self {
            case .sm: return 12
            case .md: return 14
            case .lg: return 16
            case .xl: return 20
            }
        }
    }
    
    var body: some View {
        ZStack {
            Circle()
                .fill(BrandColors.primary100)
            
            Text(initials.prefix(2).uppercased())
                .font(.system(size: size.fontSize, weight: .semibold))
                .foregroundColor(BrandColors.primary700)
        }
        .frame(width: size.dimension, height: size.dimension)
    }
}

// MARK: - Loading Spinner

struct LoadingSpinner: View {
    @State private var isAnimating = false
    var color: Color = BrandColors.primary600
    var size: CGFloat = 20
    
    var body: some View {
        Circle()
            .trim(from: 0, to: 0.7)
            .stroke(color, lineWidth: 2)
            .frame(width: size, height: size)
            .rotationEffect(Angle(degrees: isAnimating ? 360 : 0))
            .animation(
                Animation.linear(duration: 1)
                    .repeatForever(autoreverses: false),
                value: isAnimating
            )
            .onAppear {
                isAnimating = true
            }
    }
}

// MARK: - Empty State View

struct EmptyStateView: View {
    let icon: String
    let title: String
    let description: String
    var actionTitle: String? = nil
    var action: (() -> Void)? = nil
    
    var body: some View {
        VStack(spacing: AppSpacing.md) {
            Image(systemName: icon)
                .font(.system(size: 48))
                .foregroundColor(BrandColors.neutral300)
            
            Text(title)
                .font(AppTypography.h3)
                .foregroundColor(BrandColors.neutral900)
            
            Text(description)
                .font(AppTypography.body)
                .foregroundColor(BrandColors.neutral500)
                .multilineTextAlignment(.center)
                .padding(.horizontal, AppSpacing.xl)
            
            if let actionTitle = actionTitle, let action = action {
                Button(actionTitle, action: action)
                    .buttonStyle(PrimaryButtonStyle())
                    .padding(.top, AppSpacing.sm)
            }
        }
        .padding(AppSpacing.xxl)
    }
}

// MARK: - Stats Card

struct StatsCardView: View {
    let label: String
    let value: String
    var trend: String? = nil
    var trendPositive: Bool = true
    
    var body: some View {
        VStack(alignment: .leading, spacing: AppSpacing.sm) {
            Text(label)
                .font(AppTypography.caption)
                .foregroundColor(BrandColors.primary100)
            
            Text(value)
                .font(.system(size: 28, weight: .bold))
                .foregroundColor(.white)
            
            if let trend = trend {
                HStack(spacing: AppSpacing.xs) {
                    Image(systemName: trendPositive ? "arrow.up.right" : "arrow.down.right")
                        .font(.system(size: 10, weight: .bold))
                    Text(trend)
                        .font(AppTypography.caption)
                }
                .foregroundColor(trendPositive ? BrandColors.success100 : BrandColors.error100)
            }
        }
        .padding(AppSpacing.lg)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            LinearGradient(
                gradient: Gradient(colors: [BrandColors.primary600, BrandColors.primary800]),
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .cornerRadius(AppCornerRadius.lg)
    }
}

// MARK: - Transaction Item View

struct TransactionItemView: View {
    let title: String
    let subtitle: String
    let amount: String
    var isPositive: Bool = false
    var icon: String = "arrow.up.right"
    
    var body: some View {
        HStack(spacing: AppSpacing.md) {
            ZStack {
                Circle()
                    .fill(isPositive ? BrandColors.success50 : BrandColors.error50)
                    .frame(width: 40, height: 40)
                
                Image(systemName: icon)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(isPositive ? BrandColors.success600 : BrandColors.error600)
            }
            
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(AppTypography.body)
                    .fontWeight(.medium)
                    .foregroundColor(BrandColors.neutral900)
                
                Text(subtitle)
                    .font(AppTypography.caption)
                    .foregroundColor(BrandColors.neutral500)
            }
            
            Spacer()
            
            Text(amount)
                .font(.system(size: 14, weight: .semibold, design: .monospaced))
                .foregroundColor(isPositive ? BrandColors.success600 : BrandColors.error600)
        }
        .padding(AppSpacing.md)
        .background(
            RoundedRectangle(cornerRadius: AppCornerRadius.md)
                .fill(Color.white)
                .overlay(
                    RoundedRectangle(cornerRadius: AppCornerRadius.md)
                        .stroke(BrandColors.neutral100, lineWidth: 1)
                )
        )
    }
}

// MARK: - Quick Action Button

struct QuickActionButton: View {
    let icon: String
    let label: String
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            VStack(spacing: AppSpacing.sm) {
                ZStack {
                    RoundedRectangle(cornerRadius: AppCornerRadius.md)
                        .fill(BrandColors.primary100)
                        .frame(width: 44, height: 44)
                    
                    Image(systemName: icon)
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundColor(BrandColors.primary600)
                }
                
                Text(label)
                    .font(AppTypography.caption)
                    .fontWeight(.medium)
                    .foregroundColor(BrandColors.neutral700)
                    .lineLimit(1)
            }
        }
        .buttonStyle(PlainButtonStyle())
    }
}

// MARK: - View Extensions

extension View {
    func cardStyle() -> some View {
        self
            .padding(AppSpacing.lg)
            .background(
                RoundedRectangle(cornerRadius: AppCornerRadius.lg)
                    .fill(Color.white)
                    .shadow(color: Color.black.opacity(0.08), radius: 8, x: 0, y: 4)
            )
            .overlay(
                RoundedRectangle(cornerRadius: AppCornerRadius.lg)
                    .stroke(BrandColors.neutral100, lineWidth: 1)
            )
    }
    
    func pageBackground() -> some View {
        self
            .background(BrandColors.neutral50.ignoresSafeArea())
    }
}

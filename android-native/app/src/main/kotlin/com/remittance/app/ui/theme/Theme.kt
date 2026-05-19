package com.pos54link.app.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.dp
import androidx.core.view.WindowCompat

// Brand Colors - Unified Design System
object BrandColors {
    // Primary Blue Palette
    val Primary50 = Color(0xFFEFF6FF)
    val Primary100 = Color(0xFFDBEAFE)
    val Primary200 = Color(0xFFBFDBFE)
    val Primary300 = Color(0xFF93C5FD)
    val Primary400 = Color(0xFF60A5FA)
    val Primary500 = Color(0xFF3B82F6)
    val Primary600 = Color(0xFF1A56DB)
    val Primary700 = Color(0xFF1D4ED8)
    val Primary800 = Color(0xFF1E40AF)
    val Primary900 = Color(0xFF1E3A8A)
    
    // Success Green Palette
    val Success50 = Color(0xFFECFDF5)
    val Success100 = Color(0xFFD1FAE5)
    val Success500 = Color(0xFF10B981)
    val Success600 = Color(0xFF059669)
    val Success700 = Color(0xFF047857)
    
    // Warning Orange Palette
    val Warning50 = Color(0xFFFFFBEB)
    val Warning100 = Color(0xFFFEF3C7)
    val Warning500 = Color(0xFFF59E0B)
    val Warning600 = Color(0xFFD97706)
    val Warning700 = Color(0xFFB45309)
    
    // Error Red Palette
    val Error50 = Color(0xFFFEF2F2)
    val Error100 = Color(0xFFFEE2E2)
    val Error500 = Color(0xFFEF4444)
    val Error600 = Color(0xFFDC2626)
    val Error700 = Color(0xFFB91C1C)
    
    // Neutral Palette
    val Neutral50 = Color(0xFFF9FAFB)
    val Neutral100 = Color(0xFFF3F4F6)
    val Neutral200 = Color(0xFFE5E7EB)
    val Neutral300 = Color(0xFFD1D5DB)
    val Neutral400 = Color(0xFF9CA3AF)
    val Neutral500 = Color(0xFF6B7280)
    val Neutral600 = Color(0xFF4B5563)
    val Neutral700 = Color(0xFF374151)
    val Neutral800 = Color(0xFF1F2937)
    val Neutral900 = Color(0xFF111827)
}

private val DarkColorScheme = darkColorScheme(
    primary = BrandColors.Primary500,
    onPrimary = Color.White,
    primaryContainer = BrandColors.Primary800,
    onPrimaryContainer = BrandColors.Primary100,
    secondary = BrandColors.Success600,
    onSecondary = Color.White,
    secondaryContainer = BrandColors.Success700,
    onSecondaryContainer = BrandColors.Success100,
    tertiary = BrandColors.Warning600,
    onTertiary = Color.White,
    error = BrandColors.Error500,
    onError = Color.White,
    errorContainer = BrandColors.Error700,
    onErrorContainer = BrandColors.Error100,
    background = BrandColors.Neutral900,
    onBackground = BrandColors.Neutral100,
    surface = BrandColors.Neutral800,
    onSurface = BrandColors.Neutral100,
    surfaceVariant = BrandColors.Neutral700,
    onSurfaceVariant = BrandColors.Neutral300,
    outline = BrandColors.Neutral600,
    outlineVariant = BrandColors.Neutral700,
)

private val LightColorScheme = lightColorScheme(
    primary = BrandColors.Primary600,
    onPrimary = Color.White,
    primaryContainer = BrandColors.Primary100,
    onPrimaryContainer = BrandColors.Primary800,
    secondary = BrandColors.Success600,
    onSecondary = Color.White,
    secondaryContainer = BrandColors.Success100,
    onSecondaryContainer = BrandColors.Success700,
    tertiary = BrandColors.Warning600,
    onTertiary = Color.White,
    tertiaryContainer = BrandColors.Warning100,
    onTertiaryContainer = BrandColors.Warning700,
    error = BrandColors.Error600,
    onError = Color.White,
    errorContainer = BrandColors.Error100,
    onErrorContainer = BrandColors.Error700,
    background = BrandColors.Neutral50,
    onBackground = BrandColors.Neutral900,
    surface = Color.White,
    onSurface = BrandColors.Neutral900,
    surfaceVariant = BrandColors.Neutral100,
    onSurfaceVariant = BrandColors.Neutral600,
    outline = BrandColors.Neutral300,
    outlineVariant = BrandColors.Neutral200,
)

// World-class rounded shapes
val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(4.dp),
    small = RoundedCornerShape(8.dp),
    medium = RoundedCornerShape(12.dp),
    large = RoundedCornerShape(16.dp),
    extraLarge = RoundedCornerShape(24.dp)
)

// Animation specs for micro-interactions
object AppAnimations {
    val buttonPress = spring<Float>(
        dampingRatio = Spring.DampingRatioMediumBouncy,
        stiffness = Spring.StiffnessLow
    )
    
    val cardHover = spring<Float>(
        dampingRatio = Spring.DampingRatioLowBouncy,
        stiffness = Spring.StiffnessMedium
    )
    
    val pageTransition = spring<Float>(
        dampingRatio = Spring.DampingRatioNoBouncy,
        stiffness = Spring.StiffnessLow
    )
}

// Spacing scale
object AppSpacing {
    val xs = 4.dp
    val sm = 8.dp
    val md = 16.dp
    val lg = 24.dp
    val xl = 32.dp
    val xxl = 48.dp
    val xxxl = 64.dp
}

// Elevation scale
object AppElevation {
    val none = 0.dp
    val sm = 2.dp
    val md = 4.dp
    val lg = 8.dp
    val xl = 16.dp
}

@Composable
fun NigerianRemittanceTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = true,
    content: @Composable () -> Unit
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            // Use surface color for status bar for a more modern look
            window.statusBarColor = if (darkTheme) {
                BrandColors.Neutral900.toArgb()
            } else {
                Color.White.toArgb()
            }
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
            // Enable edge-to-edge
            WindowCompat.setDecorFitsSystemWindows(window, false)
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        shapes = AppShapes,
        content = content
    )
}

package com.pos54link.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.WindowCompat
import com.pos54link.app.ui.screens.onboarding.OnboardingScreen
import com.pos54link.app.ui.theme.RemittanceTheme
import com.pos54link.app.viewmodels.AuthViewModel
import com.pos54link.app.viewmodels.MainViewModel
import dagger.hilt.android.AndroidEntryPoint
import timber.log.Timber

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    
    private val authViewModel: AuthViewModel by viewModels()
    private val mainViewModel: MainViewModel by viewModels()
    
    override fun onCreate(savedInstanceState: Bundle?) {
        // Install splash screen
        val splashScreen = installSplashScreen()
        
        super.onCreate(savedInstanceState)
        
        // Configure edge-to-edge
        WindowCompat.setDecorFitsSystemWindows(window, false)
        
        // Keep splash screen visible while loading
        splashScreen.setKeepOnScreenCondition {
            authViewModel.isLoading.value
        }
        
        setContent {
            RemittanceTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    RemittanceApp(
                        authViewModel = authViewModel,
                        mainViewModel = mainViewModel
                    )
                }
            }
        }
        
        // Handle deep links
        handleIntent(intent)
        
        Timber.d("MainActivity created")
    }
    
    override fun onNewIntent(intent: android.content.Intent?) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }
    
    private fun handleIntent(intent: android.content.Intent?) {
        intent?.data?.let { uri ->
            Timber.d("Handling deep link: $uri")
            mainViewModel.handleDeepLink(uri)
        }
    }
}

@Composable
fun RemittanceApp(
    authViewModel: AuthViewModel,
    mainViewModel: MainViewModel
) {
    val isAuthenticated by authViewModel.isAuthenticated.collectAsState()
    val isLoading by authViewModel.isLoading.collectAsState()
    
    // Load session on app start
    LaunchedEffect(Unit) {
        authViewModel.loadSession()
    }
    
    when {
        isLoading -> {
            // Splash screen is shown by SplashScreen API
            // This state is just for the transition
        }
        isAuthenticated -> {
            MainApp(mainViewModel = mainViewModel)
        }
        else -> {
            OnboardingScreen(authViewModel = authViewModel)
        }
    }
}

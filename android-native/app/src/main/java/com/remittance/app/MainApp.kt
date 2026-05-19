package com.pos54link.app

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.pos54link.app.ui.screens.dashboard.DashboardScreen
import com.pos54link.app.ui.screens.profile.ProfileScreen
import com.pos54link.app.ui.screens.sendmoney.SendMoneyScreen
import com.pos54link.app.ui.screens.transactions.TransactionsScreen
import com.pos54link.app.ui.screens.wallet.WalletScreen
import com.pos54link.app.viewmodels.MainViewModel

sealed class Screen(val route: String, val title: String, val icon: ImageVector) {
    object Dashboard : Screen("dashboard", "Home", Icons.Filled.Home)
    object Send : Screen("send", "Send", Icons.Filled.Send)
    object Transactions : Screen("transactions", "Activity", Icons.Filled.List)
    object Wallet : Screen("wallet", "Wallet", Icons.Filled.AccountBalanceWallet)
    object Profile : Screen("profile", "Profile", Icons.Filled.Person)
}

val bottomNavItems = listOf(
    Screen.Dashboard,
    Screen.Send,
    Screen.Transactions,
    Screen.Wallet,
    Screen.Profile
)

@Composable
fun MainApp(
    mainViewModel: MainViewModel,
    navController: NavHostController = rememberNavController()
) {
    val networkStatus by mainViewModel.networkStatus.collectAsState()
    
    Scaffold(
        bottomBar = {
            BottomNavigationBar(navController = navController)
        },
        snackbarHost = {
            if (!networkStatus) {
                Snackbar(
                    modifier = Modifier.padding(),
                    action = {
                        TextButton(onClick = { /* Retry */ }) {
                            Text("Retry")
                        }
                    }
                ) {
                    Text("No internet connection")
                }
            }
        }
    ) { paddingValues ->
        NavHost(
            navController = navController,
            startDestination = Screen.Dashboard.route,
            modifier = Modifier.padding(paddingValues)
        ) {
            composable(Screen.Dashboard.route) {
                DashboardScreen(navController = navController)
            }
            composable(Screen.Send.route) {
                SendMoneyScreen(navController = navController)
            }
            composable(Screen.Transactions.route) {
                TransactionsScreen(navController = navController)
            }
            composable(Screen.Wallet.route) {
                WalletScreen(navController = navController)
            }
            composable(Screen.Profile.route) {
                ProfileScreen(navController = navController)
            }
        }
    }
}

@Composable
fun BottomNavigationBar(navController: NavHostController) {
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = navBackStackEntry?.destination
    
    NavigationBar {
        bottomNavItems.forEach { screen ->
            NavigationBarItem(
                icon = { Icon(screen.icon, contentDescription = screen.title) },
                label = { Text(screen.title) },
                selected = currentDestination?.hierarchy?.any { it.route == screen.route } == true,
                onClick = {
                    navController.navigate(screen.route) {
                        // Pop up to the start destination of the graph to
                        // avoid building up a large stack of destinations
                        popUpTo(navController.graph.findStartDestination().id) {
                            saveState = true
                        }
                        // Avoid multiple copies of the same destination
                        launchSingleTop = true
                        // Restore state when reselecting a previously selected item
                        restoreState = true
                    }
                }
            )
        }
    }
}

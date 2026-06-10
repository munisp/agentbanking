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
import com.pos54link.app.ui.screens.*
import com.pos54link.app.viewmodels.MainViewModel

sealed class Screen(val route: String, val title: String, val icon: ImageVector) {
    object Dashboard : Screen("dashboard", "Home", Icons.Filled.Home)
    object Send : Screen("send", "Send", Icons.Filled.Send)
    object Transactions : Screen("transactions", "Activity", Icons.Filled.List)
    object Wallet : Screen("wallet", "Wallet", Icons.Filled.AccountBalanceWallet)
    object POS : Screen("pos_hub", "POS", Icons.Filled.PointOfSale)
}

val bottomNavItems = listOf(
    Screen.Dashboard,
    Screen.Send,
    Screen.POS,
    Screen.Transactions,
    Screen.Wallet
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
            // ── Main Tabs ─────────────────────────────────────────────
            composable(Screen.Dashboard.route) {
                DashboardScreen(
                    onNavigateToSendMoney = { navController.navigate(Screen.Send.route) },
                    onNavigateToTransactions = { navController.navigate(Screen.Transactions.route) },
                    onNavigateToWallet = { navController.navigate(Screen.Wallet.route) },
                    onNavigateToProfile = { navController.navigate("profile") }
                )
            }
            composable(Screen.Send.route) {
                CashInScreen(
                    onSuccess = { /* Navigate to receipt */ },
                    onBack = { navController.popBackStack() }
                )
            }
            composable(Screen.Transactions.route) {
                CashOutScreen(
                    onSuccess = { /* Navigate to receipt */ },
                    onBack = { navController.popBackStack() }
                )
            }
            composable(Screen.Wallet.route) {
                BillPaymentScreen(
                    onSuccess = { /* Navigate to receipt */ },
                    onBack = { navController.popBackStack() }
                )
            }

            // ── POS Hub ───────────────────────────────────────────────
            composable(Screen.POS.route) {
                PosHubScreen(
                    onNavigate = { route -> navController.navigate(route) },
                    onBack = { navController.popBackStack() }
                )
            }

            // ── POS Sub-screens ───────────────────────────────────────
            composable("pos_fleet") {
                TerminalFleetScreen(onBack = { navController.popBackStack() })
            }
            composable("pos_settlement") {
                PosSettlementScreen(onBack = { navController.popBackStack() })
            }
            composable("pos_disputes") {
                PosDisputeScreen(onBack = { navController.popBackStack() })
            }
            composable("pos_voice") {
                VoiceCommandScreen(onBack = { navController.popBackStack() })
            }
            composable("pos_leasing") {
                TerminalLeasingScreen(onBack = { navController.popBackStack() })
            }
            composable("pos_firmware") {
                FirmwareUpdateScreen(onBack = { navController.popBackStack() })
            }
            composable("pos_iot") {
                IoTDeviceHealthScreen(onBack = { navController.popBackStack() })
            }
            composable("pos_receipt") {
                ReceiptScreen(
                    transactionRef = "",
                    onNewTransaction = { navController.popBackStack() },
                    onHome = { navController.navigate(Screen.Dashboard.route) }
                )
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
                        popUpTo(navController.graph.findStartDestination().id) {
                            saveState = true
                        }
                        launchSingleTop = true
                        restoreState = true
                    }
                }
            )
        }
    }
}

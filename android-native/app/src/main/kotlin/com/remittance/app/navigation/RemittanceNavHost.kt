package com.pos54link.app.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.pos54link.app.ui.screens.*
import com.pos54link.features.enhanced.*

sealed class Screen(val route: String) {
    object Login : Screen("login")
    object Register : Screen("register")
    object Dashboard : Screen("dashboard")
    object Wallet : Screen("wallet")
    object SendMoney : Screen("send_money")
    object ReceiveMoney : Screen("receive_money")
    object Transactions : Screen("transactions")
    object ExchangeRates : Screen("exchange_rates")
    object Airtime : Screen("airtime")
    object BillPayment : Screen("bill_payment")
    object VirtualAccount : Screen("virtual_account")
    object Cards : Screen("cards")
    object KYC : Screen("kyc")
    object Settings : Screen("settings")
    object Profile : Screen("profile")
    object Support : Screen("support")
    object Stablecoin : Screen("stablecoin")
    object TransferTracking : Screen("transfer_tracking/{transferId}") {
        fun createRoute(transferId: String) = "transfer_tracking/$transferId"
    }
    object BatchPayments : Screen("batch_payments")
    object SavingsGoals : Screen("savings_goals")
    object FXAlerts : Screen("fx_alerts")
}

@Composable
fun RemittanceNavHost(
    navController: NavHostController = rememberNavController()
) {
    var isAuthenticated by remember { mutableStateOf(false) }

    NavHost(
        navController = navController,
        startDestination = if (isAuthenticated) Screen.Dashboard.route else Screen.Login.route
    ) {
        composable(Screen.Login.route) {
            LoginScreen(
                onLoginSuccess = {
                    isAuthenticated = true
                    navController.navigate(Screen.Dashboard.route) {
                        popUpTo(Screen.Login.route) { inclusive = true }
                    }
                },
                onNavigateToRegister = {
                    navController.navigate(Screen.Register.route)
                }
            )
        }

        composable(Screen.Register.route) {
            RegisterScreen(
                onRegisterSuccess = {
                    isAuthenticated = true
                    navController.navigate(Screen.Dashboard.route) {
                        popUpTo(Screen.Register.route) { inclusive = true }
                    }
                },
                onNavigateToLogin = {
                    navController.popBackStack()
                }
            )
        }

        composable(Screen.Dashboard.route) {
            DashboardScreen(
                onNavigateToWallet = { navController.navigate(Screen.Wallet.route) },
                onNavigateToSend = { navController.navigate(Screen.SendMoney.route) },
                onNavigateToReceive = { navController.navigate(Screen.ReceiveMoney.route) },
                onNavigateToAirtime = { navController.navigate(Screen.Airtime.route) },
                onNavigateToBills = { navController.navigate(Screen.BillPayment.route) },
                onNavigateToTransactions = { navController.navigate(Screen.Transactions.route) },
                onNavigateToExchangeRates = { navController.navigate(Screen.ExchangeRates.route) },
                onNavigateToSettings = { navController.navigate(Screen.Settings.route) },
                onNavigateToProfile = { navController.navigate(Screen.Profile.route) }
            )
        }

        composable(Screen.Wallet.route) {
            EnhancedWalletScreen(onNavigateBack = { navController.popBackStack() })
        }

        composable(Screen.SendMoney.route) {
            SendMoneyScreen(onNavigateBack = { navController.popBackStack() })
        }

        composable(Screen.ReceiveMoney.route) {
            ReceiveMoneyScreen(onNavigateBack = { navController.popBackStack() })
        }

        composable(Screen.Transactions.route) {
            TransactionAnalyticsScreen(onNavigateBack = { navController.popBackStack() })
        }

        composable(Screen.ExchangeRates.route) {
            EnhancedExchangeRatesScreen(onNavigateBack = { navController.popBackStack() })
        }

        composable(Screen.Airtime.route) {
            AirtimeBillPaymentScreen(onNavigateBack = { navController.popBackStack() })
        }

        composable(Screen.BillPayment.route) {
            AirtimeBillPaymentScreen(onNavigateBack = { navController.popBackStack() })
        }

        composable(Screen.VirtualAccount.route) {
            EnhancedVirtualAccountScreen(onNavigateBack = { navController.popBackStack() })
        }

        composable(Screen.Cards.route) {
            VirtualCardManagementScreen(onNavigateBack = { navController.popBackStack() })
        }

        composable(Screen.KYC.route) {
            EnhancedKYCVerificationScreen(onNavigateBack = { navController.popBackStack() })
        }

        composable(Screen.Settings.route) {
            SettingsScreen(
                onNavigateBack = { navController.popBackStack() },
                onLogout = {
                    isAuthenticated = false
                    navController.navigate(Screen.Login.route) {
                        popUpTo(0) { inclusive = true }
                    }
                }
            )
        }

        composable(Screen.Profile.route) {
            ProfileScreen(onNavigateBack = { navController.popBackStack() })
        }

        composable(Screen.Support.route) {
            SupportScreen(onNavigateBack = { navController.popBackStack() })
        }

        composable(Screen.Stablecoin.route) {
            StablecoinScreen(onNavigateBack = { navController.popBackStack() })
        }

        composable(Screen.TransferTracking.route) { backStackEntry ->
            val transferId = backStackEntry.arguments?.getString("transferId") ?: ""
            TransferTrackingScreen(
                transferId = transferId,
                onNavigateBack = { navController.popBackStack() }
            )
        }

        composable(Screen.BatchPayments.route) {
            BatchPaymentsScreen(onNavigateBack = { navController.popBackStack() })
        }

        composable(Screen.SavingsGoals.route) {
            SavingsGoalsScreen(onNavigateBack = { navController.popBackStack() })
        }

        composable(Screen.FXAlerts.route) {
            FXAlertsScreen(onNavigateBack = { navController.popBackStack() })
        }
    }
}

package com.example.earlywarningsystem.ui.navigation

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AdminPanelSettings
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.ShowChart
import androidx.compose.material.icons.filled.TableChart
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Devices
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material.icons.outlined.AdminPanelSettings
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.Devices
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Dashboard
import androidx.compose.material.icons.outlined.ShowChart
import androidx.compose.material.icons.outlined.TableChart
import androidx.compose.material.icons.outlined.Warning
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.example.earlywarningsystem.data.model.UserRole
import com.example.earlywarningsystem.di.EwsViewModelFactory
import com.example.earlywarningsystem.ui.admin.AdminScreen
import com.example.earlywarningsystem.ui.admin.AdminViewModel
import com.example.earlywarningsystem.ui.alerts.AlertsScreen
import com.example.earlywarningsystem.ui.alerts.AlertsViewModel
import com.example.earlywarningsystem.ui.auth.AuthViewModel
import com.example.earlywarningsystem.ui.auth.LoginScreen
import com.example.earlywarningsystem.ui.auth.RegisterScreen
import com.example.earlywarningsystem.ui.dashboard.DashboardScreen
import com.example.earlywarningsystem.ui.dashboard.DashboardViewModel
import com.example.earlywarningsystem.ui.forecasts.ForecastsScreen
import com.example.earlywarningsystem.ui.forecasts.ForecastsViewModel
import com.example.earlywarningsystem.ui.account.AccountScreen
import com.example.earlywarningsystem.ui.devicestatus.DeviceStatusScreen
import com.example.earlywarningsystem.ui.devicestatus.DeviceStatusViewModel
import com.example.earlywarningsystem.ui.metrics.MetricsScreen
import com.example.earlywarningsystem.ui.metrics.MetricsViewModel
import com.example.earlywarningsystem.ui.sensorhistory.SensorHistoryScreen
import com.example.earlywarningsystem.ui.sensorhistory.SensorHistoryViewModel

const val ROUTE_LOGIN = "login"
const val ROUTE_REGISTER = "register"
const val ROUTE_DASHBOARD = "dashboard"
const val ROUTE_ALERTS = "alerts"
const val ROUTE_FORECASTS = "forecasts"
const val ROUTE_METRICS = "metrics"
const val ROUTE_ADMIN = "admin"
const val ROUTE_ACCOUNT = "account"
const val ROUTE_DEVICE_STATUS = "device_status"
const val ROUTE_SENSOR_HISTORY = "sensor_history"

@Composable
fun EwsApp(
    viewModelFactory: EwsViewModelFactory
) {
    val authViewModel: AuthViewModel = viewModel(factory = viewModelFactory)
    val userRole by authViewModel.userRole.collectAsState(UserRole.VIEWER)

    MainGraph(
        viewModelFactory = viewModelFactory,
        userRole = userRole,
        authViewModel = authViewModel,
        onLogout = authViewModel::signOut
    )
}

data class MainTab(
    val route: String,
    val label: String,
    val icon: ImageVector,
    val selectedIcon: ImageVector
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MainGraph(
    viewModelFactory: EwsViewModelFactory,
    userRole: UserRole,
    authViewModel: AuthViewModel,
    onLogout: () -> Unit
) {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = navBackStackEntry?.destination

    val allTabs = listOf(
        MainTab(ROUTE_DASHBOARD, "Dash", Icons.Outlined.Dashboard, Icons.Filled.Dashboard),
        MainTab(ROUTE_ALERTS, "Alerts", Icons.Outlined.Warning, Icons.Filled.Warning),
        MainTab(ROUTE_FORECASTS, "Forecast", Icons.Outlined.ShowChart, Icons.Filled.ShowChart),
        MainTab(ROUTE_LOGIN, "Login", Icons.Outlined.Person, Icons.Filled.Person),
        MainTab(ROUTE_DEVICE_STATUS, "Device", Icons.Outlined.Devices, Icons.Filled.Devices),
        MainTab(ROUTE_ADMIN, "SMS", Icons.Outlined.AdminPanelSettings, Icons.Filled.AdminPanelSettings),
        MainTab(ROUTE_ACCOUNT, "Account", Icons.Outlined.Person, Icons.Filled.Person)
    )
    val tabs = if (userRole == UserRole.ADMIN) {
        // When logged in as admin, hide the Login tab and show Admin/Device/Account
        allTabs.filter { it.route != ROUTE_LOGIN }
    } else {
        // When not logged in / non-admin, show Dashboard, Alerts, Forecast, and Login
        allTabs.filter {
            it.route == ROUTE_DASHBOARD ||
                    it.route == ROUTE_ALERTS ||
                    it.route == ROUTE_FORECASTS ||
                    it.route == ROUTE_LOGIN
        }
    }

    // Map nested routes back to their parent tab for highlighting
    val effectiveRoute: String? = when (currentDestination?.route) {
        ROUTE_SENSOR_HISTORY -> ROUTE_DASHBOARD
        ROUTE_METRICS -> ROUTE_FORECASTS
        else -> currentDestination?.route
    }

    Scaffold(
        bottomBar = {
            NavigationBar {
                tabs.forEach { tab ->
                    val isSelectedTab = when (tab.route) {
                        ROUTE_DASHBOARD -> effectiveRoute == ROUTE_DASHBOARD
                        ROUTE_FORECASTS -> effectiveRoute == ROUTE_FORECASTS
                        else -> currentDestination?.hierarchy?.any { it.route == tab.route } == true
                    }
                    NavigationBarItem(
                        icon = {
                            Icon(
                                imageVector = if (isSelectedTab) tab.selectedIcon else tab.icon,
                                contentDescription = tab.label
                            )
                        },
                        label = {
                            Text(
                                text = tab.label,
                                maxLines = 1,
                                overflow = TextOverflow.Clip
                            )
                        },
                        selected = isSelectedTab,
                        onClick = {
                            navController.navigate(tab.route) {
                                popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }
            }
        },
        topBar = {
            androidx.compose.material3.TopAppBar(
                title = { Text("Early Warning System") }
            )
        }
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = ROUTE_DASHBOARD,
            modifier = Modifier.padding(padding)
        ) {
            composable(ROUTE_LOGIN) {
                LoginScreen(
                    viewModel = authViewModel,
                    onLoginSuccess = {
                        navController.navigate(ROUTE_DASHBOARD) {
                            popUpTo(navController.graph.findStartDestination().id) {
                                saveState = true
                            }
                            launchSingleTop = true
                            restoreState = true
                        }
                    }
                )
            }
            composable(ROUTE_REGISTER) {
                RegisterScreen(
                    viewModel = authViewModel,
                    onNavigateBackToLogin = { navController.popBackStack() }
                )
            }
            composable(ROUTE_DASHBOARD) {
                val vm: DashboardViewModel = viewModel(factory = viewModelFactory)
                DashboardScreen(
                    viewModel = vm,
                    userRole = userRole,
                    onOpenHistory = { navController.navigate(ROUTE_SENSOR_HISTORY) }
                )
            }
            composable(ROUTE_ALERTS) {
                val vm: AlertsViewModel = viewModel(factory = viewModelFactory)
                AlertsScreen(viewModel = vm)
            }
            composable(ROUTE_FORECASTS) {
                val vm: ForecastsViewModel = viewModel(factory = viewModelFactory)
                ForecastsScreen(
                    viewModel = vm,
                    onOpenMetrics = { navController.navigate(ROUTE_METRICS) }
                )
            }
            composable(ROUTE_SENSOR_HISTORY) {
                val vm: SensorHistoryViewModel = viewModel(factory = viewModelFactory)
                SensorHistoryScreen(
                    viewModel = vm,
                    onBack = { navController.navigate(ROUTE_DASHBOARD) }
                )
            }
            composable(ROUTE_METRICS) {
                val vm: MetricsViewModel = viewModel(factory = viewModelFactory)
                MetricsScreen(
                    viewModel = vm,
                    onBack = { navController.navigate(ROUTE_FORECASTS) }
                )
            }
            composable(ROUTE_ADMIN) {
                val vm: AdminViewModel = viewModel(factory = viewModelFactory)
                AdminScreen(viewModel = vm)
            }
            composable(ROUTE_DEVICE_STATUS) {
                val vm: DeviceStatusViewModel = viewModel(factory = viewModelFactory)
                DeviceStatusScreen(viewModel = vm)
            }
            composable(ROUTE_ACCOUNT) {
                AccountScreen(
                    viewModel = authViewModel,
                    onLogout = {
                        onLogout()
                        navController.navigate(ROUTE_DASHBOARD) {
                            popUpTo(navController.graph.findStartDestination().id) {
                                saveState = true
                            }
                            launchSingleTop = true
                            restoreState = true
                        }
                    },
                    onAddAdmin = {
                        navController.navigate(ROUTE_REGISTER)
                    }
                )
            }
        }
    }
}

@Composable
private fun AdminLoginPrompt(
    onLoginClick: () -> Unit
) {
    androidx.compose.material3.Surface(
        modifier = Modifier.fillMaxSize()
    ) {
        androidx.compose.foundation.layout.Column(
            modifier = Modifier.padding(24.dp),
            verticalArrangement = androidx.compose.foundation.layout.Arrangement.Center
        ) {
            Text(
                text = "Admin access required",
                style = androidx.compose.material3.MaterialTheme.typography.headlineSmall,
                color = androidx.compose.material3.MaterialTheme.colorScheme.onSurface
            )
            androidx.compose.foundation.layout.Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "Please log in with an admin account to access this page.",
                style = androidx.compose.material3.MaterialTheme.typography.bodyMedium,
                color = androidx.compose.material3.MaterialTheme.colorScheme.onSurfaceVariant
            )
            androidx.compose.foundation.layout.Spacer(modifier = Modifier.height(24.dp))
            androidx.compose.material3.Button(onClick = onLoginClick) {
                Text("Log in as admin")
            }
        }
    }
}

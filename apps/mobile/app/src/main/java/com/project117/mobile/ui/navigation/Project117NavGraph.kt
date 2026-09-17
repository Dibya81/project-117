package com.project117.mobile.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.project117.mobile.ui.screens.*

@Composable
fun Project117NavGraph(
    navController: NavHostController = rememberNavController()
) {
    NavHost(
        navController = navController,
        startDestination = Screen.Login.route
    ) {
        composable(Screen.Login.route) {
            LoginScreen(
                onLoginSuccess = {
                    navController.navigate(Screen.Home.route) {
                        popUpTo(Screen.Login.route) { inclusive = true }
                    }
                },
                onNavigateToSettings = {
                    navController.navigate(Screen.ServerConfig.route)
                },
                onNavigateToEnrollment = {
                    navController.navigate(Screen.Enrollment.route)
                }
            )
        }

        composable(Screen.ServerConfig.route) {
            ServerConfigScreen(
                onNavigateBack = { navController.popBackStack() }
            )
        }

        composable(Screen.Enrollment.route) {
            EnrollmentScreen(
                onEnrollmentSuccess = {
                    navController.navigate(Screen.Login.route) {
                        popUpTo(Screen.Enrollment.route) { inclusive = true }
                    }
                },
                onNavigateToSettings = { navController.navigate(Screen.ServerConfig.route) },
                onNavigateToScan = { navController.navigate(Screen.Scan.route) }
            )
        }

        composable(Screen.Home.route) {
            HomeScreen(
                onNavigateToScan = { navController.navigate(Screen.Scan.route) },
                onNavigateToEquipment = { navController.navigate(Screen.EquipmentList.route) },
                onNavigateToWorkOrders = { navController.navigate(Screen.WorkOrderList.route) },
                onNavigateToWorkOrderDetail = { id -> navController.navigate(Screen.WorkOrderDetail.createRoute(id)) },
                onNavigateToApprovals = { navController.navigate(Screen.Approvals.route) },
                onNavigateToAgentTasks = { navController.navigate(Screen.AgentTasks.route) },
                onNavigateToReportIssue = { navController.navigate(Screen.ReportIssue.createRoute()) },
                onNavigateToSop = { navController.navigate(Screen.SopList.route) },
                onNavigateToNotifications = { navController.navigate(Screen.Notifications.route) },
                onNavigateToAssistant = { navController.navigate(Screen.VoiceAssistant.route) },
                onNavigateToSyncStatus = { navController.navigate(Screen.SyncStatus.route) },
                onNavigateToSettings = { navController.navigate(Screen.ServerConfig.route) },
                onLogout = {
                    navController.navigate(Screen.Login.route) {
                        popUpTo(Screen.Home.route) { inclusive = true }
                    }
                }
            )
        }

        composable(Screen.EquipmentList.route) {
            EquipmentListScreen(
                onNavigateBack = { navController.popBackStack() },
                onNavigateToDetail = { id -> navController.navigate(Screen.EquipmentDetail.createRoute(id)) },
                onNavigateToScan = { navController.navigate(Screen.Scan.route) }
            )
        }

        composable(
            route = Screen.EquipmentDetail.route,
            arguments = listOf(navArgument("equipmentId") { type = NavType.StringType })
        ) { backStackEntry ->
            val eqId = backStackEntry.arguments?.getString("equipmentId") ?: "EQ-P102"
            EquipmentDetailScreen(
                equipmentId = eqId,
                onNavigateBack = { navController.popBackStack() },
                onNavigateToReportIssue = { id -> navController.navigate(Screen.ReportIssue.createRoute(id)) },
                onNavigateToSop = { navController.navigate(Screen.SopList.route) }
            )
        }

        composable(Screen.Scan.route) {
            ScanScreen(
                onNavigateBack = { navController.popBackStack() },
                onEquipmentIdentified = { equipmentId ->
                    navController.navigate(Screen.EquipmentDetail.createRoute(equipmentId)) {
                        popUpTo(Screen.Scan.route) { inclusive = true }
                    }
                }
            )
        }

        composable(Screen.WorkOrderList.route) {
            WorkOrderListScreen(
                onNavigateBack = { navController.popBackStack() },
                onNavigateToDetail = { id -> navController.navigate(Screen.WorkOrderDetail.createRoute(id)) }
            )
        }

        composable(
            route = Screen.WorkOrderDetail.route,
            arguments = listOf(navArgument("workOrderId") { type = NavType.StringType })
        ) { backStackEntry ->
            val woId = backStackEntry.arguments?.getString("workOrderId") ?: "WO-2026-0891"
            WorkOrderDetailScreen(
                workOrderId = woId,
                onNavigateBack = { navController.popBackStack() },
                onNavigateToInspection = { wId, eqId -> navController.navigate(Screen.Inspection.createRoute(wId, eqId)) },
                onNavigateToSop = { navController.navigate(Screen.SopList.route) }
            )
        }

        composable(
            route = Screen.Inspection.route,
            arguments = listOf(
                navArgument("workOrderId") { type = NavType.StringType },
                navArgument("equipmentId") { type = NavType.StringType }
            )
        ) { backStackEntry ->
            val woId = backStackEntry.arguments?.getString("workOrderId") ?: "WO-2026-0891"
            val eqId = backStackEntry.arguments?.getString("equipmentId") ?: "EQ-P102"
            InspectionScreen(
                workOrderId = woId,
                equipmentId = eqId,
                onNavigateBack = { navController.popBackStack() }
            )
        }

        composable(
            route = Screen.ReportIssue.route,
            arguments = listOf(navArgument("equipmentId") {
                type = NavType.StringType
                nullable = true
                defaultValue = null
            })
        ) { backStackEntry ->
            val eqId = backStackEntry.arguments?.getString("equipmentId")
            ReportIssueScreen(
                initialEquipmentId = eqId,
                onNavigateBack = { navController.popBackStack() }
            )
        }

        composable(Screen.SopList.route) {
            SopListScreen(
                onNavigateBack = { navController.popBackStack() },
                onNavigateToDetail = { id -> navController.navigate(Screen.SopDetail.createRoute(id)) }
            )
        }

        composable(
            route = Screen.SopDetail.route,
            arguments = listOf(navArgument("sopId") { type = NavType.StringType })
        ) { backStackEntry ->
            val sopId = backStackEntry.arguments?.getString("sopId") ?: "SOP-MEC-042"
            SopDetailScreen(
                sopId = sopId,
                onNavigateBack = { navController.popBackStack() }
            )
        }

        composable(Screen.Notifications.route) {
            NotificationsScreen(
                onNavigateBack = { navController.popBackStack() }
            )
        }

        composable(Screen.Approvals.route) {
            ApprovalsScreen(
                onNavigateBack = { navController.popBackStack() }
            )
        }

        composable(Screen.AgentTasks.route) {
            AgentTasksScreen(
                onNavigateBack = { navController.popBackStack() },
                onNavigateToInspection = { wId, eqId -> navController.navigate(Screen.Inspection.createRoute(wId, eqId)) }
            )
        }

        composable(Screen.VoiceAssistant.route) {
            VoiceAssistantScreen(
                onNavigateBack = { navController.popBackStack() }
            )
        }

        composable(Screen.SyncStatus.route) {
            SyncStatusScreen(
                onNavigateBack = { navController.popBackStack() }
            )
        }
    }
}

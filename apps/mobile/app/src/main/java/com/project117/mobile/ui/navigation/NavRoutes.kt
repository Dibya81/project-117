package com.project117.mobile.ui.navigation

sealed class Screen(val route: String) {
    object ServerConfig : Screen("server_config")
    object Enrollment : Screen("enrollment")
    object Login : Screen("login")
    object Home : Screen("home")
    object EquipmentList : Screen("equipment_list")
    object EquipmentDetail : Screen("equipment_detail/{equipmentId}") {
        fun createRoute(equipmentId: String) = "equipment_detail/$equipmentId"
    }
    object Scan : Screen("scan")
    object WorkOrderList : Screen("work_order_list")
    object WorkOrderDetail : Screen("work_order_detail/{workOrderId}") {
        fun createRoute(workOrderId: String) = "work_order_detail/$workOrderId"
    }
    object Inspection : Screen("inspection/{workOrderId}/{equipmentId}") {
        fun createRoute(workOrderId: String, equipmentId: String) = "inspection/$workOrderId/$equipmentId"
    }
    object ReportIssue : Screen("report_issue?equipmentId={equipmentId}") {
        fun createRoute(equipmentId: String? = null) = if (equipmentId != null) "report_issue?equipmentId=$equipmentId" else "report_issue"
    }
    object SopList : Screen("sop_list")
    object SopDetail : Screen("sop_detail/{sopId}") {
        fun createRoute(sopId: String) = "sop_detail/$sopId"
    }
    object Notifications : Screen("notifications")
    object Approvals : Screen("approvals")
    object AgentTasks : Screen("agent_tasks")
    object VoiceAssistant : Screen("voice_assistant")
    object SyncStatus : Screen("sync_status")
}

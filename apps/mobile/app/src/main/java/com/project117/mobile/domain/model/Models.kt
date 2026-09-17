package com.project117.mobile.domain.model

// ─── App Mode ─────────────────────────────────────────────────────────────────

/**
 * Operation mode.
 *
 * DEMO       → explicit, intentional. Uses DemoBackend only, entirely in-process.
 *              Shown with a persistent DEMO MODE banner.
 * LOCAL      → LiveBackend over the LAN (cleartext http). Failure = backend/PC offline.
 * PRODUCTION → LiveBackend over HTTPS. Failure = backend offline.
 *
 * LOCAL and PRODUCTION are both "live" modes and NEVER silently fall back to DEMO;
 * an unreachable server is surfaced as offline and queued for sync.
 */
enum class AppMode {
    DEMO,
    LOCAL,
    PRODUCTION;

    /** True for any mode that talks to the real server (LOCAL or PRODUCTION). */
    val isLive get() = this != DEMO
    val isDemo get() = this == DEMO
}

// ─── Server Configuration ─────────────────────────────────────────────────────

data class ServerConfig(
    val baseUrl: String,
    val mode: AppMode,
    val isEnrolled: Boolean = false
)

// ─── User / Auth ──────────────────────────────────────────────────────────────

enum class UserRole {
    TECHNICIAN,
    OPERATOR,
    SUPERVISOR,
    ADMIN,
    UNKNOWN;

    val isSupervisorOrAbove get() = this == SUPERVISOR || this == ADMIN
}

data class UserSession(
    val userId: String,
    val username: String,
    val displayName: String,
    val role: UserRole,
    val permissions: Set<String>,
    val accessToken: String,
    val refreshToken: String
) {
    fun hasPermission(permission: String) = permissions.contains(permission) || role == UserRole.ADMIN
}

object Permissions {
    const val VIEW_EQUIPMENT         = "equipment:view"
    const val VIEW_WORK_ORDERS       = "work_orders:view"
    const val UPDATE_WORK_ORDERS     = "work_orders:update"
    const val VIEW_SOP               = "sop:view"
    const val REPORT_ISSUES          = "issues:create"
    const val CAPTURE_EVIDENCE       = "evidence:capture"
    const val USE_ASSISTANT          = "assistant:use"
    const val VIEW_APPROVALS         = "approvals:view"
    const val DECIDE_APPROVALS       = "approvals:decide"
    const val VIEW_AGENT_TASKS       = "agent_tasks:view"
    const val COMPLETE_AGENT_TASKS   = "agent_tasks:complete"
}

// ─── Equipment ────────────────────────────────────────────────────────────────

enum class EquipmentStatus {
    OPERATIONAL,
    DEGRADED,
    OFFLINE,
    UNDER_MAINTENANCE,
    UNKNOWN
}

data class Equipment(
    val id: String,
    val name: String,
    val type: String,
    val location: String,
    val status: EquipmentStatus,
    val qrCode: String?,
    val barcode: String?,
    val manufacturer: String?,
    val model: String?,
    val serialNumber: String?,
    val lastMaintenanceDate: String?,
    val nextMaintenanceDate: String?,
    val metadata: Map<String, String> = emptyMap(),
    val readings: List<EquipmentReading> = emptyList()
)

data class EquipmentReading(
    val parameter: String,
    val value: String,
    val unit: String,
    val timestamp: String,
    val isNominal: Boolean
)

// ─── Work Orders ──────────────────────────────────────────────────────────────

enum class WorkOrderStatus {
    OPEN,
    ASSIGNED,
    IN_PROGRESS,
    PENDING_APPROVAL,
    COMPLETED,
    CANCELLED,
    FAILED
}

enum class WorkOrderPriority {
    LOW, MEDIUM, HIGH, CRITICAL
}

data class WorkOrder(
    val id: String,
    val title: String,
    val description: String,
    val status: WorkOrderStatus,
    val priority: WorkOrderPriority,
    val assignedTo: String?,
    val equipmentId: String?,
    val equipmentName: String?,
    val dueDate: String?,
    val createdAt: String,
    val updatedAt: String,
    val steps: List<WorkOrderStep> = emptyList(),
    val issueId: String? = null,
    val notes: String? = null
)

data class WorkOrderStep(
    val stepNumber: Int,
    val title: String,
    val description: String,
    val isCompleted: Boolean,
    val evidenceRequired: Boolean,
    val evidenceIds: List<String> = emptyList()
)

// ─── SOP ──────────────────────────────────────────────────────────────────────

data class Sop(
    val id: String,
    val title: String,
    val category: String,
    val version: String,
    val summary: String,
    val content: String,
    val equipmentTypes: List<String> = emptyList(),
    val tags: List<String> = emptyList(),
    val lastUpdated: String
)

// ─── Issues ───────────────────────────────────────────────────────────────────

enum class IssueSeverity {
    LOW, MEDIUM, HIGH, CRITICAL
}

data class Issue(
    val id: String?,  // null when pending sync
    val equipmentId: String,
    val equipmentName: String?,
    val description: String,
    val severity: IssueSeverity,
    val reportedBy: String,
    val reportedAt: String,
    val evidenceIds: List<String> = emptyList(),
    val workOrderId: String? = null,
    val syncStatus: SyncStatus = SyncStatus.SYNCED
)

// ─── Evidence ─────────────────────────────────────────────────────────────────

data class Evidence(
    val id: String?,  // null when pending upload
    val localPath: String,
    val remoteUrl: String?,
    val type: EvidenceType,
    val equipmentId: String?,
    val workOrderId: String?,
    val caption: String?,
    val capturedAt: String,
    val syncStatus: SyncStatus = SyncStatus.SAVED_LOCALLY
)

enum class EvidenceType { PHOTO, AUDIO, DOCUMENT }

// ─── Assistant / Chatbot ──────────────────────────────────────────────────────

data class ChatMessage(
    val id: String,
    val content: String,
    val role: MessageRole,
    val timestamp: String,
    val isError: Boolean = false
)

enum class MessageRole { USER, ASSISTANT }

data class AssistantContext(
    val equipmentId: String? = null,
    val workOrderId: String? = null
)

// ─── Notifications ────────────────────────────────────────────────────────────

enum class NotificationType {
    ASSIGNMENT,
    WORK_ORDER_UPDATE,
    APPROVAL_REQUIRED,
    AGENT_TASK,
    ALERT,
    SYSTEM
}

data class AppNotification(
    val id: String,
    val type: NotificationType,
    val title: String,
    val body: String,
    val timestamp: String,
    val isRead: Boolean,
    val referenceId: String? = null,   // work order id, approval id, etc.
    val referenceType: String? = null
)

// ─── Approvals ────────────────────────────────────────────────────────────────

enum class ApprovalDecision { APPROVE, REJECT }

data class Approval(
    val id: String,
    val title: String,
    val description: String,
    val workOrderId: String?,
    val workOrderTitle: String?,
    val equipmentId: String?,
    val equipmentName: String?,
    val consequence: String,
    val requestedBy: String,
    val requestedAt: String,
    val deadline: String?,
    val evidenceIds: List<String> = emptyList(),
    val status: ApprovalStatus = ApprovalStatus.PENDING
)

enum class ApprovalStatus { PENDING, APPROVED, REJECTED, EXPIRED }

// ─── Agent Tasks ──────────────────────────────────────────────────────────────

enum class AgentTaskPriority { LOW, MEDIUM, HIGH, URGENT }

enum class AgentTaskStatus { PENDING, ACKNOWLEDGED, IN_PROGRESS, COMPLETED, FAILED }

data class AgentTask(
    val id: String,
    val title: String,
    val description: String,
    val source: String,          // "AI Orchestrator" / "Predictive Agent" etc.
    val priority: AgentTaskPriority,
    val status: AgentTaskStatus,
    val equipmentId: String?,
    val equipmentName: String?,
    val workOrderId: String?,
    val instructions: String,
    val evidenceRequired: Boolean,
    val dueBy: String?,
    val createdAt: String
)

// ─── Sync ─────────────────────────────────────────────────────────────────────

enum class SyncStatus {
    SAVED_LOCALLY,
    QUEUED,
    SYNCING,
    SYNCED,
    FAILED
}

// ─── UI Result Types ─────────────────────────────────────────────────────────

sealed class UiState<out T> {
    object Idle : UiState<Nothing>()
    object Loading : UiState<Nothing>()
    data class Success<T>(val data: T) : UiState<T>()
    data class Error(val message: String, val isBackendOffline: Boolean = false) : UiState<Nothing>()
    object Offline : UiState<Nothing>()
    object Unauthorized : UiState<Nothing>()
}

sealed class BackendResult<out T> {
    data class Success<T>(val data: T) : BackendResult<T>()
    data class Error(val message: String, val code: Int = 0) : BackendResult<Nothing>()
    object BackendOffline : BackendResult<Nothing>()
    object Unauthorized : BackendResult<Nothing>()
    object NotFound : BackendResult<Nothing>()
}

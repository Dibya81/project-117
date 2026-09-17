package com.project117.mobile.data.local.entities

import androidx.room.*

// ─── Pending Action (Offline Queue) ──────────────────────────────────────────

/**
 * PendingAction represents a MOBILE → SERVER queued operation.
 *
 * Rules:
 * - ONLY used for operations initiated by the mobile user that could not be
 *   sent immediately (e.g., offline issue report, evidence upload).
 * - Server → Mobile events (WebSocket/push) are NEVER stored as PendingAction.
 * - SyncWorker picks up PENDING items, retries on network availability.
 */
@Entity(tableName = "pending_actions")
data class PendingActionEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,

    /** Action type identifier */
    val actionType: String,

    /** JSON-encoded payload */
    val payload: String,

    /** Current retry count */
    val retryCount: Int = 0,

    /** Max retries before marking FAILED */
    val maxRetries: Int = 5,

    /** Timestamp (epoch ms) when action was created */
    val createdAt: Long = System.currentTimeMillis(),

    /** Timestamp of last attempt */
    val lastAttemptAt: Long? = null,

    /** PENDING | SYNCING | SYNCED | FAILED */
    val status: String = "PENDING",

    /** Error message from last failure */
    val lastError: String? = null,

    /** Optional: local file path for evidence uploads */
    val localFilePath: String? = null
)

object PendingActionTypes {
    const val REPORT_ISSUE        = "report_issue"
    const val UPLOAD_EVIDENCE     = "upload_evidence"
    const val UPDATE_WORK_ORDER   = "update_work_order"
    const val COMPLETE_AGENT_TASK = "complete_agent_task"
    const val DECIDE_APPROVAL     = "decide_approval"
    const val MARK_NOTIFICATION   = "mark_notification_read"
}

// ─── Cached Equipment ─────────────────────────────────────────────────────────

@Entity(tableName = "equipment_cache")
data class EquipmentCacheEntity(
    @PrimaryKey
    val id: String,
    val json: String,  // full serialized Equipment JSON
    val cachedAt: Long = System.currentTimeMillis()
)

// ─── Cached Work Orders ───────────────────────────────────────────────────────

@Entity(tableName = "work_order_cache")
data class WorkOrderCacheEntity(
    @PrimaryKey
    val id: String,
    val json: String,
    val cachedAt: Long = System.currentTimeMillis()
)

// ─── Cached SOP ───────────────────────────────────────────────────────────────

@Entity(tableName = "sop_cache")
data class SopCacheEntity(
    @PrimaryKey
    val id: String,
    val json: String,
    val cachedAt: Long = System.currentTimeMillis()
)

// ─── Local Evidence ───────────────────────────────────────────────────────────

@Entity(tableName = "local_evidence")
data class LocalEvidenceEntity(
    @PrimaryKey
    val localId: String,
    val localPath: String,
    val remoteId: String? = null,
    val type: String,
    val equipmentId: String?,
    val workOrderId: String?,
    val caption: String?,
    val capturedAt: Long,
    val syncStatus: String = "SAVED_LOCALLY"  // SAVED_LOCALLY | QUEUED | SYNCING | SYNCED | FAILED
)

// ─── Chat History ─────────────────────────────────────────────────────────────

@Entity(tableName = "chat_messages")
data class ChatMessageEntity(
    @PrimaryKey
    val id: String,
    val content: String,
    val role: String,  // "USER" | "ASSISTANT"
    val timestamp: Long,
    val isError: Boolean = false
)

// ─── Cached Notifications ─────────────────────────────────────────────────────

@Entity(tableName = "notifications_cache")
data class NotificationEntity(
    @PrimaryKey
    val id: String,
    val json: String,
    val isRead: Boolean = false,
    val cachedAt: Long = System.currentTimeMillis()
)

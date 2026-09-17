package com.project117.mobile.data.remote.dto

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

// ─── Auth ─────────────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class EnrollRequest(
    @Json(name = "device_id") val deviceId: String,
    @Json(name = "enrollment_code") val enrollmentCode: String
)

@JsonClass(generateAdapter = true)
data class EnrollResponse(
    @Json(name = "enrolled") val enrolled: Boolean,
    @Json(name = "device_token") val deviceToken: String
)

@JsonClass(generateAdapter = true)
data class LoginRequest(
    @Json(name = "username") val username: String,
    @Json(name = "password") val password: String,
    @Json(name = "device_token") val deviceToken: String
)

@JsonClass(generateAdapter = true)
data class LoginResponse(
    @Json(name = "access_token") val accessToken: String,
    @Json(name = "refresh_token") val refreshToken: String,
    @Json(name = "user_id") val userId: String,
    @Json(name = "username") val username: String,
    @Json(name = "display_name") val displayName: String,
    @Json(name = "role") val role: String,
    @Json(name = "permissions") val permissions: List<String>
)

@JsonClass(generateAdapter = true)
data class RefreshRequest(
    @Json(name = "refresh_token") val refreshToken: String
)

@JsonClass(generateAdapter = true)
data class RefreshResponse(
    @Json(name = "access_token") val accessToken: String
)

@JsonClass(generateAdapter = true)
data class MeResponse(
    @Json(name = "user_id") val userId: String,
    @Json(name = "username") val username: String,
    @Json(name = "display_name") val displayName: String,
    @Json(name = "role") val role: String,
    @Json(name = "permissions") val permissions: List<String>
)

// ─── Equipment ────────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class EquipmentDto(
    @Json(name = "id") val id: String,
    @Json(name = "name") val name: String,
    @Json(name = "type") val type: String,
    @Json(name = "location") val location: String,
    @Json(name = "status") val status: String,
    @Json(name = "qr_code") val qrCode: String?,
    @Json(name = "barcode") val barcode: String?,
    @Json(name = "manufacturer") val manufacturer: String?,
    @Json(name = "model") val model: String?,
    @Json(name = "serial_number") val serialNumber: String?,
    @Json(name = "last_maintenance_date") val lastMaintenanceDate: String?,
    @Json(name = "next_maintenance_date") val nextMaintenanceDate: String?,
    @Json(name = "metadata") val metadata: Map<String, String>?,
    @Json(name = "readings") val readings: List<ReadingDto>?
)

@JsonClass(generateAdapter = true)
data class ReadingDto(
    @Json(name = "parameter") val parameter: String,
    @Json(name = "value") val value: String,
    @Json(name = "unit") val unit: String,
    @Json(name = "timestamp") val timestamp: String,
    @Json(name = "is_nominal") val isNominal: Boolean
)

@JsonClass(generateAdapter = true)
data class IdentifyEquipmentRequest(
    @Json(name = "qr_code") val qrCode: String
)

@JsonClass(generateAdapter = true)
data class EquipmentListResponse(
    @Json(name = "items") val items: List<EquipmentDto>
)

// ─── Work Orders ──────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class WorkOrderDto(
    @Json(name = "id") val id: String,
    @Json(name = "title") val title: String,
    @Json(name = "description") val description: String,
    @Json(name = "status") val status: String,
    @Json(name = "priority") val priority: String,
    @Json(name = "assigned_to") val assignedTo: String?,
    @Json(name = "equipment_id") val equipmentId: String?,
    @Json(name = "equipment_name") val equipmentName: String?,
    @Json(name = "due_date") val dueDate: String?,
    @Json(name = "created_at") val createdAt: String,
    @Json(name = "updated_at") val updatedAt: String,
    @Json(name = "steps") val steps: List<WorkOrderStepDto>?,
    @Json(name = "issue_id") val issueId: String?,
    @Json(name = "notes") val notes: String?
)

@JsonClass(generateAdapter = true)
data class WorkOrderStepDto(
    @Json(name = "step_number") val stepNumber: Int,
    @Json(name = "title") val title: String,
    @Json(name = "description") val description: String,
    @Json(name = "is_completed") val isCompleted: Boolean,
    @Json(name = "evidence_required") val evidenceRequired: Boolean,
    @Json(name = "evidence_ids") val evidenceIds: List<String>?
)

@JsonClass(generateAdapter = true)
data class WorkOrderListResponse(
    @Json(name = "items") val items: List<WorkOrderDto>
)

@JsonClass(generateAdapter = true)
data class UpdateWorkOrderRequest(
    @Json(name = "status") val status: String,
    @Json(name = "notes") val notes: String?
)

// ─── SOP ──────────────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class SopDto(
    @Json(name = "id") val id: String,
    @Json(name = "title") val title: String,
    @Json(name = "category") val category: String,
    @Json(name = "version") val version: String,
    @Json(name = "summary") val summary: String,
    @Json(name = "content") val content: String,
    @Json(name = "equipment_types") val equipmentTypes: List<String>?,
    @Json(name = "tags") val tags: List<String>?,
    @Json(name = "last_updated") val lastUpdated: String
)

@JsonClass(generateAdapter = true)
data class SopListResponse(
    @Json(name = "items") val items: List<SopDto>
)

// ─── Issues ───────────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class ReportIssueRequest(
    @Json(name = "equipment_id") val equipmentId: String,
    @Json(name = "description") val description: String,
    @Json(name = "severity") val severity: String,
    @Json(name = "evidence_ids") val evidenceIds: List<String>
)

@JsonClass(generateAdapter = true)
data class IssueResponse(
    @Json(name = "id") val id: String,
    @Json(name = "equipment_id") val equipmentId: String,
    @Json(name = "equipment_name") val equipmentName: String?,
    @Json(name = "description") val description: String,
    @Json(name = "severity") val severity: String,
    @Json(name = "reported_by") val reportedBy: String,
    @Json(name = "reported_at") val reportedAt: String,
    @Json(name = "work_order_id") val workOrderId: String?
)

// ─── Chat / Assistant ─────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class ChatRequest(
    @Json(name = "message") val message: String,
    @Json(name = "equipment_id") val equipmentId: String?,
    @Json(name = "work_order_id") val workOrderId: String?
)

@JsonClass(generateAdapter = true)
data class ChatResponse(
    @Json(name = "response") val response: String
)

// ─── Notifications ────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class NotificationDto(
    @Json(name = "id") val id: String,
    @Json(name = "type") val type: String,
    @Json(name = "title") val title: String,
    @Json(name = "body") val body: String,
    @Json(name = "timestamp") val timestamp: String,
    @Json(name = "is_read") val isRead: Boolean,
    @Json(name = "reference_id") val referenceId: String?,
    @Json(name = "reference_type") val referenceType: String?
)

@JsonClass(generateAdapter = true)
data class NotificationsListResponse(
    @Json(name = "items") val items: List<NotificationDto>
)

// ─── Approvals ────────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class ApprovalDto(
    @Json(name = "id") val id: String,
    @Json(name = "title") val title: String,
    @Json(name = "description") val description: String,
    @Json(name = "work_order_id") val workOrderId: String?,
    @Json(name = "work_order_title") val workOrderTitle: String?,
    @Json(name = "equipment_id") val equipmentId: String?,
    @Json(name = "equipment_name") val equipmentName: String?,
    @Json(name = "consequence") val consequence: String,
    @Json(name = "requested_by") val requestedBy: String,
    @Json(name = "requested_at") val requestedAt: String,
    @Json(name = "deadline") val deadline: String?,
    @Json(name = "status") val status: String
)

@JsonClass(generateAdapter = true)
data class ApprovalsListResponse(
    @Json(name = "items") val items: List<ApprovalDto>
)

@JsonClass(generateAdapter = true)
data class ApprovalDecisionRequest(
    @Json(name = "decision") val decision: String,  // "approve" | "reject"
    @Json(name = "notes") val notes: String?
)

// ─── Agent Tasks ──────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class AgentTaskDto(
    @Json(name = "id") val id: String,
    @Json(name = "title") val title: String,
    @Json(name = "description") val description: String,
    @Json(name = "source") val source: String,
    @Json(name = "priority") val priority: String,
    @Json(name = "status") val status: String,
    @Json(name = "equipment_id") val equipmentId: String?,
    @Json(name = "equipment_name") val equipmentName: String?,
    @Json(name = "work_order_id") val workOrderId: String?,
    @Json(name = "instructions") val instructions: String,
    @Json(name = "evidence_required") val evidenceRequired: Boolean,
    @Json(name = "due_by") val dueBy: String?,
    @Json(name = "created_at") val createdAt: String
)

@JsonClass(generateAdapter = true)
data class AgentTasksListResponse(
    @Json(name = "items") val items: List<AgentTaskDto>
)

@JsonClass(generateAdapter = true)
data class CompleteAgentTaskRequest(
    @Json(name = "notes") val notes: String?,
    @Json(name = "evidence_ids") val evidenceIds: List<String>
)

// ─── Evidence ─────────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class UploadEvidenceResponse(
    @Json(name = "document_id") val documentId: String
)

// ─── Health ───────────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class HealthResponse(
    @Json(name = "status") val status: String
)

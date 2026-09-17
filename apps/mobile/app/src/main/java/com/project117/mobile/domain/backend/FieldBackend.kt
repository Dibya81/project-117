package com.project117.mobile.domain.backend

import com.project117.mobile.domain.model.*

/**
 * FieldBackend is the single abstraction layer between all repositories and the
 * actual backend implementation (LIVE or DEMO).
 *
 * Contract rules:
 * - LIVE mode: uses Retrofit → real server. Backend failure = BackendResult.BackendOffline.
 *   NEVER silently returns demo data on failure.
 * - DEMO mode: uses DemoBackend. Explicitly selected only.
 *   Always shows DEMO MODE banner.
 * - APK does NOT call any public AI/cloud API. All AI routes go through this interface
 *   → LiveBackend → on-prem server.
 */
interface FieldBackend {

    // ─── Health ───────────────────────────────────────────────────────────────

    suspend fun checkHealth(): BackendResult<Boolean>

    // ─── Enrollment ───────────────────────────────────────────────────────────

    suspend fun enroll(deviceId: String, enrollmentCode: String): BackendResult<String>

    // ─── Auth ─────────────────────────────────────────────────────────────────

    suspend fun login(username: String, password: String, deviceToken: String): BackendResult<UserSession>
    suspend fun refreshToken(refreshToken: String): BackendResult<String>
    suspend fun logout(accessToken: String): BackendResult<Unit>
    suspend fun getMe(accessToken: String): BackendResult<UserSession>

    // ─── Equipment ────────────────────────────────────────────────────────────

    suspend fun getEquipmentList(): BackendResult<List<Equipment>>
    suspend fun getEquipment(id: String): BackendResult<Equipment>
    suspend fun identifyEquipment(qrCode: String): BackendResult<Equipment>

    // ─── Work Orders ──────────────────────────────────────────────────────────

    suspend fun getWorkOrders(): BackendResult<List<WorkOrder>>
    suspend fun getWorkOrder(id: String): BackendResult<WorkOrder>
    suspend fun updateWorkOrder(id: String, status: WorkOrderStatus, notes: String?): BackendResult<WorkOrder>

    // ─── Agent Tasks ──────────────────────────────────────────────────────────

    suspend fun getAgentTasks(): BackendResult<List<AgentTask>>
    suspend fun acknowledgeAgentTask(id: String): BackendResult<AgentTask>
    suspend fun completeAgentTask(id: String, notes: String?, evidenceIds: List<String>): BackendResult<AgentTask>

    // ─── Approvals ────────────────────────────────────────────────────────────

    suspend fun getApprovals(): BackendResult<List<Approval>>
    suspend fun decideApproval(id: String, decision: ApprovalDecision, notes: String?): BackendResult<Approval>

    // ─── Chat / Assistant ─────────────────────────────────────────────────────
    // APK does NOT call OpenAI/Gemini/Anthropic directly.
    // This routes to the on-prem backend AI orchestrator.

    suspend fun sendMessage(message: String, context: AssistantContext?): BackendResult<String>

    // ─── SOP / Knowledge ──────────────────────────────────────────────────────

    suspend fun getSopList(): BackendResult<List<Sop>>
    suspend fun getSop(id: String): BackendResult<Sop>

    // ─── Issues ───────────────────────────────────────────────────────────────

    suspend fun reportIssue(
        equipmentId: String,
        description: String,
        severity: IssueSeverity,
        evidenceIds: List<String>
    ): BackendResult<Issue>

    // ─── Evidence / Documents ─────────────────────────────────────────────────

    suspend fun uploadEvidence(
        localPath: String,
        type: EvidenceType,
        equipmentId: String?,
        workOrderId: String?,
        caption: String?
    ): BackendResult<String>  // returns remote document ID

    // ─── Notifications ────────────────────────────────────────────────────────

    suspend fun getNotifications(): BackendResult<List<AppNotification>>
    suspend fun markNotificationRead(id: String): BackendResult<Unit>
}

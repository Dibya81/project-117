package com.project117.mobile.data.backend

import com.project117.mobile.data.local.preferences.SessionManager
import com.project117.mobile.domain.backend.FieldBackend
import com.project117.mobile.domain.model.*
import javax.inject.Inject
import javax.inject.Singleton

/**
 * DynamicFieldBackend routes operations to either LiveBackend or DemoBackend
 * based strictly on the user's configured AppMode in SessionManager.
 *
 * DEMO always uses DemoBackend. LOCAL and PRODUCTION both use LiveBackend.
 * It NEVER silently falls back from a live mode to DEMO: a live backend that is
 * unreachable returns BackendResult.BackendOffline so the caller can queue work.
 */
@Singleton
class DynamicFieldBackend @Inject constructor(
    private val liveBackend: LiveBackend,
    private val demoBackend: DemoBackend,
    private val sessionManager: SessionManager
) : FieldBackend {

    private val delegate: FieldBackend
        get() = if (sessionManager.appMode.value.isLive) liveBackend else demoBackend

    override suspend fun checkHealth(): BackendResult<Boolean> = delegate.checkHealth()
    override suspend fun enroll(deviceId: String, enrollmentCode: String): BackendResult<String> = delegate.enroll(deviceId, enrollmentCode)
    override suspend fun login(username: String, password: String, deviceToken: String): BackendResult<UserSession> = delegate.login(username, password, deviceToken)
    override suspend fun refreshToken(refreshToken: String): BackendResult<String> = delegate.refreshToken(refreshToken)
    override suspend fun logout(accessToken: String): BackendResult<Unit> = delegate.logout(accessToken)
    override suspend fun getMe(accessToken: String): BackendResult<UserSession> = delegate.getMe(accessToken)
    override suspend fun getEquipmentList(): BackendResult<List<Equipment>> = delegate.getEquipmentList()
    override suspend fun getEquipment(id: String): BackendResult<Equipment> = delegate.getEquipment(id)
    override suspend fun identifyEquipment(qrCode: String): BackendResult<Equipment> = delegate.identifyEquipment(qrCode)
    override suspend fun getWorkOrders(): BackendResult<List<WorkOrder>> = delegate.getWorkOrders()
    override suspend fun getWorkOrder(id: String): BackendResult<WorkOrder> = delegate.getWorkOrder(id)
    override suspend fun updateWorkOrder(id: String, status: WorkOrderStatus, notes: String?): BackendResult<WorkOrder> = delegate.updateWorkOrder(id, status, notes)
    override suspend fun getAgentTasks(): BackendResult<List<AgentTask>> = delegate.getAgentTasks()
    override suspend fun acknowledgeAgentTask(id: String): BackendResult<AgentTask> = delegate.acknowledgeAgentTask(id)
    override suspend fun completeAgentTask(id: String, notes: String?, evidenceIds: List<String>): BackendResult<AgentTask> = delegate.completeAgentTask(id, notes, evidenceIds)
    override suspend fun getApprovals(): BackendResult<List<Approval>> = delegate.getApprovals()
    override suspend fun decideApproval(id: String, decision: ApprovalDecision, notes: String?): BackendResult<Approval> = delegate.decideApproval(id, decision, notes)
    override suspend fun sendMessage(message: String, context: AssistantContext?): BackendResult<String> = delegate.sendMessage(message, context)
    override suspend fun getSopList(): BackendResult<List<Sop>> = delegate.getSopList()
    override suspend fun getSop(id: String): BackendResult<Sop> = delegate.getSop(id)
    override suspend fun reportIssue(equipmentId: String, description: String, severity: IssueSeverity, evidenceIds: List<String>): BackendResult<Issue> = delegate.reportIssue(equipmentId, description, severity, evidenceIds)
    override suspend fun uploadEvidence(localPath: String, type: EvidenceType, equipmentId: String?, workOrderId: String?, caption: String?): BackendResult<String> = delegate.uploadEvidence(localPath, type, equipmentId, workOrderId, caption)
    override suspend fun getNotifications(): BackendResult<List<AppNotification>> = delegate.getNotifications()
    override suspend fun markNotificationRead(id: String): BackendResult<Unit> = delegate.markNotificationRead(id)
}

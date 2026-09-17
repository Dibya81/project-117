package com.project117.mobile.data.backend

import com.project117.mobile.data.remote.api.Project117Api
import com.project117.mobile.data.remote.dto.*
import com.project117.mobile.domain.backend.FieldBackend
import com.project117.mobile.domain.model.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.Response
import timber.log.Timber
import java.io.File
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class LiveBackend @Inject constructor(
    private val api: Project117Api
) : FieldBackend {

    private suspend fun <T, R> safeApiCall(
        apiCall: suspend () -> Response<T>,
        transform: (T) -> R
    ): BackendResult<R> {
        return try {
            val response = apiCall()
            when {
                response.isSuccessful -> {
                    val body = response.body()
                    if (body != null) {
                        BackendResult.Success(transform(body))
                    } else {
                        BackendResult.Error("Empty response body from server", response.code())
                    }
                }
                response.code() == 401 -> BackendResult.Unauthorized
                response.code() == 404 -> BackendResult.NotFound
                else -> BackendResult.Error(response.message().ifBlank { "HTTP Error ${response.code()}" }, response.code())
            }
        } catch (e: IOException) {
            Timber.w(e, "LiveBackend connection failed: Backend offline")
            BackendResult.BackendOffline
        } catch (e: Exception) {
            Timber.e(e, "LiveBackend unexpected error")
            BackendResult.Error(e.message ?: "Unknown error")
        }
    }

    override suspend fun checkHealth(): BackendResult<Boolean> {
        return safeApiCall({ api.getHealth() }) { it.status.equals("ok", ignoreCase = true) }
    }

    override suspend fun enroll(deviceId: String, enrollmentCode: String): BackendResult<String> {
        return safeApiCall({ api.enroll(EnrollRequest(deviceId, enrollmentCode)) }) { it.deviceToken }
    }

    override suspend fun login(username: String, password: String, deviceToken: String): BackendResult<UserSession> {
        return safeApiCall({ api.login(LoginRequest(username, password, deviceToken)) }) { res ->
            UserSession(
                userId = res.userId,
                username = res.username,
                displayName = res.displayName,
                role = parseRole(res.role),
                permissions = res.permissions.toSet(),
                accessToken = res.accessToken,
                refreshToken = res.refreshToken
            )
        }
    }

    override suspend fun refreshToken(refreshToken: String): BackendResult<String> {
        return safeApiCall({ api.refreshToken(RefreshRequest(refreshToken)) }) { it.accessToken }
    }

    override suspend fun logout(accessToken: String): BackendResult<Unit> {
        return safeApiCall({ api.logout() }) { }
    }

    override suspend fun getMe(accessToken: String): BackendResult<UserSession> {
        return safeApiCall({ api.getMe() }) { res ->
            UserSession(
                userId = res.userId,
                username = res.username,
                displayName = res.displayName,
                role = parseRole(res.role),
                permissions = res.permissions.toSet(),
                accessToken = accessToken,
                refreshToken = ""
            )
        }
    }

    override suspend fun getEquipmentList(): BackendResult<List<Equipment>> {
        return safeApiCall({ api.getEquipmentList() }) { res ->
            res.items.map { it.toDomain() }
        }
    }

    override suspend fun getEquipment(id: String): BackendResult<Equipment> {
        return safeApiCall({ api.getEquipment(id) }) { it.toDomain() }
    }

    override suspend fun identifyEquipment(qrCode: String): BackendResult<Equipment> {
        return safeApiCall({ api.identifyEquipment(IdentifyEquipmentRequest(qrCode)) }) { it.toDomain() }
    }

    override suspend fun getWorkOrders(): BackendResult<List<WorkOrder>> {
        return safeApiCall({ api.getWorkOrders() }) { res ->
            res.items.map { it.toDomain() }
        }
    }

    override suspend fun getWorkOrder(id: String): BackendResult<WorkOrder> {
        return safeApiCall({ api.getWorkOrder(id) }) { it.toDomain() }
    }

    override suspend fun updateWorkOrder(id: String, status: WorkOrderStatus, notes: String?): BackendResult<WorkOrder> {
        return safeApiCall({
            api.updateWorkOrder(id, UpdateWorkOrderRequest(status.name, notes))
        }) { it.toDomain() }
    }

    override suspend fun getAgentTasks(): BackendResult<List<AgentTask>> {
        return safeApiCall({ api.getAgentTasks() }) { res ->
            res.items.map { it.toDomain() }
        }
    }

    override suspend fun acknowledgeAgentTask(id: String): BackendResult<AgentTask> {
        return safeApiCall({ api.acknowledgeAgentTask(id) }) { it.toDomain() }
    }

    override suspend fun completeAgentTask(id: String, notes: String?, evidenceIds: List<String>): BackendResult<AgentTask> {
        return safeApiCall({
            api.completeAgentTask(id, CompleteAgentTaskRequest(notes, evidenceIds))
        }) { it.toDomain() }
    }

    override suspend fun getApprovals(): BackendResult<List<Approval>> {
        return safeApiCall({ api.getApprovals() }) { res ->
            res.items.map { it.toDomain() }
        }
    }

    override suspend fun decideApproval(id: String, decision: ApprovalDecision, notes: String?): BackendResult<Approval> {
        val decisionStr = if (decision == ApprovalDecision.APPROVE) "approve" else "reject"
        return safeApiCall({
            api.decideApproval(id, ApprovalDecisionRequest(decisionStr, notes))
        }) { it.toDomain() }
    }

    override suspend fun sendMessage(message: String, context: AssistantContext?): BackendResult<String> {
        return safeApiCall({
            api.sendMessage(ChatRequest(message, context?.equipmentId, context?.workOrderId))
        }) { it.response }
    }

    override suspend fun getSopList(): BackendResult<List<Sop>> {
        return safeApiCall({ api.getSopList() }) { res ->
            res.items.map { it.toDomain() }
        }
    }

    override suspend fun getSop(id: String): BackendResult<Sop> {
        return safeApiCall({ api.getSop(id) }) { it.toDomain() }
    }

    override suspend fun reportIssue(
        equipmentId: String,
        description: String,
        severity: IssueSeverity,
        evidenceIds: List<String>
    ): BackendResult<Issue> {
        return safeApiCall({
            api.reportIssue(ReportIssueRequest(equipmentId, description, severity.name, evidenceIds))
        }) { res ->
            Issue(
                id = res.id,
                equipmentId = res.equipmentId,
                equipmentName = res.equipmentName,
                description = res.description,
                severity = severity,
                reportedBy = res.reportedBy,
                reportedAt = res.reportedAt,
                evidenceIds = evidenceIds,
                workOrderId = res.workOrderId,
                syncStatus = SyncStatus.SYNCED
            )
        }
    }

    override suspend fun uploadEvidence(
        localPath: String,
        type: EvidenceType,
        equipmentId: String?,
        workOrderId: String?,
        caption: String?
    ): BackendResult<String> {
        return try {
            val file = File(localPath)
            if (!file.exists()) {
                return BackendResult.Error("Local file does not exist: $localPath")
            }
            val mimeType = when (type) {
                EvidenceType.PHOTO -> "image/jpeg"
                EvidenceType.AUDIO -> "audio/wav"
                EvidenceType.DOCUMENT -> "application/pdf"
            }
            val requestFile = file.asRequestBody(mimeType.toMediaTypeOrNull())
            val body = MultipartBody.Part.createFormData("file", file.name, requestFile)
            val eqPart = equipmentId?.toRequestBody("text/plain".toMediaTypeOrNull())
            val woPart = workOrderId?.toRequestBody("text/plain".toMediaTypeOrNull())
            val capPart = caption?.toRequestBody("text/plain".toMediaTypeOrNull())

            val res = api.uploadEvidence(body, eqPart, woPart, capPart)
            if (res.isSuccessful && res.body() != null) {
                BackendResult.Success(res.body()!!.documentId)
            } else {
                BackendResult.Error("Failed to upload evidence: ${res.code()}", res.code())
            }
        } catch (e: IOException) {
            BackendResult.BackendOffline
        } catch (e: Exception) {
            BackendResult.Error(e.message ?: "Upload failed")
        }
    }

    override suspend fun getNotifications(): BackendResult<List<AppNotification>> {
        return safeApiCall({ api.getNotifications() }) { res ->
            res.items.map { it.toDomain() }
        }
    }

    override suspend fun markNotificationRead(id: String): BackendResult<Unit> {
        return safeApiCall({ api.markNotificationRead(id) }) { }
    }

    private fun parseRole(roleStr: String): UserRole {
        return try {
            UserRole.valueOf(roleStr.uppercase())
        } catch (e: Exception) {
            UserRole.UNKNOWN
        }
    }

    // ─── DTO Mappings ─────────────────────────────────────────────────────────

    private fun EquipmentDto.toDomain() = Equipment(
        id = id,
        name = name,
        type = type,
        location = location,
        status = parseEquipmentStatus(status),
        qrCode = qrCode,
        barcode = barcode,
        manufacturer = manufacturer,
        model = model,
        serialNumber = serialNumber,
        lastMaintenanceDate = lastMaintenanceDate,
        nextMaintenanceDate = nextMaintenanceDate,
        metadata = metadata ?: emptyMap(),
        readings = readings?.map { EquipmentReading(it.parameter, it.value, it.unit, it.timestamp, it.isNominal) } ?: emptyList()
    )

    private fun parseEquipmentStatus(status: String): EquipmentStatus {
        return try {
            EquipmentStatus.valueOf(status.uppercase())
        } catch (e: Exception) {
            EquipmentStatus.UNKNOWN
        }
    }

    private fun WorkOrderDto.toDomain() = WorkOrder(
        id = id,
        title = title,
        description = description,
        status = parseWorkOrderStatus(status),
        priority = parsePriority(priority),
        assignedTo = assignedTo,
        equipmentId = equipmentId,
        equipmentName = equipmentName,
        dueDate = dueDate,
        createdAt = createdAt,
        updatedAt = updatedAt,
        steps = steps?.map { WorkOrderStep(it.stepNumber, it.title, it.description, it.isCompleted, it.evidenceRequired, it.evidenceIds ?: emptyList()) } ?: emptyList(),
        issueId = issueId,
        notes = notes
    )

    private fun parseWorkOrderStatus(s: String) = try { WorkOrderStatus.valueOf(s.uppercase()) } catch (e: Exception) { WorkOrderStatus.OPEN }
    private fun parsePriority(s: String) = try { WorkOrderPriority.valueOf(s.uppercase()) } catch (e: Exception) { WorkOrderPriority.MEDIUM }

    private fun AgentTaskDto.toDomain() = AgentTask(
        id = id,
        title = title,
        description = description,
        source = source,
        priority = try { AgentTaskPriority.valueOf(priority.uppercase()) } catch (e: Exception) { AgentTaskPriority.MEDIUM },
        status = try { AgentTaskStatus.valueOf(status.uppercase()) } catch (e: Exception) { AgentTaskStatus.PENDING },
        equipmentId = equipmentId,
        equipmentName = equipmentName,
        workOrderId = workOrderId,
        instructions = instructions,
        evidenceRequired = evidenceRequired,
        dueBy = dueBy,
        createdAt = createdAt
    )

    private fun ApprovalDto.toDomain() = Approval(
        id = id,
        title = title,
        description = description,
        workOrderId = workOrderId,
        workOrderTitle = workOrderTitle,
        equipmentId = equipmentId,
        equipmentName = equipmentName,
        consequence = consequence,
        requestedBy = requestedBy,
        requestedAt = requestedAt,
        deadline = deadline,
        status = try { ApprovalStatus.valueOf(status.uppercase()) } catch (e: Exception) { ApprovalStatus.PENDING }
    )

    private fun SopDto.toDomain() = Sop(
        id = id,
        title = title,
        category = category,
        version = version,
        summary = summary,
        content = content,
        equipmentTypes = equipmentTypes ?: emptyList(),
        tags = tags ?: emptyList(),
        lastUpdated = lastUpdated
    )

    private fun NotificationDto.toDomain() = AppNotification(
        id = id,
        type = try { NotificationType.valueOf(type.uppercase()) } catch (e: Exception) { NotificationType.SYSTEM },
        title = title,
        body = body,
        timestamp = timestamp,
        isRead = isRead,
        referenceId = referenceId,
        referenceType = referenceType
    )
}

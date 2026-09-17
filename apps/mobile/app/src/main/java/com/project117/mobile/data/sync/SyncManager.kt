package com.project117.mobile.data.sync

import com.project117.mobile.data.local.dao.LocalEvidenceDao
import com.project117.mobile.data.local.dao.PendingActionDao
import com.project117.mobile.data.local.entities.PendingActionEntity
import com.project117.mobile.data.local.entities.PendingActionTypes
import com.project117.mobile.domain.backend.FieldBackend
import com.project117.mobile.domain.model.*
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SyncManager @Inject constructor(
    private val pendingActionDao: PendingActionDao,
    private val localEvidenceDao: LocalEvidenceDao,
    private val fieldBackend: FieldBackend
) {
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()

    private val _isSyncing = MutableStateFlow(false)
    val isSyncing: StateFlow<Boolean> = _isSyncing.asStateFlow()

    fun observePendingCount(): Flow<Int> = pendingActionDao.observePendingCount()

    fun observeAllActions(): Flow<List<PendingActionEntity>> = pendingActionDao.observeAllActions()

    suspend fun queueReportIssue(
        equipmentId: String,
        description: String,
        severity: IssueSeverity,
        evidenceIds: List<String>
    ): Long = withContext(Dispatchers.IO) {
        val payloadMap = mapOf(
            "equipment_id" to equipmentId,
            "description" to description,
            "severity" to severity.name,
            "evidence_ids" to evidenceIds.joinToString(",")
        )
        val adapter = moshi.adapter(Map::class.java)
        val json = adapter.toJson(payloadMap)

        pendingActionDao.insert(
            PendingActionEntity(
                actionType = PendingActionTypes.REPORT_ISSUE,
                payload = json,
                status = "PENDING"
            )
        )
    }

    suspend fun queueEvidenceUpload(
        localPath: String,
        type: EvidenceType,
        equipmentId: String?,
        workOrderId: String?,
        caption: String?
    ): Long = withContext(Dispatchers.IO) {
        val payloadMap = mapOf(
            "local_path" to localPath,
            "type" to type.name,
            "equipment_id" to (equipmentId ?: ""),
            "work_order_id" to (workOrderId ?: ""),
            "caption" to (caption ?: "")
        )
        val adapter = moshi.adapter(Map::class.java)
        val json = adapter.toJson(payloadMap)

        pendingActionDao.insert(
            PendingActionEntity(
                actionType = PendingActionTypes.UPLOAD_EVIDENCE,
                payload = json,
                localFilePath = localPath,
                status = "PENDING"
            )
        )
    }

    suspend fun queueWorkOrderUpdate(
        workOrderId: String,
        status: WorkOrderStatus,
        notes: String?
    ): Long = withContext(Dispatchers.IO) {
        val payloadMap = mapOf(
            "work_order_id" to workOrderId,
            "status" to status.name,
            "notes" to (notes ?: "")
        )
        val adapter = moshi.adapter(Map::class.java)
        val json = adapter.toJson(payloadMap)

        pendingActionDao.insert(
            PendingActionEntity(
                actionType = PendingActionTypes.UPDATE_WORK_ORDER,
                payload = json,
                status = "PENDING"
            )
        )
    }

    suspend fun syncAll(): SyncResult = withContext(Dispatchers.IO) {
        if (_isSyncing.value) return@withContext SyncResult(0, 0, false)
        _isSyncing.value = true

        var successCount = 0
        var failCount = 0

        try {
            val pending = pendingActionDao.getPendingActions()
            for (action in pending) {
                pendingActionDao.updateStatus(
                    id = action.id,
                    status = "SYNCING",
                    retryCount = action.retryCount,
                    lastAttemptAt = System.currentTimeMillis(),
                    lastError = null
                )

                val success = processAction(action)
                if (success) {
                    successCount++
                    pendingActionDao.updateStatus(
                        id = action.id,
                        status = "SYNCED",
                        retryCount = action.retryCount,
                        lastAttemptAt = System.currentTimeMillis(),
                        lastError = null
                    )
                } else {
                    failCount++
                    val newRetry = action.retryCount + 1
                    val newStatus = if (newRetry >= action.maxRetries) "FAILED" else "PENDING"
                    pendingActionDao.updateStatus(
                        id = action.id,
                        status = newStatus,
                        retryCount = newRetry,
                        lastAttemptAt = System.currentTimeMillis(),
                        lastError = "Sync attempt failed"
                    )
                }
            }
        } catch (e: Exception) {
            Timber.e(e, "Error during syncAll")
        } finally {
            _isSyncing.value = false
        }

        SyncResult(successCount, failCount, true)
    }

    private suspend fun processAction(action: PendingActionEntity): Boolean {
        return try {
            val adapter = moshi.adapter(Map::class.java)
            val map = adapter.fromJson(action.payload) as? Map<String, String> ?: return false

            when (action.actionType) {
                PendingActionTypes.REPORT_ISSUE -> {
                    val eqId = map["equipment_id"] ?: return false
                    val desc = map["description"] ?: return false
                    val sev = IssueSeverity.valueOf(map["severity"] ?: IssueSeverity.MEDIUM.name)
                    val rawEv = map["evidence_ids"] ?: ""
                    val evIds = if (rawEv.isBlank()) emptyList() else rawEv.split(",")

                    val res = fieldBackend.reportIssue(eqId, desc, sev, evIds)
                    res is BackendResult.Success
                }
                PendingActionTypes.UPLOAD_EVIDENCE -> {
                    val path = map["local_path"] ?: return false
                    val type = EvidenceType.valueOf(map["type"] ?: EvidenceType.PHOTO.name)
                    val eqId = map["equipment_id"]?.ifBlank { null }
                    val woId = map["work_order_id"]?.ifBlank { null }
                    val caption = map["caption"]?.ifBlank { null }

                    val res = fieldBackend.uploadEvidence(path, type, eqId, woId, caption)
                    if (res is BackendResult.Success) {
                        localEvidenceDao.updateSyncStatusByPath(path, "SYNCED", res.data)
                        true
                    } else {
                        false
                    }
                }
                PendingActionTypes.UPDATE_WORK_ORDER -> {
                    val woId = map["work_order_id"] ?: return false
                    val status = WorkOrderStatus.valueOf(map["status"] ?: WorkOrderStatus.OPEN.name)
                    val notes = map["notes"]?.ifBlank { null }

                    val res = fieldBackend.updateWorkOrder(woId, status, notes)
                    res is BackendResult.Success
                }
                else -> true
            }
        } catch (e: Exception) {
            Timber.e(e, "Failed to process queued action ${action.id}")
            false
        }
    }

    suspend fun retryAction(id: Long) = withContext(Dispatchers.IO) {
        pendingActionDao.updateStatus(id, "PENDING", 0, System.currentTimeMillis(), null)
        syncAll()
    }
}

data class SyncResult(
    val successCount: Int,
    val failCount: Int,
    val completed: Boolean
)

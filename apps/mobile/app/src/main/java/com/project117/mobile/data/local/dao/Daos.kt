package com.project117.mobile.data.local.dao

import androidx.room.*
import com.project117.mobile.data.local.entities.*
import kotlinx.coroutines.flow.Flow

// ─── Pending Actions ──────────────────────────────────────────────────────────

@Dao
interface PendingActionDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(action: PendingActionEntity): Long

    @Query("SELECT * FROM pending_actions WHERE status = 'PENDING' ORDER BY createdAt ASC")
    suspend fun getPendingActions(): List<PendingActionEntity>

    @Query("SELECT * FROM pending_actions ORDER BY createdAt DESC")
    fun observeAllActions(): Flow<List<PendingActionEntity>>

    @Query("UPDATE pending_actions SET status = :status, retryCount = :retryCount, lastAttemptAt = :lastAttemptAt, lastError = :lastError WHERE id = :id")
    suspend fun updateStatus(id: Long, status: String, retryCount: Int, lastAttemptAt: Long, lastError: String?)

    @Query("DELETE FROM pending_actions WHERE id = :id")
    suspend fun delete(id: Long)

    @Query("DELETE FROM pending_actions WHERE status = 'SYNCED'")
    suspend fun deleteSynced()

    @Query("SELECT COUNT(*) FROM pending_actions WHERE status = 'PENDING' OR status = 'SYNCING'")
    fun observePendingCount(): Flow<Int>
}

// ─── Equipment Cache ──────────────────────────────────────────────────────────

@Dao
interface EquipmentCacheDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: EquipmentCacheEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(entities: List<EquipmentCacheEntity>)

    @Query("SELECT * FROM equipment_cache ORDER BY cachedAt DESC")
    suspend fun getAll(): List<EquipmentCacheEntity>

    @Query("SELECT * FROM equipment_cache WHERE id = :id")
    suspend fun getById(id: String): EquipmentCacheEntity?

    @Query("DELETE FROM equipment_cache")
    suspend fun deleteAll()
}

// ─── Work Order Cache ─────────────────────────────────────────────────────────

@Dao
interface WorkOrderCacheDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: WorkOrderCacheEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(entities: List<WorkOrderCacheEntity>)

    @Query("SELECT * FROM work_order_cache ORDER BY cachedAt DESC")
    suspend fun getAll(): List<WorkOrderCacheEntity>

    @Query("SELECT * FROM work_order_cache WHERE id = :id")
    suspend fun getById(id: String): WorkOrderCacheEntity?

    @Query("DELETE FROM work_order_cache")
    suspend fun deleteAll()
}

// ─── SOP Cache ────────────────────────────────────────────────────────────────

@Dao
interface SopCacheDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: SopCacheEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(entities: List<SopCacheEntity>)

    @Query("SELECT * FROM sop_cache ORDER BY cachedAt DESC")
    suspend fun getAll(): List<SopCacheEntity>

    @Query("SELECT * FROM sop_cache WHERE id = :id")
    suspend fun getById(id: String): SopCacheEntity?

    @Query("DELETE FROM sop_cache")
    suspend fun deleteAll()
}

// ─── Local Evidence ───────────────────────────────────────────────────────────

@Dao
interface LocalEvidenceDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: LocalEvidenceEntity)

    @Query("SELECT * FROM local_evidence WHERE localId = :localId")
    suspend fun getById(localId: String): LocalEvidenceEntity?

    @Query("SELECT * FROM local_evidence WHERE localPath = :localPath")
    suspend fun getByPath(localPath: String): LocalEvidenceEntity?

    @Query("SELECT * FROM local_evidence ORDER BY capturedAt DESC")
    fun observeAll(): Flow<List<LocalEvidenceEntity>>

    @Query("SELECT * FROM local_evidence WHERE syncStatus != 'SYNCED' ORDER BY capturedAt ASC")
    suspend fun getUnsynced(): List<LocalEvidenceEntity>

    @Query("UPDATE local_evidence SET syncStatus = :status, remoteId = :remoteId WHERE localId = :localId")
    suspend fun updateSyncStatus(localId: String, status: String, remoteId: String?)

    @Query("UPDATE local_evidence SET syncStatus = :status, remoteId = :remoteId WHERE localPath = :localPath")
    suspend fun updateSyncStatusByPath(localPath: String, status: String, remoteId: String?)

    @Query("DELETE FROM local_evidence WHERE localId = :localId")
    suspend fun delete(localId: String)
}

// ─── Chat Messages ────────────────────────────────────────────────────────────

@Dao
interface ChatMessageDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: ChatMessageEntity)

    @Query("SELECT * FROM chat_messages ORDER BY timestamp ASC")
    fun observeAll(): Flow<List<ChatMessageEntity>>

    @Query("DELETE FROM chat_messages")
    suspend fun deleteAll()
}

// ─── Notifications ────────────────────────────────────────────────────────────

@Dao
interface NotificationDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(entities: List<NotificationEntity>)

    @Query("SELECT * FROM notifications_cache ORDER BY cachedAt DESC")
    fun observeAll(): Flow<List<NotificationEntity>>

    @Query("UPDATE notifications_cache SET isRead = 1 WHERE id = :id")
    suspend fun markRead(id: String)

    @Query("DELETE FROM notifications_cache")
    suspend fun deleteAll()
}

package com.project117.mobile.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import com.project117.mobile.data.local.dao.*
import com.project117.mobile.data.local.entities.*

@Database(
    entities = [
        PendingActionEntity::class,
        EquipmentCacheEntity::class,
        WorkOrderCacheEntity::class,
        SopCacheEntity::class,
        LocalEvidenceEntity::class,
        ChatMessageEntity::class,
        NotificationEntity::class
    ],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun pendingActionDao(): PendingActionDao
    abstract fun equipmentCacheDao(): EquipmentCacheDao
    abstract fun workOrderCacheDao(): WorkOrderCacheDao
    abstract fun sopCacheDao(): SopCacheDao
    abstract fun localEvidenceDao(): LocalEvidenceDao
    abstract fun chatMessageDao(): ChatMessageDao
    abstract fun notificationDao(): NotificationDao
}

package com.project117.mobile.di

import android.content.Context
import androidx.room.Room
import com.project117.mobile.data.local.AppDatabase
import com.project117.mobile.data.local.dao.*
import com.project117.mobile.data.local.security.DatabaseKeyManager
import net.sqlcipher.database.SupportFactory
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(
        @ApplicationContext context: Context,
        keyManager: DatabaseKeyManager
    ): AppDatabase {
        val passphrase = keyManager.getOrCreateDatabaseKey()
        val factory = SupportFactory(passphrase)

        return Room.databaseBuilder(
            context,
            AppDatabase::class.java,
            "project117_mobile_encrypted.db"
        )
            .openHelperFactory(factory)
            .fallbackToDestructiveMigration()
            .build()
    }

    @Provides
    fun providePendingActionDao(db: AppDatabase): PendingActionDao = db.pendingActionDao()

    @Provides
    fun provideEquipmentCacheDao(db: AppDatabase): EquipmentCacheDao = db.equipmentCacheDao()

    @Provides
    fun provideWorkOrderCacheDao(db: AppDatabase): WorkOrderCacheDao = db.workOrderCacheDao()

    @Provides
    fun provideSopCacheDao(db: AppDatabase): SopCacheDao = db.sopCacheDao()

    @Provides
    fun provideLocalEvidenceDao(db: AppDatabase): LocalEvidenceDao = db.localEvidenceDao()

    @Provides
    fun provideChatMessageDao(db: AppDatabase): ChatMessageDao = db.chatMessageDao()

    @Provides
    fun provideNotificationDao(db: AppDatabase): NotificationDao = db.notificationDao()
}

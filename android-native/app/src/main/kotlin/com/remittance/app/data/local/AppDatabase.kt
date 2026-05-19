package com.pos54link.app.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.TypeConverters

/**
 * Room Database for offline-first architecture.
 * Stores pending transactions, cached data, and sync state.
 */
@Database(
    entities = [
        PendingTransferEntity::class,
        CachedTransactionEntity::class,
        CachedBeneficiaryEntity::class,
        CachedWalletBalanceEntity::class,
        SyncStateEntity::class
    ],
    version = 1,
    exportSchema = true
)
@TypeConverters(Converters::class)
abstract class AppDatabase : RoomDatabase() {
    
    abstract fun pendingTransferDao(): PendingTransferDao
    abstract fun cachedTransactionDao(): CachedTransactionDao
    abstract fun cachedBeneficiaryDao(): CachedBeneficiaryDao
    abstract fun cachedWalletBalanceDao(): CachedWalletBalanceDao
    abstract fun syncStateDao(): SyncStateDao
    
    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null
        
        fun getDatabase(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "remittance_offline_db"
                )
                    .fallbackToDestructiveMigration()
                    .build()
                INSTANCE = instance
                instance
            }
        }
    }
}

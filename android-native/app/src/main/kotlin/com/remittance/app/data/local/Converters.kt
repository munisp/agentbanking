package com.pos54link.app.data.local

import androidx.room.TypeConverter
import java.util.Date

/**
 * Room Type Converters for complex types
 */
class Converters {
    
    @TypeConverter
    fun fromTimestamp(value: Long?): Date? {
        return value?.let { Date(it) }
    }
    
    @TypeConverter
    fun dateToTimestamp(date: Date?): Long? {
        return date?.time
    }
}

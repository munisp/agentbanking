package com.pos54link.app.security

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.pos54link.app.data.api.ApiClient
import com.pos54link.app.data.api.RefreshTokenRequest
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "remittance_prefs")

@Singleton
class TokenManager @Inject constructor(
    @ApplicationContext private val context: Context
) {
    
    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()
    
    private val encryptedPrefs = EncryptedSharedPreferences.create(
        context,
        "remittance_secure_prefs",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )
    
    companion object {
        private const val KEY_ACCESS_TOKEN = "access_token"
        private const val KEY_REFRESH_TOKEN = "refresh_token"
        private const val KEY_USER_ID = "user_id"
        private const val KEY_DEVICE_ID = "device_id"
        private const val KEY_BIOMETRIC_PUBLIC_KEY = "biometric_public_key"
        private const val KEY_PIN_HASH = "pin_hash"
        
        private val ACCESS_TOKEN_KEY = stringPreferencesKey(KEY_ACCESS_TOKEN)
        private val REFRESH_TOKEN_KEY = stringPreferencesKey(KEY_REFRESH_TOKEN)
        private val USER_ID_KEY = stringPreferencesKey(KEY_USER_ID)
    }
    
    // MARK: - Token Management
    
    suspend fun saveAccessToken(token: String) {
        encryptedPrefs.edit().putString(KEY_ACCESS_TOKEN, token).apply()
        context.dataStore.edit { prefs ->
            prefs[ACCESS_TOKEN_KEY] = token
        }
    }
    
    suspend fun getAccessToken(): String? {
        return encryptedPrefs.getString(KEY_ACCESS_TOKEN, null)
    }
    
    suspend fun saveRefreshToken(token: String) {
        encryptedPrefs.edit().putString(KEY_REFRESH_TOKEN, token).apply()
        context.dataStore.edit { prefs ->
            prefs[REFRESH_TOKEN_KEY] = token
        }
    }
    
    suspend fun getRefreshToken(): String? {
        return encryptedPrefs.getString(KEY_REFRESH_TOKEN, null)
    }
    
    suspend fun clearTokens() {
        encryptedPrefs.edit().apply {
            remove(KEY_ACCESS_TOKEN)
            remove(KEY_REFRESH_TOKEN)
        }.apply()
        
        context.dataStore.edit { prefs ->
            prefs.remove(ACCESS_TOKEN_KEY)
            prefs.remove(REFRESH_TOKEN_KEY)
        }
    }
    
    // MARK: - User Data
    
    suspend fun saveUserId(userId: String) {
        encryptedPrefs.edit().putString(KEY_USER_ID, userId).apply()
        context.dataStore.edit { prefs ->
            prefs[USER_ID_KEY] = userId
        }
    }
    
    suspend fun getUserId(): String? {
        return encryptedPrefs.getString(KEY_USER_ID, null)
    }
    
    suspend fun clearUserId() {
        encryptedPrefs.edit().remove(KEY_USER_ID).apply()
        context.dataStore.edit { prefs ->
            prefs.remove(USER_ID_KEY)
        }
    }
    
    // MARK: - Device ID
    
    fun getOrCreateDeviceId(): String {
        var deviceId = encryptedPrefs.getString(KEY_DEVICE_ID, null)
        if (deviceId == null) {
            deviceId = java.util.UUID.randomUUID().toString()
            encryptedPrefs.edit().putString(KEY_DEVICE_ID, deviceId).apply()
        }
        return deviceId
    }
    
    // MARK: - Biometric
    
    fun saveBiometricPublicKey(publicKey: String) {
        encryptedPrefs.edit().putString(KEY_BIOMETRIC_PUBLIC_KEY, publicKey).apply()
    }
    
    fun getBiometricPublicKey(): String? {
        return encryptedPrefs.getString(KEY_BIOMETRIC_PUBLIC_KEY, null)
    }
    
    fun clearBiometricPublicKey() {
        encryptedPrefs.edit().remove(KEY_BIOMETRIC_PUBLIC_KEY).apply()
    }
    
    fun isBiometricRegistered(): Boolean {
        return getBiometricPublicKey() != null
    }
    
    // MARK: - PIN Code
    
    fun savePinHash(pinHash: String) {
        encryptedPrefs.edit().putString(KEY_PIN_HASH, pinHash).apply()
    }
    
    fun getPinHash(): String? {
        return encryptedPrefs.getString(KEY_PIN_HASH, null)
    }
    
    fun verifyPin(pin: String): Boolean {
        val storedHash = getPinHash() ?: return false
        val inputHash = hashPin(pin)
        return storedHash == inputHash
    }
    
    fun clearPin() {
        encryptedPrefs.edit().remove(KEY_PIN_HASH).apply()
    }
    
    private fun hashPin(pin: String): String {
        return java.security.MessageDigest.getInstance("SHA-256")
            .digest(pin.toByteArray())
            .joinToString("") { "%02x".format(it) }
    }
    
    // MARK: - Token Refresh
    
    suspend fun refreshToken(): Boolean {
        return try {
            val refreshToken = getRefreshToken() ?: return false
            
            // This would normally use ApiClient, but to avoid circular dependency,
            // we'll implement it in the repository layer
            // For now, just return false and let the repository handle it
            false
        } catch (e: Exception) {
            Timber.e(e, "Failed to refresh token")
            false
        }
    }
    
    // MARK: - Session Check
    
    suspend fun hasValidSession(): Boolean {
        return getAccessToken() != null && getUserId() != null
    }
    
    // MARK: - Clear All
    
    suspend fun clearAll() {
        clearTokens()
        clearUserId()
        clearBiometricPublicKey()
        clearPin()
    }
}

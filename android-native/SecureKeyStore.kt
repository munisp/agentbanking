package com.pos54link.app.security

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Secure KeyStore Storage
 * Hardware-backed security using Android KeyStore
 */
class SecureKeyStore(private val context: Context) {
    
    private val keyStore: KeyStore = KeyStore.getInstance("AndroidKeyStore").apply {
        load(null)
    }
    
    enum class SecureItem {
        BIOMETRIC_TEMPLATE,
        ENCRYPTION_KEY,
        AUTH_TOKEN,
        PIN_HASH
    }
    
    /**
     * Store data securely in KeyStore
     */
    fun store(data: ByteArray, item: SecureItem, requireBiometric: Boolean = true): Boolean {
        return try {
            val key = getOrCreateKey(item, requireBiometric)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.ENCRYPT_MODE, key)
            
            val iv = cipher.iv
            val encrypted = cipher.doFinal(data)
            
            // Store encrypted data and IV
            val prefs = getEncryptedPreferences()
            prefs.edit()
                .putString("${item.name}_data", android.util.Base64.encodeToString(encrypted, android.util.Base64.DEFAULT))
                .putString("${item.name}_iv", android.util.Base64.encodeToString(iv, android.util.Base64.DEFAULT))
                .apply()
            
            true
        } catch (e: Exception) {
            false
        }
    }
    
    /**
     * Retrieve data from KeyStore
     */
    fun retrieve(item: SecureItem): ByteArray? {
        return try {
            val key = keyStore.getKey(item.keyAlias(), null) as? SecretKey ?: return null
            
            val prefs = getEncryptedPreferences()
            val encryptedData = prefs.getString("${item.name}_data", null) ?: return null
            val iv = prefs.getString("${item.name}_iv", null) ?: return null
            
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            val spec = GCMParameterSpec(128, android.util.Base64.decode(iv, android.util.Base64.DEFAULT))
            cipher.init(Cipher.DECRYPT_MODE, key, spec)
            
            cipher.doFinal(android.util.Base64.decode(encryptedData, android.util.Base64.DEFAULT))
        } catch (e: Exception) {
            null
        }
    }
    
    /**
     * Delete data from KeyStore
     */
    fun delete(item: SecureItem): Boolean {
        return try {
            keyStore.deleteEntry(item.keyAlias())
            val prefs = getEncryptedPreferences()
            prefs.edit()
                .remove("${item.name}_data")
                .remove("${item.name}_iv")
                .apply()
            true
        } catch (e: Exception) {
            false
        }
    }
    
    /**
     * Get or create encryption key
     */
    private fun getOrCreateKey(item: SecureItem, requireBiometric: Boolean): SecretKey {
        val alias = item.keyAlias()
        
        if (keyStore.containsAlias(alias)) {
            return keyStore.getKey(alias, null) as SecretKey
        }
        
        val keyGenerator = KeyGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_AES,
            "AndroidKeyStore"
        )
        
        val builder = KeyGenParameterSpec.Builder(
            alias,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setUserAuthenticationRequired(requireBiometric)
        
        if (requireBiometric && android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {
            builder.setUserAuthenticationParameters(30, KeyProperties.AUTH_BIOMETRIC_STRONG)
        }
        
        keyGenerator.init(builder.build())
        return keyGenerator.generateKey()
    }
    
    /**
     * Get encrypted shared preferences
     */
    private fun getEncryptedPreferences(): android.content.SharedPreferences {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        
        return EncryptedSharedPreferences.create(
            context,
            "secure_storage",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }
    
    private fun SecureItem.keyAlias(): String = "com.pos54link.${this.name.lowercase()}"
}

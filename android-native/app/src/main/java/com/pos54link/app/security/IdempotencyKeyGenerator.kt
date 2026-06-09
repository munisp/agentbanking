package com.pos54link.app.security

import java.security.SecureRandom
import java.util.concurrent.ConcurrentHashMap

/**
 * Generates and tracks idempotency keys for POS transactions.
 *
 * Each mutation call must include a unique X-Idempotency-Key header (16-64 chars)
 * to prevent double-execution on retry. Keys are tracked in-memory to detect
 * duplicate submissions before they reach the server.
 */
object IdempotencyKeyGenerator {

    private const val KEY_LENGTH = 32
    private val secureRandom = SecureRandom()
    private val alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    private val usedKeys = ConcurrentHashMap<String, Long>()
    private const val KEY_EXPIRY_MS = 3_600_000L // 1 hour

    /**
     * Generate a cryptographically secure idempotency key.
     * Format: "IDK-{timestamp}-{random}" — 32 chars, unique per call.
     */
    fun generate(): String {
        cleanExpiredKeys()
        val timestamp = System.currentTimeMillis().toString(36)
        val random = buildString {
            repeat(KEY_LENGTH - timestamp.length - 4) {
                append(alphabet[secureRandom.nextInt(alphabet.length)])
            }
        }
        val key = "IDK-$timestamp-$random"
        usedKeys[key] = System.currentTimeMillis()
        return key
    }

    /**
     * Check if a key has already been used (client-side guard).
     * Returns true if the key is a duplicate.
     */
    fun isDuplicate(key: String): Boolean {
        return usedKeys.containsKey(key)
    }

    /**
     * Mark a key as used (for keys received from server or external sources).
     */
    fun markUsed(key: String) {
        usedKeys[key] = System.currentTimeMillis()
    }

    private fun cleanExpiredKeys() {
        val now = System.currentTimeMillis()
        usedKeys.entries.removeAll { now - it.value > KEY_EXPIRY_MS }
    }
}

package com.pos54link.app.security

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Log
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * PIN Encryption Manager — Encrypts PIN blocks for secure transmission.
 *
 * Uses:
 * - Android KeyStore for PIN encryption key (hardware-backed on supported devices)
 * - ISO 9564 Format 0 PIN block generation
 * - AES-256-GCM for PIN block encryption before network transmission
 *
 * The encrypted PIN block is sent to the P2PE service (port 8281) for
 * translation under the destination switch's ZPK (Zone PIN Key).
 */

class PinEncryptionManager {

    companion object {
        private const val TAG = "PINEncrypt"
        private const val KEYSTORE_ALIAS = "pos_pin_encryption_key"
        private const val ANDROID_KEYSTORE = "AndroidKeyStore"
        private const val GCM_TAG_LENGTH = 128
    }

    init {
        ensureKeyExists()
    }

    /**
     * Generate or retrieve PIN encryption key from Android KeyStore.
     * Key is hardware-backed (StrongBox/TEE) where available.
     */
    private fun ensureKeyExists() {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE)
        keyStore.load(null)

        if (!keyStore.containsAlias(KEYSTORE_ALIAS)) {
            val keyGen = KeyGenerator.getInstance(
                KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE
            )
            keyGen.init(
                KeyGenParameterSpec.Builder(
                    KEYSTORE_ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
                )
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .setUserAuthenticationRequired(false) // PIN must work without biometric
                    .setIsStrongBoxBacked(true) // Use StrongBox if available
                    .build()
            )
            keyGen.generateKey()
            Log.i(TAG, "PIN encryption key generated in KeyStore")
        }
    }

    /**
     * Create ISO 9564 Format 0 PIN block from PIN and PAN.
     * Format: 0NPPPPPPPPPPPPPP XOR 0000PPPPPPPPPPPP
     * where N=PIN length, P=PIN digits padded with F, PAN=rightmost 12 excluding check digit.
     */
    fun createPinBlock(pin: String, pan: String): ByteArray {
        require(pin.length in 4..12) { "PIN must be 4-12 digits" }
        require(pan.length >= 13) { "PAN must be at least 13 digits" }

        // Block 1: 0 + PIN length + PIN + F padding to 16 hex chars
        val block1Hex = "0${pin.length}${pin}${"F".repeat(14 - pin.length)}"

        // Block 2: 0000 + rightmost 12 PAN digits (excluding check digit)
        val panRight12 = pan.substring(pan.length - 13, pan.length - 1)
        val block2Hex = "0000$panRight12"

        // XOR blocks
        val block1 = hexToBytes(block1Hex)
        val block2 = hexToBytes(block2Hex)
        val pinBlock = ByteArray(8)
        for (i in pinBlock.indices) {
            pinBlock[i] = (block1[i].toInt() xor block2[i].toInt()).toByte()
        }

        return pinBlock
    }

    /**
     * Encrypt PIN block using Android KeyStore AES-256-GCM.
     * Returns: IV (12 bytes) + ciphertext + auth tag (16 bytes)
     */
    fun encryptPinBlock(pinBlock: ByteArray): ByteArray {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE)
        keyStore.load(null)
        val key = keyStore.getKey(KEYSTORE_ALIAS, null) as SecretKey

        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key)

        val iv = cipher.iv // Auto-generated 12-byte IV
        val ciphertext = cipher.doFinal(pinBlock)

        // Concatenate: IV + ciphertext (includes GCM auth tag)
        return iv + ciphertext
    }

    /**
     * Full PIN processing pipeline:
     * 1. Validate PIN format
     * 2. Create ISO 9564 PIN block
     * 3. Encrypt with AES-256-GCM
     * 4. Return encrypted blob for P2PE service
     */
    fun processPinEntry(pin: String, pan: String): ByteArray {
        // Validate
        require(pin.all { it.isDigit() }) { "PIN must contain only digits" }
        require(pin.length in 4..6) { "PIN must be 4-6 digits" }

        // Create PIN block
        val pinBlock = createPinBlock(pin, pan)

        // Encrypt
        val encrypted = encryptPinBlock(pinBlock)

        Log.i(TAG, "PIN block encrypted (${encrypted.size} bytes)")
        return encrypted
    }

    private fun hexToBytes(hex: String): ByteArray {
        val len = hex.length
        val data = ByteArray(len / 2)
        for (i in 0 until len step 2) {
            data[i / 2] = ((Character.digit(hex[i], 16) shl 4) + Character.digit(hex[i + 1], 16)).toByte()
        }
        return data
    }
}

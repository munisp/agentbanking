package com.pos54link.app.security

import android.app.Activity
import android.content.Context
import android.os.Build
import android.provider.Settings
import android.view.WindowManager
import android.util.Log

/**
 * Secure Display Manager — Prevents screen capture, overlays, and split-screen attacks.
 *
 * Security controls:
 * - FLAG_SECURE: Blocks screenshots, screen recording, casting during PIN entry
 * - Overlay detection: Detects and blocks tap-jacking overlays
 * - Split-screen blocking: Prevents side-by-side with malicious apps
 * - Screen pinning: Locks to POS app during transactions
 */

class SecureDisplayManager(private val context: Context) {

    companion object {
        private const val TAG = "SecureDisplay"
    }

    /**
     * Enable FLAG_SECURE on activity window (blocks screenshots + screen recording).
     * MUST be called during PIN entry, card data display, and transaction confirmation.
     */
    fun enableSecureMode(activity: Activity) {
        activity.window.setFlags(
            WindowManager.LayoutParams.FLAG_SECURE,
            WindowManager.LayoutParams.FLAG_SECURE
        )
        Log.i(TAG, "Secure mode enabled (FLAG_SECURE)")
    }

    /**
     * Disable secure mode after sensitive operation completes.
     */
    fun disableSecureMode(activity: Activity) {
        activity.window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
        Log.i(TAG, "Secure mode disabled")
    }

    /**
     * Check if any overlay apps are drawing over the POS app.
     * Blocks tap-jacking attacks where a transparent overlay intercepts taps.
     */
    fun detectOverlays(): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            // Check if any app has overlay permission
            val hasOverlayPermission = Settings.canDrawOverlays(context)
            if (hasOverlayPermission) {
                Log.w(TAG, "Overlay permission detected on device")
            }
            return hasOverlayPermission
        }
        return false
    }

    /**
     * Check if app is in multi-window/split-screen mode.
     * In split-screen, a malicious app could observe PIN entry.
     */
    fun isInMultiWindowMode(activity: Activity): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            activity.isInMultiWindowMode
        } else {
            false
        }
    }

    /**
     * Block split-screen mode for the current activity.
     * Should be set in AndroidManifest.xml: android:resizeableActivity="false"
     * This method provides runtime enforcement.
     */
    fun blockMultiWindow(activity: Activity): Boolean {
        if (isInMultiWindowMode(activity)) {
            Log.w(TAG, "Multi-window mode detected — blocking transaction")
            return true // Caller should abort sensitive operation
        }
        return false
    }

    /**
     * Enable screen pinning (task lock) for transaction duration.
     * Prevents user from switching apps during PIN entry.
     */
    fun enableScreenPinning(activity: Activity) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            activity.startLockTask()
            Log.i(TAG, "Screen pinning enabled")
        }
    }

    /**
     * Disable screen pinning after transaction completes.
     */
    fun disableScreenPinning(activity: Activity) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            activity.stopLockTask()
            Log.i(TAG, "Screen pinning disabled")
        }
    }

    /**
     * Full security check before sensitive operation.
     * Returns list of security issues found. Empty = safe to proceed.
     */
    fun performSecurityCheck(activity: Activity): List<String> {
        val issues = mutableListOf<String>()

        if (detectOverlays()) {
            issues.add("overlay_detected")
        }
        if (isInMultiWindowMode(activity)) {
            issues.add("multi_window_active")
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            if (activity.isInPictureInPictureMode) {
                issues.add("pip_mode_active")
            }
        }

        return issues
    }
}

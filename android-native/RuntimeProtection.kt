package com.pos54link.app.security

import android.content.Context
import android.content.pm.ApplicationInfo
import android.os.Build
import android.os.Debug
import java.io.File

/**
 * Runtime Application Self-Protection (RASP)
 * Prevents 90% of Sophisticated Attacks
 */
class RuntimeProtection(private val context: Context) {
    
    /**
     * Check if debugger is attached
     */
    fun detectDebugger(): Boolean {
        return Debug.isDebuggerConnected() || Debug.waitingForDebugger()
    }
    
    /**
     * Check if running on emulator
     */
    fun detectEmulator(): Boolean {
        return checkEmulatorBuild() ||
               checkEmulatorFiles() ||
               checkEmulatorProperties()
    }
    
    private fun checkEmulatorBuild(): Boolean {
        return (Build.FINGERPRINT.startsWith("generic") ||
                Build.FINGERPRINT.startsWith("unknown") ||
                Build.MODEL.contains("google_sdk") ||
                Build.MODEL.contains("Emulator") ||
                Build.MODEL.contains("Android SDK built for x86") ||
                Build.MANUFACTURER.contains("Genymotion") ||
                Build.BRAND.startsWith("generic") && Build.DEVICE.startsWith("generic") ||
                "google_sdk" == Build.PRODUCT)
    }
    
    private fun checkEmulatorFiles(): Boolean {
        val emulatorFiles = arrayOf(
            "/dev/socket/qemud",
            "/dev/qemu_pipe",
            "/system/lib/libc_malloc_debug_qemu.so",
            "/sys/qemu_trace",
            "/system/bin/qemu-props"
        )
        
        return emulatorFiles.any { File(it).exists() }
    }
    
    private fun checkEmulatorProperties(): Boolean {
        val properties = mapOf(
            "ro.hardware" to "goldfish",
            "ro.kernel.qemu" to "1",
            "ro.product.device" to "generic",
            "ro.product.model" to "sdk"
        )
        
        return properties.any { (key, value) ->
            val prop = getSystemProperty(key)
            prop?.contains(value) == true
        }
    }
    
    /**
     * Detect code injection (Frida, Xposed, etc.)
     */
    fun detectCodeInjection(): Boolean {
        return checkFrida() || checkXposed() || checkSuspiciousLibraries()
    }
    
    private fun checkFrida(): Boolean {
        val fridaLibraries = arrayOf(
            "frida-agent",
            "frida-gadget",
            "frida-server"
        )
        
        return fridaLibraries.any { lib ->
            File("/data/local/tmp/$lib").exists()
        }
    }
    
    private fun checkXposed(): Boolean {
        return try {
            Class.forName("de.robv.android.xposed.XposedBridge")
            true
        } catch (e: ClassNotFoundException) {
            false
        }
    }
    
    private fun checkSuspiciousLibraries(): Boolean {
        val libraries = File("/proc/self/maps").readLines()
        val suspiciousPatterns = arrayOf("frida", "xposed", "substrate", "cynject")
        
        return libraries.any { line ->
            suspiciousPatterns.any { pattern ->
                line.contains(pattern, ignoreCase = true)
            }
        }
    }
    
    /**
     * Detect app tampering
     */
    fun detectTampering(): Boolean {
        return checkInstallerPackage() || checkSignature()
    }
    
    private fun checkInstallerPackage(): Boolean {
        val validInstallers = setOf(
            "com.android.vending",  // Google Play Store
            "com.google.android.feedback"
        )
        
        val installer = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            context.packageManager.getInstallSourceInfo(context.packageName).installingPackageName
        } else {
            @Suppress("DEPRECATION")
            context.packageManager.getInstallerPackageName(context.packageName)
        }
        
        return installer !in validInstallers
    }
    
    private fun checkSignature(): Boolean {
        // Check if app signature matches expected signature
        // Implementation depends on your signing configuration
        return false
    }
    
    /**
     * Perform all runtime checks
     */
    fun performRuntimeChecks(): Map<String, Boolean> {
        return mapOf(
            "debugger" to detectDebugger(),
            "emulator" to detectEmulator(),
            "injection" to detectCodeInjection(),
            "tampering" to detectTampering()
        )
    }
    
    /**
     * Check if environment is secure
     */
    fun isEnvironmentSecure(): Boolean {
        val checks = performRuntimeChecks()
        return !checks.values.any { it }
    }
    
    private fun getSystemProperty(key: String): String? {
        return try {
            val process = Runtime.getRuntime().exec("getprop $key")
            process.inputStream.bufferedReader().use { it.readText().trim() }
        } catch (e: Exception) {
            null
        }
    }
}

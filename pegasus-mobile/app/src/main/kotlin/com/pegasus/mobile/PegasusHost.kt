package com.pegasus.mobile

import android.content.Context
import android.content.SharedPreferences

/**
 * Runtime-resolved Pegasus backend host.
 *
 * - Emulator: 10.0.2.2 (Android's alias for the host loopback)
 * - Physical: the LAN IP the operator entered in ConnectionActivity,
 *   persisted in SharedPreferences.
 */
object PegasusHost {
    private const val PREFS = "pegasus"
    private const val KEY_HOST = "host"
    private const val KEY_PORT = "port"
    private const val DEFAULT_PORT = 5001

    fun isEmulator(): Boolean = (android.os.Build.FINGERPRINT.contains("generic")
            || android.os.Build.FINGERPRINT.contains("emulator")
            || android.os.Build.MODEL.contains("Emulator")
            || android.os.Build.MODEL.contains("Android SDK built for x86")
            || android.os.Build.MANUFACTURER.contains("Genymotion")
            || android.os.Build.PRODUCT.contains("vbox86")
            || android.os.Build.PRODUCT.contains("emulator"))

    fun resolve(context: Context): String {
        val prefs: SharedPreferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (isEmulator()) {
            return "http://10.0.2.2:$DEFAULT_PORT"
        }
        val host = prefs.getString(KEY_HOST, null)
        if (host.isNullOrBlank()) {
            ConnectionActivity.start(context)
            return "http://10.0.2.2:$DEFAULT_PORT" // provisional until configured
        }
        val port = prefs.getInt(KEY_PORT, DEFAULT_PORT)
        return "http://$host:$port"
    }

    fun save(context: Context, host: String, port: Int = DEFAULT_PORT) {
        val prefs: SharedPreferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        prefs.edit()
            .putString(KEY_HOST, host.trim())
            .putInt(KEY_PORT, port)
            .apply()
    }

    fun configured(context: Context): Boolean {
        val prefs: SharedPreferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return !prefs.getString(KEY_HOST, null).isNullOrBlank() || isEmulator()
    }
}

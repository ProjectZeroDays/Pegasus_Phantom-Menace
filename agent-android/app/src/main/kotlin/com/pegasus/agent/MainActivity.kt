package com.pegasus.agent

import android.app.Activity
import android.os.Bundle

class MainActivity : Activity() {
    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        Config.load(this)
        BeaconService.start(this)
        finish()
    }
}

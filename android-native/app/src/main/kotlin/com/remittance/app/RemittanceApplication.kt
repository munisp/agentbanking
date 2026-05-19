package com.pos54link.app

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class RemittanceApplication : Application() {
    override fun onCreate() {
        super.onCreate()
    }
}

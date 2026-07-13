package com.nasana.hoyofomotracker

import android.app.Application
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

class HoyoApplication : Application() {
    override fun onCreate() {
        super.onCreate()

        val request = PeriodicWorkRequestBuilder<HoyoReminderWorker>(30, TimeUnit.MINUTES).build()

        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "hoyo_reminder_check",
            ExistingPeriodicWorkPolicy.KEEP,
            request
        )
    }
}

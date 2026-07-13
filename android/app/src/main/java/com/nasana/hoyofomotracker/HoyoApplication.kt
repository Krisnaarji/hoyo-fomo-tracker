package com.nasana.hoyofomotracker

import android.app.Application
import android.content.Context
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

class HoyoApplication : Application() {
    companion object {
        fun scheduleReminderWork(context: Context) {
            val request = PeriodicWorkRequestBuilder<HoyoReminderWorker>(30, TimeUnit.MINUTES).build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                "hoyo_reminder_check",
                ExistingPeriodicWorkPolicy.KEEP,
                request
            )
        }
    }

    override fun onCreate() {
        super.onCreate()

        // Don't schedule background work on a never-configured fresh install -
        // see AppPrefs.getSetupConfirmed(). MainActivity.saveSettings()
        // schedules it once the user has looked at Settings at least once.
        if (AppPrefs.getSetupConfirmed(this)) {
            scheduleReminderWork(this)
        }
    }
}

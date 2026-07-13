package com.nasana.hoyofomotracker

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationManagerCompat
import kotlin.concurrent.thread

class NotificationActionReceiver : BroadcastReceiver() {
    companion object {
        const val EXTRA_ENDPOINT = "endpoint"
        const val EXTRA_METHOD = "method"
        const val EXTRA_BODY = "body"
    }

    override fun onReceive(context: Context, intent: Intent) {
        val endpoint = intent.getStringExtra(EXTRA_ENDPOINT) ?: return
        val method = intent.getStringExtra(EXTRA_METHOD) ?: return
        val body = intent.getStringExtra(EXTRA_BODY)

        val appContext = context.applicationContext
        val pendingResult = goAsync()

        thread {
            try {
                HoyoApi.runAction(AppPrefs.getBaseUrl(appContext), endpoint, method, body)
            } catch (_: Exception) {
            } finally {
                NotificationManagerCompat.from(appContext).cancel(HoyoReminderWorker.NOTIFICATION_ID)
                appContext.sendBroadcast(
                    Intent(appContext, HoyoWidgetProvider::class.java).apply {
                        action = HoyoWidgetProvider.ACTION_REFRESH
                    }
                )
                pendingResult.finish()
            }
        }
    }
}

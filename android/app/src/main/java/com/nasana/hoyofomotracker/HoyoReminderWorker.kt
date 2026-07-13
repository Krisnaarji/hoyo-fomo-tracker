package com.nasana.hoyofomotracker

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.Worker
import androidx.work.WorkerParameters
import org.json.JSONObject

class HoyoReminderWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    companion object {
        const val CHANNEL_ID = "hoyo_reminders"
        const val NOTIFICATION_ID = 1001
    }

    override fun doWork(): Result {
        if (!AppPrefs.getNotificationsEnabled(applicationContext)) {
            return Result.success()
        }

        if (ContextCompat.checkSelfPermission(
                applicationContext,
                Manifest.permission.POST_NOTIFICATIONS
            ) != PackageManager.PERMISSION_GRANTED
        ) {
            return Result.success()
        }

        return try {
            val root = HoyoApi.fetchWidgetToday(
                AppPrefs.getBaseUrl(applicationContext),
                AppPrefs.getWidgetLimit(applicationContext)
            )

            val totalActions = root.getInt("total_actions")
            if (totalActions > 0) {
                postNotification(root, totalActions)
            }

            Result.success()
        } catch (e: Exception) {
            Result.retry()
        }
    }

    private fun postNotification(root: JSONObject, totalActions: Int) {
        val manager = applicationContext.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "HoYo FOMO Reminders", NotificationManager.IMPORTANCE_DEFAULT)
        )

        val top = HoyoApi.findTopSingleTapEvent(root)

        val builder = NotificationCompat.Builder(applicationContext, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("HoYo FOMO — $totalActions action(s) today")
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)

        if (top != null) {
            val (event, action) = top
            builder.setContentText("${action.getString("label")} — ${event.getString("event_name")}")
            builder.addAction(
                0,
                action.getString("label"),
                actionPendingIntent(
                    action.getString("endpoint"),
                    action.getString("method"),
                    if (action.has("body")) action.getJSONObject("body").toString() else null
                )
            )
        } else {
            builder.setContentText("$totalActions event(s) need attention")
        }

        NotificationManagerCompat.from(applicationContext).notify(NOTIFICATION_ID, builder.build())
    }

    private fun actionPendingIntent(endpoint: String, method: String, body: String?): PendingIntent {
        val intent = Intent(applicationContext, NotificationActionReceiver::class.java).apply {
            putExtra(NotificationActionReceiver.EXTRA_ENDPOINT, endpoint)
            putExtra(NotificationActionReceiver.EXTRA_METHOD, method)
            putExtra(NotificationActionReceiver.EXTRA_BODY, body)
        }

        return PendingIntent.getBroadcast(
            applicationContext,
            2,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }
}

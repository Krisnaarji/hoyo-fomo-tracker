package com.nasana.hoyofomotracker

import android.Manifest
import android.app.Notification
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

        // Extracted so it can be exercised directly from an instrumented test
        // without going through WorkManager's periodic scheduler (which races
        // against fresh-install defaults pointing at the real backend).
        internal fun buildReminderNotification(
            context: Context,
            root: JSONObject,
            totalActions: Int
        ): Notification {
            val builder = NotificationCompat.Builder(context, CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle("HoYo FOMO — $totalActions action(s) today")
                .setAutoCancel(true)
                .setPriority(NotificationCompat.PRIORITY_DEFAULT)

            val topSingleTap = HoyoApi.findTopSingleTapEvent(root)
            val topHeavy = HoyoApi.findTopHeavyEvent(root)

            if (topSingleTap != null) {
                val (event, action) = topSingleTap
                builder.setContentText("${action.getString("label")} — ${event.getString("event_name")}")
                builder.addAction(
                    0,
                    action.getString("label"),
                    actionPendingIntent(
                        context,
                        2,
                        action.getString("endpoint"),
                        action.getString("method"),
                        if (action.has("body")) action.getJSONObject("body").toString() else null
                    )
                )
            } else if (topHeavy != null) {
                val (event, action) = topHeavy
                val endpoint = action.getString("endpoint")
                val method = action.getString("method")

                builder.setContentText("🔥 Update progress — ${event.getString("event_name")}")

                for ((label, value) in listOf("25%" to 25, "50%" to 50, "Done" to 100)) {
                    val body = JSONObject().put("progress_status", value).toString()
                    builder.addAction(
                        0,
                        label,
                        actionPendingIntent(context, 40 + value, endpoint, method, body)
                    )
                }
            } else {
                builder.setContentText("$totalActions event(s) need attention")
            }

            return builder.build()
        }

        private fun actionPendingIntent(
            context: Context,
            requestCode: Int,
            endpoint: String,
            method: String,
            body: String?
        ): PendingIntent {
            val intent = Intent(context, NotificationActionReceiver::class.java).apply {
                putExtra(NotificationActionReceiver.EXTRA_ENDPOINT, endpoint)
                putExtra(NotificationActionReceiver.EXTRA_METHOD, method)
                putExtra(NotificationActionReceiver.EXTRA_BODY, body)
            }

            return PendingIntent.getBroadcast(
                context,
                requestCode,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
        }
    }

    override fun doWork(): Result {
        if (!AppPrefs.getSetupConfirmed(applicationContext)) {
            return Result.success()
        }

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

        val notification = buildReminderNotification(applicationContext, root, totalActions)
        NotificationManagerCompat.from(applicationContext).notify(NOTIFICATION_ID, notification)
    }
}

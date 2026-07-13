package com.nasana.hoyofomotracker

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class HoyoWidgetProvider : AppWidgetProvider() {
    companion object {
        private const val ACTION_REFRESH = "com.nasana.hoyofomotracker.ACTION_REFRESH"
    }

    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray
    ) {
        for (appWidgetId in appWidgetIds) {
            updateLoading(context, appWidgetManager, appWidgetId)
            fetchAndUpdateWidget(context, appWidgetManager, appWidgetId)
        }
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)

        if (intent.action == ACTION_REFRESH) {
            val appWidgetManager = AppWidgetManager.getInstance(context)
            val appWidgetIds = appWidgetManager.getAppWidgetIds(
                android.content.ComponentName(context, HoyoWidgetProvider::class.java)
            )

            for (appWidgetId in appWidgetIds) {
                updateLoading(context, appWidgetManager, appWidgetId)
                fetchAndUpdateWidget(context, appWidgetManager, appWidgetId)
            }
        }
    }

    private fun refreshPendingIntent(context: Context): PendingIntent {
        val intent = Intent(context, HoyoWidgetProvider::class.java).apply {
            action = ACTION_REFRESH
        }

        return PendingIntent.getBroadcast(
            context,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    private fun baseViews(context: Context): RemoteViews {
        val views = RemoteViews(context.packageName, R.layout.hoyo_widget)
        views.setOnClickPendingIntent(R.id.widget_root, refreshPendingIntent(context))
        return views
    }

    private fun updateLoading(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetId: Int
    ) {
        val views = baseViews(context)

        views.setTextViewText(R.id.widget_title, "HoYo FOMO")
        views.setTextViewText(R.id.widget_content, "Refreshing from Raspi...")

        appWidgetManager.updateAppWidget(appWidgetId, views)
    }

    private fun fetchAndUpdateWidget(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetId: Int
    ) {
        thread {
            val content = try {
                val url = URL("http://100.96.16.97:8123/widget/today?limit=5")
                val connection = url.openConnection() as HttpURLConnection

                connection.requestMethod = "GET"
                connection.connectTimeout = 5000
                connection.readTimeout = 5000

                val responseText = connection.inputStream.bufferedReader().readText()
                formatWidgetText(responseText)
            } catch (e: Exception) {
                "Failed to connect to Raspi ❌\n${e.message}"
            }

            val views = baseViews(context)

            views.setTextViewText(R.id.widget_title, "HoYo FOMO")
            views.setTextViewText(R.id.widget_content, content)

            appWidgetManager.updateAppWidget(appWidgetId, views)
        }
    }

    private fun formatWidgetText(jsonText: String): String {
        val root = JSONObject(jsonText)
        val totalActions = root.getInt("total_actions")
        val hiddenActions = root.getInt("hidden_actions")
        val games = root.getJSONArray("games")

        val builder = StringBuilder()

        builder.appendLine("$totalActions action(s) today")
        if (hiddenActions > 0) {
            builder.appendLine("+$hiddenActions more")
        }

        for (i in 0 until games.length()) {
            val game = games.getJSONObject(i)
            val gameTitle = game.getString("game_title")
            val events = game.getJSONArray("events")

            builder.appendLine()
            builder.appendLine(gameTitle)

            for (j in 0 until events.length()) {
                val event = events.getJSONObject(j)
                val emoji = event.getString("emoji")
                val name = event.getString("event_name")
                val daysLeft = if (event.isNull("days_left")) {
                    "?"
                } else {
                    event.getInt("days_left").toString()
                }

                builder.appendLine("$emoji $name")
                builder.appendLine("   ${daysLeft}d left")
            }
        }

        return builder.toString().trim()
    }
}
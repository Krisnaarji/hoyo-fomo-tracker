package com.nasana.hoyofomotracker

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.view.View
import android.widget.RemoteViews
import org.json.JSONObject
import kotlin.concurrent.thread

class HoyoWidgetProvider : AppWidgetProvider() {
    companion object {
        const val ACTION_REFRESH = "com.nasana.hoyofomotracker.ACTION_REFRESH"
        private const val ACTION_TOP_ACTION = "com.nasana.hoyofomotracker.ACTION_TOP_ACTION"
        private const val EXTRA_ENDPOINT = "endpoint"
        private const val EXTRA_METHOD = "method"
        private const val EXTRA_BODY = "body"
    }

    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray
    ) {
        for (appWidgetId in appWidgetIds) {
            updateStatus(context, appWidgetManager, appWidgetId, "Refreshing from Raspi...")
            fetchAndUpdateWidget(context, appWidgetManager, appWidgetId)
        }
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)

        val appWidgetManager = AppWidgetManager.getInstance(context)
        val appWidgetIds = appWidgetManager.getAppWidgetIds(
            ComponentName(context, HoyoWidgetProvider::class.java)
        )

        when (intent.action) {
            ACTION_REFRESH -> {
                for (appWidgetId in appWidgetIds) {
                    updateStatus(context, appWidgetManager, appWidgetId, "Refreshing from Raspi...")
                    fetchAndUpdateWidget(context, appWidgetManager, appWidgetId)
                }
            }

            ACTION_TOP_ACTION -> {
                val endpoint = intent.getStringExtra(EXTRA_ENDPOINT) ?: return
                val method = intent.getStringExtra(EXTRA_METHOD) ?: return
                val body = intent.getStringExtra(EXTRA_BODY)

                for (appWidgetId in appWidgetIds) {
                    updateStatus(context, appWidgetManager, appWidgetId, "Sending...")
                }

                thread {
                    try {
                        HoyoApi.runAction(AppPrefs.getBaseUrl(context), endpoint, method, body)
                    } catch (_: Exception) {
                    }

                    for (appWidgetId in appWidgetIds) {
                        fetchAndUpdateWidget(context, appWidgetManager, appWidgetId)
                    }
                }
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

    private fun topActionPendingIntent(
        context: Context,
        requestCode: Int,
        endpoint: String,
        method: String,
        body: String?
    ): PendingIntent {
        val intent = Intent(context, HoyoWidgetProvider::class.java).apply {
            action = ACTION_TOP_ACTION
            putExtra(EXTRA_ENDPOINT, endpoint)
            putExtra(EXTRA_METHOD, method)
            putExtra(EXTRA_BODY, body)
        }

        return PendingIntent.getBroadcast(
            context,
            requestCode,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    private fun baseViews(context: Context): RemoteViews {
        val views = RemoteViews(context.packageName, R.layout.hoyo_widget)
        views.setOnClickPendingIntent(R.id.widget_root, refreshPendingIntent(context))
        return views
    }

    private fun updateStatus(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetId: Int,
        message: String
    ) {
        val views = baseViews(context)
        views.setTextViewText(R.id.widget_content, message)
        views.setTextViewText(R.id.widget_badge, "…")
        views.setViewVisibility(R.id.widget_action_button, View.GONE)
        views.setViewVisibility(R.id.widget_progress_group, View.GONE)

        appWidgetManager.updateAppWidget(appWidgetId, views)
    }

    private fun fetchAndUpdateWidget(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetId: Int
    ) {
        thread {
            val views = baseViews(context)

            try {
                val root = HoyoApi.fetchWidgetToday(
                    AppPrefs.getBaseUrl(context),
                    AppPrefs.getWidgetLimit(context)
                )

                views.setTextViewText(R.id.widget_badge, root.getInt("total_actions").toString())
                views.setTextViewText(R.id.widget_content, formatWidgetText(root))
                applyTopAction(context, views, root)
            } catch (e: Exception) {
                views.setTextViewText(R.id.widget_badge, "!")
                views.setTextViewText(R.id.widget_content, "Failed to connect to Raspi ❌\n${e.message}")
                views.setViewVisibility(R.id.widget_action_button, View.GONE)
                views.setViewVisibility(R.id.widget_progress_group, View.GONE)
            }

            appWidgetManager.updateAppWidget(appWidgetId, views)
        }
    }

    private fun applyTopAction(context: Context, views: RemoteViews, root: JSONObject) {
        val top = HoyoApi.findTopSingleTapEvent(root)

        if (top != null) {
            val (event, action) = top
            val endpoint = action.getString("endpoint")
            val method = action.getString("method")
            val body = if (action.has("body")) action.getJSONObject("body").toString() else null

            val buttonBg = if (event.getString("category_tag") == "DAILY") {
                R.drawable.widget_button_daily
            } else {
                R.drawable.widget_button_speedrun
            }

            views.setInt(R.id.widget_action_button, "setBackgroundResource", buttonBg)
            views.setTextViewText(
                R.id.widget_action_button,
                "${event.getString("emoji")} ${action.getString("label")} — ${event.getString("event_name")}"
            )
            views.setViewVisibility(R.id.widget_action_button, View.VISIBLE)
            views.setOnClickPendingIntent(
                R.id.widget_action_button,
                topActionPendingIntent(context, 1, endpoint, method, body)
            )
            views.setViewVisibility(R.id.widget_progress_group, View.GONE)
            return
        }

        views.setViewVisibility(R.id.widget_action_button, View.GONE)
        applyTopHeavyAction(context, views, root)
    }

    private fun applyTopHeavyAction(context: Context, views: RemoteViews, root: JSONObject) {
        val top = HoyoApi.findTopHeavyEvent(root)

        if (top == null) {
            views.setViewVisibility(R.id.widget_progress_group, View.GONE)
            return
        }

        val (event, action) = top
        val endpoint = action.getString("endpoint")
        val method = action.getString("method")

        views.setTextViewText(
            R.id.widget_progress_label,
            "${event.getString("emoji")} ${event.getString("event_name")}"
        )

        val progressButtons = listOf(
            R.id.widget_progress_25 to 25,
            R.id.widget_progress_50 to 50,
            R.id.widget_progress_75 to 75,
            R.id.widget_progress_100 to 100
        )

        for ((viewId, value) in progressButtons) {
            val body = JSONObject().put("progress_status", value).toString()
            views.setOnClickPendingIntent(
                viewId,
                topActionPendingIntent(context, 20 + value, endpoint, method, body)
            )
        }

        views.setViewVisibility(R.id.widget_progress_group, View.VISIBLE)
    }

    private fun formatWidgetText(root: JSONObject): String {
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
            builder.append(gameTitle).append(": ")

            val names = mutableListOf<String>()
            for (j in 0 until events.length()) {
                val event = events.getJSONObject(j)
                val daysLeft = if (event.isNull("days_left")) "?" else event.getInt("days_left").toString()
                names.add("${event.getString("emoji")} ${event.getString("event_name")} (${daysLeft}d)")
            }
            builder.appendLine(names.joinToString(", "))
        }

        return builder.toString().trim()
    }
}

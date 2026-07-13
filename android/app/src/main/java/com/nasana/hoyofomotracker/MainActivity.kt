package com.nasana.hoyofomotracker

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import org.json.JSONObject
import kotlin.concurrent.thread

class MainActivity : android.app.Activity() {
    private lateinit var baseUrlInput: EditText
    private lateinit var widgetLimitInput: EditText
    private lateinit var notificationsSwitch: Switch
    private lateinit var statusView: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        baseUrlInput = EditText(this).apply {
            hint = "Base API URL"
            setText(AppPrefs.getBaseUrl(this@MainActivity))
        }

        widgetLimitInput = EditText(this).apply {
            hint = "Widget item limit"
            setText(AppPrefs.getWidgetLimit(this@MainActivity).toString())
        }

        notificationsSwitch = Switch(this).apply {
            text = "Enable reminder notifications"
            isChecked = AppPrefs.getNotificationsEnabled(this@MainActivity)
        }

        val saveButton = Button(this).apply {
            text = "Save settings"
            setOnClickListener { saveSettings() }
        }

        statusView = TextView(this).apply {
            text = "HoYo FOMO Tracker\nLoading today..."
            textSize = 18f
            setPadding(0, 48, 0, 0)
        }

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.TOP
            setPadding(48, 48, 48, 48)
            addView(baseUrlInput)
            addView(widgetLimitInput)
            addView(notificationsSwitch)
            addView(saveButton)
            addView(statusView)
        }

        setContentView(root)

        fetchWidgetToday()
    }

    private fun saveSettings() {
        val baseUrl = baseUrlInput.text.toString().trim().trimEnd('/')
        val limit = widgetLimitInput.text.toString().toIntOrNull()

        if (baseUrl.isEmpty() || limit == null || limit <= 0) {
            Toast.makeText(this, "Enter a valid URL and limit", Toast.LENGTH_SHORT).show()
            return
        }

        AppPrefs.setBaseUrl(this, baseUrl)
        AppPrefs.setWidgetLimit(this, limit)
        AppPrefs.setNotificationsEnabled(this, notificationsSwitch.isChecked)

        if (notificationsSwitch.isChecked && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }

        sendBroadcast(
            Intent(this, HoyoWidgetProvider::class.java).apply {
                action = HoyoWidgetProvider.ACTION_REFRESH
            }
        )

        Toast.makeText(this, "Saved. Widget refreshing...", Toast.LENGTH_SHORT).show()
        fetchWidgetToday()
    }

    private fun fetchWidgetToday() {
        val baseUrl = AppPrefs.getBaseUrl(this)
        val limit = AppPrefs.getWidgetLimit(this)

        thread {
            try {
                val root = HoyoApi.fetchWidgetToday(baseUrl, limit)
                val formattedText = formatWidgetToday(root)

                runOnUiThread {
                    statusView.text = formattedText
                }
            } catch (e: Exception) {
                runOnUiThread {
                    statusView.text = """
                        HoYo FOMO Tracker ❌

                        API connection failed:
                        ${e.message}
                    """.trimIndent()
                }
            }
        }
    }

    private fun formatWidgetToday(root: JSONObject): String {
        val today = root.getString("today")
        val totalActions = root.getInt("total_actions")
        val hiddenActions = root.getInt("hidden_actions")
        val games = root.getJSONArray("games")

        val builder = StringBuilder()

        builder.appendLine("HoYo FOMO Tracker")
        builder.appendLine("Today: $today")
        builder.appendLine("Actions: $totalActions")
        if (hiddenActions > 0) {
            builder.appendLine("+$hiddenActions more hidden")
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
                val category = event.getString("category_tag")
                val name = event.getString("event_name")
                val daysLeft = if (event.isNull("days_left")) {
                    "?"
                } else {
                    event.getInt("days_left").toString()
                }

                builder.appendLine("$emoji $category — $name")
                builder.appendLine("   Ends in: $daysLeft day(s)")
            }
        }

        return builder.toString()
    }
}

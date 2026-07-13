package com.nasana.hoyofomotracker

import android.os.Bundle
import android.widget.TextView
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class MainActivity : android.app.Activity() {
    private lateinit var textView: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        textView = TextView(this).apply {
            text = "HoYo FOMO Tracker\nLoading today..."
            textSize = 18f
            setPadding(48, 48, 48, 48)
        }

        setContentView(textView)

        fetchWidgetToday()
    }

    private fun fetchWidgetToday() {
        thread {
            try {
                val url = URL("http://100.96.16.97:8123/widget/today?limit=8")
                val connection = url.openConnection() as HttpURLConnection

                connection.requestMethod = "GET"
                connection.connectTimeout = 5000
                connection.readTimeout = 5000

                val responseText = connection.inputStream.bufferedReader().readText()
                val formattedText = formatWidgetToday(responseText)

                runOnUiThread {
                    textView.text = formattedText
                }
            } catch (e: Exception) {
                runOnUiThread {
                    textView.text = """
                        HoYo FOMO Tracker ❌
                        
                        API connection failed:
                        ${e.message}
                    """.trimIndent()
                }
            }
        }
    }

    private fun formatWidgetToday(jsonText: String): String {
        val root = JSONObject(jsonText)
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
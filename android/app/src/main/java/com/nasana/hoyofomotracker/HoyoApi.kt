package com.nasana.hoyofomotracker

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

object HoyoApi {
    fun httpRequest(urlString: String, method: String, body: String? = null): String {
        val url = URL(urlString)
        val connection = url.openConnection() as HttpURLConnection

        connection.requestMethod = method
        connection.connectTimeout = 5000
        connection.readTimeout = 5000

        if (body != null) {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.outputStream.use { it.write(body.toByteArray()) }
        }

        return connection.inputStream.bufferedReader().readText()
    }

    fun fetchWidgetToday(baseUrl: String, limit: Int): JSONObject =
        JSONObject(httpRequest("$baseUrl/widget/today?limit=$limit", "GET"))

    fun runAction(baseUrl: String, endpoint: String, method: String, body: String?) {
        httpRequest("$baseUrl$endpoint", method, body)
    }

    // HEAVY actions expose body_options (25/50/75/100) and need their own picker later,
    // so only DAILY/SPEEDRUN actions (single tap, no choice) are eligible here.
    fun findTopSingleTapEvent(root: JSONObject): Pair<JSONObject, JSONObject>? {
        val games = root.getJSONArray("games")
        var best: Pair<JSONObject, JSONObject>? = null
        var bestRank = Int.MAX_VALUE
        var bestDaysLeft = Int.MAX_VALUE

        for (i in 0 until games.length()) {
            val events = games.getJSONObject(i).getJSONArray("events")

            for (j in 0 until events.length()) {
                val event = events.getJSONObject(j)
                val action = event.optJSONObject("action") ?: continue

                if (action.has("body_options")) continue

                val rank = when (event.getString("category_tag")) {
                    "DAILY" -> 0
                    "SPEEDRUN" -> 1
                    else -> 2
                }
                val daysLeft = if (event.isNull("days_left")) Int.MAX_VALUE else event.getInt("days_left")

                if (rank < bestRank || (rank == bestRank && daysLeft < bestDaysLeft)) {
                    bestRank = rank
                    bestDaysLeft = daysLeft
                    best = event to action
                }
            }
        }

        return best
    }
}
